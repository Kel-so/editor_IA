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
# INTEGRAÇÃO GEMINI 3.1 FLASH (Cérebro do Roteiro)
# ==========================================
def generate_script_with_gemini(tema_texto):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        st.error("🚨 Chave do Gemini (GEMINI_API_KEY) não encontrada nos secrets!")
        return None
        
    genai.configure(api_key=api_key)
    
    prompt = f"""
    Atue como um Diretor de Arte e Copywriter de apresentações "Premium Apple-style". 
    Crie um roteiro JSON baseado neste tema: {tema_texto}
    
    REGRAS DE ESTRUTURA:
    1. Crie uma lista de "scenes".
    2. Cada "scene" é um bloco de áudio contínuo de ~20 segundos (cerca de 50-60 palavras) em 'narration_text'.
    3. Dentro de CADA "scene", DEVE haver uma lista 'sub_slides' com 4 a 5 elementos visuais para trocar durante o áudio.
    4. Cada 'sub_slide' PRECISA ter 'image_url' (URL do Unsplash) e um 'layout' escolhido do catálogo abaixo.
    
    CATÁLOGO DE LAYOUTS E SUAS CHAVES OBRIGATÓRIAS (Respeite exatamente estas chaves para cada layout escolhido):
    - "hero": {{"kicker": "TEXTO PEQUENO TOPO", "title": "TITULO GRANDE", "highlight": "TEXTO EM DESTAQUE AZUL", "subtitle": "Descrição embaixo"}}
    - "pillars": {{"items": [{{"emoji": "🛡️", "title": "Segurança", "desc": "Proteção total"}}]}} (Exatamente 3 itens)
    - "philosophy": {{"title": "Nossa Essência", "paragraphs": ["Parágrafo 1", "Parágrafo 2"]}}
    - "side_by_side": {{"side_image": "url_imagem_aqui", "title": "Decisões de Dados", "subtitle": "Intro curta", "list_items": ["Análise", "Dashboards"]}}
    - "metrics": {{"metrics": [{{"value": "98%", "label": "Satisfação", "color": "text-blue-500"}}]}} (Exatamente 4 itens, cores: text-blue-500, text-purple-500, text-emerald-500, text-orange-500)
    - "team": {{"title": "Liderança", "members": [{{"name": "Erik", "role": "CEO", "avatar": "https://i.pravatar.cc/150?u=1"}}]}} (Exatamente 3 items)
    - "timeline": {{"title": "Jornada", "events": [{{"year": "2021", "event": "Fundação", "desc": "Início"}}]}} (Exatamente 4 itens)
    - "features_grid": {{"features": ["API Nativa", "Segurança", "Multi-Cloud", "Suporte", "Design", "Análise"]}} (Exatamente 6 itens)
    - "quote": {{"quote_text": "A frase", "author": "Steve Jobs", "role": "Visão"}}
    - "compare": {{"bad_title": "Cenário Antigo", "bad_items": ["Processos Manuais", "Lento"], "good_title": "Nossa Solução", "good_items": ["Automação IA", "Rápido"]}}
    - "title_only": {{"title": "Nossa Expansão Global"}}
    - "ending": {{"title": "Vamos construir o", "highlight": "Próximo Nível?", "contact": "contato@empresa.com", "website": "www.empresa.com"}}

    Use sua criatividade para misturar os layouts e entregar uma apresentação incrivelmente dinâmica.
    Responda APENAS com o JSON válido.
    """

    try:
        model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        return response.text 
    except Exception as e:
        st.error(f"Falha ao comunicar com o Gemini: {e}")
        return None

# ==========================================
# MOTOR DE VOZ
# ==========================================
def gen_audio_sync(text, filepath, tts_config):
    provider = tts_config.get("provider", "Edge-TTS")
    
    if "ElevenLabs" in provider:
        try:
            from elevenlabs.client import ElevenLabs
        except ImportError:
            st.error("Faltou o pacote 'elevenlabs'. Roda `pip install elevenlabs`.")
            st.stop()
            
        api_key = tts_config.get("api_key")
        voice_id = tts_config.get("voice_id", "JBFqnCBsd6RMkjVDRZzb")
        
        if not api_key:
            st.error("🚨 Chave da API do ElevenLabs (ELEVENLABS_API_KEY) ausente nos Secrets!")
            st.stop()
            
        try:
            client = ElevenLabs(api_key=api_key)
            audio_generator = client.text_to_speech.convert(
                text=text, voice_id=voice_id, model_id="eleven_multilingual_v2", output_format="mp3_44100_128"
            )
            with open(filepath, "wb") as f:
                for chunk in audio_generator:
                    if chunk: f.write(chunk)
        except Exception as e:
            st.error(f"Erro na ElevenLabs: {e}")
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
    layout = sub_slide.get("layout", "title_only")
    img_url = sub_slide.get("image_url", "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2000")
    
    content = ""
    
    if layout == "hero":
        kicker = sub_slide.get("kicker", "Apresentação Estratégica")
        title = sub_slide.get("title", "VISÃO")
        highlight = sub_slide.get("highlight", "2024")
        subtitle = sub_slide.get("subtitle", "Arquitetura de inovação e escalabilidade.")
        content = f"""
        <div class="text-center max-w-5xl">
            <h2 class="animate-up delay-1 text-blue-500 font-bold tracking-[0.6em] uppercase text-xs mb-6">{kicker}</h2>
            <h1 class="animate-up delay-2 text-7xl md:text-9xl font-black mb-10 leading-tight">{title} <br><span class="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-indigo-600">{highlight}</span></h1>
            <p class="animate-up delay-3 text-xl text-gray-400 font-light mb-12 max-w-2xl mx-auto leading-relaxed">{subtitle}</p>
        </div>
        """
        
    elif layout == "pillars":
        items = sub_slide.get("items", [])
        cards = ""
        for i, item in enumerate(items[:3]):
            delay = i + 1
            cards += f"""
            <div class="glass-card animate-up delay-{delay}">
                <div class="text-4xl mb-6">{item.get('emoji', '🔹')}</div>
                <h3 class="text-2xl font-bold mb-4">{item.get('title', 'Pilar')}</h3>
                <p class="text-gray-400 leading-relaxed">{item.get('desc', 'Detalhe')}</p>
            </div>
            """
        content = f'<div class="max-w-7xl w-full grid md:grid-cols-3 gap-12">{cards}</div>'
        
    elif layout == "philosophy":
        title = sub_slide.get("title", "Nossa Essência")
        paragraphs = sub_slide.get("paragraphs", [])
        p_html = "".join([f'<p class="animate-up delay-{i+2}">{p}</p>' for i, p in enumerate(paragraphs)])
        content = f"""
        <div class="max-w-4xl glass-card animate-in delay-1">
            <h2 class="text-5xl font-black mb-10 text-blue-500">{title}</h2>
            <div class="space-y-8 text-gray-300 text-xl leading-relaxed">{p_html}</div>
        </div>
        """
        
    elif layout == "side_by_side":
        side_img = sub_slide.get("side_image", "https://images.unsplash.com/photo-1551288049-bebda4e38f71?q=80&w=1000")
        title = sub_slide.get("title", "Decisões de Dados").replace("\n", "<br>")
        subtitle = sub_slide.get("subtitle", "Transformando ruído em clareza.")
        list_items = sub_slide.get("list_items", [])
        
        colors = ["text-blue-400", "text-emerald-400", "text-purple-400"]
        bg_colors = ["bg-blue-500/20", "bg-emerald-500/20", "bg-purple-500/20"]
        
        li_html = ""
        for i, item in enumerate(list_items):
            c_txt = colors[i % len(colors)]
            c_bg = bg_colors[i % len(bg_colors)]
            li_html += f"""
            <li class="flex items-center gap-4 {c_txt} font-bold">
                <span class="w-8 h-8 {c_bg} rounded-full flex items-center justify-center text-xs text-white">0{i+1}</span>
                {item}
            </li>
            """
            
        content = f"""
        <div class="max-w-7xl w-full grid md:grid-cols-2 gap-20 items-center">
            <div class="animate-in delay-1 rounded-[40px] overflow-hidden h-[600px] shadow-2xl">
                <img src="{side_img}" class="w-full h-full object-cover">
            </div>
            <div class="space-y-8">
                <h2 class="animate-up delay-2 text-6xl font-black leading-tight">{title}</h2>
                <p class="animate-up delay-3 text-gray-400 text-xl">{subtitle}</p>
                <ul class="space-y-6 animate-up delay-4">{li_html}</ul>
            </div>
        </div>
        """
        
    elif layout == "metrics":
        metrics = sub_slide.get("metrics", [])
        m_html = ""
        for i, m in enumerate(metrics[:4]):
            val = m.get("value", "0")
            lbl = m.get("label", "Métrica")
            col = m.get("color", "text-blue-500")
            m_html += f"""
            <div class="glass-card text-center animate-in delay-{i+1}">
                <div class="text-6xl font-black {col} mb-4">{val}</div>
                <div class="text-xs uppercase tracking-widest opacity-40">{lbl}</div>
            </div>
            """
        content = f'<div class="max-w-7xl w-full grid grid-cols-2 md:grid-cols-4 gap-8">{m_html}</div>'

    elif layout == "team":
        title = sub_slide.get("title", "Liderança Executiva")
        members = sub_slide.get("members", [])
        m_html = ""
        for i, m in enumerate(members[:3]):
            name = m.get("name", "Nome")
            role = m.get("role", "Cargo")
            av = m.get("avatar", "https://i.pravatar.cc/150")
            m_html += f"""
            <div class="glass-card text-center animate-up delay-{i+2}">
                <div class="w-32 h-32 rounded-full mx-auto mb-8 border-4 border-blue-500/30 overflow-hidden">
                    <img src="{av}" alt="{name}">
                </div>
                <h4 class="text-2xl font-bold">{name}</h4>
                <p class="text-blue-400">{role}</p>
            </div>
            """
        content = f"""
        <div class="max-w-6xl w-full">
            <h2 class="text-center text-4xl font-bold mb-16 animate-up delay-1">{title}</h2>
            <div class="grid md:grid-cols-3 gap-12">{m_html}</div>
        </div>
        """

    elif layout == "timeline":
        title = sub_slide.get("title", "Nossa Jornada")
        events = sub_slide.get("events", [])
        e_html = ""
        for i, e in enumerate(events[:4]):
            yr = e.get("year", "2024")
            ev = e.get("event", "Evento")
            desc = e.get("desc", "Descrição")
            e_html += f"""
            <div class="glass-card animate-in delay-{i+2}">
                <div class="text-blue-500 font-bold text-sm mb-2">{yr}</div>
                <h5 class="font-bold">{ev}</h5>
                <p class="text-xs text-gray-500 mt-4">{desc}</p>
            </div>
            """
        content = f"""
        <div class="max-w-6xl w-full">
            <h2 class="text-4xl font-bold mb-16 animate-up delay-1">{title}</h2>
            <div class="grid md:grid-cols-4 gap-6">{e_html}</div>
        </div>
        """

    elif layout == "features_grid":
        feats = sub_slide.get("features", [])
        f_html = "".join([f'<div class="glass-card animate-up delay-{i+1}">{f}</div>' for i, f in enumerate(feats[:6])])
        content = f'<div class="max-w-7xl w-full grid grid-cols-2 md:grid-cols-3 gap-8">{f_html}</div>'

    elif layout == "quote":
        quote = sub_slide.get("quote_text", "Inovação nos move.")
        author = sub_slide.get("author", "Visionário")
        role = sub_slide.get("role", "Líder")
        content = f"""
        <div class="max-w-5xl text-center">
            <span class="text-8xl text-blue-500 font-serif animate-up delay-1">“</span>
            <h2 class="text-5xl font-light italic animate-up delay-2 leading-relaxed">{quote}</h2>
            <div class="mt-12 animate-up delay-3">
                <p class="text-2xl font-bold">{author}</p>
                <p class="text-blue-400 text-sm tracking-widest uppercase">{role}</p>
            </div>
        </div>
        """

    elif layout == "compare":
        bt = sub_slide.get("bad_title", "Cenário Antigo")
        bi = sub_slide.get("bad_items", [])
        gt = sub_slide.get("good_title", "Solução Luminal")
        gi = sub_slide.get("good_items", [])
        
        b_html = "".join([f"<li>✕ {b}</li>" for b in bi])
        g_html = "".join([f"<li>✓ {g}</li>" for g in gi])
        
        content = f"""
        <div class="max-w-6xl w-full grid md:grid-cols-2 gap-px bg-white/5 rounded-[40px] overflow-hidden border border-white/10">
            <div class="glass-card !rounded-none !bg-red-500/5 p-16 animate-in delay-1">
                <h3 class="text-3xl font-bold mb-8 text-red-400">{bt}</h3>
                <ul class="space-y-6 opacity-60">{b_html}</ul>
            </div>
            <div class="glass-card !rounded-none !bg-emerald-500/5 p-16 animate-in delay-2">
                <h3 class="text-3xl font-bold mb-8 text-emerald-400">{gt}</h3>
                <ul class="space-y-6">{g_html}</ul>
            </div>
        </div>
        """

    elif layout == "ending":
        title = sub_slide.get("title", "Vamos construir o")
        highlight = sub_slide.get("highlight", "Próximo Nível?")
        contact = sub_slide.get("contact", "contato@email.com")
        website = sub_slide.get("website", "www.site.com")
        content = f"""
        <div class="text-center">
            <h2 class="animate-up delay-1 text-7xl font-black mb-12">{title} <br><span class="text-blue-500">{highlight}</span></h2>
            <div class="glass-card inline-block text-left animate-in delay-2">
                <p class="text-blue-400 font-bold mb-2">{contact}</p>
                <p class="text-gray-400">{website}</p>
            </div>
        </div>
        """

    else: # title_only
        title = sub_slide.get("title", "Título Principal")
        content = f'<h2 class="text-6xl text-center font-black animate-up delay-1">{title}</h2>'

    return f"""
    <section class="slide" data-index="{total_index}">
        <div class="bg-container"><img src="{img_url}" alt="bg"></div>
        {content}
    </section>
    """


def render_html_player(roteiro, tts_config):
    audio_clips = []
    slides_html = ""
    durations_array = []
    
    progress_bar = st.progress(0)
    total_scenes = len(roteiro["scenes"])
    
    total_sub_slides_count = 0
    
    for idx, scene in enumerate(roteiro["scenes"]):
        st.write(f"🎙️ Processando áudio e cena {idx+1}...")
        
        audio_path = f"temp_files/audio_{idx}.mp3"
        gen_audio_sync(scene["narration_text"], audio_path, tts_config)
        clip = AudioFileClip(audio_path)
        audio_clips.append(clip)
        
        sub_slides = scene.get("sub_slides", [])
        if not sub_slides: continue
        
        time_per_slide = (clip.duration * 1000) / len(sub_slides)
        
        for sub in sub_slides:
            slides_html += build_luminal_slide(sub, total_sub_slides_count)
            durations_array.append(int(time_per_slide))
            total_sub_slides_count += 1
            
        progress_bar.progress((idx + 1) / total_scenes)

    st.write("🎬 Gerando Masterclass Interativa...")
    final_audio = concatenate_audioclips(audio_clips)
    final_audio_path = "temp_files/final_audio.mp3"
    final_audio.write_audiofile(final_audio_path, logger=None)
    
    with open(final_audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')
        
    js_durations = json.dumps(durations_array)

    html_template = """
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <title>Luminal - Master Presentation</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root { --primary: #3b82f6; --bg-dark: #020617; }
            body { font-family: 'Inter', sans-serif; overflow: hidden; background: var(--bg-dark); color: white; margin: 0; }
            
            .slide { position: absolute; inset: 0; opacity: 0; visibility: hidden; transition: opacity 1.2s cubic-bezier(0.4, 0, 0.2, 1), visibility 1.2s; display: flex; align-items: center; justify-content: center; padding: 2rem; }
            .slide.active { opacity: 1; visibility: visible; }
            
            .bg-container { position: absolute; inset: 0; z-index: -1; overflow: hidden; }
            .bg-container img { width: 100%; height: 100%; object-fit: cover; filter: blur(25px) brightness(0.4); transform: scale(1.1); transition: transform 12s linear; }
            .active .bg-container img { transform: scale(1.3); }
            
            .glass-card { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 32px; padding: 3rem; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); }
            
            .animate-up { transform: translateY(50px); opacity: 0; transition: all 1.2s cubic-bezier(0.22, 1, 0.36, 1); }
            .animate-in { transform: scale(0.9); opacity: 0; transition: all 1.2s cubic-bezier(0.22, 1, 0.36, 1); }
            .active .animate-up, .active .animate-in { transform: translateY(0) scale(1); opacity: 1; }
            
            .delay-1 { transition-delay: 0.2s; }
            .delay-2 { transition-delay: 0.5s; }
            .delay-3 { transition-delay: 0.8s; }
            .delay-4 { transition-delay: 1.1s; }
            .delay-5 { transition-delay: 1.4s; }
            .delay-6 { transition-delay: 1.7s; }
            
            .progress-bar-container { position: fixed; top: 0; left: 0; width: 100%; height: 4px; background: rgba(255,255,255,0.05); z-index: 100; }
            #progress-fill { height: 100%; background: linear-gradient(90deg, #3b82f6, #6366f1); width: 0%; transition: width 0.1s linear; }
            
            #overlay { position: absolute; inset: 0; z-index: 999; background: #020617; display: flex; align-items: center; justify-content: center; }
        </style>
    </head>
    <body>
        <div id="overlay">
            <button id="play-btn" class="px-16 py-8 bg-blue-600 text-white font-black rounded-full hover:scale-105 transition-all text-2xl shadow-[0_0_50px_rgba(59,130,246,0.5)]">
                INICIAR APRESENTAÇÃO
            </button>
        </div>

        <div class="progress-bar-container"><div id="progress-fill"></div></div>
        
        <header class="fixed top-10 left-10 z-50 flex items-center gap-6">
            <div class="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center font-black text-2xl shadow-lg">L</div>
            <div>
                <div class="text-[10px] font-bold tracking-[0.5em] uppercase opacity-40">Luminal Auto-Player</div>
            </div>
        </header>

        <audio id="audio" src="data:audio/mp3;base64,[[AUDIO_B64]]"></audio>
        
        <main class="relative h-screen w-full overflow-hidden" id="slides-container">
            [[SLIDES_HTML]]
        </main>

        <script>
            const audio = document.getElementById('audio');
            const slides = document.querySelectorAll('.slide');
            const progressFill = document.getElementById('progress-fill');
            const durations = [[DURATIONS_JS]];
            let currentSlide = -1;

            document.getElementById('play-btn').onclick = () => {
                document.getElementById('overlay').style.opacity = '0';
                setTimeout(() => document.getElementById('overlay').style.display = 'none', 500);
                audio.play();
                update();
            };

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
                    if(currentSlide >= 0 && slides[currentSlide]) slides[currentSlide].classList.remove('active');
                    currentSlide = target;
                    if(slides[currentSlide]) slides[currentSlide].classList.add('active');
                }

                if (!audio.ended) requestAnimationFrame(update);
            }
        </script>
    </body>
    </html>
    """
    
    html_final = html_template.replace("[[AUDIO_B64]]", audio_b64).replace("[[SLIDES_HTML]]", slides_html).replace("[[DURATIONS_JS]]", js_durations)
    components.html(html_final, height=850, scrolling=False)


# ==========================================
# UI STREAMLIT PRINCIPAL
# ==========================================
st.set_page_config(page_title="Luminal Master IA", layout="wide")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4370/4370757.png", width=60)
    st.title("Settings")
    
    modo_render = st.radio("Modo de Saída:", ["1️⃣ Web Player (Luminal HTML5 Max)"])
    
    st.divider()
    tts_provider = st.radio("Voz:", ["Edge-TTS (Free)", "ElevenLabs (Premium)"])
    eleven_key = st.secrets.get("ELEVENLABS_API_KEY", "") if "ElevenLabs" in tts_provider else ""
    eleven_voice = st.text_input("Voice ID", "JBFqnCBsd6RMkjVDRZzb") if "ElevenLabs" in tts_provider else ""
    
    tts_config = {"provider": tts_provider, "api_key": eleven_key, "voice_id": eleven_voice}

st.title("✨ Criação Luminal MAX com Gemini")
st.markdown("Deixe o Gemini mastigar o texto e criar a estrutura visual com TODOS os 12 layouts para você.")

tema = st.text_area("Sobre o que é a apresentação?", "O impacto da Inteligência Artificial no mercado financeiro global até 2030.")

if st.button("🧠 1. Gerar Roteiro Mágico (Gemini)", use_container_width=True):
    with st.spinner("Conectando ao Gemini 3.1 Flash Lite..."):
        script_json = generate_script_with_gemini(tema)
        if script_json:
            st.session_state['generated_script'] = script_json
            st.success("Roteiro criado com sucesso!")

if 'generated_script' in st.session_state:
    with st.expander("✅ Ver Roteiro Gerado pelo Gemini", expanded=True):
        st.markdown("Copie o código abaixo clicando no ícone no canto superior direito do bloco e cole na caixa de edição final.")
        st.code(st.session_state['generated_script'], language="json")

st.divider()

DEFAULT_JSON = {
  "project_name": "Projeto_Hibrido_MAX",
  "scenes": [
    {
      "narration_text": "Cole aqui o JSON gerado pelo Gemini ou crie o seu próprio usando a estrutura Luminal completa.",
      "sub_slides": [
        {"layout": "hero", "kicker": "SISTEMA ATUALIZADO", "title": "LUMINAL", "highlight": "MAX", "subtitle": "Todos os layouts ativos.", "image_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1200"},
        {"layout": "title_only", "title": "Basta gerar com o Gemini e colar abaixo.", "image_url": "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?q=80&w=1200"}
      ]
    }
  ]
}

if os.path.exists("ia_educacao_premium.json"):
    with open("ia_educacao_premium.json", "r", encoding="utf-8") as f:
        default_val = f.read()
else:
    default_val = json.dumps(DEFAULT_JSON, indent=2, ensure_ascii=False)

st.markdown("### 📝 Roteiro Final")
json_input = st.text_area("Cole aqui o JSON gerado acima para rodar a apresentação:", value=default_val, height=400)

if st.button("🎬 2. Renderizar Apresentação Completa", type="primary", use_container_width=True):
    try:
        roteiro = json.loads(json_input)
    except Exception as e:
        st.error(f"Erro no JSON: {e}")
        st.stop()
        
    cleanup_temp()
    render_html_player(roteiro, tts_config)
