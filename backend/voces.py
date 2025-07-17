import asyncio
import edge_tts


async def list_voices():
    voices = await edge_tts.list_voices()
    for voice in voices:
        print(f"{voice['ShortName']} ({voice['Locale']})")

# Ejecutar la función para listar las voces
asyncio.run(list_voices())
