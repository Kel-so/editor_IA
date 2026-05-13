import streamlit as st
import streamlit.components.v1 as components
import json
import os
import shutil
import asyncio
import edge_tts
import base64
import requests
import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.editor import ColorClip, AudioFileClip, CompositeVideoClip, ImageClip, concatenate_videoclips, concatenate_audioclips

# ==========================================
# CONFIGURAÇÕES GERAIS E CLEANUP
# ==========================================
def cleanup_temp():
    """Limpa a pasta de ficheiros temporários."""
    if os.path.exists("temp_files"):
        shutil.rmtree("temp_files")
    os.makedirs("temp_files", exist_ok=True)

async def gen_audio(text, filepath):
    """Gera áudio com IA (Edge TTS)."""
    tts = edge_tts.Communicate(text, "pt-BR-AntonioNeural")
    await tts.save(filepath)


# ==========================================
# MOTOR 1: WEB PLAYER HTML5 (O mais rápido)
# ==========================================
def build_slide_html(idx, cena, dur_ms):
    active_class = "active" if idx == 0 else ""
    layout = cena.get("layout", "centered_list")
    title = cena.get("overlay_text", "").replace("\n", "<br>")
    subtitle = cena.get("subtitle", "")
    bullets = cena.get("bullets", [])
    img_url = cena.get("image_url", "")
    video_url = cena.get("video_url", "")
    emoji = cena.get("icon_emoji", "✨")
    accent = cena.get("accent_color", "blue-500")
    
    bullets_html = "".join([
        f'<li class="flex items-center gap-3 mb-3 bg-white/5 p-3 rounded-xl border border-white/10">'
        f'<span class="flex-shrink-0 w-2 h-2 rounded-full bg-{accent}"></span>'
        f'<span class="text-slate-200 text-lg">{b}</span></li>' 
        for b in bullets
    ])
    
    bg_style = f"background-image: linear-gradient(to bottom, rgba(2, 6, 23, 0.7), #020617), url('{img_url}'); background-size: cover; background-position: center;" if img_url else ""

    if layout == "split_hero":
        content = f"""
        <div class="flex flex-col md:flex-row items-center gap-16 w-full max-w-6xl px-12 z-10">
            <div class="flex-[1.2] text-left">
                <div class="inline-block px-4 py-1 rounded-full bg-{accent}/20 border border-{accent}/30 text-{accent} text-xs font-black tracking-widest uppercase mb-6 animate-pulse">
                    {emoji} {subtitle or "Destaque"}
                </div>
                <h2 class="text-7xl font-black mb-6 uppercase tracking-tighter leading-[0.9] text-white drop-shadow-2xl">{title}</h2>
                <div class="h-1.5 w-20 bg-{accent} mb-8 rounded-full"></div>
                <ul class="space-y-2">{bullets_html}</ul>
            </div>
            <div class="flex-1 w-full relative">
                <div class="absolute -inset-4 bg-{accent}/20 blur-3xl rounded-full"></div>
                <img src="{img_url}" class="relative rounded-[40px] shadow-2xl border-2 border-white/10 transform rotate-3 hover:rotate-0 transition-all duration-700">
            </div>
        </div>
        """
    elif layout == "quote_focus":
        content = f"""
        <div class="text-center max-w-5xl px-12 z-10">
            <div class="text-9xl font-black opacity-10 text-white mb-[-80px] leading-none italic">"</div>
            <h2 class="text-5xl md:text-6xl font-black italic mb-10 leading-tight text-white tracking-tight">{cena.get('text')}</h2>
            <div class="flex items-center justify-center gap-4">
                <div class="h-[1px] w-12 bg-white/30"></div>
                <p class="text-2xl font-black uppercase tracking-[0.3em] text-{accent}">{title}</p>
                <div class="h-[1px] w-12 bg-white/30"></div>
            </div>
        </div>
        """
    elif layout == "grid_stats":
        content = f"""
        <div class="w-full max-w-6xl px-12 z-10">
            <h2 class="text-4xl font-black mb-4 text-center uppercase tracking-widest text-white">{title}</h2>
            <p class="text-center text-slate-400 mb-12 text-xl font-light">{subtitle}</p>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
                {"".join([f'<div class="glass-card p-10 rounded-[32px] border-t-2 border-{accent} shadow-2xl"><p class="text-xl leading-relaxed text-slate-100 font-medium text-center">{b}</p></div>' for b in bullets])}
            </div>
        </div>
        """
    else:
        content = f"""
        <div class="text-center max-w-4xl px-12 z-10">
            <span class="text-7xl mb-8 block drop-shadow-lg">{emoji}</span>
            <h2 class="text-8xl font-black mb-6 uppercase tracking-tighter text-white leading-none">{title}</h2>
            <p class="text-2xl text-slate-400 mb-10 font-light max-w-2xl mx-auto">{subtitle}</p>
            <div class="flex flex-wrap justify-center gap-4">
                {"".join([f'<span class="px-6 py-3 rounded-2xl glass-card border border-white/10 text-lg font-bold text-{accent}">{b}</span>' for b in bullets])}
            </div>
        </div>
        """

    return f"""
    <div class="slide {active_class} flex-col items-center justify-center w-full h-full relative" data-duration="{dur_ms}" style="{bg_style}">
        {content}
        <div class="absolute inset-0 bg-black/40 z-0"></div>
    </div>
    """

def render_html_player(roteiro):
    audio_clips = []
    slides_html = ""
    progress_bar = st.progress(0)
    total_scenes = len(roteiro["scenes"])
    
    for idx, cena in enumerate(roteiro["scenes"]):
        st.write(f"🎭 A montar HTML cena {idx+1}: {cena.get('overlay_text', '...')}")
        audio_path = f"temp_files/audio_{idx}.mp3"
        asyncio.run(gen_audio(cena["text"], audio_path))
        clip = AudioFileClip(audio_path)
        audio_clips.append(clip)
        dur_ms = int(clip.duration * 1000)
        slides_html += build_slide_html(idx, cena, dur_ms)
        progress_bar.progress((idx + 1) / total_scenes)

    final_audio = concatenate_audioclips(audio_clips)
    final_audio_path = "temp_files/final_audio.mp3"
    final_audio.write_audiofile(final_audio_path, logger=None)
    with open(final_audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')
    
    # Template HTML puro, sem ser f-string, para não quebrar as cores do teu editor!
    html_template = """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; background: #020617; color: white; overflow: hidden; margin: 0; height: 100vh; }
            .slide { display: none; width: 100%; height: 100%; position: absolute; inset: 0; }
            .slide.active { display: flex; animation: slideEnter 1.2s cubic-bezier(0.23, 1, 0.32, 1) forwards; }
            .slide.exit { display: flex; animation: slideExit 0.8s cubic-bezier(0.23, 1, 0.32, 1) forwards; }
            @keyframes slideEnter { from { opacity: 0; transform: scale(1.15) translateY(40px); filter: blur(30px); } to { opacity: 1; transform: scale(1) translateY(0); filter: blur(0); } }
            @keyframes slideExit { from { opacity: 1; transform: scale(1); filter: blur(0); } to { opacity: 0; transform: scale(0.9) translateY(-40px); filter: blur(30px); } }
            .glass-card { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(25px); border: 1px rgba(255, 255, 255, 0.1) solid; box-shadow: 0 50px 100px -20px rgba(0, 0, 0, 0.5); }
            .progress-segment { height: 5px; background: rgba(255, 255, 255, 0.05); flex: 1; margin: 0 3px; border-radius: 10px; overflow: hidden; }
            .progress-fill { height: 100%; background: #fff; width: 0%; box-shadow: 0 0 15px #fff; }
            #overlay { position: absolute; inset: 0; z-index: 100; background: #020617; display: flex; align-items: center; justify-content: center; }
        </style>
    </head>
    <body class="flex flex-col items-center justify-center">
        <div id="overlay">
            <button id="play-btn" class="px-20 py-10 bg-white text-black font-black rounded-[40px] hover:scale-110 active:scale-95 transition-all text-4xl shadow-[0_0_100px_rgba(255,255,255,0.1)]">
                START SHOW
            </button>
        </div>
        <audio id="audio" src="data:audio/mp3;base64,[[AUDIO_B64]]"></audio>
        <div id="container" class="relative w-full h-full flex items-center justify-center">[[SLIDES_HTML]]</div>
        <div class="fixed bottom-12 left-0 right-0 px-20 max-w-7xl mx-auto w-full z-50">
            <div class="flex gap-1" id="progress-bar"></div>
            <div class="mt-5 flex justify-between text-[10px] font-black text-slate-500 uppercase tracking-[0.5em]">
                <span>Brand Motion • Digital Experience</span>
                <span id="timer">00:00</span>
            </div>
        </div>
        <script>
            const audio = document.getElementById('audio');
            const slides = document.querySelectorAll('.slide');
            const timer = document.getElementById('timer');
            const bar = document.getElementById('progress-bar');
            let current = 0;
            const durations = Array.from(slides).map(s => parseInt(s.dataset.duration));
            
            slides.forEach((_, i) => {
                const seg = document.createElement('div');
                seg.className = 'progress-segment';
                const fill = document.createElement('div');
                fill.className = 'progress-fill';
                fill.id = 'f-' + i;
                seg.appendChild(fill);
                bar.appendChild(seg);
            });

            document.getElementById('play-btn').onclick = () => {
                document.getElementById('overlay').style.opacity = '0';
                setTimeout(() => document.getElementById('overlay').style.display = 'none', 500);
                audio.play();
                update();
            };

            function update() {
                const now = audio.currentTime * 1000;
                const s = Math.floor(now / 1000);
                const ms = Math.floor((now % 1000) / 10);
                timer.textContent = s.toString().padStart(2, '0') + ':' + ms.toString().padStart(2, '0');

                let acc = 0; let target = 0;
                for(let i=0; i<durations.length; i++) {
                    const start = acc; const end = acc + durations[i];
                    const fill = document.getElementById('f-' + i);
                    if (now >= end) fill.style.width = '100%';
                    else if (now >= start) {
                        fill.style.width = ((now - start) / durations[i] * 100) + '%';
                        target = i;
                    } else fill.style.width = '0%';
                    acc = end;
                }

                if (target !== current) {
                    slides[current].classList.remove('active');
                    slides[current].classList.add('exit');
                    const prev = current;
                    current = target;
                    setTimeout(() => {
                        slides[prev].classList.remove('exit');
                        slides[current].classList.add('active');
                    }, 100);
                }
                if (!audio.ended) requestAnimationFrame(update);
            }
        </script>
    </body>
    </html>
    """
    
    # Injetamos os dados de forma segura sem rebentar com a sintaxe do teu editor
    html_final = html_template.replace("[[AUDIO_B64]]", audio_b64).replace("[[SLIDES_HTML]]", slides_html)
    
    st.success("✅ Apresentação Motion renderizada!")
    components.html(html_final, height=900, scrolling=False)


# ==========================================
# MOTOR 2: RENDERIZADOR MP4 (O clássico)
# ==========================================
def ease_out_cubic(t, duration=0.8):
    p = min(1.0, t / duration)
    return 1 - pow(1 - p, 3)

FONT_CACHE = {}
def get_font(size=70):
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
        print(f"Erro ao carregar fonte: {e}")
        return ImageFont.load_default()

def create_text_overlay(text):
    font = get_font(70)
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
    shadow_layer = Image.new('RGBA', (final_width, final_height), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    
    shadow_draw.multiline_text((padding + 10, padding + 15), text, font=font, fill=(0, 0, 0, 255), align="left")
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=25))
    
    img.alpha_composite(shadow_layer)
    img.alpha_composite(shadow_layer)
    img.alpha_composite(shadow_layer)
    
    draw = ImageDraw.Draw(img)
    draw.multiline_text((padding, padding), text, font=font, fill="white", align="left")
    return np.array(img)

def render_mp4_video(roteiro):
    clips_finais = []
    progress_bar = st.progress(0)
    total_scenes = len(roteiro["scenes"])
    
    for idx, cena in enumerate(roteiro["scenes"]):
        st.write(f"⚙️ A renderizar MP4 cena {idx+1}...")
        
        audio_path = f"temp_files/audio_{idx}.mp3"
        asyncio.run(gen_audio(cena["text"], audio_path))
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        # Fallback ColorClip se for usar sem imagens dinâmicas
        color = (20, 60, 120) if cena.get("type", "worker") == "worker" else (120, 40, 40)
        base_clip = ColorClip(size=(1280, 720), color=color, duration=duration)
        base_clip = base_clip.set_audio(audio_clip)
        layers = [base_clip]
        
        # Pega o texto principal da cena (do antigo overlay_text ou title)
        texto_tela = cena.get("overlay_text", "")
        if not texto_tela:
            texto_tela = f"CENA {idx+1}"
            
        txt_array = create_text_overlay(texto_tela)
        txt_h = txt_array.shape[0]
        
        target_y = (720 - txt_h) // 2
        start_y = target_y + 120
        
        txt_clip = (ImageClip(txt_array)
                    .set_duration(duration)
                    .crossfadein(0.8)
                    .set_position(lambda t, sy=start_y, ty=target_y: (100, int(sy - (sy - ty) * ease_out_cubic(t)))))
        
        layers.append(txt_clip)
        
        cena_composita = CompositeVideoClip(layers, size=(1280, 720))
        clips_finais.append(cena_composita)
        progress_bar.progress((idx + 1) / total_scenes)

    st.write("✂️ A unificar blocos e a exportar...")
    video_final = concatenate_videoclips(clips_finais, method="compose")
    output_path = "temp_files/video_final.mp4"
    video_final.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
    
    st.success("✅ Vídeo final MP4 gerado com sucesso!")
    st.video(output_path)


# ==========================================
# UI STREAMLIT PRINCIPAL
# ==========================================
st.set_page_config(page_title="Ilha de Edição Híbrida", layout="wide")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4370/4370757.png", width=80)
    st.title("Configurações")
    st.markdown("Escolha o motor de renderização.")
    modo_render = st.radio(
        "Modo de Saída:",
        ["1️⃣ Web Player (HTML5 Dinâmico)", "2️⃣ Vídeo Real (Gerar .MP4)"]
    )
    st.divider()
    st.markdown("**Nota:** O modo MP4 usa o motor clássico (ColorClip + PIL), enquanto o HTML5 usa o design imersivo avançado.")

st.title("🎬 Ilha de Edição Multimotor")

# Tenta carregar o último JSON premium (IA na Educação) ou joga um padrãozinho
DEFAULT_JSON = {
  "project_name": "Projeto_Hibrido",
  "scenes": [
    {
      "type": "worker",
      "layout": "centered_list",
      "text": "Bem-vindo ao motor híbrido. Escolha na barra lateral como você quer que eu trabalhe hoje.",
      "overlay_text": "O MEGAZORD\nDA EDIÇÃO",
      "bullets": ["Modo HTML5 Ultra Rápido", "Modo MP4 Clássico Seguro"],
      "accent_color": "indigo-500",
      "icon_emoji": "🤖"
    }
  ]
}

if os.path.exists("ia_educacao_premium.json"):
    with open("ia_educacao_premium.json", "r", encoding="utf-8") as f:
        default_val = f.read()
else:
    default_val = json.dumps(DEFAULT_JSON, indent=2, ensure_ascii=False)

json_input = st.text_area("Roteiro JSON:", value=default_val, height=400)

if st.button(f"🚀 Iniciar: {modo_render}", type="primary", use_container_width=True):
    try:
        roteiro = json.loads(json_input)
    except Exception as e:
        st.error(f"Erro no JSON: {e}")
        st.stop()
        
    cleanup_temp()
    
    # Roteamento Mágico
    if "Web Player" in modo_render:
        st.info("A iniciar motor HTML5... (Foco em velocidade e CSS avançado)")
        render_html_player(roteiro)
    else:
        st.info("A iniciar motor MoviePy... (Foco em gerar ficheiro MP4 final para download)")
        render_mp4_video(roteiro)
