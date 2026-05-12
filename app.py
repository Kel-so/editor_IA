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

# --- FUNÇÃO DE EASING (Para o movimento ficar fluido estilo After Effects) ---
def ease_out_cubic(t, duration=0.8):
    # Vai de 0 a 1 de forma suave, desacelerando no final
    p = min(1.0, t / duration)
    return 1 - pow(1 - p, 3)

# --- TEXTO PREMIUM (ALINHADO À ESQUERDA, MULTILINHA + SOFT SHADOW) ---
def create_text_overlay(text):
    # Link bruto corrigido pra não baixar HTML por engano e quebrar a fonte
    font_path = "temp_files/Montserrat-Black.ttf"
    try:
        # Se o arquivo não existir ou tiver menos de 10KB (sinal de que baixou erro 404)
        if not os.path.exists(font_path) or os.path.getsize(font_path) < 10000:
            font_url = "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat-Black.ttf"
            r = requests.get(font_url)
            r.raise_for_status()
            with open(font_path, "wb") as f:
                f.write(r.content)
        
        # Tamanho cavalão e com suporte a acentos de boa
        font = ImageFont.truetype(font_path, 100)
    except:
        # Se TUDO der errado, cai pra cá, mas com o link novo não deve acontecer
        font = ImageFont.load_default()
        
    temp_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    try:
        # Mudamos o alinhamento para a ESQUERDA
        bbox = temp_draw.multiline_textbbox((0, 0), text, font=font, align="left")
        text_w = int(bbox[2] - bbox[0])
        text_h = int(bbox[3] - bbox[1])
    except:
        text_w, text_h = 800, 300
        
    # Lona exata do texto + respiro gigante pra sombra suave
    padding = 40
    
    final_width = max(10, int(text_w) + padding * 2)
    final_height = max(10, int(text_h) + padding * 2)
    
    img = Image.new('RGBA', (final_width, final_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 1. SOFT DROP SHADOW (Gambiarra premium iterativa)
    for i in range(10, 0, -1):
        alpha = int(255 * (0.02 * (11 - i)))
        shadow_color = (0, 0, 0, alpha)
        # Sombra alinhada à esquerda também
        draw.multiline_text((padding + (i*1.5), padding + (i*1.5)), text, font=font, fill=shadow_color, align="left")
    
    # Sombra base mais dura pra dar contraste final
    draw.multiline_text((padding + 4, padding + 4), text, font=font, fill=(0, 0, 0, 200), align="left")
    
    # 2. Texto Principal Branco (Alinhado à esquerda)
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

# --- DADOS PADRÃO (SAGA DO PENTACAMPEONATO) ---
# Dica de amigo: evite emojis como troféus. O Pillow não suporta fontes coloridas de emoji.
default_scenes = [
    {
      "type": "worker",
      "text": "O mundo conheceu a magia em 58. Na Suécia, a camisa amarela tornou-se lendária.",
      "visual_prompt": "Cinematic archival style, 1958 vintage aesthetic, young Pelé crying and hugging teammates, film grain, highly detailed, 4k",
      "overlay_text": "1958: A PRIMEIRA ESTRELA\n- Sede: Suécia\n- Destaque: Pelé (17 anos)\n- Gols na final: Pelé (2), Vavá (2), Zagallo",
      "overlay_image_url": ""
    },
    {
      "type": "motion",
      "text": "Quatro anos depois, o bicampeonato chegou com a força de Mané Garrincha.",
      "visual_prompt": "Dynamic abstract motion graphics, golden stars flying through a dark stadium, epic lighting, unreal engine 5 render",
      "overlay_text": "1962: O BICAMPEONATO\n- Sede: Chile\n- Herói: Garrincha\n- Final: Brasil 3 x 1 Tchecoslováquia",
      "overlay_image_url": ""
    },
    {
      "type": "worker",
      "text": "A melhor seleção de todos os tempos. O tri no México consagrou o futebol arte.",
      "visual_prompt": "Cinematic shot, 1970 iconic yellow jersey, intense sun, players celebrating with the Jules Rimet trophy, hyperrealistic, 8k",
      "overlay_text": "1970: O TRI\n- Sede: México\n- O Esquadrão de Ouro\n- Capitão: Carlos Alberto Torres",
      "overlay_image_url": ""
    },
    {
      "type": "motion",
      "text": "Após um jejum agoniante, o grito de É Tetra ecoou pelos Estados Unidos.",
      "visual_prompt": "Modern glitch motion graphics, golden trophy forming from digital particles, dramatic blue and yellow lighting, 3d animation",
      "overlay_text": "1994: É TETRA!\n- Sede: EUA\n- Dupla: Romário & Bebeto\n- Decisão nos pênaltis",
      "overlay_image_url": ""
    },
    {
      "type": "worker",
      "text": "E na Ásia, a redenção do Fenômeno trouxe o tão sonhado Pentacampeonato. O Brasil no topo do mundo.",
      "visual_prompt": "Epic celebration, Ronaldo Fenômeno smiling with the World Cup trophy, confetti falling in Yokohama stadium, cinematic lighting, ultra realistic",
      "overlay_text": "2002: O PENTA\n- Sede: Coreia e Japão\n- O Retorno do Fenômeno\n- 2 gols na grande final",
      "overlay_image_url": "https://upload.wikimedia.org/wikipedia/en/thumb/e/e3/2002_FIFA_World_Cup.svg/200px-2002_FIFA_World_Cup.svg.png"
    }
]

# Inicializa o estado
if 'scenes' not in st.session_state:
    st.session_state.scenes = default_scenes.copy()

# --- UI STREAMLIT ---
st.set_page_config(page_title="Gerador Wan 2.1", layout="wide")
st.title("🎬 Ilha de Edição IA - Modo Premium")
st.markdown("Textos alinhados à esquerda, gigantes, com sombra e animação fluida.")

with st.sidebar:
    st.header("Configurações")
    api_key = st.text_input("SiliconFlow API Key", type="password", help="Vazio = Simulação com fundos coloridos")

# --- CONSTRUTOR DE CENAS ---
for i, scene in enumerate(st.session_state.scenes):
    with st.expander(f"🎬 Cena {i+1} | Tipo: {scene['type'].upper()}", expanded=False):
        col1, col2 = st.columns([1, 4])
        scene['type'] = col1.selectbox("Estilo", ["worker", "motion"], index=0 if scene['type'] == 'worker' else 1, key=f"type_{i}")
        scene['text'] = col2.text_input("Narração (Voz)", value=scene.get('text', ''), key=f"text_{i}")
        
        scene['visual_prompt'] = st.text_area("Prompt para a IA (Inglês)", value=scene.get('visual_prompt', ''), key=f"prompt_{i}")
        
        col3, col4 = st.columns(2)
        scene['overlay_text'] = col3.text_area("Motion Text (Sem emojis coloridos, use ENTER)", value=scene.get('overlay_text', ''), height=120, key=f"otext_{i}")
        scene['overlay_image_url'] = col4.text_input("URL do Logotipo/Ícone", value=scene.get('overlay_image_url', ''), key=f"oimg_{i}")

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
    st.info("Renderizando frame a frame com animações fluidas...")
    
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
            
            # Centralizado verticalmente, mas fixo com 100px de margem na esquerda
            target_y = (720 - txt_h) // 2
            start_y = target_y + 120
            
            # Posição X fixa em 100, animando apenas o Y pra deslizar bonitão
            txt_clip = (ImageClip(txt_array)
                        .set_duration(duration)
                        .crossfadein(0.8)
                        .set_position(lambda t, sy=start_y, ty=target_y: (100, int(sy - (sy - ty) * ease_out_cubic(t)))))
            
            layers.append(txt_clip)
            
        cena_composita = CompositeVideoClip(layers, size=(1280, 720))
        clips_finais.append(cena_composita)
        
        progress_bar.progress((idx + 1) / total_scenes)

    st.write("✂️ Unificando blocos e exportando...")
    video_final = concatenate_videoclips(clips_finais, method="compose")
    output_path = "temp_files/video_final.mp4"
    video_final.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
    
    st.success("✅ Tá no ar! Aperta o play pra ver o texto de gente grande.")
    st.video(output_path)
