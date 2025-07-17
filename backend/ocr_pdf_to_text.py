import fitz  # PyMuPDF
import re
import os
import io
import platform
from PIL import Image
import pytesseract
from dotenv import load_dotenv

# --- Configuración de Tesseract dependiente del sistema operativo ---

# Cargar variables de entorno desde .env
load_dotenv()

# Por defecto, no se necesita configurar rutas (para Linux/Render)
tessdata_dir = ''

# Si estamos en Windows, usamos las rutas del .env
if platform.system() == "Windows":
    print("Sistema Windows detectado. Usando rutas de Tesseract desde .env")
    tesseract_cmd = os.getenv('TESSERACT_CMD')
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    else:
        print("Advertencia: TESSERACT_CMD no está configurado en .env para Windows.")

    tessdata_dir_win = os.getenv('TESSDATA_PREFIX')
    if tessdata_dir_win:
        tessdata_dir = tessdata_dir_win
    else:
        print("Advertencia: TESSDATA_PREFIX no está configurado en .env para Windows.")
else:
    print("Sistema no-Windows (Linux/Render) detectado. Tesseract debe estar en el PATH.")

def extract_text_from_pdf(pdf_path, language='spa'):
    """
    Extrae texto de un PDF usando un método híbrido:
    1. Intenta la extracción de texto directa (rápido y preciso para PDFs con texto).
    2. Si falla o el texto es mínimo, usa OCR con Tesseract (potente para PDFs basados en imágenes).
    """
    doc = fitz.open(pdf_path)
    all_text = ""
    
    for pg, page in enumerate(doc, start=1):
        print(f"Procesando página {pg}/{len(doc)}...")
        
        # Intento 1: Extracción de texto directa
        text = page.get_text("text")
        
        # Si el texto es mínimo, probablemente es una imagen. Usar OCR.
        if len(text.strip()) < 20:
            print(f"Página {pg} parece ser una imagen. Usando OCR con Tesseract...")
            try:
                pix = page.get_pixmap(dpi=300)
                img_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_bytes))
                
                # Construir el argumento de configuración para Tesseract, SIN comillas
                config = f'--tessdata-dir {tessdata_dir}' if tessdata_dir else ''
                
                # Usar Tesseract para el OCR, pasando la configuración directamente
                text = pytesseract.image_to_string(img, lang=language, config=config)

            except Exception as e:
                print(f"Error durante el OCR con Tesseract en la página {pg}: {e}")
                text = "" # Continuar con la siguiente página si hay un error

        all_text += text + "\n"  # Usar \n para poder procesar guiones al final de línea
    
    # --- Limpieza final del texto completo ---
    
    # 1. Unir palabras separadas por guion al final de la línea. Ej: "palab-\nra" -> "palabra"
    all_text = re.sub(r'-\s*\n\s*', '', all_text)
    
    # 2. Eliminar números sueltos (como paginación) que no forman parte de una oración
    all_text = re.sub(r'\b\d+\b', '', all_text)
    
    # 3. Corregir errores comunes de OCR (se puede expandir si aparecen más)
    all_text = all_text.replace('â', 'á')
    
    # 4. Normalizar todos los espacios en blanco (incluidos saltos de línea restantes) a un solo espacio
    all_text = re.sub(r'\s+', ' ', all_text).strip()
    
    return all_text

def ocr_pdf_to_text(pdf_path, output_txt, language='spa'):
    """
    Extrae texto de un PDF y lo guarda en un archivo de texto.
    Mantenido por retrocompatibilidad con el endpoint /procesar.
    """
    all_text = extract_text_from_pdf(pdf_path, language)
    
    # Dividir en oraciones completas para una mejor estructura en el archivo de salida
    sentences = re.split(r'(?<=[.!?])\s+', all_text)
    with open(output_txt, 'w', encoding='utf-8') as out:
        for s in sentences:
            if s.strip(): # Asegurarse de no escribir líneas vacías
                out.write(s.strip() + "\n")

    print(f"\n✅ Texto procesado con Tesseract y guardado en: {output_txt}")
