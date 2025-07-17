import asyncio
import edge_tts
import os

async def text_to_speech(text_file: str, output_file: str, voice: str):
    """
    Convierte un archivo de texto a un archivo de audio MP3 usando edge-tts.
    """
    # 1. Leer el texto completo del archivo
    with open(text_file, 'r', encoding='utf-8') as f:
        full_text = f.read()

    if not full_text.strip():
        print("El archivo de texto está vacío. No se generará audio.")
        return

    try:
        # 2. Crear el objeto Communicate de edge-tts
        print(f"🚀 Iniciando generación de audio con edge-tts y la voz: {voice}")
        communicate = edge_tts.Communicate(full_text, voice)
        
        # 3. Guardar el archivo de audio
        await communicate.save(output_file)
        print(f"\n🎉 Audio completo guardado en: {output_file}")

    except Exception as e:
        print(f"❌ Error durante la generación del audio con edge-tts: {e}")

# --- Ejecución Directa (para pruebas) ---
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Uso: python text_to_speech.py <archivo_de_texto> <archivo_de_salida.mp3> <nombre_de_la_voz>")
        print("Ejemplo: python text_to_speech.py mi_texto.txt mi_audio.mp3 es-CL-LorenzoNeural")
        sys.exit(1)
        
    input_text_file = sys.argv[1]
    output_audio_file = sys.argv[2]
    selected_voice = sys.argv[3]
    
    asyncio.run(text_to_speech(input_text_file, output_audio_file, selected_voice))
