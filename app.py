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
# INTEGRAÇÃO GEMINI 2.5 FLASH (Cérebro do Roteiro)
# ==========================================
def generate_script_with_gemini(tema_texto):
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        st.error("🚨 Chave do Gemini (GEMINI_API_KEY) não encontrada nos secrets!")
        return None
        
    # Configura a biblioteca oficial do Google com a sua chave
    genai.configure(api_key=api_key)
    
    prompt = f"""
    Atue como um Diretor de Arte e Copywriter. 
    Transforme o seguinte texto/tema em um roteiro de apresentação em formato JSON.
    Tema: {tema_texto}
    
    REGRAS DE ESTRUTURA:
    1. Crie uma lista de "scenes".
    2. Cada "scene" representa um bloco de áudio de ~20 segundos (cerca de 50 a 60 palavras) em 'narration_text'.
    3. Dentro de CADA "scene", DEVE haver exatamente uma lista chamada 'sub_slides' com 5 elementos.
    4. Cada 'sub_slide' representa uma troca de tela visual. Use URLs reais de imagens do Unsplash relacionadas ao contexto em 'image_url'.
    5. 'layout' pode ser: "hero" (precisa de title, highlight, subtitle), "pillars" (precisa de 3 itens com emoji, titulo e desc), "quote" (precisa de quote_text, author, role).
    
    Exemplo de saída:
    {{
      "project_name": "Pitch_Luminal",
      "scenes": [
        {{
          "narration_text": "O texto que o narrador vai falar continuamente durante 20 segundos... Explicando a visão e o futuro.",
          "sub_slides": [
            {{"layout": "hero", "title": "VISÃO", "highlight": "2026", "subtitle": "Arquitetura de inovação.", "image_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=1200"}},
            {{"layout": "pillars", "items": [{{"emoji": "🚀", "title": "Velocidade", "desc": "Rápido"}}, {{"emoji": "🛡️", "title": "Seguro", "desc": "Forte"}}, {{"emoji": "🌐", "title": "Global", "desc": "Mundo"}}], "image_url": "https://images.unsplash.com/..."}},
            {{"layout": "quote", "quote_text": "Inovação é o que fazemos.", "author": "Steve Jobs", "role": "CEO", "image_url": "https://..."}},
            {{"layout": "hero", "title": "DADOS", "highlight": "REAIS", "subtitle": "Decisões precisas.", "image_url": "https://..."}},
            {{"layout": "hero", "title": "O FUTURO", "highlight": "É AGORA", "subtitle": "Venha conosco.", "image_url": "https://..."}}
          ]
        }}
      ]
    }}
    
    Responda APENAS com o JSON válido, sem markdown extra.
    """

    try:
        # Chama direto o 3.1-flash usando a SDK oficial
        model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")
        
        # Força o formato de resposta em JSON
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
# MOTOR DE VOZ (EDGE-TTS vs ELEVENLABS)
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
# MOTOR 1: WEB PLAYER HTML5 (O TEMPLATE LUMINAL)
# ==========================================
def build_luminal_slide(sub_slide, total_index):
    layout = sub_slide.get("layout", "hero")
    img_url = sub_slide.get("image_url", "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2000")
    
    if layout == "hero":
        title = sub_slide.get("title", "TÍTULO")
        highlight = sub_slide.get("highlight", "DESTAQUE")
        subtitle = sub_slide.get("subtitle", "Descrição da cena vai aqui...")
        
        content = f"""
        <div class="text-center max-w-5xl">
            <h2 class="animate-up delay-1 text-blue-500 font-bold tracking-[0.6em] uppercase text-xs mb-6">Insight Estratégico</h2>
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
                <p class="text-gray-400 leading-relaxed">{item.get('desc', 'Detalhe do pilar')}</p>
            </div>
            """
        content = f'<div class="max-w-7xl w-full grid md:grid-cols-3 gap-12">{cards}</div>'
    elif layout == "quote":
        quote = sub_slide.get("quote_text", "Inovação é o que nos move.")
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
    else:
        # Fallback
        content = f'<h1 class="text-5xl font-bold">{sub_slide.get("title", "Apresentação")}</h1>'

    # O HTML de cada cena menor
    return f"""
    <section class="slide" data-index="{total_index}">
        <div class="bg-container"><img src="{img_url}" alt="bg"></div>
        {content}
    </section>
    """


def render_html_player(roteiro, tts_config):
    audio_clips = []
    slides_html = ""
    durations_array = [] # Armazena o tempo em milissegundos de cada sub-slide
    
    progress_bar = st.progress(0)
    total_scenes = len(roteiro["scenes"])
    
    total_sub_slides_count = 0
    
    for idx, scene in enumerate(roteiro["scenes"]):
        st.write(f"🎙️ Gerando narração bloco {idx+1}...")
        
        # 1. Gera o áudio longo (ex: 20s)
        audio_path = f"temp_files/audio_{idx}.mp3"
        gen_audio_sync(scene["narration_text"], audio_path, tts_config)
        clip = AudioFileClip(audio_path)
        audio_clips.append(clip)
        
        # 2. Divide a duração do áudio pelo número de sub_slides
        sub_slides = scene.get("sub_slides", [])
        if not sub_slides: continue
        
        time_per_slide = (clip.duration * 1000) / len(sub_slides)
        
        for sub in sub_slides:
            slides_html += build_luminal_slide(sub, total_sub_slides_count)
            durations_array.append(int(time_per_slide))
            total_sub_slides_count += 1
            
        progress_bar.progress((idx + 1) / total_scenes)

    st.write("🎬 Compilando Masterclass...")
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
                
                // Atualiza barra superior
                progressFill.style.width = `${(now / globalDuration) * 100}%`;

                // Acha em qual slide estamos
                for(let i=0; i<durations.length; i++) {
                    const start = acc;
                    const end = acc + durations[i];
                    if (now >= start && now < end) {
                        target = i;
                        break;
                    }
                    if (now >= end && i === durations.length - 1) {
                        target = i; // crava no último se passar
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
# MOTOR 2: RENDERIZADOR MP4 (Clássico Simples)
# ==========================================
# Mantido simples porque transições Luminal complexas no MoviePy precisariam de centenas de linhas de máscara.
def render_mp4_video(roteiro, tts_config):
    # Lógica clássica (ignorando sub_slides, usa apenas o texto principal pra não quebrar)
    st.info("Papo reto: O design Luminal (Glassmorphism e Blurs) funciona apenas no HTML5. O MP4 será exportado com um visual flat simples.")
    st.stop() # Parei por aqui pra não gerar lixo. O foco agora é o player HTML.


# ==========================================
# UI STREAMLIT PRINCIPAL
# ==========================================
st.set_page_config(page_title="Luminal Master IA", layout="wide")

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4370/4370757.png", width=60)
    st.title("Settings")
    
    modo_render = st.radio("Modo de Saída:", ["1️⃣ Web Player (Luminal HTML5)"])
    
    st.divider()
    tts_provider = st.radio("Voz:", ["Edge-TTS (Free)", "ElevenLabs (Premium)"])
    eleven_key = st.secrets.get("ELEVENLABS_API_KEY", "") if "ElevenLabs" in tts_provider else ""
    eleven_voice = st.text_input("Voice ID", "JBFqnCBsd6RMkjVDRZzb") if "ElevenLabs" in tts_provider else ""
    
    tts_config = {"provider": tts_provider, "api_key": eleven_key, "voice_id": eleven_voice}

st.title("✨ Criação Luminal com Gemini")
st.markdown("Deixe o Gemini criar as cenas e subdividir o áudio pra você.")

tema = st.text_area("Sobre o que é a apresentação?", "O impacto da Inteligência Artificial no mercado financeiro global até 2030.")

if st.button("🧠 1. Gerar Roteiro Mágico (Gemini)", use_container_width=True):
    with st.spinner("Conectando ao Gemini..."):
        script_json = generate_script_with_gemini(tema)
        if script_json:
            st.session_state['roteiro_json'] = script_json
            st.success("Roteiro criado!")

default_json = st.session_state.get('roteiro_json', "{\n  // Gere com a IA primeiro ou cole aqui seu JSON\n}")
json_input = st.text_area("Roteiro Final (Formato Luminal Sub-slides):", value=default_json, height=400)

if st.button("🎬 2. Renderizar Apresentação", type="primary", use_container_width=True):
    try:
        roteiro = json.loads(json_input)
    except Exception as e:
        st.error(f"Erro no JSON: {e}")
        st.stop()
        
    cleanup_temp()
    render_html_player(roteiro, tts_config)
