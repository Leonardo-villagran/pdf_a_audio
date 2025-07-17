import asyncio
import edge_tts

async def text_to_speech(text, output_file):
    communicate = edge_tts.Communicate(text, voice="es-US-PalomaNeural")
    await communicate.save(output_file)
    print(f"Audio guardado en: {output_file}")

async def main():
    text = "Hola, esta es una prueba de texto a voz con la voz Paloma."
    output_file = "es-US-PalomaNeural.wav"
    await text_to_speech(text, output_file)

asyncio.run(main())
