import streamlit as st
import streamlit.components.v1 as components
import json
import os
import shutil
import asyncio
import edge_tts
import base64
import requests
import time
import numpy as np
import google.generativeai as genai
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.editor import ColorClip, AudioFileClip, CompositeVideoClip, ImageClip, concatenate_videoclips, concatenate_audioclips

# ==========================================
# SETUP & CLEANUP
# ==========================================
def cleanup_temp():
    if os.path.exists("temp_files"):
        shutil.rmtree("temp_files")
    os.makedirs("temp_files", exist_ok=True)

# ==========================================
# INTEGRAÇÃO GEMINI 3.1 FLASH LITE (Cérebro)
# ==========================================
def generate_script_with_gemini(tema_texto):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        st.error("🚨 Chave do Gemini (GEMINI_API_KEY) não encontrada!")
        return None
        
    genai.configure(api_key=api_key)
    
    prompt = f"""
    Atue como um Diretor de Arte e Copywriter "Premium Apple-style". 
    Crie um roteiro JSON baseado neste tema: {tema_texto}
    
    REGRAS CRÍTICAS:
    1. O JSON DEVE ser um objeto com a chave raiz "scenes". Ex: {{"scenes": [...]}}
    2. Cada "scene" é um bloco de áudio de ~20 segundos em 'narration_text'.
    3. Cada "scene" TEM que ter 'sub_slides' com 4 a 5 elementos visuais para trocar durante o áudio.
    4. NÃO use a chave "data". Coloque as propriedades diretamente na raiz do sub_slide.
    
    CATÁLOGO DE LAYOUTS (Use as chaves exatas mostradas aqui):
    - "hero": {{"layout": "hero", "image_url": "url", "kicker": "TOPO", "title": "TITULO", "highlight": "AZUL", "subtitle": "Desc"}}
    - "pillars": {{"layout": "pillars", "image_url": "url", "items": [{{"emoji": "🛡️", "title": "Segurança", "desc": "Proteção"}}]}} (Exatamente 3 itens)
    - "philosophy": {{"layout": "philosophy", "image_url": "url", "title": "Essência", "paragraphs": ["P1", "P2"]}}
    - "side_by_side": {{"layout": "side_by_side", "image_url": "url", "side_image": "url", "title": "Titulo", "subtitle": "Sub", "list_items": ["A", "B"]}}
    - "metrics": {{"layout": "metrics", "image_url": "url", "metrics": [{{"value": "98%", "label": "Taxa", "color": "text-blue-500"}}]}} (Exatamente 4 itens)
    - "team": {{"layout": "team", "image_url": "url", "title": "Equipe", "members": [{{"name": "Nome", "role": "Cargo", "avatar": "url"}}]}} (Exatamente 3 items)
    - "timeline": {{"layout": "timeline", "image_url": "url", "title": "Jornada", "events": [{{"year": "2024", "event": "Fato", "desc": "Desc"}}]}} (Exatamente 4 itens)
    - "features_grid": {{"layout": "features_grid", "image_url": "url", "features": ["F1", "F2", "F3", "F4", "F5", "F6"]}} (Exatamente 6 itens)
    - "quote": {{"layout": "quote", "image_url": "url", "quote_text": "Frase", "author": "Autor", "role": "Cargo"}}
    - "compare": {{"layout": "compare", "image_url": "url", "bad_title": "Ruim", "bad_items": ["A"], "good_title": "Bom", "good_items": ["B"]}}
    - "title_only": {{"layout": "title_only", "image_url": "url", "title": "Frase de Impacto"}}
    - "ending": {{"layout": "ending", "image_url": "url", "title": "Vamos ao", "highlight": "Fim?", "contact": "email", "website": "site"}}

    Responda apenas o JSON.
    """

    try:
        model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(response_mime_type="application/json")
        )
        return response.text 
    except Exception as e:
        st.error(f"Erro no Gemini: {e}")
        return None

# ==========================================
# MOTOR DE VOZ
# ==========================================
def gen_audio_sync(text, filepath, tts_config):
    provider = tts_config.get("provider", "Edge-TTS")
    if "ElevenLabs" in provider:
        try:
            from elevenlabs.client import ElevenLabs
            api_key = st.secrets.get("ELEVENLABS_API_KEY", "")
            voice_id = tts_config.get("voice_id", "JBFqnCBsd6RMkjVDRZzb")
            client = ElevenLabs(api_key=api_key)
            audio_generator = client.text_to_speech.convert(
                text=text, voice_id=voice_id, model_id="eleven_multilingual_v2", output_format="mp3_44100_128"
            )
            with open(filepath, "wb") as f:
                for chunk in audio_generator:
                    if chunk: f.write(chunk)
        except Exception as e:
            st.error(f"Erro ElevenLabs: {e}")
            st.stop()
    else:
        async def _edge_gen(txt, path):
            tts = edge_tts.Communicate(txt, "pt-BR-AntonioNeural")
            await tts.save(path)
        asyncio.run(_edge_gen(text, filepath))


# ==========================================
# MOTOR 1: WEB PLAYER HTML5 LUMINAL MAX
# ==========================================
def build_luminal_slide(sub_slide, total_index):
    img_url = sub_slide.get("image_url", "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2000")
    layout = sub_slide.get("layout", "title_only")
    p = sub_slide.get("data", sub_slide) # Catch-all para JSON mal comportado
    
    content = ""
    
    if layout == "hero":
        content = f"""
        <div class="text-center max-w-5xl">
            <h2 class="animate-up delay-1 text-blue-500 font-bold tracking-[0.6em] uppercase text-xs mb-6">{p.get('kicker', 'Insight Estratégico')}</h2>
            <h1 class="animate-up delay-2 text-7xl md:text-9xl font-black mb-10 leading-tight">
                {p.get('title', 'TÍTULO')} <br>
                <span class="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-600">{p.get('highlight', '')}</span>
            </h1>
            <p class="animate-up delay-3 text-xl text-gray-400 font-light mb-12 max-w-2xl mx-auto leading-relaxed">{p.get('subtitle', '')}</p>
        </div>
        """
        
    elif layout == "pillars":
        cards = ""
        for i, item in enumerate(p.get("items", [])[:3]):
            cards += f"""
            <div class="glass-card animate-up delay-{i+1}">
                <div class="text-4xl mb-6">{item.get("emoji", "🔹")}</div>
                <h3 class="text-2xl font-bold mb-4">{item.get("title", "Pilar")}</h3>
                <p class="text-gray-400 leading-relaxed">{item.get("desc", "")}</p>
            </div>
            """
        content = f'<div class="max-w-7xl w-full grid md:grid-cols-3 gap-12">{cards}</div>'
        
    elif layout == "philosophy":
        p_html = "".join([f'<p class="animate-up delay-{i+2}">{par}</p>' for i, par in enumerate(p.get("paragraphs", []))])
        content = f"""
        <div class="max-w-4xl glass-card animate-in delay-1">
            <h2 class="text-5xl font-black mb-10 text-blue-500">{p.get('title', 'Nossa Essência')}</h2>
            <div class="space-y-8 text-gray-300 text-xl leading-relaxed">{p_html}</div>
        </div>
        """
        
    elif layout == "side_by_side":
        side_img = p.get("side_image", img_url)
        li_html = "".join([f'<li class="flex items-center gap-4 text-blue-400 font-bold"><span class="w-8 h-8 bg-blue-500/20 rounded-full flex items-center justify-center text-xs text-white">0{i+1}</span>{item}</li>' for i, item in enumerate(p.get("list_items", []))])
        content = f"""
        <div class="max-w-7xl w-full grid md:grid-cols-2 gap-20 items-center">
            <div class="animate-in delay-1 rounded-[40px] overflow-hidden h-[600px] shadow-2xl">
                <img src="{side_img}" class="w-full h-full object-cover">
            </div>
            <div class="space-y-8">
                <h2 class="animate-up delay-2 text-6xl font-black leading-tight">{p.get('title', 'Decisões').replace(chr(10), '<br>')}</h2>
                <p class="animate-up delay-3 text-gray-400 text-xl">{p.get('subtitle', '')}</p>
                <ul class="space-y-6 animate-up delay-4">{li_html}</ul>
            </div>
        </div>
        """
        
    elif layout == "metrics":
        m_html = ""
        for i, m in enumerate(p.get("metrics", [])[:4]):
            m_html += f"""
            <div class="glass-card text-center animate-in delay-{i+1}">
                <div class="text-6xl font-black {m.get("color", "text-blue-500")} mb-4">{m.get("value", "0")}</div>
                <div class="text-xs uppercase tracking-widest opacity-40">{m.get("label", "Dado")}</div>
            </div>
            """
        content = f'<div class="max-w-7xl w-full grid grid-cols-2 md:grid-cols-4 gap-8">{m_html}</div>'

    elif layout == "team":
        m_html = ""
        for i, m in enumerate(p.get("members", [])[:3]):
            m_html += f"""
            <div class="glass-card text-center animate-up delay-{i+2}">
                <div class="w-32 h-32 rounded-full mx-auto mb-8 border-4 border-blue-500/30 overflow-hidden">
                    <img src="{m.get("avatar", "https://i.pravatar.cc/150")}" alt="av">
                </div>
                <h4 class="text-2xl font-bold">{m.get("name", "Nome")}</h4>
                <p class="text-blue-400">{m.get("role", "Cargo")}</p>
            </div>
            """
        content = f"""
        <div class="max-w-6xl w-full">
            <h2 class="text-center text-4xl font-bold mb-16 animate-up delay-1">{p.get('title', 'Equipe')}</h2>
            <div class="grid md:grid-cols-3 gap-12">{m_html}</div>
        </div>
        """

    elif layout == "timeline":
        e_html = ""
        for i, e in enumerate(p.get("events", [])[:4]):
            e_html += f"""
            <div class="glass-card animate-in delay-{i+2}">
                <div class="text-blue-500 font-bold text-sm mb-2">{e.get("year", "2024")}</div>
                <h5 class="font-bold">{e.get("event", "Evento")}</h5>
                <p class="text-xs text-gray-500 mt-4">{e.get("desc", "Descrição")}</p>
            </div>
            """
        content = f"""
        <div class="max-w-6xl w-full">
            <h2 class="text-4xl font-bold mb-16 animate-up delay-1">{p.get('title', 'Jornada')}</h2>
            <div class="grid md:grid-cols-4 gap-6">{e_html}</div>
        </div>
        """

    elif layout == "features_grid":
        f_html = "".join([f'<div class="glass-card text-center font-bold animate-up delay-{i+1}">{f}</div>' for i, f in enumerate(p.get("features", [])[:6])])
        content = f'<div class="max-w-7xl w-full grid grid-cols-2 md:grid-cols-3 gap-8">{f_html}</div>'

    elif layout == "quote":
        content = f"""
        <div class="max-w-5xl text-center">
            <span class="text-8xl text-blue-500 font-serif animate-up delay-1">“</span>
            <h2 class="text-5xl font-light italic animate-up delay-2 leading-relaxed">{p.get('quote_text', 'Frase')}</h2>
            <div class="mt-12 animate-up delay-3">
                <p class="text-2xl font-bold">{p.get('author', 'Autor')}</p>
                <p class="text-blue-400 text-sm tracking-widest uppercase">{p.get('role', 'Cargo')}</p>
            </div>
        </div>
        """

    elif layout == "compare":
        bi = "".join([f"<li>✕ {b}</li>" for b in p.get("bad_items", [])])
        gi = "".join([f"<li>✓ {g}</li>" for g in p.get("good_items", [])])
        content = f"""
        <div class="max-w-6xl w-full grid md:grid-cols-2 gap-px bg-white/5 rounded-[40px] overflow-hidden border border-white/10">
            <div class="glass-card !rounded-none !bg-red-500/5 p-16 animate-in delay-1">
                <h3 class="text-3xl font-bold mb-8 text-red-400">{p.get("bad_title", "Antigo")}</h3>
                <ul class="space-y-6 opacity-60">{bi}</ul>
            </div>
            <div class="glass-card !rounded-none !bg-emerald-500/5 p-16 animate-in delay-2">
                <h3 class="text-3xl font-bold mb-8 text-emerald-400">{p.get("good_title", "Novo")}</h3>
                <ul class="space-y-6">{gi}</ul>
            </div>
        </div>
        """

    elif layout == "ending":
        content = f"""
        <div class="text-center">
            <h2 class="animate-up delay-1 text-7xl font-black mb-12">{p.get("title", "Vamos ao")} <br><span class="text-blue-500">{p.get("highlight", "Fim?")}</span></h2>
            <div class="glass-card inline-block text-left animate-in delay-2">
                <p class="text-blue-400 font-bold mb-2">{p.get("contact", "@contato")}</p>
                <p class="text-gray-400">{p.get("website", "www.site.com")}</p>
            </div>
        </div>
        """
        
    else: # title_only
        content = f'<h2 class="text-6xl text-center font-black animate-up delay-1">{p.get("title", "...")}</h2>'

    return f"""
    <section class="slide" data-index="{total_index}">
        <div class="bg-container"><img src="{img_url}" alt="bg"></div>
        {content}
    </section>
    """


def render_html_player(roteiro, tts_config):
    if isinstance(roteiro, list): 
        roteiro = {"scenes": roteiro}
        
    audio_clips = []
    slides_html = ""
    durations = []
    progress = st.progress(0)
    
    scenes = roteiro.get("scenes", [])
    total_idx = 0
    
    for i, scene in enumerate(scenes):
        st.write(f"🎙️ Processando Cena {i+1}/{len(scenes)}...")
        path = f"temp_files/audio_{i}.mp3"
        gen_audio_sync(scene.get("narration_text", "Texto não encontrado"), path, tts_config)
        
        clip = AudioFileClip(path)
        audio_clips.append(clip)
        
        subs = scene.get("sub_slides", [])
        time_per = (clip.duration * 1000) / len(subs) if subs else 0
        
        for sub in subs:
            slides_html += build_luminal_slide(sub, total_idx)
            durations.append(int(time_per))
            total_idx += 1
            
        progress.progress((i+1)/len(scenes))

    st.write("🎬 Compilando Masterclass Luminal...")
    final_audio = concatenate_audioclips(audio_clips)
    final_audio.write_audiofile("temp_files/final.mp3", logger=None)
    
    with open("temp_files/final.mp3", "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')

    # CSS e JS Extensos e Lindos restaurados em toda sua glória
    html_code = """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Luminal - Master Presentation</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #3b82f6;
                --accent: #10b981;
                --bg-dark: #020617;
            }

            body {
                font-family: 'Inter', sans-serif;
                overflow: hidden;
                background: var(--bg-dark);
                color: white;
                margin: 0;
            }

            .slide {
                position: absolute;
                inset: 0;
                opacity: 0;
                visibility: hidden;
                transition: opacity 1.2s cubic-bezier(0.4, 0, 0.2, 1), visibility 1.2s;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 2rem;
            }

            .slide.active {
                opacity: 1;
                visibility: visible;
            }

            .bg-container {
                position: absolute;
                inset: 0;
                z-index: -1;
                overflow: hidden;
            }

            .bg-container img {
                width: 100%;
                height: 100%;
                object-fit: cover;
                filter: blur(25px) brightness(0.4);
                transform: scale(1.1);
                transition: transform 12s linear;
            }

            .active .bg-container img {
                transform: scale(1.3);
            }

            .glass-card {
                background: rgba(255, 255, 255, 0.03);
                backdrop-filter: blur(12px);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 32px;
                padding: 3rem;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                transition: all 0.5s ease;
            }

            .animate-up { transform: translateY(50px); opacity: 0; transition: all 1.2s cubic-bezier(0.22, 1, 0.36, 1); }
            .animate-in { transform: scale(0.9); opacity: 0; transition: all 1.2s cubic-bezier(0.22, 1, 0.36, 1); }
            
            .active .animate-up, .active .animate-in { transform: translateY(0) scale(1); opacity: 1; }

            .delay-1 { transition-delay: 0.2s; }
            .delay-2 { transition-delay: 0.5s; }
            .delay-3 { transition-delay: 0.8s; }
            .delay-4 { transition-delay: 1.1s; }
            .delay-5 { transition-delay: 1.4s; }
            .delay-6 { transition-delay: 1.7s; }

            .progress-bar-container {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 4px;
                background: rgba(255,255,255,0.05);
                z-index: 100;
            }

            #progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #3b82f6, #6366f1);
                width: 0%;
                transition: width 0.3s linear;
            }

            #overlay { 
                position: fixed; inset: 0; z-index: 999; background: #020617; 
                display: flex; align-items: center; justify-content: center; 
            }
        </style>
    </head>
    <body>

        <div id="overlay">
            <button onclick="startPresentation()" class="px-16 py-8 bg-blue-600 text-white font-black rounded-full hover:scale-105 transition-all text-2xl shadow-[0_0_50px_rgba(59,130,246,0.5)]">
                INICIAR APRESENTAÇÃO
            </button>
        </div>

        <div class="progress-bar-container"><div id="progress-fill"></div></div>

        <header class="fixed top-10 left-10 z-50 flex items-center gap-6">
            <div class="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center font-black text-2xl shadow-lg shadow-blue-500/20">L</div>
            <div>
                <div class="text-[10px] font-bold tracking-[0.5em] uppercase opacity-40">Pitch Deck Elite</div>
                <div class="text-sm font-medium text-blue-400">Luminal AI Engine</div>
            </div>
        </header>

        <audio id="audio" src="data:audio/mp3;base64,[[AUDIO]]"></audio>
        
        <main class="relative h-screen w-full overflow-hidden">
            [[SLIDES]]
        </main>

        <script>
            const audio = document.getElementById('audio');
            const slides = document.querySelectorAll('.slide');
            const progressFill = document.getElementById('progress-fill');
            const durations = [[DURS]];
            let currentSlide = -1;

            function startPresentation() {
                document.getElementById('overlay').style.display = 'none';
                audio.play();
                update();
            }

            function update() {
                const now = audio.currentTime * 1000;
                let acc = 0;
                let target = 0;
                let globalDuration = durations.reduce((a,b)=>a+b,0);
                
                // Barra de progresso suave
                progressFill.style.width = `${(now / globalDuration) * 100}%`;

                for(let i=0; i<durations.length; i++) {
                    const start = acc;
                    const end = acc + durations[i];
                    if (now >= start && now < end) {
                        target = i;
                        break;
                    }
                    if (now >= end && i === durations.length - 1) {
                        target = i; // Crava no último slide se o áudio passar milissegundos a mais
                    }
                    acc = end;
                }

                if (target !== currentSlide) {
                    if(currentSlide >= 0 && slides[currentSlide]) {
                        slides[currentSlide].classList.remove('active');
                    }
                    currentSlide = target;
                    if(slides[currentSlide]) {
                        slides[currentSlide].classList.add('active');
                    }
                }

                if (!audio.ended) {
                    requestAnimationFrame(update);
                }
            }
        </script>
    </body>
    </html>
    """
    
    final_html = html_code.replace("[[AUDIO]]", audio_b64).replace("[[SLIDES]]", slides_html).replace("[[DURS]]", json.dumps(durations))
    components.html(final_html, height=850, scrolling=False)


# ==========================================
# MOTOR 2: RENDERIZADOR MP4 (Clássico/Simples)
# ==========================================
def render_mp4_video(roteiro, tts_config):
    st.info("⚙️ Iniciando renderização MP4 (Pillow + MoviePy)...")
    if isinstance(roteiro, list): roteiro = {"scenes": roteiro}
    clips = []
    
    scenes = roteiro.get("scenes", [])
    if not scenes:
        st.error("JSON inválido para MP4.")
        return

    progress = st.progress(0)
    for i, scene in enumerate(scenes):
        path = f"temp_files/mp4_audio_{i}.mp3"
        gen_audio_sync(scene.get("narration_text", ""), path, tts_config)
        audio = AudioFileClip(path)
        
        # Cria um clip visual de cor sólida como base para a cena
        base = ColorClip(size=(1280, 720), color=(15, 23, 42), duration=audio.duration).set_audio(audio)
        
        # Simplificação para o MP4: 1 texto por áudio (fazer CSS glassmorphism em MP4 via python requereria bibliotecas gráficas pesadas)
        txt = scene.get("narration_text", "")[:60] + "..."
        img = Image.new('RGBA', (1280, 720), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Usa fonte default por segurança
        font = ImageFont.load_default()
        draw.text((100, 300), txt, fill="white", font=font)
        
        txt_clip = ImageClip(np.array(img)).set_duration(audio.duration).set_position('center')
        clips.append(CompositeVideoClip([base, txt_clip]))
        progress.progress((i+1)/len(scenes))
        
    st.write("✂️ Unificando MP4...")
    final_v = concatenate_videoclips(clips, method="compose")
    final_v.write_videofile("temp_files/output.mp4", fps=24, codec="libx264", logger=None)
    st.success("✅ MP4 Pronto!")
    st.video("temp_files/output.mp4")

# ==========================================
# UI
# ==========================================
st.set_page_config(page_title="Luminal Master IA", layout="wide")

with st.sidebar:
    st.title("Settings")
    modo = st.radio("Modo de Saída:", ["1️⃣ Web Player (Luminal HTML5 Max)", "2️⃣ Gerar Arquivo .MP4"])
    
    st.divider()
    tts = st.radio("Voz:", ["Edge-TTS (Free)", "ElevenLabs (Premium)"])
    eleven_key = st.secrets.get("ELEVENLABS_API_KEY", "") if "ElevenLabs" in tts else ""
    v_id = st.text_input("Voice ID", "JBFqnCBsd6RMkjVDRZzb") if "ElevenLabs" in tts else ""
    tts_conf = {"provider": tts, "api_key": eleven_key, "voice_id": v_id}

st.title("🎬 Luminal Master Editor")
tema = st.text_area("Tema da Apresentação:", "Sustentabilidade e Inovação 2030")

if st.button("🧠 1. Gerar Roteiro Mágico (Gemini)", use_container_width=True):
    with st.spinner("Conectando ao Gemini..."):
        res = generate_script_with_gemini(tema)
        if res: 
            st.session_state['script'] = res
            st.success("Roteiro Criado!")

if 'script' in st.session_state:
    with st.expander("✅ JSON Gerado", expanded=True):
        st.code(st.session_state['script'], language="json")

st.divider()
final_json = st.text_area("Roteiro Final (Cole o JSON aqui):", height=300)

if st.button("🚀 2. Renderizar Projeto", type="primary", use_container_width=True):
    cleanup_temp()
    try:
        data = json.loads(final_json)
        if "1️⃣" in modo: 
            render_html_player(data, tts_conf)
        else: 
            render_mp4_video(data, tts_conf)
    except Exception as e: 
        st.error(f"Erro ao ler JSON: {e}")
