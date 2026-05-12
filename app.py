import streamlit as st
import streamlit.components.v1 as components
import json
import os
import shutil
import asyncio
import edge_tts
import base64
from io import BytesIO
from moviepy.editor import AudioFileClip, concatenate_audioclips

# --- SETUP E LIMPEZA ---
def cleanup_temp():
    if os.path.exists("temp_files"):
        shutil.rmtree("temp_files")
    os.makedirs("temp_files", exist_ok=True)

# --- ÁUDIO IA ---
async def gen_audio(text, filepath):
    tts = edge_tts.Communicate(text, "pt-BR-AntonioNeural")
    await tts.save(filepath)

# --- CONSTRUTOR DE LAYOUTS HTML ---
def build_slide_html(idx, cena, dur_ms):
    active_class = "active" if idx == 0 else ""
    layout = cena.get("layout", "centered_list")
    title = cena.get("overlay_text", "").replace("\n", "<br>")
    subtitle = cena.get("subtitle", "")
    bullets = cena.get("bullets", [])
    img_url = cena.get("image_url", "")
    emoji = cena.get("icon_emoji", "✨")
    accent = cena.get("accent_color", "yellow-400")
    
    # Gera o HTML dos bullets
    bullets_html = "".join([f'<li class="flex items-start gap-3 mb-2"><span class="text-{accent}">•</span> {b}</li>' for b in bullets])
    
    # Switch de Layouts
    if layout == "split_hero":
        content = f"""
        <div class="flex flex-col md:flex-row items-center gap-10 w-full max-w-6xl">
            <div class="flex-1 text-left">
                <span class="text-{accent} font-black text-6xl mb-4 block animate-bounce">{emoji}</span>
                <h2 class="text-6xl font-black mb-4 uppercase tracking-tighter">{title}</h2>
                <p class="text-2xl text-slate-400 mb-6 font-light">{subtitle}</p>
                <ul class="text-xl text-slate-300">{bullets_html}</ul>
            </div>
            <div class="flex-1">
                <img src="{img_url}" class="rounded-3xl shadow-2xl border-4 border-white/10 rotate-2 hover:rotate-0 transition-transform duration-500">
            </div>
        </div>
        """
    elif layout == "quote_focus":
        content = f"""
        <div class="text-center max-w-4xl">
            <span class="text-8xl opacity-20 block mb-[-40px]">"</span>
            <h2 class="text-5xl md:text-6xl font-serif italic mb-8 leading-tight">{cena.get('text')}</h2>
            <div class="h-1 w-24 bg-{accent} mx-auto mb-6"></div>
            <p class="text-2xl font-bold uppercase tracking-widest text-{accent}">{title}</p>
            <p class="text-slate-500">{subtitle}</p>
        </div>
        """
    elif layout == "grid_stats":
        content = f"""
        <div class="w-full max-w-5xl">
            <h2 class="text-4xl font-black mb-12 text-center uppercase tracking-widest">{title}</h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                {"".join([f'<div class="glass-card p-8 rounded-3xl border-t-4 border-{accent}"><p class="text-lg">{b}</p></div>' for b in bullets])}
            </div>
        </div>
        """
    else: # centered_list (Default)
        content = f"""
        <div class="text-center max-w-3xl">
            <div class="inline-block p-4 rounded-2xl bg-{accent}/10 border border-{accent}/20 mb-6">
                <span class="text-5xl">{emoji}</span>
            </div>
            <h2 class="text-6xl font-black mb-4 uppercase tracking-tight">{title}</h2>
            <p class="text-2xl text-{accent} mb-8 font-medium">{subtitle}</p>
            <div class="glass-card p-8 rounded-3xl text-left inline-block w-full">
                <ul class="space-y-4 text-xl text-slate-200">{bullets_html}</ul>
            </div>
        </div>
        """

    return f"""
    <div class="slide {active_class} flex-col items-center justify-center" data-duration="{dur_ms}">
        {content}
    </div>
    """

# --- UI STREAMLIT ---
st.set_page_config(page_title="WebMotion IA", layout="wide")
st.title("🎨 Editor de Experiências HTML5")
st.markdown("Transformando JSON em apresentações imersivas com sincronia de áudio.")

# Roteiro Padrão embutido para evitar FileNotFoundError
DEFAULT_ROTEIRO = {
  "project_name": "Doc_Inteligencia_Emocional_Premium",
  "scenes": [
    {
      "layout": "split_hero",
      "text": "Inteligência Emocional não é sobre engolir o choro ou virar um robô. É sobre entender o que você sente.",
      "overlay_text": "AUTOCONHECIMENTO",
      "subtitle": "A base de tudo",
      "bullets": ["Identificar gatilhos", "Nomear sentimentos", "Perceber reações"],
      "accent_color": "blue-500",
      "icon_emoji": "🧠",
      "image_url": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?q=80&w=500&auto=format&fit=crop"
    }
  ]
}

# Tenta carregar do arquivo, se não existir usa o DEFAULT_ROTEIRO acima
if os.path.exists("roteiro_ie.json"):
    with open("roteiro_ie.json", "r", encoding="utf-8") as f:
        default_json = f.read()
else:
    default_json = json.dumps(DEFAULT_ROTEIRO, indent=2, ensure_ascii=False)

json_input = st.text_area("Roteiro JSON (Edite à vontade):", value=default_json, height=300)

if st.button("🚀 Gerar Player Premium", type="primary", use_container_width=True):
    try:
        roteiro = json.loads(json_input)
    except Exception as e:
        st.error(f"Erro no JSON: {e}")
        st.stop()

    cleanup_temp()
    st.info("A preparar os media e a construir os layouts dinâmicos...")
    
    audio_clips = []
    durations_ms = []
    slides_html = ""
    
    progress_bar = st.progress(0)
    total_scenes = len(roteiro["scenes"])
    
    for idx, cena in enumerate(roteiro["scenes"]):
        st.write(f"🎙️ A processar cena {idx+1}: {cena.get('overlay_text', 'Sem Título')}")
        
        audio_path = f"temp_files/audio_{idx}.mp3"
        asyncio.run(gen_audio(cena["text"], audio_path))
        clip = AudioFileClip(audio_path)
        audio_clips.append(clip)
        
        dur_ms = int(clip.duration * 1000)
        durations_ms.append(dur_ms)
        
        slides_html += build_slide_html(idx, cena, dur_ms)
        progress_bar.progress((idx + 1) / total_scenes)

    # Compila áudio final
    final_audio = concatenate_audioclips(audio_clips)
    final_audio_path = "temp_files/final_audio.mp3"
    final_audio.write_audiofile(final_audio_path, logger=None)
    
    with open(final_audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')
    
    # HTML Master com Tailwind e Montserrat
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700;900&display=swap" rel="stylesheet">
        <style>
            body {{
                font-family: 'Montserrat', sans-serif;
                background: #020617;
                color: white;
                overflow: hidden;
                margin: 0;
                height: 100vh;
            }}
            .slide {{
                display: none;
                animation: slideIn 0.8s cubic-bezier(0.23, 1, 0.32, 1) forwards;
                width: 100%;
                height: 100%;
            }}
            .slide.active {{ display: flex; }}
            @keyframes slideIn {{
                from {{ opacity: 0; transform: scale(0.9) translateY(30px); filter: blur(10px); }}
                to {{ opacity: 1; transform: scale(1) translateY(0); filter: blur(0); }}
            }}
            .glass-card {{
                background: rgba(255, 255, 255, 0.03);
                backdrop-filter: blur(12px);
                border: 1px rgba(255, 255, 255, 0.1) solid;
            }}
            .progress-segment {{ height: 6px; background: rgba(255, 255, 255, 0.1); flex: 1; margin: 0 4px; border-radius: 3px; overflow: hidden; }}
            .progress-fill {{ height: 100%; background: #facc15; width: 0%; transition: width 0.1s linear; }}
            #overlay {{ position: absolute; inset: 0; z-index: 100; background: rgba(2, 6, 23, 0.98); display: flex; align-items: center; justify-content: center; }}
        </style>
    </head>
    <body class="flex flex-col items-center justify-center p-10">
        
        <div id="overlay">
            <button id="play-btn" class="px-12 py-6 bg-white text-black font-black rounded-full hover:scale-110 transition-transform text-2xl shadow-2xl shadow-white/10">
                REPRODUZIR EXPERIÊNCIA
            </button>
        </div>

        <audio id="audio" src="data:audio/mp3;base64,{audio_b64}"></audio>

        <div id="container" class="relative w-full h-full flex items-center justify-center">
            {slides_html}
        </div>

        <div class="fixed bottom-12 left-0 right-0 px-20 max-w-6xl mx-auto w-full">
            <div class="flex gap-2" id="progress-bar"></div>
            <div class="mt-4 flex justify-between text-xs font-black text-slate-500 uppercase tracking-[0.3em]">
                <span>Inteligência Emocional • Masterclass</span>
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

            // Cria barras
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
                document.getElementById('overlay').style.display = 'none';
                audio.play();
                update();
            }};

            function update() {{
                const now = audio.currentTime * 1000;
                
                const s = Math.floor(now / 1000);
                const ms = Math.floor((now % 1000) / 10);
                timer.textContent = s.toString().padStart(2, '0') + ':' + ms.toString().padStart(2, '0');

                let acc = 0;
                let target = 0;

                for(let i=0; i<durations.length; i++) {{
                    const start = acc;
                    const end = acc + durations[i];
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
                    current = target;
                    slides[current].classList.add('active');
                }}

                if (!audio.ended) requestAnimationFrame(update);
            }}
        </script>
    </body>
    </html>
    """
    
    st.success("✅ Player Dinâmico Gerado!")
    components.html(html_template, height=850, scrolling=False)
