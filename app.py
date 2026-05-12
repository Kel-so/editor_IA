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
    """Função assíncrona real que chama a API gratuita da Microsoft"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def gerar_audio(text, voice, output_path):
    """Wrapper síncrono para rodar a função assíncrona dentro do Streamlit"""
    asyncio.run(generate_audio_async(text, voice, output_path))

def gerar_video(prompt, output_filename, api_key, duration_fallback=5):
    """
    Chama a API do Replicate. Se não houver API Key, cria um vídeo de teste (dummy).
    """
    if not api_key or api_key == "SUA_CHAVE_AQUI":
        # Modo de simulação para testar o app gratuitamente
        st.warning(f"⚠️ Simulando vídeo para o prompt: '{prompt[:30]}...'")
        time.sleep(1) # Simula um pequeno atraso
        # Cria um clipe azul sólido (dummy) com a duração aproximada
        clip = ColorClip(size=(1280, 720), color=(20, 30, 80), duration=duration_fallback)
        clip.write_videofile(output_filename, fps=24, logger=None)
        return output_filename

    # Chamada real para a API do Replicate (Modelo Zeroscope)
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }
    url = "https://api.replicate.com/v1/predictions"
    data = {
        "version": "9f747673945c62801b13b84701c783929c0ee784e4748ec062204894dda1a351",
        "input": {
            "prompt": prompt,
            "num_frames": 24,
            "fps": 8
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data).json()
        prediction_url = response["urls"]["get"]

        # Loop de espera (Polling)
        while True:
            status_response = requests.get(prediction_url, headers=headers).json()
            status = status_response["status"]
            if status == "succeeded":
                video_url = status_response["output"]
                break
            elif status == "failed":
                st.error("Falha ao gerar vídeo na API.")
                return None
            time.sleep(3)
        
        # Faz o download do vídeo gerado
        video_data = requests.get(video_url).content
        with open(output_filename, 'wb') as handler:
            handler.write(video_data)
        
        return output_filename
    except Exception as e:
        st.error(f"Erro na API: {e}")
        return None

st.set_page_config(page_title="Auto-Studio IA", page_icon="🎬", layout="wide")

st.title("🎬 Orquestrador de Vídeo 100% IA")
st.markdown("Insira o seu roteiro abaixo e deixe o sistema gerar os áudios, vídeos e fazer a montagem automática.")

# --- BARRA LATERAL (Configurações) ---
with st.sidebar:
    st.header("⚙️ Configurações")
    replicate_key = st.text_input("Replicate API Key", type="password", help="Deixe em branco para rodar a simulação (vídeo sem imagem).")
    
    voz_escolhida = st.selectbox(
        "Voz da Narração (Grátis)",
        options=["pt-BR-AntonioNeural", "pt-BR-FranciscaNeural"],
        format_func=lambda x: "Antônio (Masculino)" if "Antonio" in x else "Francisca (Feminino)"
    )

# --- ÁREA PRINCIPAL (Roteiro) ---
st.subheader("📝 Seu Roteiro (JSON)")

roteiro_padrao = """{
  "project_name": "Video_Institucional_01",
  "scenes": [
    {
      "id": 1,
      "type": "worker",
      "text": "O trabalho nas fábricas do futuro já começou.",
      "prompt": "Cinematic 4k, medium shot, a smiling latin worker in a modern high-tech factory, soft lighting, hyperrealistic"
    },
    {
      "id": 2,
      "type": "motion",
      "text": "Dados em tempo real se conectam perfeitamente para acelerar processos.",
      "prompt": "Abstract motion graphics, glowing blue data nodes connecting in dark space, 3d render, UI design elements"
    }
  ]
}"""

# O usuário pode editar o JSON direto na tela
roteiro_texto = st.text_area("Edite as cenas do seu vídeo:", value=roteiro_padrao, height=300)

if st.button("🚀 Gerar Vídeo Final", use_container_width=True, type="primary"):
    try:
        roteiro = json.loads(roteiro_texto)
    except json.JSONDecodeError:
        st.error("Erro no formato JSON! Verifique as vírgulas e aspas do seu roteiro.")
        st.stop()
        
    # Limpa arquivos de gerações anteriores para não lotar o servidor na nuvem
    if os.path.exists("temp_files"):
        shutil.rmtree("temp_files")
    os.makedirs("temp_files", exist_ok=True)
    
    video_clips = []
    
    # Área de status para o usuário acompanhar
    status_container = st.status("Iniciando pipeline de geração...", expanded=True)
    barra_progresso = st.progress(0)
    
    total_cenas = len(roteiro["scenes"])
    
    with status_container:
        for idx, cena in enumerate(roteiro["scenes"]):
            st.write(f"**🎬 Processando Cena {cena['id']}...**")
            
            audio_path = f"temp_files/audio_{cena['id']}.mp3"
            video_path = f"temp_files/video_{cena['id']}.mp4"
            
            # 1. Gerar Áudio
            st.write(f"🎙️ Gerando locução: *{cena['text']}*")
            gerar_audio(cena["text"], voz_escolhida, audio_path)
            
            # Descobrir tempo do audio para parametrizar o video
            clip_audio = AudioFileClip(audio_path)
            duracao_audio = clip_audio.duration
            
            # 2. Gerar Vídeo
            st.write(f"🎥 Renderizando visual: *{cena['prompt'][:50]}...*")
            # Passamos a duração do áudio como fallback caso estejamos no modo simulação
            gerar_video(cena["prompt"], video_path, replicate_key, duration_fallback=duracao_audio)
            
            # 3. Montagem da Cena
            st.write(f"✂️ Sincronizando áudio e vídeo...")
            clip_video = VideoFileClip(video_path)
            
            # Ajusta o vídeo para ter exatamente a duração da fala (loop ou freeze frame)
            # Como a IA geralmente gera vídeos curtos (3 a 5s), ajustamos aqui para bater com a voz
            if clip_video.duration < duracao_audio:
                # Estica o vídeo fazendo um loop (ou poderia fazer um freeze do último frame)
                clip_video = clip_video.loop(duration=duracao_audio)
            else:
                clip_video = clip_video.subclip(0, duracao_audio)
                
            clip_final = clip_video.set_audio(clip_audio)
            video_clips.append(clip_final)
            
            # Atualiza barra de progresso
            barra_progresso.progress((idx + 1) / total_cenas)
            st.write("✅ Cena concluída!")
            st.divider()

        if video_clips:
            st.write("🎞️ Renderizando vídeo final na linha de tempo (Isso pode levar alguns segundos)...")
            video_final = concatenate_videoclips(video_clips, method="compose")
            
            output_file = f"{roteiro['project_name']}.mp4"
            # Renderiza. logger=None esconde os logs do ffmpeg no terminal
            video_final.write_videofile(output_file, fps=24, codec="libx264", audio_codec="aac", logger=None)
            
            status_container.update(label="Vídeo Finalizado com Sucesso!", state="complete", expanded=False)
            
            st.success("🎉 Geração completa! Assista abaixo:")
            
            # Mostra o vídeo no próprio Streamlit
            st.video(output_file)
            
            # Botão de download
            with open(output_file, "rb") as file:
                btn = st.download_button(
                    label="⬇️ Baixar Vídeo Final",
                    data=file,
                    file_name=output_file,
                    mime="video/mp4",
                    type="primary"
                )
