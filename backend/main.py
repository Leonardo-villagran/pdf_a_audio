
import argparse
import asyncio
import os
from ocr_pdf_to_text import ocr_pdf_to_text
from text_to_speech import text_to_speech

def main():
    parser = argparse.ArgumentParser(description='Convierte un PDF a texto y luego a audio')
    parser.add_argument('--pdf', required=True, help='Nombre del archivo PDF (solo el nombre, debe estar en la carpeta input)')
    parser.add_argument('--out', help='Nombre del archivo de salida de texto (solo el nombre, irá a output)')
    parser.add_argument('--audio', help='Nombre del archivo de salida de audio (solo el nombre, irá a output)')
    parser.add_argument('--lang', default=None, help='Idioma para Tesseract (por defecto: spa)')
    parser.add_argument('--voice', default=None, help='Nombre exacto de la voz para la síntesis (por defecto: es-ES-ElviraNeural)')
    args = parser.parse_args()

    # Definir carpetas
    input_dir = 'input'
    output_dir = 'output'
    temp_dir = 'temp'

    # Crear carpetas si no existen
    for d in [input_dir, output_dir, temp_dir]:
        os.makedirs(d, exist_ok=True)



    # Valores por defecto para lang y voice
    lang = args.lang if args.lang else 'spa'
    voice = args.voice if args.voice else 'es-ES-ElviraNeural'

    # Sugerir nombres de salida si no se especifican
    base_name = os.path.splitext(args.pdf)[0]
    out_txt_name = args.out if args.out else f"{base_name}.txt"
    out_audio_name = args.audio if args.audio else f"{base_name}.mp3"
    if not args.out or not args.audio:
        print(f"[INFO] Archivo de texto de salida: output/{out_txt_name}")
        print(f"[INFO] Archivo de audio de salida: output/{out_audio_name}")
    if not args.lang:
        print(f"[INFO] Idioma por defecto usado: spa")
    if not args.voice:
        print(f"[INFO] Voz por defecto usada: es-ES-ElviraNeural")

    # Rutas completas
    pdf_path = os.path.join(input_dir, args.pdf)
    out_txt = os.path.join(output_dir, out_txt_name)
    out_audio = os.path.join(output_dir, out_audio_name)


    # Paso 1: PDF a texto con manejo de error si el archivo no existe
    try:
        ocr_pdf_to_text(pdf_path, out_txt, language=lang)
    except FileNotFoundError as e:
        print(f"[ERROR] No se encontró el archivo PDF: {pdf_path}")
        return
    except Exception as e:
        print(f"[ERROR] Ocurrió un error procesando el PDF: {e}")
        return

    # Paso 2: Texto a audio
    asyncio.run(text_to_speech(out_txt, out_audio, voice=voice))

if __name__ == '__main__':
    main()
