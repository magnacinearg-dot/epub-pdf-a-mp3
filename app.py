import sys
# Parche de compatibilidad para Python 3.13/3.14 en Streamlit Cloud
try:
    import audioop
except ImportError:
    import audioop_lts
    sys.modules["audioop"] = audioop_lts

import streamlit as st
import asyncio
import edge_tts
from ebooklib import epub
from bs4 import BeautifulSoup
import pypdf
import os
import re
import io
from pydub import AudioSegment

# Configuración visual de la aplicación
st.set_page_config(
    page_title="AudioBook Studio", 
    page_icon="🎙️", 
    layout="centered"
)

# Estilos CSS para una interfaz moderna y atractiva
st.markdown("""
    <style>
    .main {
        background-color: #0f172a;
        color: #f8fafc;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
        color: white;
        border: none;
        padding: 12px 24px;
        border-radius: 10px;
        font-weight: bold;
        font-size: 16px;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }
    .voice-card {
        background-color: #1e293b;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #334155;
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🎙️ AudioBook Studio")
st.caption("Transformá tus libros digitales en audiolibros humanos con un solo clic.")

# Catálogo con las voces más expresivas y naturales de Edge-TTS
VOCES = {
    "🇦🇷 Argentina - Tomás (Narración Cálida)": "es-AR-TomasNeural",
    "🇦🇷 Argentina - Elena (Expresiva)": "es-AR-ElenaNeural",
    "🇲🇽 México - Dalia (Neutro / Relato)": "es-MX-DaliaNeural",
    "🇲🇽 México - Jorge (Voz Profunda)": "es-MX-JorgeNeural",
    "🇨🇴 Colombia - Salomé (Suave)": "es-CO-SalomeNeural",
    "🇨🇴 Colombia - Gonzalo (Pausado)": "es-CO-GonzaloNeural",
    "🇨🇱 Chile - Catalina (Femenino)": "es-CL-CatalinaNeural",
    "🇨🇱 Chile - Lorenzo (Masculino)": "es-CL-LorenzoNeural",
    "🇪🇸 España - Álvaro (Novela)": "es-ES-AlvaroNeural",
    "🇪🇸 España - Elvira (Cálida)": "es-ES-ElviraNeural",
    "🇺🇸 EE.UU. - Alonso (Latino Fluido)": "es-US-AlonsoNeural",
    "🇺🇸 EE.UU. - Paloma (Latino Femenino)": "es-US-PalomaNeural"
}

# Limpiador de texto para evitar pausas robóticas y saltos innecesarios
def limpiar_texto_para_narracion(texto):
    # Unir palabras partidas por guion al final de una línea
    texto = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', texto)
    # Reemplazar múltiples saltos de línea por un punto y espacio
    texto = re.sub(r'\n+', '. ', texto)
    # Eliminar espacios dobles o repetidos
    texto = re.sub(r'\s+', ' ', texto)
    # Filtrar caracteres raros manteniendo la puntuación básica
    texto = re.sub(r'[^\w\s,.:;?!¡¿"\'—-]', '', texto)
    return texto.strip()

# Interfaz de usuario
st.markdown("<div class='voice-card'>", unsafe_allow_html=True)
voz_nombre = st.selectbox("🎙️ Elegí la voz del narrador:", list(VOCES.keys()))
voz_codigo = VOCES[voz_nombre]
st.markdown("</div>", unsafe_allow_html=True)

archivo_subido = st.file_uploader("📂 Arrastrá tu libro en formato EPUB o PDF:", type=["epub", "pdf"])

async def generar_audio_fragmento(texto, archivo_salida, voz):
    # Ajuste de velocidad (-4%) para un tono de lectura más pausado y humano
    communicate = edge_tts.Communicate(texto, voz, rate="-4%")
    await communicate.save(archivo_salida)

def extraer_capitulos_epub(bytes_file):
    with open("temp.epub", "wb") as f:
        f.write(bytes_file)
    book = epub.read_epub("temp.epub")
    capitulos = []
    for item in book.get_items():
        if item.get_type() == 9: # Documentos HTML de capítulos
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            texto_limpio = limpiar_texto_para_narracion(soup.get_text())
            if len(texto_limpio) > 300: # Ignorar páginas vacías o breves
                capitulos.append(texto_limpio)
    if os.path.exists("temp.epub"):
        os.remove("temp.epub")
    return capitulos

def extraer_capitulos_pdf(bytes_file):
    reader = pypdf.PdfReader(io.BytesIO(bytes_file))
    capitulos = []
    texto_acumulado = ""
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            texto_acumulado += " " + txt
            if len(texto_acumulado) > 3500: # Agrupar en bloques de lectura
                capitulos.append(limpiar_texto_para_narracion(texto_acumulado))
                texto_acumulado = ""
    if texto_acumulado.strip():
        capitulos.append(limpiar_texto_para_narracion(texto_acumulado))
    return capitulos

# Acción de conversión
if archivo_subido is not None:
    if st.button("✨ Generar Audiolibro Unificado"):
        st.info("Procesando y optimizando el texto del libro...")
        bytes_data = archivo_subido.read()
        
        if archivo_subido.name.endswith(".epub"):
            capitulos = extraer_capitulos_epub(bytes_data)
        else:
            capitulos = extraer_capitulos_pdf(bytes_data)
            
        if not capitulos:
            st.error("No se pudo extraer texto utilizable del archivo.")
        else:
            st.success(f"Libro procesado correctamente: {len(capitulos)} secciones/capitulos detectados.")
            
            archivos_temporales = []
            barra_progreso = st.progress(0)
            
            # Generar el audio de cada sección
            for i, cap_texto in enumerate(capitulos, start=1):
                nombre_temp = f"temp_cap_{i}.mp3"
                st.caption(f"🎧 Narrando Sección {i} de {len(capitulos)}...")
                
                asyncio.run(generar_audio_fragmento(cap_texto, nombre_temp, voz_codigo))
                archivos_temporales.append(nombre_temp)
                barra_progreso.progress(i / len(capitulos))
            
            st.info("Uniendo todas las secciones en un único archivo MP3...")
            
            # Concatenar todos los audios individuales con pydub
            audio_completo = AudioSegment.empty()
            silencio_intermedio = AudioSegment.silent(duration=1200) # 1.2s de silencio entre capítulos
            
            for file in archivos_temporales:
                segmento = AudioSegment.from_mp3(file)
                audio_completo += segmento + silencio_intermedio
                os.remove(file) # Eliminar fragmento temporal
                
            nombre_salida = "Audiolibro_Completo.mp3"
            audio_completo.export(nombre_salida, format="mp3", bitrate="128k")
            
            with open(nombre_salida, "rb") as f:
                bytes_mp3 = f.read()
                
            st.success("🎉 ¡Tu audiolibro está listo!")
            
            # Reproductor para escuchar directo en la web
            st.audio(bytes_mp3, format="audio/mp3")
            
            # Botón de descarga del archivo unificado
            st.download_button(
                label="📥 Descargar Audiolibro Completo (.MP3)",
                data=bytes_mp3,
                file_name=f"{os.path.splitext(archivo_subido.name)[0]}_Audiolibro.mp3",
                mime="audio/mp3"
            )
            
            if os.path.exists(nombre_salida):
                os.remove(nombre_salida)
