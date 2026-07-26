import streamlit as st
import asyncio
import edge_tts
from ebooklib import epub
from bs4 import BeautifulSoup
import pypdf
import os
import zipfile
import io

# Configuración de la página
st.set_page_config(page_title="Convertidor de Libros a MP3", page_icon="🎧", layout="centered")

st.title("🎧 Convertidor de EPUB/PDF a MP3")
st.write("Subí tu libro, elegí una voz natural y descargá tus MP3s organizados por capítulo.")

# Catálogo de voces naturales en español (Edge-TTS)
VOCES = {
    "Argentina - Tomás (Masculino)": "es-AR-TomasNeural",
    "Argentina - Elena (Femenino)": "es-AR-ElenaNeural",
    "México - Dalia (Femenino Neutro)": "es-MX-DaliaNeural",
    "México - Jorge (Masculino Neutro)": "es-MX-JorgeNeural",
    "Colombia - Salomé (Femenino)": "es-CO-SalomeNeural",
    "Colombia - Gonzalo (Masculino)": "es-CO-GonzaloNeural",
    "Chile - Catalina (Femenino)": "es-CL-CatalinaNeural",
    "Chile - Lorenzo (Masculino)": "es-CL-LorenzoNeural",
    "España - Elvira (Femenino)": "es-ES-ElviraNeural",
    "España - Álvaro (Masculino)": "es-ES-AlvaroNeural",
    "EE.UU. - Paloma (Latino Femenino)": "es-US-PalomaNeural",
    "EE.UU. - Alonso (Latino Masculino)": "es-US-AlonsoNeural",
}

# Selección de voz e interfaz
voz_seleccionada_nombre = st.selectbox("Seleccioná la voz para tu audiolibro:", list(VOCES.keys()))
voz_codigo = VOCES[voz_seleccionada_nombre]

archivo_subido = st.file_uploader("Cargá tu archivo (EPUB o PDF):", type=["epub", "pdf"])

# Función asíncrona para convertir texto a audio
async def texto_a_mp3(texto, ruta_salida, voz):
    communicate = edge_tts.Communicate(texto, voz)
    await communicate.save(ruta_salida)

# Extractor de capítulos para EPUB
def extraer_capitulos_epub(bytes_file):
    with open("temp.epub", "wb") as f:
        f.write(bytes_file)
    book = epub.read_epub("temp.epub")
    capitulos = []
    for item in book.get_items():
        if item.get_type() == 9: # Documentos HTML internos
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            texto = soup.get_text().strip()
            if len(texto) > 300: # Filtrar páginas vacías, portadas o créditos
                capitulos.append(texto)
    if os.path.exists("temp.epub"):
        os.remove("temp.epub")
    return capitulos

# Extractor de texto por páginas/secciones para PDF
def extraer_capitulos_pdf(bytes_file):
    reader = pypdf.PdfReader(io.BytesIO(bytes_file))
    capitulos = []
    texto_actual = ""
    for i, page in enumerate(reader.pages):
        t = page.extract_text()
        if t:
            texto_actual += f"\n\n{t}"
            # Dividir en bloques de aproximadamente 3000 caracteres para simular capítulos
            if len(texto_actual) > 3000:
                capitulos.append(texto_actual.strip())
                texto_actual = ""
    if texto_actual.strip():
        capitulos.append(texto_actual.strip())
    return capitulos

# Botón de procesamiento
if archivo_subido is not None:
    if st.button("🚀 Comenzar Conversión a MP3"):
        st.info("Extrayendo texto y procesando capítulos...")
        
        bytes_data = archivo_subido.read()
        es_epub = archivo_subido.name.endswith(".epub")
        
        if es_epub:
            capitulos = extraer_capitulos_epub(bytes_data)
        else:
            capitulos = extraer_capitulos_pdf(bytes_data)
            
        if not capitulos:
            st.error("No se pudo extraer texto utilizable del archivo.")
        else:
            st.success(f"Se detectaron {len(capitulos)} capítulos/bloques de lectura.")
            
            archivos_mp3 = []
            progreso = st.progress(0)
            
            for index, cap_texto in enumerate(capitulos, start=1):
                nombre_archivo = f"Capitulo_{index:02d}.mp3"
                st.write(f"🔊 Generando audio: `{nombre_archivo}`...")
                
                # Generar el archivo MP3 temporalmente
                asyncio.run(texto_a_mp3(cap_texto, nombre_archivo, voz_codigo))
                archivos_mp3.append(nombre_archivo)
                
                # Actualizar barra de progreso
                progreso.progress(index / len(capitulos))
            
            # Crear un archivo ZIP con todos los MP3s
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for file_mp3 in archivos_mp3:
                    zf.write(file_mp3)
                    os.remove(file_mp3) # Borrar archivo local temporal
                    
            st.success("🎉 ¡Audiolibro completado con éxito!")
            
            # Botón de descarga del paquete ZIP
            st.download_button(
                label="📦 Descargar todos los MP3s (ZIP)",
                data=zip_buffer.getvalue(),
                file_name=f"{os.path.splitext(archivo_subido.name)[0]}_MP3.zip",
                mime="application/zip"
            )
