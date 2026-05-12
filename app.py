import streamlit as st
import os
import json
import time
import asyncio
import requests
import shutil
import edge_tts
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, ColorClip
import numpy as np
from PIL import Image, ImageDraw, ImageFont

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
    # MODO DE SIMULAÇÃO (Sem Chave)
    if not api_key or api_key.strip() == "":
        st.info(f"Modo de simulação ativo. Fabricando clipe em branco para montagem...")
        try:
            duracao = max(int(duration_fallback), 1) 
            clip = ColorClip(size=(1280, 720), color=(20, 30, 80), duration=duracao)
            clip.write_videofile(output_filename, fps=24, logger=None)
            return os.path.exists(output_filename)
        except Exception as e:
            st.error(f"Falha na simulação MoviePy: {e}")
            return False

    # MODO REAL (SiliconFlow - Wan 2.1)
    if not api_key.startswith("sk-"):
        st.error("Sua chave da API parece inválida. Chaves da SiliconFlow começam com 'sk-'.")
        return False

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    url_submit = "https://api.siliconflow.cn/v1/video/submit"
    data = {
        "model": "alibaba/wan-2.1-t2v",
        "prompt": prompt,
        "resolution": "1280x720"
    }

    try:
        st.write("Conectando aos servidores da SiliconFlow (Modelo Wan 2.1)...")
        response_post = requests.post(url_submit, headers=headers, json=data)
        
        if response_post.status_code == 401:
            st.error("Erro 401: Chave da API inválida ou expirada. Limpe o campo para rodar a simulação grátis ou gere uma nova chave no site.")
            return False
        elif response_post.status_code != 200:
            st.error(f"A API recusou o pedido. Código {response_post.status_code}. Detalhes: {response_post.text}")
            return False
            
        response_json = response_post.json()
        task_id = response_json.get("data", {}).get("task_id")
        
        if not task_id:
             st.error("Não foi possível obter o task_id da resposta.")
             return False

        status_url = "https://api.siliconflow.cn/v1/video/status"
        
        st.write("Aguardando renderização (Isso pode levar alguns minutos)...")
        while True:
            status_data = {"task_id": task_id}
            status_response = requests.post(status_url, headers=headers, json=status_data).json()
            status = status_response.get("data", {}).get("status")
            
            if status == "SUCCESS":
                video_url = status_response.get("data", {}).get("video_url")
                break
            elif status == "FAILED":
                erro_detalhado = status_response.get("data", {}).get("reason", "Erro desconhecido.")
                st.error(f"Falha na API: {erro_detalhado}")
                return False
            
            time.sleep(5)
        
        st.write("Fazendo download do vídeo...")
        video_data = requests.get(video_url).content
        with open(output_filename, 'wb') as handler:
            handler.write(video_data)
        
        return os.path.exists(output_filename)
            
    except Exception as e:
        st.error(f"Erro na comunicação com a API: {e}")
        return False

# Função para desenhar overlays nativamente (Evita erros do ImageMagick/Pillow no Streamlit)
def add_overlay_to_frame(frame, texto, img_path):
    pil_img = Image.fromarray(frame)
    width, height = pil_img.size
    
    # Adicionar Imagem
    if img_path and os.path.exists(img_path):
        try:
            overlay_img = Image.open(img_path).convert("RGBA")
            try:
                resample_filter = Image.Resampling.LANCZOS
            except AttributeError:
                resample_filter = Image.LANCZOS 
                
            nova_altura = 150
            proporcao = nova_altura / float(overlay_img.size[1])
            nova_largura = int((float(overlay_img.size[0]) * float(proporcao)))
            overlay_img = overlay_img.resize((nova_largura, nova_altura), resample_filter)
            
            x_pos = width - nova_largura - 30
            y_pos = 30
            pil_img.paste(overlay_img, (x_pos, y_pos), overlay_img)
        except Exception:
            pass 
            
    # Adicionar Texto
    if texto:
        draw = ImageDraw.Draw(pil_img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        except IOError:
             try:
                 font = ImageFont.truetype("arial.ttf", 60)
             except:
                 font = ImageFont.load_default()
        
        try:
             bbox = font.getbbox(texto)
             text_width = bbox[2] - bbox[0]
             text_height = bbox[3] - bbox[1]
        except AttributeError:
             text_width, text_height = draw.textsize(texto, font=font)
             
        x_text = (width - text_width) / 2
        y_text = height * 0.8
        
        stroke_color = "black"
        stroke_width = 3
        for offset_x in range(-stroke_width, stroke_width+1):
            for offset_y in range(-stroke_width, stroke_width+1):
                 draw.text((x_text + offset_x, y_text + offset_y), texto, font=font, fill=stroke_color)
                 
        draw.text((x_text, y_text), texto, font=font, fill="white")

    return np.array(pil_img)


st.set_page_config(page_title="Auto-Studio IA", page_icon="🎬", layout="wide")

st.title("🎬 Orquestrador de Vídeo Wan 2.1")
st.markdown("Gerador de vídeo com composição nativa (Camadas de Imagem e Texto).")

with st.sidebar:
    st.header("⚙️ Configurações")
    siliconflow_key = st.text_input("SiliconFlow API Key", type="password", help="Deixe em branco para rodar a simulação visual.")
    voz_escolhida = st.selectbox("Voz", options=["pt-BR-AntonioNeural", "pt-BR-FranciscaNeural"])

st.subheader("📝 Seu Roteiro (JSON)")

roteiro_padrao = """{
  "project_name": "Video_Industria_Futuro",
  "scenes": [
    {
      "id": 1,
      "type": "worker",
      "text": "A revolução industrial do nosso século não é feita apenas de engrenagens, mas de inteligência e adaptação.",
      "prompt": "Cinematic 4k, medium shot, a focused engineer wearing safety glasses and a futuristic vest, looking at a glowing holographic blueprint in a high-tech modern factory, cinematic lighting, photorealistic",
      "overlay_text": "INDÚSTRIA 5.0"
    },
    {
      "id": 2,
      "type": "motion",
      "text": "Dados fluem em tempo real, conectando máquinas, processos e pessoas em um ecossistema digital perfeito.",
      "prompt": "Abstract motion graphics, glowing blue and gold data streams flowing through a dark environment, futuristic fiber optics, high quality 3d render, dynamic camera movement",
      "overlay_text": "ECOSSISTEMA DIGITAL",
      "overlay_image_url": "https://cdn-icons-png.flaticon.com/512/8672/8672990.png"
    }
  ]
}"""

roteiro_texto = st.text_area("Edite as cenas (adicione overlay_text ou overlay_image_url):", value=roteiro_padrao, height=350)

if st.button("🚀 Gerar Vídeo Final", use_container_width=True, type="primary"):
    try:
        roteiro = json.loads(roteiro_texto)
    except json.JSONDecodeError:
        st.error("Erro no formato JSON! Verifique as vírgulas e aspas.")
        st.stop()
        
    pasta_temp = "temp_files"
    if os.path.exists(pasta_temp):
        shutil.rmtree(pasta_temp)
    os.makedirs(pasta_temp, exist_ok=True)
    
    video_clips = []
    status_container = st.status("Iniciando pipeline de composição...", expanded=True)
    barra_progresso = st.progress(0)
    total_cenas = len(roteiro["scenes"])
    
    with status_container:
        for idx, cena in enumerate(roteiro["scenes"]):
            st.write(f"**🎬 Processando Cena {cena['id']}...**")
            
            audio_path = os.path.join(pasta_temp, f"audio_{cena['id']}.mp3")
            video_path = os.path.join(pasta_temp, f"video_{cena['id']}.mp4")
            
            sucesso_audio = gerar_audio(cena["text"], voz_escolhida, audio_path)
            if not sucesso_audio:
                st.error("Falha no áudio.")
                st.stop()
                
            clip_audio = AudioFileClip(audio_path)
            duracao_audio = clip_audio.duration
            
            sucesso_video = gerar_video(cena["prompt"], video_path, siliconflow_key, duracao_audio)
            if not sucesso_video:
                st.error("Falha no vídeo.")
                clip_audio.close()
                st.stop()
            
            st.write("✂️ Aplicando Camadas e Sincronizando...")
            clip_video = VideoFileClip(video_path)
            
            if clip_video.duration < duracao_audio:
                clip_video = clip_video.loop(duration=duracao_audio)
            else:
                clip_video = clip_video.subclip(0, duracao_audio)
                
            texto_overlay = cena.get("overlay_text", None)
            img_url = cena.get("overlay_image_url", None)
            
            img_path = None
            if img_url:
                 img_path = os.path.join(pasta_temp, f"img_{cena['id']}.png")
                 try:
                     img_data = requests.get(img_url).content
                     with open(img_path, 'wb') as f:
                         f.write(img_data)
                 except:
                     img_path = None

            if texto_overlay or img_path:
                clip_video = clip_video.fl_image(lambda frame: add_overlay_to_frame(frame, texto_overlay, img_path))
                
            clip_final = clip_video.set_audio(clip_audio)
            video_clips.append(clip_final)
            
            barra_progresso.progress((idx + 1) / total_cenas)
            st.divider()

        if video_clips:
            st.write("🎞️ Renderizando composição final (isso exige processamento)...")
            video_final = concatenate_videoclips(video_clips, method="compose")
            output_file = f"{roteiro['project_name']}.mp4"
            video_final.write_videofile(output_file, fps=24, codec="libx264", audio_codec="aac", logger=None)
            status_container.update(label="Concluído!", state="complete", expanded=False)
            st.video(output_file)
