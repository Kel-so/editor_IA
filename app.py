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

# --- TEXTO NATIVO E SEGURO (COM FONTE BOA) ---
def create_text_overlay(text, width=1280, height=720):
    # Cria a lona transparente inteira do tamanho do vídeo
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Baixa a fonte bonitona caso o servidor não tenha
    font_path = "temp_files/Montserrat-Bold.ttf"
    try:
        if not os.path.exists(font_path):
            font_url = "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat-Bold.ttf"
            r = requests.get(font_url)
            with open(font_path, "wb") as f:
                f.write(r.content)
        font = ImageFont.truetype(font_path, 60)
    except:
        font = ImageFont.load_default()
        
    # Centraliza horizontal e margem na base
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except:
        text_w, text_h = 400, 60
        
    x = (width - text_w) // 2
    y = height - text_h - 80 # Fica 80px acima do rodapé
    
    # Efeito stroke (borda preta bruta) para dar leitura em qualquer fundo
    for adj_x in [-3, 0, 3]:
        for adj_y in [-3, 0, 3]:
            draw.text((x+adj_x, y+adj_y), text, font=font, fill="black")
            
    # Preenchimento branco
    draw.text((x, y), text, font=font, fill="white")
    return np.array(img)

# --- CARREGAR IMAGENS ---
def load_overlay_image(url):
    try:
        resp = requests.get(url)
        img = Image.open(BytesIO(resp.content)).convert("RGBA")
        # Previne o erro do ANTIALIAS em versões novas do PIL
        resample_filter = getattr(Image.Resampling, 'LANCZOS', Image.ANTIALIAS)
        img.thumbnail((150, 150), resample_filter)
        return np.array(img)
    except Exception:
        return None

# --- UI STREAMLIT ---
st.set_page_config(page_title="Gerador Wan 2.1", layout="wide")
st.title("🎬 Ilha de Edição IA - Wan 2.1")

with st.sidebar:
    st.header("Configurações")
    api_key = st.text_input("SiliconFlow API Key (sk-...)", type="password", help="Deixe vazio para ver o vídeo em modo de simulação")

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
    st.info("Bora lá... Renderizando seu projeto!")
    
    clips_finais = []
    progress_bar = st.progress(0)
    total_scenes = len(roteiro["scenes"])
    
    for idx, cena in enumerate(roteiro["scenes"]):
        st.write(f"⚙️ Processando cena {idx+1}: {cena['type'].upper()}")
        
        # 1. Gera e carrega áudio
        audio_path = f"temp_files/audio_{idx}.mp3"
        asyncio.run(gen_audio(cena["text"], audio_path))
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        # 2. Prepara o Vídeo Base (Simulação se não tiver chave)
        if not api_key:
            # Cores diferentes para você saber onde foi o corte
            color = (20, 60, 120) if cena["type"] == "worker" else (120, 40, 40)
            base_clip = ColorClip(size=(1280, 720), color=color, duration=duration)
        else:
            # Em prod, aqui entra o Request pro Wan 2.1 via SiliconFlow
            st.warning("Cena enviada pra SiliconFlow! (Gerando cor provisória no app de simulação)")
            base_clip = ColorClip(size=(1280, 720), color=(30, 80, 40), duration=duration)
            
        base_clip = base_clip.set_audio(audio_clip)
        
        # 3. Compositing RIGOROSAMENTE ISOLADO
        layers = [base_clip]
        
        # Adiciona Ícone
        if "overlay_image_url" in cena:
            img_array = load_overlay_image(cena["overlay_image_url"])
            if img_array is not None:
                # Topo direito com margem
                logo_clip = ImageClip(img_array).set_duration(duration).set_position(("right", "top")).margin(top=30, right=30, opacity=0)
                layers.append(logo_clip)
        
        # Adiciona Texto Novo
        if "overlay_text" in cena:
            txt_array = create_text_overlay(cena["overlay_text"])
            txt_clip = ImageClip(txt_array).set_duration(duration).set_position("center")
            layers.append(txt_clip)
            
        # Assa o bolo dessa cena e guarda
        cena_composita = CompositeVideoClip(layers, size=(1280, 720))
        clips_finais.append(cena_composita)
        
        progress_bar.progress((idx + 1) / total_scenes)

    # 4. Costura a parada toda e Exporta
    st.write("✂️ Colando as cenas e exportando...")
    video_final = concatenate_videoclips(clips_finais, method="compose")
    output_path = "temp_files/video_final.mp4"
    video_final.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
    
    st.success("✅ Tá na mão o seu vídeo!")
    st.video(output_path)
