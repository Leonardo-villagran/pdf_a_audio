
import asyncio
import edge_tts
import os
import tempfile
import subprocess
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

def split_text_by_dot(text, max_length=3000):
    """
    Divide el texto en fragmentos de hasta max_length caracteres, cortando siempre en el punto final más cercano.
    """
    fragments = []
    while len(text) > max_length:
        # Buscar el último punto antes del límite
        split_pos = text.rfind('.', 0, max_length)
        if split_pos == -1:
            # Si no hay punto, cortar en el límite
            split_pos = max_length
        else:
            split_pos += 1  # Incluir el punto
        fragments.append(text[:split_pos].strip())
        text = text[split_pos:].lstrip()
    if text:
        fragments.append(text.strip())
    return fragments

async def text_to_speech(text_file: str, output_file: str, voice: str):
    """
    Convierte un archivo de texto a un archivo de audio MP3 usando edge-tts, dividiendo el texto en fragmentos por puntos.
    """
    # 1. Leer el texto completo del archivo
    with open(text_file, 'r', encoding='utf-8') as f:
        full_text = f.read()

    if not full_text.strip():
        print("El archivo de texto está vacío. No se generará audio.")
        return

    fragments = split_text_by_dot(full_text, max_length=3000)
    temp_files = []

    def limpiar_texto(texto):
        # Elimina caracteres no imprimibles y espacios redundantes
        import re
        texto = re.sub(r'[^\x20-\x7E\n\ráéíóúÁÉÍÓÚñÑüÜ.,;:!\?"\'\-\(\)\[\]{}]', '', texto)
        texto = re.sub(r'\s+', ' ', texto)
        return texto.strip()

    async def procesar_fragmento(fragment, idx, total, profundidad=0):
        if not fragment.strip():
            print(f"  Fragmento {idx+1}/{total} vacío tras limpieza. Deteniendo proceso.")
            raise RuntimeError(f"Fragmento {idx+1} vacío tras limpieza.")
        print(f"\nProcesando fragmento {idx+1}/{total} (longitud: {len(fragment)}):\n{fragment[:200]}{'...' if len(fragment) > 200 else ''}")
        temp_fd, temp_path = tempfile.mkstemp(suffix=f"_{idx}_d{profundidad}.mp3")
        os.close(temp_fd)
        try:
            communicate = edge_tts.Communicate(fragment, voice)
            await asyncio.wait_for(communicate.save(temp_path), timeout=60)
            print(f"  Fragmento {idx+1}/{total} generado.")
            return [temp_path]
        except Exception as e:
            print(f"❌ Error en fragmento {idx+1} (profundidad {profundidad}): {e}\nIntentando limpiar y reintentar...")
            fragment_limpio = limpiar_texto(fragment)
            if fragment_limpio != fragment:
                try:
                    communicate = edge_tts.Communicate(fragment_limpio, voice)
                    await asyncio.wait_for(communicate.save(temp_path), timeout=60)
                    print(f"  Fragmento {idx+1} generado tras limpieza.")
                    return [temp_path]
                except Exception as e2:
                    print(f"❌ Error tras limpieza: {e2}")
            # Si sigue fallando, subdividir si es suficientemente largo
            if len(fragment) > 500 and profundidad < 2:
                print(f"  Subdividiendo fragmento {idx+1} en partes más pequeñas...")
                subfrags = []
                sublen = max(200, len(fragment)//3)
                for i in range(0, len(fragment), sublen):
                    sub = fragment[i:i+sublen]
                    try:
                        subfrags.extend(await procesar_fragmento(sub, idx, total, profundidad+1))
                    except Exception as sub_e:
                        print(f"❌ Error en subfragmento de {idx+1}: {sub_e}")
                        try: os.remove(temp_path)
                        except: pass
                        raise
                # Eliminar archivo temporal fallido
                try: os.remove(temp_path)
                except: pass
                return subfrags
            print(f"  Fragmento {idx+1} no se pudo procesar tras todos los intentos. Deteniendo proceso.")
            try: os.remove(temp_path)
            except: pass
            raise RuntimeError(f"Fragmento {idx+1} no se pudo procesar tras todos los intentos.")

    try:
        print(f"🚀 Generando audio en fragmentos con edge-tts y la voz: {voice}")
        for idx, fragment in enumerate(fragments):
            temp_files.extend(await procesar_fragmento(fragment, idx, len(fragments)))

        # Unir todos los fragmentos en un solo archivo MP3 usando ffmpeg
        if len(temp_files) == 1:
            os.rename(temp_files[0], output_file)
        else:
            concat_file = tempfile.mktemp(suffix="_concat.txt")
            with open(concat_file, 'w', encoding='utf-8') as f:
                for temp_path in temp_files:
                    f.write(f"file '{temp_path.replace('\\', '/').replace("'", "'\\''")}'\n")

            # Buscar ffmpeg en .env, luego en backend/ffmpeg/ffmpeg.exe, luego en el PATH
            ffmpeg_env = os.getenv('FFMPEG_PATH')
            ffmpeg_local = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'ffmpeg.exe')
            if ffmpeg_env and os.path.isfile(ffmpeg_env):
                ffmpeg_bin = ffmpeg_env
            elif os.path.isfile(ffmpeg_local):
                ffmpeg_bin = ffmpeg_local
            else:
                ffmpeg_bin = 'ffmpeg'

            ffmpeg_cmd = [
                ffmpeg_bin, '-y', '-f', 'concat', '-safe', '0',
                '-i', concat_file, '-c', 'copy', output_file
            ]
            try:
                subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print(f"\n🎉 Audio completo guardado en: {output_file}")
            except Exception as e:
                print(f"❌ Error al unir los fragmentos con ffmpeg: {e}")
            finally:
                os.remove(concat_file)

    except Exception as e:
        print(f"❌ Error durante la generación del audio con edge-tts: {e}")
    finally:
        # Limpiar archivos temporales
        for temp_path in temp_files:
            try:
                os.remove(temp_path)
            except Exception:
                pass

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
