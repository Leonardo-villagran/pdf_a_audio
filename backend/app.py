from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import asyncio
import edge_tts
import uuid
import time
from datetime import datetime, timedelta
from ocr_pdf_to_text import ocr_pdf_to_text, extract_text_from_pdf
from text_to_speech import text_to_speech

app = Flask(__name__, static_folder=None)
CORS(app) # Habilitar CORS para toda la aplicación

basedir = os.path.abspath(os.path.dirname(__file__))
INPUT_DIR = os.path.join(basedir, 'input')
OUTPUT_DIR = os.path.join(basedir, 'output')
for d in [INPUT_DIR, OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)

def cleanup_old_files():
    """Elimina archivos PDF y MP3 más viejos de 24 horas."""
    print("--- Ejecutando limpieza de archivos antiguos ---")
    now = time.time()
    twelve_hours_in_seconds = 12 * 60 * 60
    
    # Limpiar directorio de entrada (PDFs)
    for filename in os.listdir(INPUT_DIR):
        if filename.lower().endswith('.pdf'):
            file_path = os.path.join(INPUT_DIR, filename)
            try:
                if os.path.getmtime(file_path) < now - twelve_hours_in_seconds:
                    os.remove(file_path)
                    print(f"Eliminado PDF antiguo: {filename}")
            except Exception as e:
                print(f"Error eliminando archivo {file_path}: {e}")

    # Limpiar directorio de salida (MP3s)
    for filename in os.listdir(OUTPUT_DIR):
        if filename.lower().endswith('.mp3'):
            file_path = os.path.join(OUTPUT_DIR, filename)
            try:
                if os.path.getmtime(file_path) < now - twelve_hours_in_seconds:
                    os.remove(file_path)
                    print(f"Eliminado MP3 antiguo: {filename}")
            except Exception as e:
                print(f"Error eliminando archivo {file_path}: {e}")
    print("--- Limpieza finalizada ---")


@app.route('/api/output/<path:filename>')
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.route('/api/voices', methods=['GET'])
def get_voices():
    async def list_voices():
        return await edge_tts.list_voices()
    
    try:
        voices = asyncio.run(list_voices())
        return jsonify(voices)
    except Exception as e:
        return jsonify({'error': f'Error obteniendo voces: {str(e)}'}), 500

@app.route('/api/pdf-to-text', methods=['POST'])
def pdf_to_text():
    # Ejecutar limpieza antes de procesar el nuevo archivo
    cleanup_old_files()
    
    if 'pdf' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo PDF'}), 400
    
    pdf_file = request.files['pdf']
    lang = request.form.get('lang', 'spa')
    
    # Guardar temporalmente el archivo para procesarlo
    temp_filename = str(uuid.uuid4()) + ".pdf"
    pdf_path = os.path.join(INPUT_DIR, temp_filename)
    pdf_file.save(pdf_path)

    try:
        extracted_text = extract_text_from_pdf(pdf_path, language=lang)
        return jsonify({'text': extracted_text})
    except Exception as e:
        return jsonify({'error': f'Error procesando PDF: {str(e)}'}), 500
    finally:
        # Limpiar el archivo temporal
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

@app.route('/api/text-to-audio', methods=['POST'])
def text_to_audio():
    data = request.get_json()
    if not data or 'text' not in data or 'voice' not in data:
        return jsonify({'error': 'Faltan los parámetros "text" o "voice"'}), 400

    text = data['text']
    voice = data['voice']
    
    # Generar un nombre de archivo único para el audio
    audio_filename = str(uuid.uuid4()) + ".mp3"
    output_path = os.path.join(OUTPUT_DIR, audio_filename)

    # Crear un archivo de texto temporal para usar con text_to_speech
    temp_text_filename = str(uuid.uuid4()) + ".txt"
    temp_text_path = os.path.join(INPUT_DIR, temp_text_filename)
    
    with open(temp_text_path, 'w', encoding='utf-8') as f:
        f.write(text)

    try:
        # Llamar a la función principal de texto a voz con el archivo temporal
        asyncio.run(text_to_speech(temp_text_path, output_path, voice))
        return jsonify({'audio': audio_filename})
    except Exception as e:
        return jsonify({'error': f'Error generando audio: {str(e)}'}), 500
    finally:
        # Limpiar el archivo de texto temporal
        if os.path.exists(temp_text_path):
            os.remove(temp_text_path)

@app.route('/api/procesar', methods=['POST'])
def procesar():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo PDF'}), 400
    pdf_file = request.files['pdf']
    pdf_filename = pdf_file.filename
    pdf_path = os.path.join(INPUT_DIR, pdf_filename)
    pdf_file.save(pdf_path)

    lang = request.form.get('lang', 'spa')
    voice = request.form.get('voice', 'es-ES-ElviraNeural')
    base_name = os.path.splitext(pdf_filename)[0]
    out_txt_name = request.form.get('out', f"{base_name}.txt")
    out_audio_name = request.form.get('audio', f"{base_name}.mp3")
    out_txt = os.path.join(OUTPUT_DIR, out_txt_name)
    out_audio = os.path.join(OUTPUT_DIR, out_audio_name)

    try:
        ocr_pdf_to_text(pdf_path, out_txt, language=lang)
    except Exception as e:
        return jsonify({'error': f'Error procesando PDF: {str(e)}'}), 500

    try:
        asyncio.run(text_to_speech(out_txt, out_audio, voice=voice))
    except Exception as e:
        return jsonify({'error': f'Error generando audio: {str(e)}'}), 500

    return jsonify({
        'pdf': pdf_filename,
        'texto': out_txt_name,
        'audio': out_audio_name,
        'idioma': lang,
        'voz': voice
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
