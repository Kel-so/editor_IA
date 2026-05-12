import streamlit as st
import json
import os
import shutil
import asyncio
import edge_tts
import requests
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ColorClip, AudioFileClip, CompositeVideoClip, ImageClip, concatenate_videoclips

# --- SETUP E LIMPEZA ---
def cleanup_temp():
    if os.path.exists("temp_files"):
        shutil.rmtree("temp_files")
    os.makedirs("temp_files", exist_ok=True)

# --- ÁUDIO IA ---
async def gen_audio(text, filepath):
    tts = edge_tts.Communicate(text, "pt-BR-AntonioNeural")
    await tts.save(filepath)

# --- TEXTO PREMIUM (SOMBRA + TAMANHO EXATO) ---
def create_text_overlay(text):
    font_path = "temp_files/Poppins-Black.ttf"
    try:
        if not os.path.exists(font_path):
            font_url = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Black.ttf"
            r = requests.get(font_url)
            with open(font_path, "wb") as f:
                f.write(r.content)
        font = ImageFont.truetype(font_path, 65) 
    except:
        font = ImageFont.load_default()
        
    temp_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    try:
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except:
        text_w, text_h = 400, 60
        
    padding = 20
    img = Image.new('RGBA', (text_w + padding*2, text_h + padding*2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Drop Shadow
    draw.text((padding + 5, padding + 5), text, font=font, fill=(0, 0, 0, 180))
    # Texto Principal
    draw.text((padding, padding), text, font=font, fill="white")
    
    return np.array(img)

# --- CARREGAR IMAGENS ---
def load_overlay_image(url):
    if not url: return None
    try:
        resp = requests.get(url)
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        resample_filter = getattr(Image.Resampling, 'LANCZOS', Image.ANTIALIAS)
        img.thumbnail((150, 150), resample_filter)
        return np.array(img)
    except Exception:
        return None

# --- DADOS PADRÃO (SEU ROTEIRO CYBERPUNK) ---
default_scenes = [
    {
      "type": "worker",
      "text": "A revolução não vai ser transmitida na televisão. Vai ser programada.",
      "visual_prompt": "Cinematic shot, cyberpunk hacker typing furiously in a dark neon-lit room, glowing screens reflecting on glasses, 4k, hyperrealistic",
      "overlay_text": "CÓDIGO PURO",
      "overlay_image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Python-logo-notext.svg/182px-Python-logo-notext.svg.png"
    },
    {
      "type": "motion",
      "text": "Servidores globais a sincronizar dados em tempo real. A infraestrutura invisível que move o mundo.",
      "visual_prompt": "Abstract motion graphics, glowing blue and purple server racks forming a massive digital city, camera flying through data streams, 3D render, Octane",
      "overlay_text": "INFRAESTRUTURA",
      "overlay_image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/React-icon.svg/200px-React-icon.svg.png"
    },
    {
      "type": "worker",
      "text": "Não construímos apenas software. Destruímos as limitações do sistema antigo.",
      "visual_prompt": "Close up, confident tech CEO looking at a floating holographic projection in a modern dark office, cinematic lighting, highly detailed",
      "overlay_text": "SEM LIMITES",
      "overlay_image_url": ""
    },
    {
      "type": "motion",
      "text": "Velocidade, precisão e uma arquitetura desenhada para o caos.",
      "visual_prompt": "Fast paced abstract 3D UI elements, glassmorphism, floating glowing charts and data nodes shifting dynamically, cyberpunk aesthetic",
      "overlay_text": "CAOS CONTROLADO",
      "overlay_image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/HTML5_logo_and_wordmark.svg/120px-HTML5_logo_and_wordmark.svg.png"
    },
    {
      "type": "worker",
      "text": "A tua equipa precisa de estar armada com as melhores ferramentas da atualidade.",
      "visual_prompt": "Team of diverse developers looking at a giant glowing interactive wall screen, neon ambient lighting, intense focus, 8k resolution",
      "overlay_text": "A TUA EQUIPA",
      "overlay_image_url": ""
    },
    {
      "type": "motion",
      "text": "O futuro já começou. Estás pronto para dominar o jogo?",
      "visual_prompt": "Epic logo reveal motion, neon glowing geometric shapes forming a futuristic crest, dark background, lens flares, unreal engine 5",
      "overlay_text": "DOMINA O JOGO",
      "overlay_image_url": ""
    }
]

# Inicializa o estado se for a primeira vez
if 'scenes' not in st.session_state:
    st.session_state.scenes = default_scenes.copy()

# --- UI STREAMLIT ---
st.set_page_config(page_title="Gerador Wan 2.1", layout="wide")
st.title("🎬 Ilha de Edição IA - Modo Visual")
st.markdown("Chega de editar JSON na mão. Monte seu vídeo abaixo:")

with st.sidebar:
    st.header("Configurações")
    api_key = st.text_input("SiliconFlow API Key", type="password", help="Vazio = Simulação com fundos coloridos")

# --- CONSTRUTOR DE CENAS ---
for i, scene in enumerate(st.session_state.scenes):
    with st.expander(f"🎬 Cena {i+1} | Tipo: {scene['type'].upper()}", expanded=False):
        col1, col2 = st.columns([1, 4])
        scene['type'] = col1.selectbox("Estilo", ["worker", "motion"], index=0 if scene['type'] == 'worker' else 1, key=f"type_{i}")
        scene['text'] = col2.text_input("Texto da Narração (Voz)", value=scene.get('text', ''), key=f"text_{i}")
        
        scene['visual_prompt'] = st.text_area("Prompt para a IA (Inglês)", value=scene.get('visual_prompt', ''), key=f"prompt_{i}")
        
        col3, col4 = st.columns(2)
        scene['overlay_text'] = col3.text_input("Motion Text (Surgirá na tela)", value=scene.get('overlay_text', ''), key=f"otext_{i}")
        scene['overlay_image_url'] = col4.text_input("URL do Logotipo/Ícone (Opcional)", value=scene.get('overlay_image_url', ''), key=f"oimg_{i}")

        if st.button(f"🗑️ Deletar Cena {i+1}", key=f"del_{i}"):
            st.session_state.scenes.pop(i)
            st.rerun()

if st.button("➕ Adicionar Nova Cena", use_container_width=True):
    st.session_state.scenes.append({"type": "worker", "text": "", "visual_prompt": "", "overlay_text": "", "overlay_image_url": ""})
    st.rerun()

st.divider()

# --- MOTOR DE RENDERIZAÇÃO ---
if st.button("🚀 Renderizar Vídeo Final", type="primary", use_container_width=True):
    if len(st.session_state.scenes) == 0:
        st.warning("Adicione pelo menos uma cena antes de renderizar!")
        st.stop()

    cleanup_temp()
    st.info("Trancando as portas da ilha de edição... Renderizando!")
    
    clips_finais = []
    progress_bar = st.progress(0)
    total_scenes = len(st.session_state.scenes)
    
    for idx, cena in enumerate(st.session_state.scenes):
        st.write(f"⚙️ Processando cena {idx+1}...")
        
        audio_path = f"temp_files/audio_{idx}.mp3"
        asyncio.run(gen_audio(cena["text"], audio_path))
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        if not api_key:
            color = (20, 60, 120) if cena["type"] == "worker" else (120, 40, 40)
            base_clip = ColorClip(size=(1280, 720), color=color, duration=duration)
        else:
            base_clip = ColorClip(size=(1280, 720), color=(30, 80, 40), duration=duration)
            
        base_clip = base_clip.set_audio(audio_clip)
        layers = [base_clip]
        
        # Logo com Fade In
        if cena.get("overlay_image_url"):
            img_array = load_overlay_image(cena["overlay_image_url"])
            if img_array is not None:
                logo_clip = (ImageClip(img_array)
                             .set_duration(duration)
                             .set_position(("right", "top"))
                             .margin(top=30, right=30, opacity=0)
                             .crossfadein(0.5))
                layers.append(logo_clip)
        
        # Texto com Slide Up
        if cena.get("overlay_text"):
            txt_array = create_text_overlay(cena["overlay_text"])
            txt_h = txt_array.shape[0]
            target_y = 720 - txt_h - 100
            
            txt_clip = (ImageClip(txt_array)
                        .set_duration(duration)
                        .crossfadein(0.5)
                        .set_position(lambda t, y=target_y: ('center', int(y + max(0, 0.5 - t) * 100))))
            layers.append(txt_clip)
            
        cena_composita = CompositeVideoClip(layers, size=(1280, 720))
        clips_finais.append(cena_composita)
        
        progress_bar.progress((idx + 1) / total_scenes)

    st.write("✂️ Colando as cenas e aplicando aquele polimento...")
    video_final = concatenate_videoclips(clips_finais, method="compose")
    output_path = "temp_files/video_final.mp4"
    video_final.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
    
    st.success("✅ Cinema! Vídeo pronto.")
    st.video(output_path)
