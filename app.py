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
    - "hero": {{"narration_text": "...", "layout": "hero", "image_url": "url_do_unsplash", "kicker": "CATEGORIA", "title": "TÍTULO IMPACTANTE", "highlight": "DESTAQUE NEON", "subtitle": "Subtítulo instigante"}}
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
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Erro no Gemini: {e}")
        return None

# ==========================================
# MOTOR DE VOZ
# ==========================================
def gen_audio_sync(text, filepath, tts_config):
    provider = tts_config.get("provider", "Edge-TTS")
    # Adicionando um pequeno espaço extra para evitar cortes no final
    text_with_buffer = text + " . . ." 
    
    if "ElevenLabs" in provider:
        try:
            from elevenlabs.client import ElevenLabs
            api_key = st.secrets.get("ELEVENLABS_API_KEY", "")
            voice_id = tts_config.get("voice_id", "JBFqnCBsd6RMkjVDRZzb")
            client = ElevenLabs(api_key=api_key)
            audio_generator = client.text_to_speech.convert(
                text=text_with_buffer, voice_id=voice_id, model_id="eleven_multilingual_v2", output_format="mp3_44100_128"
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
        asyncio.run(_edge_gen(text_with_buffer, filepath))

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

def render_html_player(scenes, tts_config, brand_config):
    audio_clips = []
    slides_html = ""
    durations = []
    progress = st.progress(0)
    
    for i, scene in enumerate(scenes):
        st.write(f"🎙️ A processar Cena {i+1}/{len(scenes)}...")
        path = f"temp_files/audio_{i}.mp3"
        gen_audio_sync(scene.get("narration_text", "Texto não encontrado"), path, tts_config)
        
        clip = AudioFileClip(path)
        audio_clips.append(clip)
        
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
        <div id="start-overlay" class="overlay-screen">
            <button onclick="startPresentation()" class="px-16 py-8 bg-brand text-black font-black rounded-full hover:scale-105 transition-all text-2xl shadow-[0_0_50px_var(--primary)]">
                INICIAR APRESENTAÇÃO
            </button>
        </div>
        <div id="replay-overlay" class="overlay-screen blur-bg" style="display: none;">
            <div class="text-center">
                <h2 class="text-5xl font-black mb-10 text-white">Apresentação Concluída</h2>
                <button onclick="replayPresentation()" class="px-12 py-6 bg-brand text-black font-black rounded-full hover:scale-105 transition-all text-xl shadow-[0_0_30px_var(--primary)]">
                    🔄 REPLAY
                </button>
            </div>
        </div>
        <div class="progress-bar-container"><div id="progress-fill"></div></div>
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
                currentSlide = -1;
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
                    if (now >= start && now < end) { target = i; break; }
                    if (now >= end && i === durations.length - 1) { target = i; }
                    acc = end;
                }
                if (target !== currentSlide) {
                    if(currentSlide >= 0 && slides[currentSlide]) { slides[currentSlide].classList.remove('active'); }
                    currentSlide = target;
                    if(slides[currentSlide]) { slides[currentSlide].classList.add('active'); }
                }
                if (audio.ended) {
                    document.getElementById('replay-overlay').style.display = 'flex';
                    return; 
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
def render_mp4_video(scenes, tts_config):
    st.info("⚙️ A iniciar renderização MP4 (Pillow + MoviePy)...")
    clips = []
    
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
# MOTOR DA SUPER AULA (COMPILADOR HTML/JS)
# ==========================================
def render_super_aula_html(course_data, tts_config, brand_config):
    js_course_data = []
    html_layers = ""
    
    st.write("⚙️ A pré-compilar Inteligência da Aula (Isso leva uns segundos)...")
    progress = st.progress(0)
    
    # 1. Pré-gerar áudios padrão (Feedback)
    cleanup_temp()
    
    success_path = "temp_files/sa_success.mp3"
    gen_audio_sync("Exatamente! Você pegou a visão perfeitamente. Vamos avançar para o próximo nível.", success_path, tts_config)
    with open(success_path, "rb") as f:
        success_b64 = "data:audio/mp3;base64," + base64.b64encode(f.read()).decode('utf-8')

    error_b64s = []
    erros = [
        "Ops, não é bem por aí. Pensa um pouquinho mais na explicação que eu dei.",
        "Quase, mas a lógica falhou. Tente novamente.",
        "Acho que você piscou na hora da explicação. Foca aqui e tenta de novo."
    ]
    for idx, err in enumerate(erros):
        epath = f"temp_files/sa_err_{idx}.mp3"
        gen_audio_sync(err, epath, tts_config)
        with open(epath, "rb") as f:
            error_b64s.append("data:audio/mp3;base64," + base64.b64encode(f.read()).decode('utf-8'))

    end_path = "temp_files/sa_end.mp3"
    gen_audio_sync("Parabéns, guerreiro! Você concluiu a masterclass com excelência. O diploma é seu.", end_path, tts_config)
    with open(end_path, "rb") as f:
        end_b64 = "data:audio/mp3;base64," + base64.b64encode(f.read()).decode('utf-8')

    # 2. Processar a Trilha da Aula
    total_global_slides = 0
    total_steps = len(course_data)
    
    for step_idx, block in enumerate(course_data):
        st.write(f"🎙️ A processar Bloco {step_idx+1}/{total_steps}...")
        
        if block["type"] == "video":
            audio_clips = []
            durations = []
            slides_html = ""

            for s_idx, scene in enumerate(block["scenes"]):
                path = f"temp_files/sa_vid_{step_idx}_{s_idx}.mp3"
                gen_audio_sync(scene.get("narration_text", ""), path, tts_config)
                clip = AudioFileClip(path)
                audio_clips.append(clip)

                slides_html += build_luminal_slide(scene, total_global_slides)
                durations.append(int(clip.duration * 1000))
                total_global_slides += 1

            # Concatena o áudio DESSA cena de vídeo
            final_audio = concatenate_audioclips(audio_clips)
            block_audio_path = f"temp_files/sa_vid_final_{step_idx}.mp3"
            final_audio.write_audiofile(block_audio_path, logger=None)
            with open(block_audio_path, "rb") as f:
                block_audio_b64 = "data:audio/mp3;base64," + base64.b64encode(f.read()).decode('utf-8')

            js_course_data.append({
                "type": "video",
                "layer_id": f"layer_{step_idx}",
                "audio_src": block_audio_b64,
                "durations": durations
            })

            # Envelopa os slides num layer invisível
            html_layers += f'<div id="layer_{step_idx}" class="video-layer" style="display:none; position:absolute; inset:0;">{slides_html}</div>'

        elif block["type"] == "quiz":
            js_course_data.append({
                "type": "quiz",
                "question": block["question"],
                "options": block["options"],
                "answer_idx": block["options"].index(block["answer"]),
                "audio_success": success_b64,
                "audio_errors": error_b64s
            })
            
        progress.progress((step_idx + 1) / total_steps)

    # 3. Montar o Super HTML Monolítico
    html_code = """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Luminal - Super Aula</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script>tailwind.config = { theme: { extend: { colors: { brand: '[[BRAND_COLOR]]' } } } }</script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root { --primary: [[BRAND_COLOR]]; --bg-dark: #020617; }
            body { font-family: 'Inter', sans-serif; overflow: hidden; background: var(--bg-dark); color: white; margin: 0; }
            
            .slide { position: absolute; inset: 0; opacity: 0; visibility: hidden; transition: opacity 1.2s cubic-bezier(0.4, 0, 0.2, 1), visibility 1.2s; display: flex; align-items: center; justify-content: center; padding: 2rem; }
            .slide.active { opacity: 1; visibility: visible; }
            .bg-container { position: absolute; inset: 0; z-index: -1; overflow: hidden; }
            .bg-container img { width: 100%; height: 100%; object-fit: cover; filter: blur(25px) brightness(0.4); transform: scale(1.1); transition: transform 12s linear; }
            .active .bg-container img { transform: scale(1.3); }

            .glass-card { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 32px; padding: 3rem; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); transition: all 0.5s ease; }
            
            .animate-up { transform: translateY(50px); opacity: 0; transition: all 1.2s cubic-bezier(0.22, 1, 0.36, 1); }
            .animate-in { transform: scale(0.9); opacity: 0; transition: all 1.2s cubic-bezier(0.22, 1, 0.36, 1); }
            .active .animate-up, .active .animate-in { transform: translateY(0) scale(1); opacity: 1; }

            .delay-1 { transition-delay: 0.2s; } .delay-2 { transition-delay: 0.5s; } .delay-3 { transition-delay: 0.8s; }
            .delay-4 { transition-delay: 1.1s; } .delay-5 { transition-delay: 1.4s; } .delay-6 { transition-delay: 1.7s; }

            #progress-fill { position: fixed; top: 0; left: 0; height: 4px; background: linear-gradient(90deg, var(--primary), #ffffff); width: 0%; transition: width 0.3s linear; box-shadow: 0 0 10px var(--primary); z-index: 100; }
            
            .overlay-screen { position: fixed; inset: 0; z-index: 999; background: #020617; display: flex; align-items: center; justify-content: center; flex-direction: column;}
            .blur-bg { background: rgba(2, 6, 23, 0.85); backdrop-filter: blur(20px); }
            
            .quiz-btn { border: 1px solid rgba(255,255,255,0.1); cursor: pointer; }
            .quiz-btn:hover:not(:disabled) { border-color: var(--primary); background: rgba(255,255,255,0.1); }
            .quiz-btn:disabled { cursor: not-allowed; opacity: 0.6; }
        </style>
    </head>
    <body>

        <!-- OVERLAYS -->
        <div id="start-overlay" class="overlay-screen">
            <button onclick="startCourse()" class="px-16 py-8 bg-brand text-black font-black rounded-full hover:scale-105 transition-all text-2xl shadow-[0_0_50px_var(--primary)]">
                INICIAR SUPER AULA
            </button>
        </div>

        <div id="end-overlay" class="overlay-screen blur-bg" style="display: none;">
            <h2 class="text-6xl font-black mb-6 text-white text-center">Masterclass Concluída!</h2>
            <p class="text-2xl text-gray-400 mb-12">O seu diploma de conhecimento foi validado.</p>
            <button onclick="replayCourse()" class="px-12 py-6 bg-brand text-black font-black rounded-full hover:scale-105 transition-all text-xl shadow-[0_0_30px_var(--primary)]">
                🔄 REINICIAR EXPERIÊNCIA
            </button>
        </div>

        <div id="quiz-overlay" class="overlay-screen blur-bg" style="display: none;">
            <div class="max-w-4xl w-full px-8">
                <div class="inline-block px-4 py-1 rounded-full bg-brand/20 border border-brand/30 text-brand text-xs font-black tracking-widest uppercase mb-6">
                    ⚡ DESAFIO DE CONHECIMENTO
                </div>
                <h2 id="quiz-question" class="text-4xl md:text-5xl font-black mb-10 leading-tight">Pergunta...</h2>
                <div id="quiz-options" class="space-y-4"></div>
            </div>
        </div>

        <div id="progress-fill"></div>

        <!-- HEADER -->
        <header class="fixed top-10 left-10 z-50 flex items-center gap-6">
            [[LOGO_HTML]]
            <div>
                <div class="text-[10px] font-bold tracking-[0.5em] uppercase opacity-40">[[HEADER_TOP]]</div>
                <div class="text-sm font-medium text-brand">[[HEADER_BOTTOM]]</div>
            </div>
        </header>

        <!-- AUDIO MASTER -->
        <audio id="main-audio"></audio>
        
        <!-- VIDEO LAYERS -->
        <main id="video-container" class="relative h-screen w-full overflow-hidden">
            [[HTML_LAYERS]]
        </main>

        <script>
            const courseData = [[JS_COURSE_DATA]];
            const endAudioSrc = "[[END_AUDIO_B64]]";
            const audio = document.getElementById('main-audio');
            let currentStep = 0;
            let animationFrameId;

            function startCourse() {
                document.getElementById('start-overlay').style.display = 'none';
                playStep();
            }

            function replayCourse() {
                document.getElementById('end-overlay').style.display = 'none';
                currentStep = 0;
                playStep();
            }

            function playStep() {
                cancelAnimationFrame(animationFrameId); // Para qualquer vídeo rodando

                if(currentStep >= courseData.length) {
                    document.getElementById('end-overlay').style.display = 'flex';
                    audio.src = endAudioSrc;
                    audio.play();
                    return;
                }

                const step = courseData[currentStep];

                if(step.type === 'video') {
                    // Esconde Quiz e outras camadas
                    document.getElementById('quiz-overlay').style.display = 'none';
                    document.querySelectorAll('.video-layer').forEach(el => el.style.display = 'none');

                    // Mostra o layer atual
                    const layer = document.getElementById(step.layer_id);
                    layer.style.display = 'block';

                    audio.src = step.audio_src;
                    audio.play();

                    runVideoLogic(step, layer);

                    audio.onended = () => {
                        audio.onended = null;
                        currentStep++;
                        playStep();
                    };

                } else if (step.type === 'quiz') {
                    document.getElementById('progress-fill').style.width = '100%';
                    // Esconde os vídeos e mostra o quiz
                    document.querySelectorAll('.video-layer').forEach(el => el.style.display = 'none');
                    showQuiz(step);
                }
            }

            function runVideoLogic(step, layer) {
                const slides = layer.querySelectorAll('.slide');
                let currentSlide = -1;

                function update() {
                    const now = audio.currentTime * 1000;
                    let acc = 0; let target = 0;
                    let globalDuration = step.durations.reduce((a,b)=>a+b,0);
                    
                    document.getElementById('progress-fill').style.width = `${(now / globalDuration) * 100}%`;

                    for(let i=0; i<step.durations.length; i++) {
                        const start = acc;
                        const end = acc + step.durations[i];
                        if (now >= start && now < end) { target = i; break; }
                        if (now >= end && i === step.durations.length - 1) { target = i; }
                        acc = end;
                    }

                    if (target !== currentSlide) {
                        if(currentSlide >= 0 && slides[currentSlide]) slides[currentSlide].classList.remove('active');
                        currentSlide = target;
                        if(slides[currentSlide]) slides[currentSlide].classList.add('active');
                    }

                    animationFrameId = requestAnimationFrame(update);
                }
                update();
            }

            function showQuiz(step) {
                const quizContainer = document.getElementById('quiz-overlay');
                quizContainer.style.display = 'flex';
                document.getElementById('quiz-question').innerText = step.question;

                const optsContainer = document.getElementById('quiz-options');
                optsContainer.innerHTML = '';

                step.options.forEach((opt, idx) => {
                    const btn = document.createElement('button');
                    btn.className = "quiz-btn glass-card w-full text-left p-6 text-xl transition-all flex items-center justify-between";
                    btn.innerHTML = `<span>${opt}</span> <span class="indicator text-2xl"></span>`;
                    btn.onclick = () => handleQuizAnswer(idx, step, btn);
                    optsContainer.appendChild(btn);
                });
            }

            function handleQuizAnswer(idx, step, btnElement) {
                // Desativa botões
                document.querySelectorAll('.quiz-btn').forEach(b => b.disabled = true);
                const indicator = btnElement.querySelector('.indicator');

                if(idx === step.answer_idx) {
                    btnElement.classList.add('bg-green-500/20', 'border-green-400');
                    indicator.innerText = "✅";
                    audio.src = step.audio_success;
                    audio.play();
                    audio.onended = () => {
                        audio.onended = null;
                        currentStep++;
                        playStep();
                    };
                } else {
                    btnElement.classList.add('bg-red-500/20', 'border-red-400');
                    indicator.innerText = "❌";
                    // Toca erro aleatório
                    const randomErr = step.audio_errors[Math.floor(Math.random() * step.audio_errors.length)];
                    audio.src = randomErr;
                    audio.play();
                    audio.onended = () => {
                        audio.onended = null;
                        // Restaura botões
                        document.querySelectorAll('.quiz-btn').forEach(b => b.disabled = false);
                        btnElement.classList.remove('bg-red-500/20', 'border-red-400');
                        indicator.innerText = "";
                    };
                }
            }
        </script>
    </body>
    </html>
    """
    
    final_html = html_code.replace("[[BRAND_COLOR]]", brand_config["color"]) \
                          .replace("[[LOGO_HTML]]", brand_config["logo"]) \
                          .replace("[[HEADER_TOP]]", brand_config["header_top"]) \
                          .replace("[[HEADER_BOTTOM]]", brand_config["header_bottom"]) \
                          .replace("[[HTML_LAYERS]]", html_layers) \
                          .replace("[[END_AUDIO_B64]]", end_b64) \
                          .replace("[[JS_COURSE_DATA]]", json.dumps(js_course_data))
                          
    st.success("✅ Masterclass compilada com sucesso!")
    components.html(final_html, height=900, scrolling=False)


# ==========================================
# UI STREAMLIT (EDITOR VISUAL E SUPER AULA)
# ==========================================
st.set_page_config(page_title="Luminal Master", layout="wide")

with st.sidebar:
    st.title("Settings")
    header_top = st.text_input("Texto Superior", "Masterclass IA")
    header_bottom = st.text_input("Texto Inferior", "Módulo 01")
    brand_color = st.color_picker("Cor de Destaque", "#8ef736")
    logo_file = st.file_uploader("Upload da Logo (PNG/JPG)", type=["png", "jpg", "jpeg", "svg"])
    
    if logo_file:
        logo_b64 = base64.b64encode(logo_file.getvalue()).decode("utf-8")
        logo_mime = logo_file.type
        logo_html = f'<img src="data:{logo_mime};base64,{logo_b64}" class="h-12 w-auto object-contain">'
    else:
        logo_html = f'<div class="w-12 h-12 rounded-2xl flex items-center justify-center font-black text-2xl text-black" style="background-color:{brand_color}">L</div>'
    
    brand_config = {"color": brand_color, "logo": logo_html, "header_top": header_top, "header_bottom": header_bottom}
    
    st.divider()
    modo = st.radio("Modo Saída Editor:", ["1️⃣ HTML5 Max", "2️⃣ MP4 Simples"])
    tts_mode = st.radio("Voz:", ["Edge-TTS (Free)", "ElevenLabs (Premium)"])
    v_id = st.text_input("Voice ID", "JBFqnCBsd6RMkjVDRZzb")
    tts_conf = {"provider": tts_mode, "voice_id": v_id}

# DIVISÃO MÁGICA: ABAS!
tab1, tab2 = st.tabs(["🎬 Ilha de Edição (Criador)", "🎓 Super Aula (Modo Aluno)"])

# ---------------------------------------------------------
# ABA 1: O SEU CÓDIGO ANTIGO FICA TODO AQUI DENTRO
# ---------------------------------------------------------
with tab1:
    st.title("🎬 Masterclass Visual Editor")

    if 'scenes' not in st.session_state:
        st.session_state['scenes'] = []

    tema = st.text_input("O que vamos ensinar hoje?", placeholder="Ex: Fotossíntese, Mercado de Ações...")
    if st.button("🧠 1. Gerar Roteiro Mágico", use_container_width=True):
        with st.spinner("IA criando aula..."):
            res = generate_script_with_gemini(tema)
            if res:
                st.session_state['scenes'] = res['scenes']

    if st.session_state['scenes']:
        st.markdown("### 📝 Linha do Tempo e Conteúdo")
        
        new_scenes = []
        for i, scene in enumerate(st.session_state['scenes']):
            with st.expander(f"Cena {i+1}: {scene.get('layout', 'Slide').upper()}", expanded=False):
                col1, col2 = st.columns([2, 1])
                with col1:
                    narration = st.text_area(f"Falas (Cena {i+1})", value=scene.get('narration_text', ''), key=f"narr_{i}")
                    title = st.text_input(f"Título", value=scene.get('title', ''), key=f"title_{i}")
                    highlight = st.text_input(f"Destaque Neon", value=scene.get('highlight', ''), key=f"high_{i}")
                with col2:
                    layout = st.selectbox("Layout", ["hero", "pillars", "philosophy", "side_by_side", "metrics", "team", "timeline", "features_grid", "quote", "compare", "title_only", "ending"], index=0, key=f"lay_{i}")
                    img = st.text_input("Imagem URL", value=scene.get('image_url', ''), key=f"img_{i}")
                
                scene['narration_text'] = narration
                scene['title'] = title
                scene['highlight'] = highlight
                scene['layout'] = layout
                scene['image_url'] = img
                new_scenes.append(scene)
        
        st.session_state['scenes'] = new_scenes

        if st.button("➕ Adicionar Nova Cena", use_container_width=True):
            st.session_state['scenes'].append({"layout": "title_only", "narration_text": "Nova fala aqui.", "title": "Novo Slide"})
            st.rerun()

        st.divider()
        if st.button("🚀 2. Renderizar Projeto", type="primary", use_container_width=True):
            cleanup_temp()
            if "1️⃣" in modo:
                render_html_player(st.session_state['scenes'], tts_conf, brand_config)
            else:
                render_mp4_video(st.session_state['scenes'], tts_conf)
    else:
        st.info("Aguardando você digitar um tema e gerar o roteiro...")


# ---------------------------------------------------------
# ABA 2: O NOVO MOTOR DE SUPER AULA INTERATIVA MONOLÍTICO
# ---------------------------------------------------------
with tab2:
    st.title("🎓 Super Aula: Redes Neurais")
    st.markdown("Uma experiência interativa com vídeo, voz e testes de conhecimento 100% contínua.")
    
    SUPER_AULA = [
        {
            "type": "video",
            "scenes": [
                {"layout": "hero", "image_url": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?q=80&w=1200", "kicker": "Módulo 1", "title": "REDES", "highlight": "NEURAIS", "subtitle": "A base do aprendizado profundo.", "narration_text": "O cérebro humano é a máquina mais eficiente do universo. Quando decidimos criar inteligência artificial de verdade, paramos de programar regras fixas e começamos a copiar a biologia."},
                {"layout": "philosophy", "image_url": "https://images.unsplash.com/photo-1507146426996-ef05306b995a?q=80&w=1200", "title": "O Neurônio Digital", "paragraphs": ["Em vez de 'Se A, faça B', criamos nós conectados.", "Eles recebem dados, multiplicam por pesos e disparam respostas."], "narration_text": "A mágica acontece no perceptron, o nosso neurônio digital. Ele pega a informação bruta da imagem ou do texto, joga um peso matemático nela, e decide se a informação deve seguir adiante ou parar ali mesmo."}
            ]
        },
        {
            "type": "quiz",
            "question": "Baseado no vídeo, qual é o princípio fundamental de uma rede neural em vez da programação tradicional?",
            "options": ["Ela usa regras de 'Se A, faça B'.", "Ela usa nós conectados e pesos matemáticos.", "Ela salva dados no disco rígido para consultar depois."],
            "answer": "Ela usa nós conectados e pesos matemáticos."
        },
        {
            "type": "video",
            "scenes": [
                {"layout": "pillars", "image_url": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=1200", "items": [{"emoji": "📥", "title": "Input", "desc": "Recebe os dados brutos."}, {"emoji": "🧠", "title": "Hidden Layers", "desc": "Onde o processamento pesado ocorre."}, {"emoji": "📤", "title": "Output", "desc": "A resposta final da IA."}], "narration_text": "Para uma rede ser profunda, o famoso Deep Learning, ela precisa de camadas ocultas. O dado entra na camada de Input, é mastigado por milhares de neurônios nas Hidden Layers, e cospe o resultado na camada de Output."},
                {"layout": "quote", "image_url": "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=1200", "quote_text": "A profundidade da rede define o nível de abstração que ela consegue entender.", "author": "Geoffrey Hinton", "role": "Padrinho da IA", "narration_text": "É nessas camadas ocultas que o computador aprende a diferença entre um cachorro e um gato, construindo padrões visuais complexos que nenhum humano conseguiria codificar manualmente."}
            ]
        },
        {
            "type": "quiz",
            "question": "Onde ocorre o 'processamento pesado' onde a IA realmente encontra os padrões complexos?",
            "options": ["Na camada de Input (Entrada).", "Na camada de Output (Saída).", "Nas Hidden Layers (Camadas Ocultas)."],
            "answer": "Nas Hidden Layers (Camadas Ocultas)."
        },
        {
            "type": "video",
            "scenes": [
                {"layout": "ending", "image_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1200", "title": "Módulo", "highlight": "Concluído.", "contact": "Você dominou a base.", "website": "Prepare-se para o nível 2.", "narration_text": "Chegamos ao fim da fundação. Você entende agora que não se trata de código escrito, mas de arquitetura de aprendizado. Você está pronto para construir os modelos do amanhã."}
            ]
        }
    ]

    st.info("💡 A aula foi pré-configurada. Clique abaixo para compilar a experiência (Pode levar de 15 a 30 segundos).")
    
    if st.button("🔥 Compilar e Iniciar Super Aula Interativa", type="primary", use_container_width=True):
        render_super_aula_html(SUPER_AULA, tts_conf, brand_config)
