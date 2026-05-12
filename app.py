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

# --- CONFIGURAÇÃO E LIMPEZA ---
def cleanup_temp():
    if os.path.exists("temp_files"):
        shutil.rmtree("temp_files")
    os.makedirs("temp_files", exist_ok=True)

# --- GERAÇÃO DE ÁUDIO COM IA ---
async def gen_audio(text, filepath):
    tts = edge_tts.Communicate(text, "pt-BR-AntonioNeural")
    await tts.save(filepath)

# --- CONSTRUTOR DE LAYOUTS PREMIUM ---
def build_slide_html(idx, cena, dur_ms):
    active_class = "active" if idx == 0 else ""
    layout = cena.get("layout", "centered_list")
    title = cena.get("overlay_text", "").replace("\n", "<br>")
    subtitle = cena.get("subtitle", "")
    bullets = cena.get("bullets", [])
    img_url = cena.get("image_url", "")
    emoji = cena.get("icon_emoji", "✨")
    accent = cena.get("accent_color", "blue-500")
    
    # Renderização de tópicos estilizados
    bullets_html = "".join([
        f'<li class="flex items-center gap-3 mb-3 bg-white/5 p-3 rounded-xl border border-white/10">'
        f'<span class="flex-shrink-0 w-2 h-2 rounded-full bg-{accent}"></span>'
        f'<span class="text-slate-200 text-lg">{b}</span></li>' 
        for b in bullets
    ])
    
    # Estilo de fundo (Imagem Full ou Gradiente)
    bg_style = f"background-image: linear-gradient(to bottom, rgba(2, 6, 23, 0.7), #020617), url('{img_url}'); background-size: cover; background-position: center;" if img_url else ""

    # Switch de Layouts Elaborados
    if layout == "split_hero": # Texto Esquerda, Imagem Direita (Moderno)
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
    elif layout == "quote_focus": # Texto Gigante e Central (Impacto)
        content = f"""
        <div class="text-center max-w-5xl px-12 z-10">
            <div class="text-9xl font-black opacity-10 text-white mb-[-80px] leading-none italic">"</div>
            <h2 class="text-5xl md:text-6xl font-black italic mb-10 leading-tight text-white tracking-tight">
                {cena.get('text')}
            </h2>
            <div class="flex items-center justify-center gap-4">
                <div class="h-[1px] w-12 bg-white/30"></div>
                <p class="text-2xl font-black uppercase tracking-[0.3em] text-{accent}">{title}</p>
                <div class="h-[1px] w-12 bg-white/30"></div>
            </div>
        </div>
        """
    elif layout == "grid_stats": # Grid de Cartões (Informativo)
        content = f"""
        <div class="w-full max-w-6xl px-12 z-10">
            <h2 class="text-4xl font-black mb-4 text-center uppercase tracking-widest text-white">{title}</h2>
            <p class="text-center text-slate-400 mb-12 text-xl font-light">{subtitle}</p>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
                {"".join([f'<div class="glass-card p-10 rounded-[32px] border-t-2 border-{accent} shadow-2xl"><p class="text-xl leading-relaxed text-slate-100 font-medium text-center">{b}</p></div>' for b in bullets])}
            </div>
        </div>
        """
    else: # centered_list (Hero Minimalista)
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

# --- INTERFACE ---
st.set_page_config(page_title="WebMotion Designer", layout="wide")
st.title("💎 Design de Experiências Ultra-Motion")

# Roteiro padrão enxuto
DEFAULT_ROTEIRO = {
  "project_name": "Presentation_Ultra",
  "scenes": [
    {
      "layout": "centered_list",
      "text": "O design não é apenas o que parece. Design é como funciona.",
      "overlay_text": "DESIGN\nEXPERIENCE",
      "subtitle": "Steve Jobs",
      "bullets": ["Estética", "Funcionalidade", "Emoção"],
      "accent_color": "blue-500",
      "icon_emoji": "🎨",
      "image_url": "https://images.unsplash.com/photo-1558655146-d09347e92766?q=80&w=1200&auto=format&fit=crop"
    }
  ]
}

if os.path.exists("roteiro_premium.json"):
    with open("roteiro_premium.json", "r", encoding="utf-8") as f:
        default_json = f.read()
else:
    default_json = json.dumps(DEFAULT_ROTEIRO, indent=2, ensure_ascii=False)

json_input = st.text_area("Roteiro JSON (30 cenas recomendadas para Motion):", value=default_json, height=300)

if st.button("🚀 Gerar Apresentação de Alto Nível", type="primary", use_container_width=True):
    try:
        roteiro = json.loads(json_input)
    except Exception as e:
        st.error(f"Erro no JSON: {e}")
        st.stop()

    cleanup_temp()
    st.info("Renderizando vozes e orquestrando layouts...")
    
    audio_clips = []
    slides_html = ""
    progress_bar = st.progress(0)
    
    for idx, cena in enumerate(roteiro["scenes"]):
        st.write(f"🎭 Montando cena {idx+1}: {cena.get('overlay_text', '...')}")
        audio_path = f"temp_files/audio_{idx}.mp3"
        asyncio.run(gen_audio(cena["text"], audio_path))
        clip = AudioFileClip(audio_path)
        audio_clips.append(clip)
        dur_ms = int(clip.duration * 1000)
        slides_html += build_slide_html(idx, cena, dur_ms)
        progress_bar.progress((idx + 1) / len(roteiro["scenes"]))

    # Concatenação e Base64
    final_audio = concatenate_audioclips(audio_clips)
    final_audio_path = "temp_files/final_audio.mp3"
    final_audio.write_audiofile(final_audio_path, logger=None)
    with open(final_audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')
    
    # HTML FINAL
    html_template = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Inter', sans-serif; background: #020617; color: white; overflow: hidden; margin: 0; height: 100vh; }}
            .slide {{ display: none; width: 100%; height: 100%; position: absolute; inset: 0; }}
            .slide.active {{ display: flex; animation: slideEnter 1.2s cubic-bezier(0.23, 1, 0.32, 1) forwards; }}
            .slide.exit {{ display: flex; animation: slideExit 0.8s cubic-bezier(0.23, 1, 0.32, 1) forwards; }}
            
            @keyframes slideEnter {{
                from {{ opacity: 0; transform: scale(1.15) translateY(40px); filter: blur(30px); }}
                to {{ opacity: 1; transform: scale(1) translateY(0); filter: blur(0); }}
            }}
            @keyframes slideExit {{
                from {{ opacity: 1; transform: scale(1); filter: blur(0); }}
                to {{ opacity: 0; transform: scale(0.9) translateY(-40px); filter: blur(30px); }}
            }}
            
            .glass-card {{ 
                background: rgba(255, 255, 255, 0.03); 
                backdrop-filter: blur(25px); 
                border: 1px rgba(255, 255, 255, 0.1) solid; 
                box-shadow: 0 50px 100px -20px rgba(0, 0, 0, 0.5);
            }}
            .progress-segment {{ height: 5px; background: rgba(255, 255, 255, 0.05); flex: 1; margin: 0 3px; border-radius: 10px; overflow: hidden; }}
            .progress-fill {{ height: 100%; background: #fff; width: 0%; box-shadow: 0 0 15px #fff; }}
            #overlay {{ position: absolute; inset: 0; z-index: 100; background: #020617; display: flex; align-items: center; justify-content: center; }}
        </style>
    </head>
    <body class="flex flex-col items-center justify-center">
        <div id="overlay">
            <button id="play-btn" class="px-20 py-10 bg-white text-black font-black rounded-[40px] hover:scale-110 active:scale-95 transition-all text-4xl shadow-[0_0_100px_rgba(255,255,255,0.1)]">
                START SHOW
            </button>
        </div>
        <audio id="audio" src="data:audio/mp3;base64,{audio_b64}"></audio>
        <div id="container" class="relative w-full h-full flex items-center justify-center">{slides_html}</div>
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
            
            slides.forEach((_, i) => {{
                const seg = document.createElement('div');
                seg.className = 'progress-segment';
                const fill = document.createElement('div');
                fill.className = 'progress-fill';
                fill.id = 'f-' + i;
                seg.appendChild(fill);
                bar.appendChild(seg);
            }});

            document.getElementById('play-btn').onclick = () => {{
                document.getElementById('overlay').style.opacity = '0';
                setTimeout(() => document.getElementById('overlay').style.display = 'none', 500);
                audio.play();
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
                    slides[current].classList.remove('active');
                    slides[current].classList.add('exit');
                    const prev = current;
                    current = target;
                    setTimeout(() => {{
                        slides[prev].classList.remove('exit');
                        slides[current].classList.add('active');
                    }}, 100);
                }}
                if (!audio.ended) requestAnimationFrame(update);
            }}
        </script>
    </body>
    </html>
    """
    st.success("✅ Apresentação Motion renderizada!")
    components.html(html_template, height=900, scrolling=False)
