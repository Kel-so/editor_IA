import streamlit as st
import os
import json
import time
import asyncio
import requests
import shutil
import edge_tts
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, ColorClip

async def generate_audio_async(text, voice, output_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def gerar_audio(text, voice, output_path):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(generate_audio_async(text, voice, output_path))
        return True
    except Exception as e:
        st.error(f"Erro ao gerar áudio: {e}")
        return False

def gerar_video(prompt, output_filename, api_key, duration_fallback=5):
    # SIMULAÇÃO SE NÃO HOUVER CHAVE
    if not api_key or api_key == "SUA_CHAVE_AQUI":
        st.info(f"Modo de simulação ativo. Fabricando clipe em branco...")
        try:
            # Força garantir que a duração seja um número inteiro seguro
            duracao = max(int(duration_fallback), 1) 
            clip = ColorClip(size=(1280, 720), color=(20, 30, 80), duration=duracao)
            clip.write_videofile(output_filename, fps=24, logger=None)
            
            # Verificação dupla de segurança
            if os.path.exists(output_filename):
                 return True
            else:
                 st.error("Erro interno do Streamlit ao criar o arquivo de simulação na pasta temp_files.")
                 return False
        except Exception as e:
            st.error(f"Falha na simulação MoviePy: {e}")
            return False

    # MODO REAL (CHAMADA DE API SILICONFLOW - WAN 2.1)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Endpoint de Text-to-Video da SiliconFlow
    url_submit = "https://api.siliconflow.cn/v1/video/submit"
    
    # Payload configurado especificamente para o modelo Wan
    data = {
        "model": "alibaba/wan-2.1-t2v", # ID oficial do modelo Wan 2.1 na SiliconFlow
        "prompt": prompt,
        "resolution": "1280x720" # Wan geralmente utiliza resolution
    }

    try:
        st.write("Conectando aos servidores da SiliconFlow (Modelo Wan 2.1)...")
        response_post = requests.post(url_submit, headers=headers, json=data)
        
        if response_post.status_code != 200:
            st.error(f"A SiliconFlow recusou o pedido. Código {response_post.status_code}. Detalhes: {response_post.text}")
            return False
            
        response_json = response_post.json()
        task_id = response_json.get("data", {}).get("task_id")
        
        if not task_id:
             st.error("Não foi possível obter o task_id da resposta.")
             return False

        status_url = "https://api.siliconflow.cn/v1/video/status"
        
        st.write("Aguardando renderização do Wan na nuvem (Isso pode levar uns minutos)...")
        while True:
            # Check status enviando via POST (Padrão de algumas rotas assíncronas da SF)
            status_data = {"task_id": task_id}
            status_response = requests.post(status_url, headers=headers, json=status_data).json()
            
            status = status_response.get("data", {}).get("status")
            
            if status == "SUCCESS":
                video_url = status_response.get("data", {}).get("video_url")
                break
            elif status == "FAILED":
                erro_detalhado = status_response.get("data", {}).get("reason", "Erro desconhecido na geração.")
                st.error(f"Falha ao gerar o vídeo na API. Motivo: {erro_detalhado}")
                return False
            
            time.sleep(5) # Polling a cada 5 segundos
        
        st.write("Fazendo download do vídeo gerado...")
        video_data = requests.get(video_url).content
        with open(output_filename, 'wb') as handler:
            handler.write(video_data)
        
        if os.path.exists(output_filename):
            return True
        else:
            return False
            
    except Exception as e:
        st.error(f"Erro na comunicação com a API: {e}")
        return False

st.set_page_config(page_title="Auto-Studio IA", page_icon="🎬", layout="wide")

st.title("🎬 Orquestrador de Vídeo 100% IA (Wan 2.1 Edition)")

with st.sidebar:
    st.header("⚙️ Configurações")
    replicate_key = st.text_input("SiliconFlow API Key", type="password", help="Deixe em branco para rodar a simulação.")
    voz_escolhida = st.selectbox("Voz", options=["pt-BR-AntonioNeural", "pt-BR-FranciscaNeural"])

st.subheader("📝 Seu Roteiro (JSON)")

roteiro_padrao = """{
  "project_name": "Video_Institucional_01",
  "scenes": [
    {
      "id": 1,
      "type": "worker",
      "text": "O trabalho nas fábricas do futuro já começou.",
      "prompt": "Cinematic 4k, medium shot, a smiling latin worker in a modern high-tech factory, soft lighting, hyperrealistic"
    }
  ]
}"""

roteiro_texto = st.text_area("Edite as cenas:", value=roteiro_padrao, height=300)

if st.button("🚀 Gerar Vídeo Final", use_container_width=True, type="primary"):
    try:
        roteiro = json.loads(roteiro_texto)
    except json.JSONDecodeError:
        st.error("Erro no formato JSON!")
        st.stop()
        
    pasta_temp = "temp_files"
    if os.path.exists(pasta_temp):
        shutil.rmtree(pasta_temp)
    os.makedirs(pasta_temp, exist_ok=True)
    
    video_clips = []
    status_container = st.status("Iniciando pipeline...", expanded=True)
    barra_progresso = st.progress(0)
    total_cenas = len(roteiro["scenes"])
    
    with status_container:
        for idx, cena in enumerate(roteiro["scenes"]):
            st.write(f"**🎬 Processando Cena {cena['id']}...**")
            
            audio_path = os.path.join(pasta_temp, f"audio_{cena['id']}.mp3")
            video_path = os.path.join(pasta_temp, f"video_{cena['id']}.mp4")
            
            # 1. Gerar Áudio
            sucesso_audio = gerar_audio(cena["text"], voz_escolhida, audio_path)
            if not sucesso_audio or not os.path.exists(audio_path):
                st.error(f"Interrompendo: Falha na geração do áudio da cena {cena['id']}.")
                st.stop()
                
            clip_audio = AudioFileClip(audio_path)
            duracao_audio = clip_audio.duration
            
            # 2. Gerar Vídeo
            sucesso_video = gerar_video(cena["prompt"], video_path, replicate_key, duracao_audio)
            
            # BLINDAGEM: Se o vídeo não existir fisicamente, o MoviePy não é chamado.
            if not sucesso_video or not os.path.exists(video_path):
                st.error(f"Interrompendo: O arquivo de vídeo {video_path} não foi criado ou salvo com sucesso.")
                clip_audio.close() # Libera o arquivo de áudio da memória
                st.stop()
            
            # 3. Montagem da Cena
            st.write("✂️ Sincronizando...")
            clip_video = VideoFileClip(video_path)
            
            if clip_video.duration < duracao_audio:
                clip_video = clip_video.loop(duration=duracao_audio)
            else:
                clip_video = clip_video.subclip(0, duracao_audio)
                
            clip_final = clip_video.set_audio(clip_audio)
            video_clips.append(clip_final)
            
            barra_progresso.progress((idx + 1) / total_cenas)
            st.divider()

        if video_clips:
            st.write("🎞️ Renderizando vídeo final...")
            video_final = concatenate_videoclips(video_clips, method="compose")
            output_file = f"{roteiro['project_name']}.mp4"
            video_final.write_videofile(output_file, fps=24, codec="libx264", audio_codec="aac", logger=None)
            status_container.update(label="Concluído!", state="complete", expanded=False)
            st.video(output_file)
