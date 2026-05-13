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
from moviepy.audio.AudioClip import AudioArrayClip

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
        st.error("🚨 Chave do Gemini não encontrada!")
        return None
    
    genai.configure(api_key=api_key)
    prompt = f"""
    Atue como um Diretor de Arte e Copywriter "Premium Apple-style". 
    Crie um roteiro JSON de uma AULA rápida sobre: {tema_texto}
    
    REGRAS CRÍTICAS DE ESTRUTURA JSON:
    1. O JSON DEVE ser um objeto com a chave raiz "scenes". Ex: {{"scenes": [...]}}
    2. NÃO crie listas de 'sub_slides'. A própria "scene" é o slide.
    3. Coloque as propriedades do layout (layout, image_url, title, etc) DIRETAMENTE na raiz da scene, junto com 'narration_text'.
    4. NÃO use a chave "data".
    5. Cada cena deve ter ~8 segundos de narração.

    CATÁLOGO DE LAYOUTS (Use as chaves exatas mostradas aqui dentro de cada scene):
    - "hero": {{"narration_text": "...", "layout": "hero", "image_url": "url_unsplash", "kicker": "CATEGORIA", "title": "TÍTULO IMPACTANTE", "highlight": "DESTAQUE NEON", "subtitle": "Subtítulo"}}
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

    Responda APENAS o JSON puro.
    """
    try:
        model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")
        response = model.generate_content(
            prompt, 
            generation_config=genai.GenerationConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"Erro Gemini: {e}")
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
                text=text_with_buffer, 
                voice_id=voice_id, 
                model_id="eleven_multilingual_v2", 
                output_format="mp3_44100_128"
            )
            with open(filepath, "wb") as f:
                for chunk in audio_generator:
                    if chunk: 
                        f.write(chunk)
        except Exception as e:
            st.error(f"Erro ElevenLabs: {e}")
            st.stop()
    else:
        async def _edge_gen(txt, path):
            tts = edge_tts.Communicate(txt, "pt-BR-AntonioNeural")
            await tts.save(path)
        asyncio.run(_edge_gen(text_with_buffer, filepath))

# ==========================================
# MOTOR VISUAL (CONSTRUTOR DE SLIDES HTML)
# ==========================================
def build_luminal_slide(slide_data, total_index):
    img_url = slide_data.get("image_url", "https://images.unsplash.com/photo-1544465544-1b71aee9dfa3?q=80&w=1200")
    layout = slide_data.get("layout", "title_only")
    p = slide_data.get("data", slide_data)
    
    content = ""
    
    if layout == "hero":
        content = f"""
        <div class="text-center max-w-5xl">
            <h2 class="animate-up delay-1 text-brand font-bold tracking-[0.6em] uppercase text-xs mb-6">
                {p.get('kicker', 'Módulo')}
            </h2>
            <h1 class="animate-up delay-2 text-7xl md:text-9xl font-black mb-10 leading-tight">
                {p.get('title', 'TÍTULO')} <br>
                <span class="text-transparent bg-clip-text bg-gradient-to-r from-brand to-white/50">
                    {p.get('highlight', '')}
                </span>
            </h1>
            <p class="animate-up delay-3 text-xl text-gray-400 font-light max-w-2xl mx-auto">
                {p.get('subtitle', '')}
            </p>
        </div>
        """
    
    elif layout == "pillars":
        cards = ""
        for i, item in enumerate(p.get("items", [])):
            cards += f"""
            <div class="glass-card animate-up delay-{i+1}">
                <div class="text-4xl mb-6">{item.get("emoji", "🔹")}</div>
                <h3 class="text-2xl font-bold mb-4">{item.get("title", "Pilar")}</h3>
                <p class="text-gray-400 text-sm">{item.get("desc", "")}</p>
            </div>
            """
        content = f"""
        <div class="max-w-7xl w-full grid md:grid-cols-3 gap-12">
            {cards}
        </div>
        """
    
    elif layout == "philosophy":
        p_html = ""
        for i, par in enumerate(p.get("paragraphs", [])):
            p_html += f'<p class="animate-up delay-{i+2}">{par}</p>'
            
        content = f"""
        <div class="max-w-4xl glass-card animate-in delay-1">
            <h2 class="text-5xl font-black mb-10 text-brand">{p.get('title', 'Filosofia')}</h2>
            <div class="space-y-8 text-gray-300 text-xl leading-relaxed">
                {p_html}
            </div>
        </div>
        """
    
    elif layout == "side_by_side":
        side_img = p.get("side_image", img_url)
        li_html = ""
        for i, item in enumerate(p.get("list_items", [])):
            li_html += f"""
            <li class="flex items-center gap-4 text-brand font-bold">
                <span class="w-8 h-8 bg-brand/20 rounded-full flex items-center justify-center text-xs text-white">0{i+1}</span>
                {item}
            </li>
            """
            
        content = f"""
        <div class="max-w-7xl w-full grid md:grid-cols-2 gap-20 items-center">
            <div class="animate-in delay-1 rounded-[40px] overflow-hidden h-[600px] shadow-2xl">
                <img src="{side_img}" class="w-full h-full object-cover">
            </div>
            <div class="space-y-8">
                <h2 class="animate-up delay-2 text-6xl font-black leading-tight">
                    {p.get('title', 'Análise').replace(chr(10), '<br>')}
                </h2>
                <p class="animate-up delay-3 text-gray-400 text-xl">{p.get('subtitle', '')}</p>
                <ul class="space-y-6 animate-up delay-4">
                    {li_html}
                </ul>
            </div>
        </div>
        """

    elif layout == "metrics":
        m_html = ""
        for i, m in enumerate(p.get("metrics", [])):
            m_html += f"""
            <div class="glass-card text-center animate-in delay-{i+1}">
                <div class="text-6xl font-black text-brand mb-4">{m.get("value", "0")}</div>
                <div class="text-xs uppercase tracking-widest opacity-40">{m.get("label", "Dado")}</div>
            </div>
            """
        content = f"""
        <div class="max-w-7xl w-full grid grid-cols-2 md:grid-cols-4 gap-8">
            {m_html}
        </div>
        """

    elif layout == "team":
        m_html = ""
        for i, m in enumerate(p.get("members", [])):
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
            <div class="grid md:grid-cols-3 gap-12">
                {m_html}
            </div>
        </div>
        """

    elif layout == "timeline":
        e_html = ""
        for i, e in enumerate(p.get("events", [])):
            e_html += f"""
            <div class="glass-card animate-in delay-{i+2}">
                <div class="text-brand font-bold text-sm mb-2">{e.get("year", "Fase")}</div>
                <h5 class="font-bold">{e.get("event", "Evento")}</h5>
                <p class="text-xs text-gray-500 mt-4">{e.get("desc", "Descrição")}</p>
            </div>
            """
        content = f"""
        <div class="max-w-6xl w-full">
            <h2 class="text-4xl font-bold mb-16 animate-up delay-1">{p.get('title', 'Jornada')}</h2>
            <div class="grid md:grid-cols-4 gap-6">
                {e_html}
            </div>
        </div>
        """

    elif layout == "features_grid":
        f_html = ""
        for i, f in enumerate(p.get("features", [])):
            f_html += f"""
            <div class="glass-card text-center font-bold animate-up delay-{i+1}">
                {f}
            </div>
            """
        content = f"""
        <div class="max-w-7xl w-full grid grid-cols-2 md:grid-cols-3 gap-8">
            {f_html}
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
    
    elif layout == "quote":
        content = f"""
        <div class="max-w-5xl text-center">
            <span class="text-8xl text-brand font-serif animate-up delay-1">“</span>
            <h2 class="text-5xl font-light italic animate-up delay-2 leading-relaxed">{p.get('quote_text', '')}</h2>
            <div class="mt-12 animate-up delay-3">
                <p class="text-2xl font-bold">{p.get('author', '')}</p>
                <p class="text-brand/80 text-sm uppercase">{p.get('role', '')}</p>
            </div>
        </div>
        """
    
    elif layout == "ending":
        content = f"""
        <div class="text-center">
            <h2 class="animate-up delay-1 text-7xl font-black mb-12">
                {p.get("title", "Vamos ao")} <br>
                <span class="text-brand">{p.get("highlight", "Fim?")}</span>
            </h2>
            <div class="glass-card inline-block text-left animate-in delay-2">
                <p class="text-brand font-bold mb-2">{p.get("contact", "@contato")}</p>
                <p class="text-gray-400">{p.get("website", "www.site.com")}</p>
            </div>
        </div>
        """

    else:
        content = f"""
        <h2 class="text-6xl text-center font-black animate-up delay-1">
            {p.get("title", "...")}
        </h2>
        """

    return f"""
    <section class="slide" data-index="{total_index}">
        <div class="bg-container">
            <img src="{img_url}" alt="bg">
        </div>
        {content}
    </section>
    """


# ==========================================
# MOTOR DO EDITOR CLÁSSICO HTML (Aba 1)
# ==========================================
def render_html_player(scenes, tts_config, brand_config):
    audio_clips = []
    slides_html = ""
    durations = []
    progress = st.progress(0)
    
    # Criador de silencio fisico (1 segundo) para evitar cortes
    silence_array = np.zeros((44100, 2))
    silence_clip = AudioArrayClip(silence_array, fps=44100)
    
    for i, scene in enumerate(scenes):
        st.write(f"🎙️ Processando Cena {i+1}/{len(scenes)}...")
        path = f"temp_files/audio_{i}.mp3"
        gen_audio_sync(scene.get("narration_text", "Texto não encontrado"), path, tts_config)
        
        clip = AudioFileClip(path)
        audio_clips.append(clip)
        audio_clips.append(silence_clip) # Injeta 1s de silêncio obrigatório
        
        slides_html += build_luminal_slide(scene, i)
        # O slide dura o tempo do áudio + 1s do silêncio
        durations.append(int(clip.duration * 1000) + 1000) 
            
        progress.progress((i+1)/len(scenes))

    st.write("🎬 Compilando Apresentação...")
    final_audio = concatenate_audioclips(audio_clips)
    final_audio.write_audiofile("temp_files/final_classic.mp3", logger=None)
    
    with open("temp_files/final_classic.mp3", "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode('utf-8')

    html_code = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {{ 
                theme: {{ 
                    extend: {{ 
                        colors: {{ brand: '{brand_config["color"]}' }} 
                    }} 
                }} 
            }}
        </script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {{ 
                --primary: {brand_config["color"]}; 
                --bg-dark: #020617; 
            }}
            body {{ 
                font-family: 'Inter', sans-serif; 
                overflow: hidden; 
                background: var(--bg-dark); 
                color: white; 
                margin: 0; 
            }}
            .slide {{ 
                position: absolute; 
                inset: 0; 
                opacity: 0; 
                visibility: hidden; 
                transition: opacity 0.8s, visibility 0.8s; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                padding: 2rem; 
            }}
            .slide.active {{ 
                opacity: 1; 
                visibility: visible; 
            }}
            .bg-container {{ 
                position: absolute; 
                inset: 0; 
                z-index: -1; 
                overflow: hidden; 
            }}
            .bg-container img {{ 
                width: 100%; 
                height: 100%; 
                object-fit: cover; 
                filter: blur(25px) brightness(0.4); 
                transform: scale(1.1); 
                transition: transform 12s linear; 
            }}
            .active .bg-container img {{ 
                transform: scale(1.3); 
            }}
            .glass-card {{ 
                background: rgba(255, 255, 255, 0.03); 
                backdrop-filter: blur(12px); 
                border: 1px solid rgba(255, 255, 255, 0.08); 
                border-radius: 32px; 
                padding: 3rem; 
            }}
            .animate-up {{ 
                transform: translateY(50px); 
                opacity: 0; 
                transition: all 1s cubic-bezier(0.22, 1, 0.36, 1); 
            }}
            .animate-in {{ 
                transform: scale(0.9); 
                opacity: 0; 
                transition: all 1s cubic-bezier(0.22, 1, 0.36, 1); 
            }}
            .active .animate-up, .active .animate-in {{ 
                transform: translateY(0) scale(1); 
                opacity: 1; 
            }}
            .delay-1 {{ transition-delay: 0.2s; }} 
            .delay-2 {{ transition-delay: 0.5s; }} 
            .delay-3 {{ transition-delay: 0.8s; }} 
            .delay-4 {{ transition-delay: 1.1s; }}
            #progress-fill {{ 
                position: fixed; 
                top: 0; 
                left: 0; 
                height: 4px; 
                background: linear-gradient(90deg, var(--primary), #ffffff); 
                width: 0%; 
                transition: width 0.3s linear; 
                box-shadow: 0 0 10px var(--primary); 
                z-index: 100;
            }}
            .overlay-screen {{ 
                position: fixed; 
                inset: 0; 
                z-index: 999; 
                background: #020617; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
            }}
            .blur-bg {{ 
                background: rgba(2, 6, 23, 0.85); 
                backdrop-filter: blur(15px); 
            }}
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
        
        <div id="progress-fill"></div>
        
        <header class="fixed top-10 left-10 z-50 flex items-center gap-6">
            {brand_config["logo"]}
            <div>
                <div class="text-[10px] font-bold tracking-[0.5em] uppercase opacity-40">{brand_config["header_top"]}</div>
                <div class="text-sm font-medium text-brand">{brand_config["header_bottom"]}</div>
            </div>
        </header>
        
        <audio id="audio" src="data:audio/mp3;base64,{audio_b64}"></audio>
        
        <main class="relative h-screen w-full overflow-hidden">
            {slides_html}
        </main>
        
        <script>
            const audio = document.getElementById('audio');
            const slides = document.querySelectorAll('.slide');
            const durations = {json.dumps(durations)};
            let currentSlide = -1;
            let animationFrameId;

            function playWithFadeIn() {{
                audio.volume = 0; 
                audio.play();
                let vol = 0;
                let fade = setInterval(() => {{
                    if (vol < 0.6) {{ 
                        vol += 0.05; 
                        audio.volume = vol; 
                    }} else {{ 
                        clearInterval(fade); 
                    }}
                }}, 50);
            }}

            function startPresentation() {{ 
                document.getElementById('start-overlay').style.display = 'none'; 
                playWithFadeIn(); 
                update(); 
            }}
            
            function replayPresentation() {{ 
                document.getElementById('replay-overlay').style.display = 'none'; 
                audio.currentTime = 0; 
                currentSlide = -1; 
                playWithFadeIn(); 
                update(); 
            }}
            
            function update() {{
                const now = audio.currentTime * 1000;
                let acc = 0; 
                let target = 0;
                let globalDuration = durations.reduce((a,b)=>a+b,0);
                
                document.getElementById('progress-fill').style.width = `${{(now / globalDuration) * 100}}%`;
                
                for(let i=0; i<durations.length; i++) {{
                    if (now >= acc && now < acc + durations[i]) {{ 
                        target = i; 
                        break; 
                    }}
                    acc += durations[i];
                }}
                
                if (target !== currentSlide) {{
                    if(currentSlide >= 0 && slides[currentSlide]) {{ 
                        slides[currentSlide].classList.remove('active'); 
                    }}
                    currentSlide = target;
                    if(slides[currentSlide]) {{ 
                        slides[currentSlide].classList.add('active'); 
                    }}
                }}
                
                if (audio.ended) {{
                    document.getElementById('replay-overlay').style.display = 'flex';
                }} else {{
                    animationFrameId = requestAnimationFrame(update);
                }}
            }}
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=850, scrolling=False)


# ==========================================
# MOTOR DA SUPER AULA (O MONOLITO DA ABA 2)
# ==========================================
def render_super_aula_html(course_data, tts_config, brand_config):
    js_course_data = []
    html_layers = ""
    st.write("⚙️ Compilando Inteligência da Super Aula...")
    progress = st.progress(0)
    cleanup_temp()

    # Criador de silencio fisico (1 segundo) para evitar cortes entre slides nos blocos de vídeo
    silence_array = np.zeros((44100, 2))
    silence_clip = AudioArrayClip(silence_array, fps=44100)

    # Gerar 10 feedbacks de sucesso
    success_b64s = []
    sucessos = [
        "Exatamente!", "Na mosca!", "Perfeito!", "Cirúrgico.", 
        "Mandou bem!", "Exato!", "Aí sim!", "Sensacional.", 
        "Certíssimo!", "Brilhante!"
    ]
    for idx, suc in enumerate(sucessos):
        p = f"temp_files/sa_s_{idx}.mp3"
        gen_audio_sync(suc, p, tts_config)
        with open(p, "rb") as f: 
            success_b64s.append("data:audio/mp3;base64," + base64.b64encode(f.read()).decode('utf-8'))

    # Gerar 10 feedbacks de erro
    error_b64s = []
    erros = [
        "Ops!", "Quase lá!", "Acho que piscou.", "Escorregou.", 
        "Negativo.", "Não passou nessa.", "Erroooou!", "Longe disso.", 
        "Incorreto.", "Não rolou."
    ]
    for idx, err in enumerate(erros):
        p = f"temp_files/sa_e_{idx}.mp3"
        gen_audio_sync(err, p, tts_config)
        with open(p, "rb") as f: 
            error_b64s.append("data:audio/mp3;base64," + base64.b64encode(f.read()).decode('utf-8'))

    end_p = f"temp_files/sa_final_end.mp3"
    gen_audio_sync("Parabéns guerreiro! Você concluiu a masterclass com excelência. O diploma é seu.", end_p, tts_config)
    with open(end_p, "rb") as f: 
        end_b64 = "data:audio/mp3;base64," + base64.b64encode(f.read()).decode('utf-8')

    total_global_slides = 0
    for idx, block in enumerate(course_data):
        st.write(f"🎙️ Processando Bloco {idx+1}/{len(course_data)}...")
        
        if block["type"] == "video":
            audio_clips = []
            durations = []
            slides_html = ""
            
            for s_idx, scene in enumerate(block["scenes"]):
                p = f"temp_files/sa_v_{idx}_{s_idx}.mp3"
                gen_audio_sync(scene.get("narration_text", ""), p, tts_config)
                
                clip = AudioFileClip(p)
                audio_clips.append(clip)
                audio_clips.append(silence_clip) # Respiro de 1s obrigatório
                
                slides_html += build_luminal_slide(scene, total_global_slides)
                durations.append(int(clip.duration * 1000) + 1000) # Adiciona 1s na duração do slide
                total_global_slides += 1
            
            final_audio = concatenate_audioclips(audio_clips)
            fa_p = f"temp_files/sa_block_{idx}.mp3"
            final_audio.write_audiofile(fa_p, logger=None)
            
            with open(fa_p, "rb") as f: 
                b64 = "data:audio/mp3;base64," + base64.b64encode(f.read()).decode('utf-8')
                
            js_course_data.append({
                "type": "video", 
                "layer_id": f"layer_{idx}", 
                "audio_src": b64, 
                "durations": durations
            })
            html_layers += f"""
            <div id="layer_{idx}" class="video-layer" style="display:none; position:absolute; inset:0;">
                {slides_html}
            </div>
            """

        elif block["type"] == "quiz":
            qs = []
            for q in block["questions"]:
                qs.append({
                    "question": q["question"], 
                    "options": q["options"], 
                    "answer_idx": q["options"].index(q["answer"])
                })
                
            js_course_data.append({
                "type": "quiz", 
                "questions": qs, 
                "audio_successes": success_b64s, 
                "audio_errors": error_b64s
            })
        
        elif block["type"] == "game":
            js_course_data.append({
                "type": "game", 
                "url": block["url"], 
                "title": block.get("title", "Desafio Prático")
            })

        progress.progress((idx+1)/len(course_data))

    html_code = f"""
    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <script>
            tailwind.config = {{ 
                theme: {{ 
                    extend: {{ 
                        colors: {{ brand: '{brand_config["color"]}' }} 
                    }} 
                }} 
            }}
        </script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;900&display=swap" rel="stylesheet">
        <style>
            :root {{ 
                --primary: {brand_config["color"]}; 
                --bg-dark: #020617; 
            }}
            body {{ 
                font-family: 'Inter', sans-serif; 
                background: var(--bg-dark); 
                color: white; 
                overflow: hidden; 
                margin: 0; 
            }}
            .slide {{ 
                position: absolute; 
                inset: 0; 
                opacity: 0; 
                visibility: hidden; 
                transition: opacity 0.8s; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                padding: 2rem; 
            }}
            .slide.active {{ 
                opacity: 1; 
                visibility: visible; 
            }}
            .bg-container {{ 
                position: absolute; 
                inset: 0; 
                z-index: -1; 
            }}
            .bg-container img {{ 
                width: 100%; 
                height: 100%; 
                object-fit: cover; 
                filter: blur(25px) brightness(0.35); 
                transition: 10s linear; 
            }}
            .active .bg-container img {{ 
                transform: scale(1.2); 
            }}
            .glass-card {{ 
                background: rgba(255,255,255,0.03); 
                backdrop-filter: blur(12px); 
                border: 1px solid rgba(255,255,255,0.1); 
                border-radius: 32px; 
                padding: 3rem; 
            }}
            .animate-up {{ 
                transform: translateY(40px); 
                opacity: 0; 
                transition: 1s cubic-bezier(0.2,1,0.3,1); 
            }}
            .active .animate-up {{ 
                transform: translateY(0); 
                opacity: 1; 
            }}
            #progress-fill {{ 
                position: fixed; 
                top: 0; 
                left: 0; 
                height: 4px; 
                background: var(--primary); 
                width: 0%; 
                transition: width 0.3s linear; 
                z-index: 1000; 
                box-shadow: 0 0 10px var(--primary);
            }}
            .overlay {{ 
                position: fixed; 
                inset: 0; 
                z-index: 999; 
                background: #020617; 
                display: flex; 
                align-items: center; 
                justify-content: center; 
                flex-direction: column; 
            }}
            .quiz-btn {{ 
                border: 1px solid rgba(255,255,255,0.1); 
                cursor: pointer; 
                transition: 0.2s; 
            }}
            .quiz-btn:hover:not(:disabled) {{ 
                border-color: var(--primary); 
                background: rgba(255,255,255,0.1); 
                transform: scale(1.02); 
            }}
            .btn-shake {{ 
                animation: shake 0.5s; 
                border-color: #ef4444 !important; 
                background: rgba(239,68,68,0.2) !important;
            }}
            .btn-pulse {{ 
                animation: pulse 1s infinite; 
                border-color: #22c55e !important; 
                background: rgba(34,197,94,0.2) !important;
            }}
            @keyframes shake {{ 
                0%, 100% {{ transform: translateX(0); }} 
                20%, 60% {{ transform: translateX(-8px); }} 
                40%, 80% {{ transform: translateX(8px); }} 
            }}
            @keyframes popIn {{ 
                0% {{ transform: scale(0.8) translateY(30px); opacity: 0; }} 
                100% {{ transform: scale(1) translateY(0); opacity: 1; }} 
            }}
            @keyframes pulse {{ 
                0% {{ box-shadow: 0 0 0 0 rgba(34,197,94,0.4); }} 
                70% {{ box-shadow: 0 0 0 20px rgba(34,197,94,0); }} 
                100% {{ box-shadow: 0 0 0 0 rgba(34,197,94,0); }} 
            }}
            .anim-pop {{ 
                animation: popIn 0.7s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; 
            }}
        </style>
    </head>
    <body>
        <div id="progress-fill"></div>
        
        <div id="start-overlay" class="overlay">
            <button onclick="start()" class="px-16 py-8 bg-brand text-black font-black rounded-full text-2xl shadow-[0_0_50px_brand]">
                INICIAR SUPER AULA
            </button>
        </div>
        
        <div id="end-overlay" class="overlay" style="display:none; background: rgba(2,6,23,0.9); backdrop-filter: blur(20px);">
            <h2 class="text-6xl font-black mb-12 text-white">Masterclass Concluída!</h2>
            <button onclick="location.reload()" class="px-12 py-6 bg-brand text-black font-black rounded-full">
                🔄 REINICIAR
            </button>
        </div>
        
        <div id="quiz-overlay" class="overlay" style="display:none; background: rgba(2,6,23,0.9); backdrop-filter: blur(20px);">
            <div id="quiz-content" class="max-w-4xl w-full px-8">
                <div class="inline-block px-4 py-1 rounded-full bg-brand/20 border border-brand/30 text-brand text-xs font-black tracking-widest uppercase mb-6 flex justify-between w-full">
                    <span>⚡ DESAFIO</span>
                    <span id="quiz-progress-text"></span>
                </div>
                <h2 id="q-txt" class="text-4xl font-black mb-10 leading-tight">Pergunta...</h2>
                <div id="q-opts" class="space-y-4"></div>
            </div>
        </div>

        <!-- LAYER DO GAME (IFRAME EM TELA CHEIA POR CIMA) -->
        <div id="game-overlay" class="overlay" style="display:none; background: #000; z-index: 1000;">
            <div class="absolute top-6 left-1/2 -translate-x-1/2 z-[1001] flex items-center gap-4 bg-black/80 p-4 rounded-full border border-white/10">
                <span class="text-brand font-bold uppercase" id="game-title">SIMULADOR</span>
                <button onclick="finishGame()" class="px-6 py-2 bg-brand text-black font-bold rounded-full text-sm hover:scale-105 transition-all">
                    FINALIZAR GAME
                </button>
            </div>
            <iframe id="game-frame" src="" class="w-full h-full border-none"></iframe>
        </div>

        <header class="fixed top-10 left-10 z-50 flex items-center gap-6">
            {brand_config["logo"]}
            <div>
                <div class="text-[10px] font-bold uppercase opacity-40">{brand_config["header_top"]}</div>
                <div class="text-sm font-medium text-brand">{brand_config["header_bottom"]}</div>
            </div>
        </header>
        
        <audio id="aud"></audio>
        
        <main id="video-container" class="relative h-screen w-full overflow-hidden">
            {html_layers}
        </main>

        <script>
            const data = {json.dumps(js_course_data)}; 
            const endAudio = "{end_b64}";
            const aud = document.getElementById('aud'); 
            let current = 0; 
            let animId;

            // Fades de áudio
            function playAudioFadeIn(src) {{
                aud.src = src; 
                aud.volume = 0; 
                aud.play();
                let vol = 0; 
                let fade = setInterval(() => {{ 
                    if (vol < 0.6) {{ 
                        vol += 0.05; 
                        aud.volume = vol; 
                    }} else {{ 
                        clearInterval(fade); 
                    }} 
                }}, 50);
            }}

            function start() {{ 
                document.getElementById('start-overlay').style.display = 'none'; 
                playStep(); 
            }}
            
            function nextStep() {{ 
                current++; 
                setTimeout(playStep, 1000); 
            }}
            
            function finishGame() {{ 
                document.getElementById('game-overlay').style.display = 'none'; 
                document.getElementById('game-frame').src = ""; 
                nextStep(); 
            }}

            function playStep() {{
                cancelAnimationFrame(animId);
                document.getElementById('quiz-overlay').style.display = 'none';
                document.getElementById('game-overlay').style.display = 'none';
                document.querySelectorAll('.video-layer').forEach(l => l.style.display = 'none');

                if(current >= data.length) {{ 
                    document.getElementById('end-overlay').style.display = 'flex'; 
                    playAudioFadeIn(endAudio); 
                    return; 
                }}

                const step = data[current];
                if(step.type === 'video') {{
                    const layer = document.getElementById(step.layer_id); 
                    layer.style.display = 'block';
                    playAudioFadeIn(step.audio_src);
                    runVideo(step, layer);
                    aud.onended = () => {{ 
                        aud.onended = null; 
                        nextStep(); 
                    }};
                
                }} else if(step.type === 'quiz') {{
                    document.getElementById('progress-fill').style.width = '100%';
                    showQuiz(step, 0);
                
                }} else if(step.type === 'game') {{
                    document.getElementById('game-overlay').style.display = 'flex';
                    document.getElementById('game-title').innerText = step.title;
                    document.getElementById('game-frame').src = step.url;
                }}
            }}

            function runVideo(step, layer) {{
                const slides = layer.querySelectorAll('.slide'); 
                let lastIdx = -1;
                function update() {{
                    const now = aud.currentTime * 1000; 
                    let acc = 0; 
                    let target = 0;
                    let global = step.durations.reduce((a,b)=>a+b,0);
                    
                    document.getElementById('progress-fill').style.width = (now/global*100)+'%';
                    
                    for(let i=0; i<step.durations.length; i++) {{
                        if (now >= acc && now < acc + step.durations[i]) {{ 
                            target = i; 
                            break; 
                        }}
                        acc += step.durations[i];
                    }}
                    
                    if (target !== lastIdx) {{
                        if(lastIdx >= 0 && slides[lastIdx]) slides[lastIdx].classList.remove('active');
                        lastIdx = target; 
                        if(slides[lastIdx]) slides[lastIdx].classList.add('active');
                    }}
                    animId = requestAnimationFrame(update);
                }}
                update();
            }}

            function showQuiz(step, qIdx) {{
                const qc = document.getElementById('quiz-overlay'); 
                qc.style.display = 'flex';
                const content = document.getElementById('quiz-content');
                content.style.animation = 'none'; 
                void content.offsetWidth; 
                content.style.animation = 'popIn 0.7s forwards';
                
                const q = step.questions[qIdx];
                document.getElementById('quiz-progress-text').innerText = `Pergunta ${{qIdx+1}}/${{step.questions.length}}`;
                document.getElementById('q-txt').innerText = q.question;
                
                const opts = document.getElementById('q-opts'); 
                opts.innerHTML = '';
                
                q.options.forEach((opt, i) => {{
                    const btn = document.createElement('button');
                    btn.className = "quiz-btn glass-card w-full text-left p-6 text-xl flex justify-between";
                    btn.innerHTML = `<span>${{opt}}</span><span class="indicator text-2xl"></span>`;
                    
                    btn.onclick = () => {{
                        document.querySelectorAll('.quiz-btn').forEach(b => b.disabled = true);
                        const ind = btn.querySelector('.indicator');
                        
                        if(i === q.answer_idx) {{
                            btn.classList.add('btn-pulse'); 
                            ind.innerText = "✅";
                            playAudioFadeIn(step.audio_successes[Math.floor(Math.random()*10)]); 
                            aud.onended = () => {{ 
                                aud.onended = null; 
                                btn.classList.remove('btn-pulse'); 
                                if(qIdx+1 < step.questions.length) {{
                                    showQuiz(step, qIdx+1); 
                                }} else {{
                                    nextStep(); 
                                }}
                            }};
                        }} else {{
                            btn.classList.add('btn-shake'); 
                            ind.innerText = "❌";
                            playAudioFadeIn(step.audio_errors[Math.floor(Math.random()*10)]); 
                            aud.onended = () => {{ 
                                aud.onended = null; 
                                document.querySelectorAll('.quiz-btn').forEach(b => b.disabled = false); 
                                btn.classList.remove('btn-shake'); 
                                ind.innerText = ""; 
                            }};
                        }}
                    }};
                    opts.appendChild(btn);
                }});
            }}
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=900, scrolling=False)

# ==========================================
# RENDERIZADOR MP4 
# ==========================================
def render_mp4_video(scenes, tts_config):
    st.info("⚙️ Renderizando MP4...")
    clips = []
    
    if not scenes:
        st.error("JSON inválido para MP4.")
        return
        
    progress = st.progress(0)
    for i, scene in enumerate(scenes):
        p = f"temp_files/m_{i}.mp3"
        gen_audio_sync(scene.get("narration_text", ""), p, tts_config)
        
        audio = AudioFileClip(p)
        base = ColorClip(size=(1280, 720), color=(15, 23, 42), duration=audio.duration).set_audio(audio)
        
        txt = scene.get("narration_text", "")[:60] + "..."
        img = Image.new('RGBA', (1280, 720), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((100, 300), txt, fill="white", font=font)
        
        txt_clip = ImageClip(np.array(img)).set_duration(audio.duration).set_position('center')
        clips.append(CompositeVideoClip([base, txt_clip]))
        progress.progress((i+1)/len(scenes))
        
    final_v = concatenate_videoclips(clips, method="compose")
    final_v.write_videofile("temp_files/output.mp4", fps=24, codec="libx264", logger=None)
    st.video("temp_files/output.mp4")

# ==========================================
# UI 
# ==========================================
st.set_page_config(page_title="Luminal Master", layout="wide")
with st.sidebar:
    st.title("Settings")
    htop = st.text_input("Superior", "Saber Gestão")
    hbot = st.text_input("Inferior", "NR-33 Expert")
    brand = st.color_picker("Destaque", "#8ef736")
    logo = st.file_uploader("Logo PNG", type=["png", "jpg"])
    
    if logo:
        b64 = base64.b64encode(logo.getvalue()).decode("utf-8")
        l_html = f'<img src="data:{logo.type};base64,{b64}" class="h-12 w-auto">'
    else: 
        l_html = f'<div class="w-12 h-12 rounded-2xl flex items-center justify-center font-black text-2xl text-black" style="background-color:{brand}">L</div>'
    
    bc = {"color": brand, "logo": l_html, "header_top": htop, "header_bottom": hbot}
    st.divider()
    
    modo = st.radio("Modo Saída Editor (Aba 1):", ["1️⃣ HTML5 Max", "2️⃣ MP4 Simples"])
    tts_mode = st.radio("Voz:", ["Edge-TTS (Free)", "ElevenLabs (Premium)"])
    v_id = st.text_input("Voice ID", "JBFqnCBsd6RMkjVDRZzb")
    tc = {"provider": tts_mode, "voice_id": v_id}

tab1, tab2 = st.tabs(["🎬 Editor Visual", "🎓 Super Aula NR-33"])

with tab1:
    st.title("🎬 Masterclass Visual Editor")
    if 'scenes' not in st.session_state: 
        st.session_state['scenes'] = []
        
    tema = st.text_input("Tema:")
    if st.button("🧠 Gerar Roteiro"):
        res = generate_script_with_gemini(tema)
        if res: 
            st.session_state['scenes'] = res['scenes']
    
    if st.session_state['scenes']:
        for i, sc in enumerate(st.session_state['scenes']):
            with st.expander(f"Cena {i+1} ({sc.get('layout', 'Slide').upper()})"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    sc['narration_text'] = st.text_area(f"Fala", sc['narration_text'], key=f"n{i}")
                    sc['title'] = st.text_input(f"Título", sc.get('title',''), key=f"t{i}")
                    sc['highlight'] = st.text_input(f"Destaque Neon", sc.get('highlight',''), key=f"h{i}")
                with col2:
                    sc['layout'] = st.selectbox(
                        "Layout", 
                        ["hero","pillars","philosophy","side_by_side","metrics","team","timeline","features_grid","quote","compare","title_only","ending"], 
                        key=f"l{i}", 
                        index=0
                    )
                    sc['image_url'] = st.text_input("Imagem URL", sc.get('image_url',''), key=f"img{i}")
        
        if st.button("🚀 Renderizar Editor"):
            cleanup_temp()
            if "1️⃣" in modo:
                render_html_player(st.session_state['scenes'], tc, bc)
            else:
                render_mp4_video(st.session_state['scenes'], tc)

with tab2:
    st.title("🎓 Super Aula: PET NR-33 (A Experiência Completa)")
    # ROTEIRO COMPLEXO NR-33 TOTALMENTE EXPANDIDO
    SUPER_AULA = [
        # FASE 1: O QUE É A PET (5 Slides)
        {
            "type": "video",
            "scenes": [
                {
                    "layout": "hero", 
                    "image_url": "https://images.unsplash.com/photo-1544465544-1b71aee9dfa3?q=80&w=1200", 
                    "kicker": "NR 33: Segurança em Espaço Confinado", 
                    "title": "A PET", 
                    "highlight": "PERMISSÃO DE TRABALHO", 
                    "subtitle": "O documento que separa a vida do acidente fatal.", 
                    "narration_text": "Em espaços confinados, o perigo é invisível. A PET, ou Permissão de Entrada e Trabalho, não é apenas um papel, mas um protocolo rigoroso de sobrevivência."
                },
                {
                    "layout": "quote", 
                    "image_url": "https://images.unsplash.com/photo-1513128034602-7814ccaddd4e?q=80&w=1200", 
                    "quote_text": "É proibida a entrada e o trabalho em espaços confinados sem a emissão da PET.", 
                    "author": "Texto da Norma", 
                    "role": "NR 33.3.3.1", 
                    "narration_text": "A norma é clara: ninguém entra, ninguém desce e ninguém opera sem uma PET emitida, datada e assinada por quem entende do risco."
                },
                {
                    "layout": "philosophy", 
                    "image_url": "https://images.unsplash.com/photo-1581094288338-2314dddb7ecc?q=80&w=1200", 
                    "title": "Um Processo Vivo", 
                    "paragraphs": [
                        "A PET encerra-se ao final de cada turno de trabalho.", 
                        "Qualquer interrupção ou saída requer uma nova validação."
                    ], 
                    "narration_text": "Entenda que a PET tem validade curta. Ela é específica para aquela atividade e aquele momento. Se o turno acabou ou a equipe saiu, o processo recomeça do zero."
                },
                {
                    "layout": "compare", 
                    "image_url": "https://images.unsplash.com/photo-1504307651254-35680f356dfd?q=80&w=1200", 
                    "bad_title": "Entrada Informal", 
                    "bad_items": [
                        "Risco de asfixia imediato", 
                        "Falta de vigia externo", 
                        "Sem plano de resgate"
                    ], 
                    "good_title": "Entrada com PET", 
                    "good_items": [
                        "Monitoramento de gases", 
                        "Vigia posicionado", 
                        "Equipamentos aferidos"
                    ], 
                    "narration_text": "Trabalhar no achismo em um tanque ou silo é uma sentença de morte. Com a PET, transformamos o ambiente hostil em um cenário controlado e monitorado."
                },
                {
                    "layout": "title_only", 
                    "image_url": "https://images.unsplash.com/photo-1516937941344-00b4e0337589?q=80&w=1200", 
                    "title": "Quem são os responsáveis por esse documento?", 
                    "narration_text": "Não basta preencher. É preciso saber quem tem o poder legal e a responsabilidade técnica de autorizar a descida da equipe."
                }
            ]
        },
        
        # QUIZ 1: FUNDAMENTOS
        {
            "type": "quiz",
            "questions": [
                {
                    "question": "A PET (Permissão de Entrada e Trabalho) pode ser utilizada para vários turnos de trabalho diferentes?",
                    "options": [
                        "Sim, desde que o trabalho seja o mesmo.", 
                        "Não, ela é válida apenas para cada entrada e deve ser encerrada ao final do turno.", 
                        "Sim, ela vale por até 30 dias após a assinatura."
                    ],
                    "answer": "Não, ela é válida apenas para cada entrada e deve ser encerrada ao final do turno."
                },
                {
                    "question": "O que acontece se houver uma interrupção nas condições de trabalho ou saída dos trabalhadores?",
                    "options": [
                        "Eles podem voltar quando quiserem usando a mesma PET.",
                        "A PET deve ser cancelada e uma nova permissão deve ser emitida para o retorno.",
                        "Basta o vigia dar um 'visto' no verso do documento atual."
                    ],
                    "answer": "A PET deve ser cancelada e uma nova permissão deve ser emitida para o retorno."
                }
            ]
        },
        
        # FASE 2: O CORE TÉCNICO (8 Slides)
        {
            "type": "video",
            "scenes": [
                {
                    "layout": "side_by_side", 
                    "image_url": "https://images.unsplash.com/photo-1581092160562-40aa08e78837?q=80&w=1200", 
                    "side_image": "https://images.unsplash.com/photo-1576086213369-97a306d36557?q=80&w=1000", 
                    "title": "Monitoramento", 
                    "subtitle": "A primeira linha de defesa.", 
                    "list_items": [
                        "Níveis de Oxigênio", 
                        "Gases Inflamáveis e Tóxicos"
                    ], 
                    "narration_text": "O passo técnico mais importante da PET é a avaliação atmosférica. Antes de entrar, testamos o ar. Se os níveis de oxigênio ou gases tóxicos estiverem fora do padrão, ninguém desce."
                },
                {
                    "layout": "pillars", 
                    "image_url": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?q=80&w=1200", 
                    "items": [
                        {"emoji": "✍️", "title": "Supervisor", "desc": "Emite e encerra a PET."}, 
                        {"emoji": "👁️", "title": "Vigia", "desc": "Monitora do lado de fora."}, 
                        {"emoji": "👷", "title": "Trabalhador", "desc": "Executa a tarefa interna."}
                    ], 
                    "narration_text": "A PET define três papéis vitais. O Supervisor que assina, o Trabalhador que entra e, o mais importante: o Vigia, que nunca abandona seu posto do lado de fora."
                },
                {
                    "layout": "metrics", 
                    "image_url": "https://images.unsplash.com/photo-1582139329536-e7284fece509?q=80&w=1200", 
                    "metrics": [
                        { "value": "20.9%", "label": "Oxigênio Ideal", "color": "text-blue-500" },
                        { "value": "0%", "label": "LEL (Explosividade)", "color": "text-orange-500" },
                        { "value": "100%", "label": "Ventilação Ativa", "color": "text-emerald-500" },
                        { "value": "1", "label": "Vigia por Acesso", "color": "text-brand" }
                    ],
                    "narration_text": "Estes são os números da vida. Qualquer variação nesses indicadores exige a evacuação imediata do espaço confinado e a suspensão da permissão de trabalho."
                },
                {
                    "layout": "features_grid", 
                    "image_url": "https://images.unsplash.com/photo-1530124560676-587cabee14f2?q=80&w=1200", 
                    "features": [
                        "Exaustores", 
                        "Insufladores", 
                        "Rádios Intrinsecamente Seguros", 
                        "Tripés de Resgate", 
                        "Lanternas à prova de explosão", 
                        "Detectores Multigases"
                    ],
                    "narration_text": "A PET lista os equipamentos obrigatórios. Tudo o que entra no espaço deve ser intrinsecamente seguro para não gerar faíscas em atmosferas explosivas."
                },
                {
                    "layout": "timeline", 
                    "image_url": "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?q=80&w=1200", 
                    "title": "Fluxo da PET", 
                    "events": [
                        {"year": "Início", "event": "Avaliação", "desc": "Teste de gases e riscos."},
                        {"year": "Emissão", "event": "Assinatura", "desc": "Supervisor libera o acesso."},
                        {"year": "Trabalho", "event": "Vigilância", "desc": "Monitoramento contínuo."},
                        {"year": "Fim", "event": "Arquivamento", "desc": "PET guardada por 5 anos."}
                    ],
                    "narration_text": "O ciclo de vida da PET começa na avaliação, passa pela vigilância constante e termina no RH. Sim, toda PET deve ser arquivada por cinco anos para rastreabilidade legal."
                },
                {
                    "layout": "team", 
                    "image_url": "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?q=80&w=1200", 
                    "title": "A Equipe de Resgate", 
                    "members": [
                        { "name": "Interna", "role": "Brigada Própria", "avatar": "https://i.pravatar.cc/150?u=r1" },
                        { "name": "Externa", "role": "Corpo de Bombeiros", "avatar": "https://i.pravatar.cc/150?u=r2" },
                        { "name": "Equipamentos", "role": "Prontos para Uso", "avatar": "https://i.pravatar.cc/150?u=r3" }
                    ],
                    "narration_text": "A PET deve conter o plano de resgate. Se algo der errado, ninguém entra para salvar no susto. O resgate deve ser técnico, treinado e equipado."
                },
                {
                    "layout": "quote", 
                    "image_url": "https://images.unsplash.com/photo-1581092918056-0c4c3acd3789?q=80&w=1200", 
                    "quote_text": "O Vigia não pode realizar outras tarefas que possam comprometer seu dever principal.", 
                    "author": "Regra de Ouro", 
                    "role": "NR 33.3.4.1", 
                    "narration_text": "Muitos acidentes ocorrem porque o vigia tentou ajudar em outra tarefa ou saiu para buscar uma ferramenta. Sua única função é vigiar e acionar o resgate."
                },
                {
                    "layout": "title_only", 
                    "image_url": "https://images.unsplash.com/photo-1541888946425-d81bb19480c5?q=80&w=1200", 
                    "title": "Segurança não é custo, é investimento em vida.", 
                    "narration_text": "Agora que você entende o peso técnico da Permissão de Trabalho, está pronto para ser o guardião da vida da sua equipe."
                }
            ]
        },
        
        # QUIZ 2: OPERACIONAL
        {
            "type": "quiz",
            "questions": [
                {
                    "question": "Qual das alternativas abaixo é uma função EXCLUSIVA do Vigia durante o trabalho?",
                    "options": [
                        "Entrar no espaço para ajudar o colega em dificuldades.", 
                        "Manter contagem contínua dos trabalhadores e acionar o resgate se necessário.", 
                        "Operar máquinas pesadas fora do espaço confinado."
                    ],
                    "answer": "Manter contagem contínua dos trabalhadores e acionar o resgate se necessário."
                },
                {
                    "question": "Por quanto tempo a empresa deve manter arquivada a PET após o encerramento do trabalho?",
                    "options": [
                        "6 meses.",
                        "1 ano.",
                        "5 anos."
                    ],
                    "answer": "5 anos."
                }
            ]
        },

        # FASE 3: O GAME (Desafio Gate Keeper)
        {
            "type": "game",
            "title": "🕹️ SIMULADOR: GATE KEEPER",
            "url": "https://game.sabergestao.com.br/embed/unified/gate-keeper-v1-moslttly"
        },

        # FASE 4: CONCLUSÃO (3 Slides)
        {
            "type": "video",
            "scenes": [
                {
                    "layout": "philosophy", 
                    "image_url": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?q=80&w=1200", 
                    "title": "Zero Acidentes", 
                    "paragraphs": [
                        "A PET é a ferramenta que formaliza a sua segurança.", 
                        "Nenhum trabalho é tão urgente que não possa ser feito com proteção."
                    ], 
                    "narration_text": "Nosso objetivo é um só: que cada colaborador que desça em um espaço confinado, suba de volta para sua família ao final do dia."
                },
                {
                    "layout": "compare", 
                    "image_url": "https://images.unsplash.com/photo-1506784365847-bbad939e9335?q=80&w=1200", 
                    "bad_title": "O Atalho", 
                    "bad_items": ["Ganho de 10 minutos", "Risco de morte de 100%"], 
                    "good_title": "O Protocolo", 
                    "good_items": ["Trabalho Profissional", "Segurança Garantida"], 
                    "narration_text": "Não aceite atalhos. O tempo que você gasta preenchendo a PET e testando os gases é o tempo que garante que você terá um amanhã."
                },
                {
                    "layout": "ending", 
                    "image_url": "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?q=80&w=1200", 
                    "title": "Missão", 
                    "highlight": "CUMPRIDA.", 
                    "contact": "Segurança do Trabalho", 
                    "website": "Treinamento Concluído", 
                    "narration_text": "Você concluiu o treinamento sobre PET da NR 33. Leve esse conhecimento para o campo. Proteja-se e proteja seus colegas. Até a próxima."
                }
            ]
        }
    ]
    
    if st.button("🔥 Compilar Super Aula NR-33", type="primary"):
        render_super_aula_html(SUPER_AULA, tc, bc)
