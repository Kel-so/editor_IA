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
        st.error("🚨 Chave do Gemini (GEMINI_API_KEY) não encontrada nos secrets!")
        return None
        
    genai.configure(api_key=api_key)
    
    prompt = f"""
    Atue como um Roteirista Sênior, Diretor de Arte e Especialista em Masterclasses "Premium Apple-style". 
    Sua missão é criar um roteiro JSON de uma AULA/MASTERCLASS profunda e dinâmica sobre: {tema_texto}
    
    DIRETRIZES DE STORYTELLING E SINCRONIA (A REGRA DOS 8 SEGUNDOS):
    - Cada cena terá exatamente um áudio curto e direto ao ponto de ~8 segundos (cerca de 20-25 palavras).
    - Para CADA cena, você deve definir exatamente UM layout visual que combine 100% com o áudio.
    
    REGRAS CRÍTICAS DE ESTRUTURA JSON:
    1. O JSON DEVE ser um objeto com a chave raiz "scenes". Ex: {{"scenes": [...]}}
    2. NÃO crie listas de 'sub_slides'. A própria "scene" é o slide.
    3. Coloque as propriedades do layout (layout, image_url, title, etc) DIRETAMENTE na raiz da scene, junto com 'narration_text'.
    4. NÃO use a chave "data".
    
    CATÁLOGO DE LAYOUTS (Use as chaves exatas mostradas aqui dentro de cada scene):
    - "hero": {{"narration_text": "...", "layout": "hero", "image_url": "url", "kicker": "CATEGORIA", "title": "TÍTULO IMPACTANTE", "highlight": "DESTAQUE NEON", "subtitle": "Subtítulo instigante"}}
    - "pillars": {{"narration_text": "...", "layout": "pillars", "image_url": "url", "items": [{{"emoji": "🧠", "title": "Conceito 1", "desc": "Explicação"}}]}} (Exatamente 3 itens)
    - "philosophy": {{"narration_text": "...", "layout": "philosophy", "image_url": "url", "title": "Mudança", "paragraphs": ["P1", "P2"]}}
    - "side_by_side": {{"narration_text": "...", "layout": "side_by_side", "image_url": "url", "side_image": "url_lateral", "title": "Análise", "subtitle": "Contexto", "list_items": ["Ponto A", "Ponto B"]}}
    - "metrics": {{"narration_text": "...", "layout": "metrics", "image_url": "url", "metrics": [{{"value": "99%", "label": "Impacto", "color": "text-brand"}}]}} (Exatamente 4 itens)
    - "team": {{"narration_text": "...", "layout": "team", "image_url": "url", "title": "Protagonistas", "members": [{{"name": "Nome", "role": "Papel", "avatar": "url"}}]}} (Exatamente 3 items)
    - "timeline": {{"narration_text": "...", "layout": "timeline", "image_url": "url", "title": "Evolução", "events": [{{"year": "Fase 1", "event": "O Início", "desc": "Contexto"}}]}} (Exatamente 4 itens)
    - "features_grid": {{"narration_text": "...", "layout": "features_grid", "image_url": "url", "features": ["A", "B", "C", "D", "E", "F"]}} (Exatamente 6 itens)
    - "quote": {{"narration_text": "...", "layout": "quote", "image_url": "url", "quote_text": "Frase genial", "author": "Autor", "role": "Contexto"}}
    - "compare": {{"narration_text": "...", "layout": "compare", "image_url": "url", "bad_title": "O Passado", "bad_items": ["Erro 1"], "good_title": "O Futuro", "good_items": ["Acerto 1"]}}
    - "title_only": {{"narration_text": "...", "layout": "title_only", "image_url": "url", "title": "Frase de Impacto Absoluto"}}
    - "ending": {{"narration_text": "...", "layout": "ending", "image_url": "url", "title": "Qual será o seu", "highlight": "Próximo Passo?", "contact": "contato@empresa.com", "website": "www.empresa.com"}}

    Construa de 6 a 8 cenas rápidas.
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
def build_luminal_slide(slide_data, total_index):
    img_url = slide_data.get("image_url", "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2000")
    layout = slide_data.get("layout", "title_only")
    p = slide_data.get("data", slide_data) 
    
    content = ""
    
    if layout == "hero":
        content = f"""
        <div class="text-center max-w-5xl">
            <h2 class="animate-up delay-1 text-brand font-bold tracking-[0.6em] uppercase text-xs mb-6">{p.get('kicker', 'Insight Estratégico')}</h2>
            <h1 class="animate-up delay-2 text-7xl md:text-9xl font-black mb-10 leading-tight">
                {p.get('title', 'TÍTULO')} <br>
                <span class="text-transparent bg-clip-text bg-gradient-to-r from-brand to-white/50">{p.get('highlight', '')}</span>
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
            <h2 class="text-5xl font-black mb-10 text-brand">{p.get('title', 'Nossa Essência')}</h2>
            <div class="space-y-8 text-gray-300 text-xl leading-relaxed">{p_html}</div>
        </div>
        """
        
    elif layout == "side_by_side":
        side_img = p.get("side_image", img_url)
        li_html = "".join([f'<li class="flex items-center gap-4 text-brand font-bold"><span class="w-8 h-8 bg-brand/20 rounded-full flex items-center justify-center text-xs text-white">0{i+1}</span>{item}</li>' for i, item in enumerate(p.get("list_items", []))])
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
            color_class = m.get("color", "text-brand")
            if "blue-500" in color_class: color_class = "text-brand"
            m_html += f"""
            <div class="glass-card text-center animate-in delay-{i+1}">
                <div class="text-6xl font-black {color_class} mb-4">{m.get("value", "0")}</div>
                <div class="text-xs uppercase tracking-widest opacity-40">{m.get("label", "Dado")}</div>
            </div>
            """
        content = f'<div class="max-w-7xl w-full grid grid-cols-2 md:grid-cols-4 gap-8">{m_html}</div>'

    elif layout == "team":
        m_html = ""
        for i, m in enumerate(p.get("members", [])[:3]):
            m_html += f"""
            <div class="glass-card text-center animate-up delay-{i+2}">
                <div class="w-32 h-32 rounded-full mx-auto mb-8 border-4 border-brand/30 overflow-hidden">
                    <img src="{m.get("avatar", "https://i.pravatar.cc/150")}" alt="av">
                </div>
                <h4 class="text-2xl font-bold">{m.get("name", "Nome")}</h4>
                <p class="text-brand/80">{m.get("role", "Cargo")}</p>
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
                <div class="text-brand font-bold text-sm mb-2">{e.get("year", "2024")}</div>
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
            <span class="text-8xl text-brand font-serif animate-up delay-1">“</span>
            <h2 class="text-5xl font-light italic animate-up delay-2 leading-relaxed">{p.get('quote_text', 'Frase')}</h2>
            <div class="mt-12 animate-up delay-3">
                <p class="text-2xl font-bold">{p.get('author', 'Autor')}</p>
                <p class="text-brand/80 text-sm tracking-widest uppercase">{p.get('role', 'Cargo')}</p>
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
            <div class="glass-card !rounded-none !bg-brand/10 p-16 animate-in delay-2">
                <h3 class="text-3xl font-bold mb-8 text-brand">{p.get("good_title", "Novo")}</h3>
                <ul class="space-y-6">{gi}</ul>
            </div>
        </div>
        """

    elif layout == "ending":
        content = f"""
        <div class="text-center">
            <h2 class="animate-up delay-1 text-7xl font-black mb-12">{p.get("title", "Vamos ao")} <br><span class="text-brand">{p.get("highlight", "Fim?")}</span></h2>
            <div class="glass-card inline-block text-left animate-in delay-2">
                <p class="text-brand font-bold mb-2">{p.get("contact", "@contato")}</p>
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


def render_html_player(roteiro, tts_config, brand_config):
    if isinstance(roteiro, list): 
        roteiro = {"scenes": roteiro}
        
    audio_clips = []
    slides_html = ""
    durations = []
    progress = st.progress(0)
    
    scenes = roteiro.get("scenes", [])
    
    for i, scene in enumerate(scenes):
        st.write(f"🎙️ A processar Cena {i+1}/{len(scenes)}...")
        path = f"temp_files/audio_{i}.mp3"
        gen_audio_sync(scene.get("narration_text", "Texto não encontrado"), path, tts_config)
        
        clip = AudioFileClip(path)
        audio_clips.append(clip)
        
        # 1 Cena = 1 Áudio = 1 Slide
        slides_html += build_luminal_slide(scene, i)
        durations.append(int(clip.duration * 1000))
            
        progress.progress((i+1)/len(scenes))

    st.write("🎬 A compilar Masterclass Luminal...")
    final_audio = concatenate_audioclips(audio_clips)
    final_audio.write_audiofile("temp_files/final.mp3", logger=None)
    
    with open("temp_files/final.mp3", "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')

    html_code = """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Luminal - Master Presentation</title>
        <script src="https://cdn.tailwindcss.com"></script>
        
        <!-- Configuração Dinâmica do Tailwind com a Cor da Marca -->
        <script>
            tailwind.config = {
                theme: {
                    extend: {
                        colors: {
                            brand: '[[BRAND_COLOR]]',
                        }
                    }
                }
            }
        </script>

        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: [[BRAND_COLOR]];
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

            .slide.active { opacity: 1; visibility: visible; }
            .bg-container { position: absolute; inset: 0; z-index: -1; overflow: hidden; }
            .bg-container img { width: 100%; height: 100%; object-fit: cover; filter: blur(25px) brightness(0.4); transform: scale(1.1); transition: transform 12s linear; }
            .active .bg-container img { transform: scale(1.3); }

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

            .delay-1 { transition-delay: 0.2s; } .delay-2 { transition-delay: 0.5s; } .delay-3 { transition-delay: 0.8s; }
            .delay-4 { transition-delay: 1.1s; } .delay-5 { transition-delay: 1.4s; } .delay-6 { transition-delay: 1.7s; }

            .progress-bar-container { position: fixed; top: 0; left: 0; width: 100%; height: 4px; background: rgba(255,255,255,0.05); z-index: 100; }
            #progress-fill { height: 100%; background: linear-gradient(90deg, var(--primary), #ffffff); width: 0%; transition: width 0.3s linear; box-shadow: 0 0 10px var(--primary); }

            .overlay-screen { position: fixed; inset: 0; z-index: 999; background: #020617; display: flex; align-items: center; justify-content: center; }
            .overlay-screen.blur-bg { background: rgba(2, 6, 23, 0.85); backdrop-filter: blur(15px); }
        </style>
    </head>
    <body>

        <!-- Ecrã de Início -->
        <div id="start-overlay" class="overlay-screen">
            <button onclick="startPresentation()" class="px-16 py-8 bg-brand text-black font-black rounded-full hover:scale-105 transition-all text-2xl shadow-[0_0_50px_var(--primary)]">
                INICIAR APRESENTAÇÃO
            </button>
        </div>

        <!-- Ecrã de Replay (Escondido no início) -->
        <div id="replay-overlay" class="overlay-screen blur-bg" style="display: none;">
            <div class="text-center">
                <h2 class="text-5xl font-black mb-10 text-white">Apresentação Concluída</h2>
                <button onclick="replayPresentation()" class="px-12 py-6 bg-brand text-black font-black rounded-full hover:scale-105 transition-all text-xl shadow-[0_0_30px_var(--primary)]">
                    🔄 REPLAY
                </button>
            </div>
        </div>

        <div class="progress-bar-container"><div id="progress-fill"></div></div>

        <!-- Header Dinâmico com Logo e Textos Personalizados -->
        <header class="fixed top-10 left-10 z-50 flex items-center gap-6">
            [[LOGO_HTML]]
            <div>
                <div class="text-[10px] font-bold tracking-[0.5em] uppercase opacity-40">[[HEADER_TOP]]</div>
                <div class="text-sm font-medium text-brand">[[HEADER_BOTTOM]]</div>
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
            let animationFrameId;

            function startPresentation() {
                document.getElementById('start-overlay').style.display = 'none';
                audio.play();
                update();
            }

            function replayPresentation() {
                document.getElementById('replay-overlay').style.display = 'none';
                audio.currentTime = 0;
                currentSlide = -1; // Reset 
                audio.play();
                update();
            }

            function update() {
                const now = audio.currentTime * 1000;
                let acc = 0;
                let target = 0;
                let globalDuration = durations.reduce((a,b)=>a+b,0);
                
                progressFill.style.width = `${(now / globalDuration) * 100}%`;

                for(let i=0; i<durations.length; i++) {
                    const start = acc;
                    const end = acc + durations[i];
                    if (now >= start && now < end) {
                        target = i;
                        break;
                    }
                    if (now >= end && i === durations.length - 1) {
                        target = i; 
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

                if (audio.ended) {
                    document.getElementById('replay-overlay').style.display = 'flex';
                    return; // Para o loop de animação
                } else {
                    animationFrameId = requestAnimationFrame(update);
                }
            }
        </script>
    </body>
    </html>
    """
    
    final_html = html_code.replace("[[AUDIO]]", audio_b64) \
                          .replace("[[SLIDES]]", slides_html) \
                          .replace("[[DURS]]", json.dumps(durations)) \
                          .replace("[[BRAND_COLOR]]", brand_config["color"]) \
                          .replace("[[LOGO_HTML]]", brand_config["logo"]) \
                          .replace("[[HEADER_TOP]]", brand_config["header_top"]) \
                          .replace("[[HEADER_BOTTOM]]", brand_config["header_bottom"])
                          
    components.html(final_html, height=850, scrolling=False)


# ==========================================
# MOTOR 2: RENDERIZADOR MP4 (Clássico/Simples)
# ==========================================
def render_mp4_video(roteiro, tts_config):
    st.info("⚙️ A iniciar renderização MP4 (Pillow + MoviePy)...")
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
        
        base = ColorClip(size=(1280, 720), color=(15, 23, 42), duration=audio.duration).set_audio(audio)
        
        txt = scene.get("narration_text", "")[:60] + "..."
        img = Image.new('RGBA', (1280, 720), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((100, 300), txt, fill="white", font=font)
        
        txt_clip = ImageClip(np.array(img)).set_duration(audio.duration).set_position('center')
        clips.append(CompositeVideoClip([base, txt_clip]))
        progress.progress((i+1)/len(scenes))
        
    st.write("✂️ A unificar MP4...")
    final_v = concatenate_videoclips(clips, method="compose")
    final_v.write_videofile("temp_files/output.mp4", fps=24, codec="libx264", logger=None)
    st.success("✅ MP4 Pronto!")
    st.video("temp_files/output.mp4")

# ==========================================
# UI STREAMLIT
# ==========================================
st.set_page_config(page_title="Luminal Master IA", layout="wide")

with st.sidebar:
    st.title("Settings")
    modo = st.radio("Modo de Saída:", ["1️⃣ Web Player (Luminal HTML5 Max)", "2️⃣ Gerar Arquivo .MP4"])
    
    st.divider()
    st.markdown("### 🎨 Identidade Visual")
    
    # Textos do Header
    header_top = st.text_input("Texto Superior", "Pitch Deck Elite")
    header_bottom = st.text_input("Texto Inferior", "Luminal AI Engine")
    
    brand_color = st.color_picker("Cor de Destaque", "#8ef736")
    logo_file = st.file_uploader("Upload da Logo (PNG/JPG)", type=["png", "jpg", "jpeg", "svg"])
    
    if logo_file:
        # getvalue() impede que o arquivo venha vazio se for lido duas vezes
        logo_b64 = base64.b64encode(logo_file.getvalue()).decode("utf-8")
        logo_mime = logo_file.type
        logo_html = f'<img src="data:{logo_mime};base64,{logo_b64}" class="h-12 w-auto object-contain">'
    else:
        # Logo padrão com a cor selecionada
        logo_html = f'<div class="w-12 h-12 rounded-2xl flex items-center justify-center font-black text-2xl shadow-lg text-black" style="background-color: {brand_color};">L</div>'
    
    brand_config = {
        "color": brand_color, 
        "logo": logo_html,
        "header_top": header_top,
        "header_bottom": header_bottom
    }
    
    st.divider()
    tts = st.radio("Voz:", ["Edge-TTS (Free)", "ElevenLabs (Premium)"])
    eleven_key = st.secrets.get("ELEVENLABS_API_KEY", "") if "ElevenLabs" in tts else ""
    v_id = st.text_input("Voice ID", "JBFqnCBsd6RMkjVDRZzb") if "ElevenLabs" in tts else ""
    tts_conf = {"provider": tts, "api_key": eleven_key, "voice_id": v_id}


st.title("🎬 Luminal Master Editor")
tema = st.text_area("Tema da Apresentação:", "Sustentabilidade e Inovação 2030")

if st.button("🧠 1. Gerar Roteiro Mágico (Gemini)", use_container_width=True):
    with st.spinner("A ligar ao Gemini..."):
        res = generate_script_with_gemini(tema)
        if res: 
            st.session_state['script'] = res
            st.success("Roteiro Criado!")

if 'script' in st.session_state:
    with st.expander("✅ JSON Gerado", expanded=True):
        st.code(st.session_state['script'], language="json")

st.divider()

# JSON padrão ajustado para a nova estrutura (1 Cena = 1 Áudio = 1 Layout)
DEFAULT_JSON = {
  "project_name": "Projeto_Hibrido_TURBO",
  "scenes": [
    {
      "narration_text": "Bem-vindo ao novo formato turbo. Oito segundos de áudio, direto ao ponto.",
      "layout": "hero",
      "kicker": "SISTEMA ATUALIZADO",
      "title": "LUMINAL",
      "highlight": "TURBO",
      "subtitle": "1 Cena = 1 Áudio = 1 Slide.",
      "image_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1200"
    }
  ]
}

if os.path.exists("ia_educacao_premium.json"):
    with open("ia_educacao_premium.json", "r", encoding="utf-8") as f:
        default_val = f.read()
else:
    default_val = json.dumps(DEFAULT_JSON, indent=2, ensure_ascii=False)

final_json = st.text_area("Roteiro Final (Cole o JSON aqui):", value=default_val, height=300)

if st.button("🚀 2. Renderizar Projeto", type="primary", use_container_width=True):
    cleanup_temp()
    try:
        data = json.loads(final_json)
        if "1️⃣" in modo: 
            render_html_player(data, tts_conf, brand_config)
        else: 
            render_mp4_video(data, tts_conf)
    except Exception as e: 
        st.error(f"Erro ao ler JSON: {e}")
