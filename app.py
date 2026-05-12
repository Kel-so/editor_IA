import streamlit as st
import streamlit.components.v1 as components
import json
import os
import shutil
import asyncio
import edge_tts
import base64
import requests
from io import BytesIO
from moviepy.editor import AudioFileClip, concatenate_audioclips

# --- CONFIGURAÇÃO E LIMPEZA DE TEMPORÁRIOS ---
def cleanup_temp():
    """Remove a pasta de ficheiros temporários e cria uma nova."""
    if os.path.exists("temp_files"):
        shutil.rmtree("temp_files")
    os.makedirs("temp_files", exist_ok=True)

# --- GERAÇÃO DE ÁUDIO COM IA ---
async def gen_audio(text, filepath):
    """Gera o áudio usando a voz neural pt-BR."""
    tts = edge_tts.Communicate(text, "pt-BR-AntonioNeural")
    await tts.save(filepath)

# --- CONSTRUTOR DINÂMICO DE LAYOUTS HTML5 ---
def build_slide_html(idx, cena, dur_ms):
    """Constrói a estrutura HTML de cada slide com base no layout escolhido."""
    active_class = "active" if idx == 0 else ""
    layout = cena.get("layout", "centered_list")
    title = cena.get("overlay_text", "").replace("\n", "<br>")
    subtitle = cena.get("subtitle", "")
    bullets = cena.get("bullets", [])
    img_url = cena.get("image_url", "")
    video_url = cena.get("video_url", "")
    emoji = cena.get("icon_emoji", "✨")
    accent = cena.get("accent_color", "yellow-400")
    
    # Renderização da lista de tópicos
    bullets_html = "".join([f'<li class="flex items-start gap-3 mb-2"><span class="text-{accent}">•</span> {b}</li>' for b in bullets])
    
    # Tratamento de Mídia (Vídeo tem prioridade)
    media_html = ""
    if video_url:
        media_html = f"""
        <div class="relative w-full h-full overflow-hidden rounded-3xl shadow-2xl border-4 border-white/10 aspect-video">
            <video muted loop playsinline class="w-full h-full object-cover">
                <source src="{video_url}" type="video/mp4">
            </video>
        </div>
        """
    elif img_url:
        media_html = f'<img src="{img_url}" class="rounded-3xl shadow-2xl border-4 border-white/10 w-full aspect-video object-cover">'

    # Seleção de Template de Layout
    if layout == "split_hero":
        content = f"""
        <div class="flex flex-col md:flex-row items-center gap-12 w-full max-w-6xl px-10">
            <div class="flex-1 text-left">
                <span class="text-{accent} font-black text-6xl mb-4 block">{emoji}</span>
                <h2 class="text-6xl font-black mb-4 uppercase tracking-tighter leading-none text-white drop-shadow-2xl">{title}</h2>
                <p class="text-2xl text-slate-400 mb-6 font-light">{subtitle}</p>
                <ul class="text-xl text-slate-300 space-y-2">{bullets_html}</ul>
            </div>
            <div class="flex-1 w-full">{media_html}</div>
        </div>
        """
    elif layout == "quote_focus":
        content = f"""
        <div class="text-center max-w-4xl px-10">
            <span class="text-9xl opacity-10 block mb-[-60px] text-white">"</span>
            <h2 class="text-4xl md:text-5xl font-serif italic mb-8 leading-tight text-white">{cena.get('text')}</h2>
            <div class="h-1 w-24 bg-{accent} mx-auto mb-6"></div>
            <p class="text-2xl font-bold uppercase tracking-widest text-{accent}">{title}</p>
        </div>
        """
    elif layout == "grid_stats":
        content = f"""
        <div class="w-full max-w-6xl px-10 text-center">
            <h2 class="text-4xl font-black mb-12 uppercase tracking-widest text-white">{title}</h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                {"".join([f'<div class="glass-card p-8 rounded-3xl border-b-4 border-{accent} hover:bg-white/10 transition-all cursor-default"><p class="text-lg text-slate-200">{b}</p></div>' for b in bullets])}
            </div>
        </div>
        """
    else: # centered_list
        content = f"""
        <div class="text-center max-w-3xl px-10">
            <div class="inline-block p-4 rounded-2xl bg-{accent}/10 border border-{accent}/20 mb-6">
                <span class="text-5xl">{emoji}</span>
            </div>
            <h2 class="text-6xl font-black mb-4 uppercase tracking-tight text-white">{title}</h2>
            <p class="text-2xl text-{accent} mb-8 font-medium">{subtitle}</p>
            <div class="glass-card p-8 rounded-3xl text-left inline-block w-full">
                <ul class="space-y-4 text-xl text-slate-200">{bullets_html}</ul>
            </div>
        </div>
        """

    return f"""
    <div class="slide {active_class} flex-col items-center justify-center w-full h-full" data-duration="{dur_ms}">
        {content}
    </div>
    """

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="WebMotion Master", layout="wide")
st.title("🎬 Gerador de Vídeo Híbrido (HTML5 Motion)")

# Roteiro padrão para demonstração
DEFAULT_ROTEIRO = {{
  "project_name": "Futuro_da_Criatividade",
  "scenes": [
    {{
      "layout": "centered_list",
      "text": "O futuro da criatividade não é sobre máquinas, mas sobre o que fazemos com elas.",
      "overlay_text": "A NOVA ERA\\nCRIATIVA",
      "subtitle": "Expandindo os limites",
      "bullets": ["Inovação", "Design", "Tecnologia"],
      "accent_color": "purple-500",
      "icon_emoji": "✨",
      "video_url": "https://assets.mixkit.co/videos/preview/mixkit-abstract-graphic-of-a-starry-galaxy-background-39744-large.mp4"
    }}
  ]
}}

# Carregamento do input JSON
if os.path.exists("roteiro_premium.json"):
    with open("roteiro_premium.json", "r", encoding="utf-8") as f:
        default_json = f.read()
else:
    default_json = json.dumps(DEFAULT_ROTEIRO, indent=2, ensure_ascii=False)

json_input = st.text_area("Roteiro JSON (Cole aqui as suas 10 cenas):", value=default_json, height=300)

if st.button("🚀 Renderizar Experiência Web", type="primary", use_container_width=True):
    try:
        roteiro = json.loads(json_input)
    except Exception as e:
        st.error(f"Erro no JSON: {{e}}")
        st.stop()

    cleanup_temp()
    st.info("A sincronizar vozes e a montar o ambiente digital...")
    
    audio_clips = []
    slides_html = ""
    progress_bar = st.progress(0)
    total_scenes = len(roteiro["scenes"])
    
    for idx, cena in enumerate(roteiro["scenes"]):
        st.write(f"🎙️ A processar: {{cena.get('overlay_text', 'Cena ' + str(idx+1))}}")
        
        audio_path = f"temp_files/audio_{{idx}}.mp3"
        asyncio.run(gen_audio(cena["text"], audio_path))
        clip = AudioFileClip(audio_path)
        audio_clips.append(clip)
        
        dur_ms = int(clip.duration * 1000)
        slides_html += build_slide_html(idx, cena, dur_ms)
        progress_bar.progress((idx + 1) / total_scenes)

    # Concatenação e conversão para Base64
    final_audio = concatenate_audioclips(audio_clips)
    final_audio_path = "temp_files/final_audio.mp3"
    final_audio.write_audiofile(final_audio_path, logger=None)
    
    with open(final_audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')
    
    # TEMPLATE HTML5 FINAL COM ENGINE DE SINCRONIA
    html_template = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700;900&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Montserrat', sans-serif; background: #020617; color: white; overflow: hidden; margin: 0; height: 100vh; }}
            .slide {{ display: none; animation: slideIn 0.8s cubic-bezier(0.23, 1, 0.32, 1) forwards; width: 100%; height: 100%; }}
            .slide.active {{ display: flex; }}
            @keyframes slideIn {{
                from {{ opacity: 0; transform: scale(1.1); filter: blur(20px); }}
                to {{ opacity: 1; transform: scale(1); filter: blur(0); }}
            }}
            @keyframes slideOut {{
                from {{ opacity: 1; transform: scale(1); filter: blur(0); }}
                to {{ opacity: 0; transform: scale(0.9); filter: blur(20px); }}
            }}
            .glass-card {{ background: rgba(255, 255, 255, 0.02); backdrop-filter: blur(15px); border: 1px rgba(255, 255, 255, 0.08) solid; }}
            .progress-segment {{ height: 4px; background: rgba(255, 255, 255, 0.1); flex: 1; margin: 0 4px; border-radius: 2px; overflow: hidden; }}
            .progress-fill {{ height: 100%; background: #facc15; width: 0%; transition: width 0.1s linear; }}
            #overlay {{ position: absolute; inset: 0; z-index: 100; background: #020617; display: flex; align-items: center; justify-content: center; }}
        </style>
    </head>
    <body class="flex flex-col items-center justify-center">
        <div id="overlay">
            <button id="play-btn" class="px-16 py-8 bg-white text-black font-black rounded-full hover:scale-110 transition-transform text-3xl shadow-[0_0_50px_rgba(255,255,255,0.2)]">
                PLAY MOTION
            </button>
        </div>
        <audio id="audio" src="data:audio/mp3;base64,{audio_b64}"></audio>
        <div id="container" class="relative w-full h-full flex items-center justify-center">{{slides_html}}</div>
        <div class="fixed bottom-12 left-0 right-0 px-20 max-w-6xl mx-auto w-full">
            <div class="flex gap-2" id="progress-bar"></div>
            <div class="mt-4 flex justify-between text-xs font-black text-slate-600 uppercase tracking-[0.4em]">
                <span>Experience Designer • WebMotion IA</span>
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
            
            slides.forEach((_, i) => {{
                const seg = document.createElement('div');
                seg.className = 'progress-segment';
                const fill = document.createElement('div');
                fill.className = 'progress-fill';
                fill.id = 'f-' + i;
                seg.appendChild(fill);
                bar.appendChild(seg);
            }});

            function playMedia(index) {{
                const video = slides[index].querySelector('video');
                if(video) {{
                    video.currentTime = 0;
                    video.play().catch(e => console.log("Erro video:", e));
                }}
            }}

            document.getElementById('play-btn').onclick = () => {{
                document.getElementById('overlay').style.display = 'none';
                audio.play();
                playMedia(0);
                update();
            }};

            function update() {{
                const now = audio.currentTime * 1000;
                const s = Math.floor(now / 1000);
                const ms = Math.floor((now % 1000) / 10);
                timer.textContent = s.toString().padStart(2, '0') + ':' + ms.toString().padStart(2, '0');

                let acc = 0; let target = 0;
                for(let i=0; i<durations.length; i++) {{
                    const start = acc; const end = acc + durations[i];
                    const fill = document.getElementById('f-' + i);
                    if (now >= end) fill.style.width = '100%';
                    else if (now >= start) {{
                        fill.style.width = ((now - start) / durations[i] * 100) + '%';
                        target = i;
                    }} else fill.style.width = '0%';
                    acc = end;
                }}

                if (target !== current) {{
                    slides[current].style.animation = 'slideOut 0.4s forwards';
                    const prev = current;
                    current = target;
                    setTimeout(() => {{
                        slides[prev].classList.remove('active');
                        slides[current].classList.add('active');
                        slides[current].style.animation = 'slideIn 0.8s forwards';
                        playMedia(current);
                    }}, 300);
                }}
                if (!audio.ended) requestAnimationFrame(update);
            }}
        </script>
    </body>
    </html>
    """
    st.success("✅ Cinema WebMotion renderizado!")
    components.html(html_template, height=850, scrolling=False)
