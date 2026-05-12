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
    # Baixa a Poppins Black (Fonte gringa de alta conversão)
    font_path = "temp_files/Poppins-Black.ttf"
    try:
        if not os.path.exists(font_path):
            font_url = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Black.ttf"
            r = requests.get(font_url)
            with open(font_path, "wb") as f:
                f.write(r.content)
        font = ImageFont.truetype(font_path, 65) # Um pouco maior
    except:
        font = ImageFont.load_default()
        
    # Calculando o tamanho exato da caixa de texto para podermos animar
    temp_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    try:
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except:
        text_w, text_h = 400, 60
        
    # Criando a lona SÓ do tamanho do texto + respiro pra sombra
    padding = 20
    img = Image.new('RGBA', (text_w + padding*2, text_h + padding*2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 1. Drop Shadow (Sombra macia descentralizada)
    draw.text((padding + 5, padding + 5), text, font=font, fill=(0, 0, 0, 180))
    
    # 2. Texto Principal
    draw.text((padding, padding), text, font=font, fill="white")
    
    return np.array(img)

# --- CARREGAR IMAGENS ---
def load_overlay_image(url):
    try:
        resp = requests.get(url)
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        resample_filter = getattr(Image.Resampling, 'LANCZOS', Image.ANTIALIAS)
        img.thumbnail((150, 150), resample_filter)
        return np.array(img)
    except Exception:
        return None

# --- UI STREAMLIT ---
st.set_page_config(page_title="Gerador Wan 2.1", layout="wide")
st.title("🎬 Ilha de Edição IA - Wan 2.1 (Motion Edition)")

with st.sidebar:
    st.header("Configurações")
    api_key = st.text_input("SiliconFlow API Key (sk-...)", type="password", help="Deixe vazio para simulação")

json_input = st.text_area("Roteiro JSON (Pode colar que o motor aguenta):", height=300)

if st.button("Gerar Vídeo Final"):
    if not json_input:
        st.warning("Eita, esqueceu o roteiro pai! Cola o JSON aí.")
        st.stop()

    try:
        roteiro = json.loads(json_input)
    except:
        st.error("Ops! Tem erro de sintaxe nesse JSON (uma vírgula ou aspas sobrando/faltando).")
        st.stop()

    cleanup_temp()
    st.info("Bora lá... Renderizando seu projeto com Motion!")
    
    clips_finais = []
    progress_bar = st.progress(0)
    total_scenes = len(roteiro["scenes"])
    
    for idx, cena in enumerate(roteiro["scenes"]):
        st.write(f"⚙️ Processando cena {idx+1}: {cena['type'].upper()}")
        
        audio_path = f"temp_files/audio_{idx}.mp3"
        asyncio.run(gen_audio(cena["text"], audio_path))
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        if not api_key:
            color = (20, 60, 120) if cena["type"] == "worker" else (120, 40, 40)
            base_clip = ColorClip(size=(1280, 720), color=color, duration=duration)
        else:
            st.warning("Cena enviada pra SiliconFlow! (Gerando cor provisória no app de simulação)")
            base_clip = ColorClip(size=(1280, 720), color=(30, 80, 40), duration=duration)
            
        base_clip = base_clip.set_audio(audio_clip)
        layers = [base_clip]
        
        # Overlay da Imagem/Logo (Agora usando o crossfadein nativo)
        if "overlay_image_url" in cena:
            img_array = load_overlay_image(cena["overlay_image_url"])
            if img_array is not None:
                logo_clip = (ImageClip(img_array)
                             .set_duration(duration)
                             .set_position(("right", "top"))
                             .margin(top=30, right=30, opacity=0)
                             .crossfadein(0.5)) # <- FADE IN CORRIGIDO AQUI
                layers.append(logo_clip)
        
        # O PULO DO GATO: Motion do Texto
        if "overlay_text" in cena:
            txt_array = create_text_overlay(cena["overlay_text"])
            
            # Altura final desejada (uns 100px acima do rodapé)
            txt_h = txt_array.shape[0]
            target_y = 720 - txt_h - 100
            
            # Criamos o clip, usamos crossfadein e a posição faz o "Slide Up"
            txt_clip = (ImageClip(txt_array)
                        .set_duration(duration)
                        .crossfadein(0.5) # <- FADE IN CORRIGIDO AQUI
                        .set_position(lambda t: ('center', int(target_y + max(0, 0.5 - t) * 100))))
            
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
