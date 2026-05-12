import streamlit as st
import streamlit.components.v1 as components
import json
import os
import shutil
import asyncio
import edge_tts
import base64
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

# --- UI STREAMLIT ---
st.set_page_config(page_title="Gerador WebMotion", layout="wide")
st.title("⚡ Ilha de Edição HTML5 - Modo Express")
st.markdown("Chega de renderizar vídeo. O navegador faz o trabalho sujo e em tempo real.")

json_input = st.text_area("Cole seu Roteiro JSON:", height=300, placeholder='{\n  "scenes": [\n    ...\n  ]\n}')

if st.button("🚀 Gerar Apresentação Animada", type="primary", use_container_width=True):
    if not json_input.strip():
        st.warning("Cadê o JSON, mestre?")
        st.stop()
        
    try:
        roteiro = json.loads(json_input)
    except Exception as e:
        st.error(f"Erro no JSON: {e}")
        st.stop()

    cleanup_temp()
    st.info("Gerando vozes e calculando tempos milimétricos...")
    
    audio_clips = []
    durations_ms = []
    slides_html = ""
    
    progress_bar = st.progress(0)
    total_scenes = len(roteiro["scenes"])
    
    # 1. PROCESSA ÁUDIO E GERA SLIDES HTML DINAMICAMENTE
    for idx, cena in enumerate(roteiro["scenes"]):
        st.write(f"🎙️ Gravando cena {idx+1}...")
        
        # Gera e mede o áudio
        audio_path = f"temp_files/audio_{idx}.mp3"
        asyncio.run(gen_audio(cena["text"], audio_path))
        clip = AudioFileClip(audio_path)
        audio_clips.append(clip)
        
        dur_ms = int(clip.duration * 1000)
        durations_ms.append(dur_ms)
        
        # Formata o texto para o HTML (Quebras de linha viram <br>)
        title = cena.get("overlay_text", f"CENA {idx+1}").replace("\n", "<br>")
        text = cena.get("text", "")
        
        # Monta o bloquinho do Slide
        active_class = "active" if idx == 0 else ""
        slides_html += f"""
        <div class="slide {active_class} flex-col items-center text-center" data-duration="{dur_ms}">
            <h2 class="text-5xl md:text-6xl font-black mb-8 uppercase text-white drop-shadow-[0_5px_15px_rgba(0,0,0,0.8)] leading-tight">{title}</h2>
            <div class="glass-card p-6 md:p-8 rounded-3xl w-full max-w-3xl border-l-4 border-l-yellow-400">
                <p class="text-xl md:text-2xl text-slate-200 font-light leading-relaxed">{text}</p>
            </div>
        </div>
        """
        progress_bar.progress((idx + 1) / total_scenes)

    st.write("🔧 Compilando o Player Web...")
    
    # 2. CONCATENA O ÁUDIO E CONVERTE PRA BASE64
    final_audio = concatenate_audioclips(audio_clips)
    final_audio_path = "temp_files/final_audio.mp3"
    final_audio.write_audiofile(final_audio_path, logger=None)
    
    with open(final_audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')
    
    # 3. MONTA O HTML FINAL MESTRE
    html_template = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700;900&display=swap" rel="stylesheet">
        <style>
            body {{
                font-family: 'Montserrat', sans-serif;
                background-color: #0f172a;
                background-image: radial-gradient(circle at 50% 0%, #1e293b 0%, #0f172a 100%);
                color: white;
                overflow: hidden;
                margin: 0;
                height: 100vh;
            }}
            .slide {{
                display: none;
                animation: slideIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                width: 100%;
                justify-content: center;
            }}
            .slide.active {{ display: flex; }}
            @keyframes slideIn {{
                from {{ opacity: 0; transform: translateY(40px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            @keyframes slideOut {{
                from {{ opacity: 1; transform: translateY(0); }}
                to {{ opacity: 0; transform: translateY(-40px); }}
            }}
            .progress-segment {{
                height: 6px;
                background: rgba(255, 255, 255, 0.1);
                flex: 1;
                margin: 0 4px;
                border-radius: 3px;
                overflow: hidden;
                position: relative;
            }}
            .progress-fill {{
                height: 100%;
                background: #facc15;
                width: 0%;
            }}
            .glass-card {{
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(10px);
                border: 1px rgba(255, 255, 255, 0.1) solid;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            }}
            #start-overlay {{
                position: absolute; inset: 0; z-index: 50;
                background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(5px);
                display: flex; flex-direction: column; align-items: center; justify-content: center;
            }}
        </style>
    </head>
    <body class="flex flex-col items-center justify-center relative">
        
        <!-- Bloqueio de Autoplay (Navegadores exigem clique pra tocar áudio) -->
        <div id="start-overlay">
            <h1 class="text-4xl font-black mb-6 uppercase tracking-widest text-yellow-400">Pronto para rodar</h1>
            <button id="start-btn" class="px-8 py-4 bg-white text-slate-900 font-black rounded-full hover:bg-yellow-400 transition-all transform hover:scale-105 text-xl">
                ▶ INICIAR APRESENTAÇÃO
            </button>
        </div>

        <audio id="narration" src="data:audio/mp3;base64,{audio_b64}"></audio>

        <div id="presentation-container" class="relative w-full max-w-5xl h-[600px] flex items-center justify-center px-6">
            {slides_html}
        </div>

        <div class="fixed bottom-8 left-0 right-0 px-8 max-w-5xl mx-auto w-full">
            <div class="flex gap-2 w-full" id="progress-container"></div>
            <div class="mt-4 flex justify-between items-center text-sm font-bold text-slate-400 uppercase tracking-widest">
                <span>⚡ Apresentação Dinâmica</span>
                <span id="timer-display">00:00</span>
            </div>
        </div>

        <script>
            const audio = document.getElementById('narration');
            const startBtn = document.getElementById('start-btn');
            const overlay = document.getElementById('start-overlay');
            const slides = document.querySelectorAll('.slide');
            const progressContainer = document.getElementById('progress-container');
            const timerDisplay = document.getElementById('timer-display');
            
            let currentSlide = 0;
            const slideDurations = Array.from(slides).map(s => parseInt(s.dataset.duration));
            const totalDuration = slideDurations.reduce((a, b) => a + b, 0);
            
            // Cria barras de progresso
            slides.forEach((_, i) => {{
                const segment = document.createElement('div');
                segment.className = 'progress-segment';
                const fill = document.createElement('div');
                fill.className = 'progress-fill';
                fill.id = `fill-${{i}}`;
                segment.appendChild(fill);
                progressContainer.appendChild(segment);
            }});

            startBtn.addEventListener('click', () => {{
                overlay.style.opacity = '0';
                setTimeout(() => overlay.style.display = 'none', 300);
                audio.play();
                requestAnimationFrame(update);
            }});

            function update() {{
                // SINCRONIA MAGISTRA: O tempo agora vem do áudio, não do relógio do PC!
                const elapsed = audio.currentTime * 1000; 
                
                const secs = Math.floor(elapsed / 1000);
                const ms = Math.floor((elapsed % 1000) / 10);
                timerDisplay.textContent = `${{secs.toString().padStart(2, '0')}}:${{ms.toString().padStart(2, '0')}}`;

                let accumulatedTime = 0;
                let targetSlide = 0;

                for(let i = 0; i < slideDurations.length; i++) {{
                    const slideStart = accumulatedTime;
                    const slideEnd = accumulatedTime + slideDurations[i];
                    
                    const fillElement = document.getElementById(`fill-${{i}}`);
                    if (elapsed >= slideEnd) {{
                        fillElement.style.width = '100%';
                    }} else if (elapsed >= slideStart) {{
                        const slideProgress = ((elapsed - slideStart) / slideDurations[i]) * 100;
                        fillElement.style.width = `${{slideProgress}}%`;
                        targetSlide = i;
                    }} else {{
                        fillElement.style.width = '0%';
                    }}
                    accumulatedTime = slideEnd;
                }}

                if (targetSlide !== currentSlide && targetSlide < slides.length) {{
                    changeSlide(targetSlide);
                }}

                if (!audio.ended) {{
                    requestAnimationFrame(update);
                }}
            }}

            function changeSlide(index) {{
                slides[currentSlide].classList.remove('active');
                slides[currentSlide].style.animation = 'slideOut 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards';
                
                const oldIndex = currentSlide;
                currentSlide = index;
                
                setTimeout(() => {{
                    slides[oldIndex].style.display = 'none';
                    slides[currentSlide].style.display = 'flex';
                    slides[currentSlide].style.animation = 'slideIn 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards';
                    slides[currentSlide].classList.add('active');
                }}, 400);
            }}
        </script>
    </body>
    </html>
    """
    
    st.success("✅ Player compilado com sucesso!")
    
    # Roda o HTML inteiro dentro do Streamlit, simulando uma tela de 800px de altura
    components.html(html_template, height=800, scrolling=False)
