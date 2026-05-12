import streamlit as st
import json
import os
import shutil
import asyncio
import edge_tts
import requests
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
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

# --- FUNÇÃO DE EASING (Para o movimento ficar fluido estilo After Effects) ---
def ease_out_cubic(t, duration=0.8):
    p = min(1.0, t / duration)
    return 1 - pow(1 - p, 3)

# Cache da fonte na RAM para evitar bloqueios de disco do servidor
FONT_CACHE = {}
def get_font(size=50): # Tamanho reduzido de 70 para 50
    if size in FONT_CACHE:
        return FONT_CACHE[size]
        
    system_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "arial.ttf"
    ]
    
    for font_path in system_fonts:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, size)
                FONT_CACHE[size] = font
                return font
            except:
                continue
                
    try:
        font_url = "https://cdn.jsdelivr.net/gh/googlefonts/roboto@main/src/hinted/Roboto-Black.ttf"
        r = requests.get(font_url, timeout=10)
        font = ImageFont.truetype(BytesIO(r.content), size)
        FONT_CACHE[size] = font
        return font
    except Exception as e:
        print(f"Erro brutal ao carregar fonte: {e}")
        return ImageFont.load_default()

# --- TEXTO PREMIUM (ALINHADO À ESQUERDA, MULTILINHA + SOFT SHADOW) ---
def create_text_overlay(text):
    font = get_font(50) # Texto menorzinho, elegante
    
    temp_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    try:
        bbox = temp_draw.multiline_textbbox((0, 0), text, font=font, align="left")
        text_w = int(bbox[2] - bbox[0])
        text_h = int(bbox[3] - bbox[1])
    except:
        text_w, text_h = 800, 300
        
    padding = 100
    
    final_width = max(10, int(text_w) + padding * 2)
    final_height = max(10, int(text_h) + padding * 2)
    
    img = Image.new('RGBA', (final_width, final_height), (0, 0, 0, 0))
    
    # 1. SOMBRA DIFUSA PROFISSIONAL (Gaussian Blur)
    shadow_layer = Image.new('RGBA', (final_width, final_height), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    
    shadow_draw.multiline_text((padding + 10, padding + 15), text, font=font, fill=(0, 0, 0, 255), align="left")
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=25))
    
    img.alpha_composite(shadow_layer)
    img.alpha_composite(shadow_layer)
    img.alpha_composite(shadow_layer)
    
    # 2. Texto Principal Branco
    draw = ImageDraw.Draw(img)
    draw.multiline_text((padding, padding), text, font=font, fill="white", align="left")
    
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


# --- UI STREAMLIT ---
st.set_page_config(page_title="Gerador Wan 2.1", layout="wide")
st.title("🎬 Ilha de Edição IA - Modo Raiz")
st.markdown("Cole o seu JSON abaixo. Texto menor e grudado na esquerda.")

with st.sidebar:
    st.header("Configurações")
    api_key = st.text_input("SiliconFlow API Key", type="password", help="Vazio = Simulação com fundos coloridos")

# Área limpa só pro JSON
json_input = st.text_area("Roteiro JSON:", height=400, placeholder='{\n  "scenes": [\n    ...\n  ]\n}')

st.divider()

# --- MOTOR DE RENDERIZAÇÃO ---
if st.button("🚀 Renderizar Vídeo Final", type="primary", use_container_width=True):
    if not json_input.strip():
        st.warning("Eita, esqueceu de colar o JSON aí, mestre!")
        st.stop()
        
    try:
        roteiro = json.loads(json_input)
        if "scenes" not in roteiro:
            st.error("JSON inválido: Faltou a chave 'scenes'.")
            st.stop()
    except Exception as e:
        st.error(f"Erro de sintaxe no JSON. Dá uma revisada: {e}")
        st.stop()

    cleanup_temp()
    st.info("Renderizando frame a frame com animações fluidas...")
    
    clips_finais = []
    progress_bar = st.progress(0)
    total_scenes = len(roteiro["scenes"])
    
    for idx, cena in enumerate(roteiro["scenes"]):
        st.write(f"⚙️ Processando cena {idx+1}...")
        
        audio_path = f"temp_files/audio_{idx}.mp3"
        asyncio.run(gen_audio(cena["text"], audio_path))
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        # Define fallback caso falte a chave 'type'
        cena_type = cena.get("type", "worker")
        
        if not api_key:
            color = (20, 60, 120) if cena_type == "worker" else (120, 40, 40)
            base_clip = ColorClip(size=(1280, 720), color=color, duration=duration)
        else:
            base_clip = ColorClip(size=(1280, 720), color=(30, 80, 40), duration=duration)
            
        base_clip = base_clip.set_audio(audio_clip)
        layers = [base_clip]
        
        if cena.get("overlay_image_url"):
            img_array = load_overlay_image(cena["overlay_image_url"])
            if img_array is not None:
                logo_clip = (ImageClip(img_array)
                             .set_duration(duration)
                             .set_position(("right", "top"))
                             .margin(top=30, right=30, opacity=0)
                             .crossfadein(0.8))
                layers.append(logo_clip)
        
        if cena.get("overlay_text"):
            txt_array = create_text_overlay(cena["overlay_text"])
            txt_h = txt_array.shape[0]
            
            target_y = (720 - txt_h) // 2
            start_y = target_y + 120
            
            # Posição X colada na esquerda (50px) ao invés de 100px
            txt_clip = (ImageClip(txt_array)
                        .set_duration(duration)
                        .crossfadein(0.8)
                        .set_position(lambda t, sy=start_y, ty=target_y: (50, int(sy - (sy - ty) * ease_out_cubic(t)))))
            
            layers.append(txt_clip)
            
        cena_composita = CompositeVideoClip(layers, size=(1280, 720))
        clips_finais.append(cena_composita)
        
        progress_bar.progress((idx + 1) / total_scenes)

    st.write("✂️ Unificando blocos e exportando...")
    video_final = concatenate_videoclips(clips_finais, method="compose")
    output_path = "temp_files/video_final.mp4"
    video_final.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
    
    st.success("✅ Tá no ar! Aperta o play pra ver a obra.")
    st.video(output_path)
