
import asyncio
import base64
import edge_tts
import json
import os
import shutil
import tempfile
import subprocess
from html import escape
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from dotenv import load_dotenv
from piper.download_voices import download_voice
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

def get_ffmpeg_bin():
    """Resuelve la ruta de ffmpeg desde .env, una copia local o el PATH."""
    ffmpeg_env = os.getenv('FFMPEG_PATH')
    ffmpeg_local = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'ffmpeg.exe')
    if ffmpeg_env and os.path.isfile(ffmpeg_env):
        return ffmpeg_env
    if os.path.isfile(ffmpeg_local):
        return ffmpeg_local
    return 'ffmpeg'

def is_azure_tts_configured():
    """Indica si Azure Speech está configurado para síntesis."""
    return bool(os.getenv('AZURE_SPEECH_KEY') and os.getenv('AZURE_SPEECH_REGION'))

def get_google_tts_credentials():
    """Carga credenciales de Google Cloud desde archivo o variable inline."""
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    credentials_json = os.getenv('GOOGLE_CLOUD_TTS_CREDENTIALS_JSON')
    scopes = ['https://www.googleapis.com/auth/cloud-platform']

    if credentials_path and os.path.isfile(credentials_path):
        return service_account.Credentials.from_service_account_file(credentials_path, scopes=scopes)

    if credentials_json:
        info = json.loads(credentials_json)
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)

    return None

def is_google_tts_configured():
    """Indica si Google Cloud Text-to-Speech está configurado."""
    return get_google_tts_credentials() is not None

def get_tts_capabilities():
    """Expone capacidades de proveedores para que el frontend tome decisiones."""
    return {
        'azureConfigured': is_azure_tts_configured(),
        'googleConfigured': is_google_tts_configured(),
        'piperConfigured': True,
        'localVoices': list_windows_voices(),
    }

def ensure_piper_voice(voice_code: str):
    """Descarga la voz Piper si no existe en backend/models."""
    models_dir = Path(os.path.join(os.path.dirname(__file__), 'models'))
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / f'{voice_code}.onnx'
    config_path = models_dir / f'{voice_code}.onnx.json'
    if not model_path.exists() or not config_path.exists():
        download_voice(voice_code, models_dir)
    return model_path, config_path

def map_voice_to_piper(voice: str):
    """
    Mapea opciones de UI a voces offline reales de Piper.
    """
    mapping = {
        'es-LATAM-LorenzoOffline': {
            'voice_code': 'es_MX-claude-high',
            'speaker': '0',
            'display_voice': 'es_MX-claude-high',
            'length_scale': '1.18',
        },
        'es-LATAM-CatalinaOffline': {
            'voice_code': 'es_ES-sharvard-medium',
            'speaker': '1',
            'display_voice': 'es_ES-sharvard-medium (F)',
            'length_scale': '1.18',
        },
    }
    return mapping.get(voice)

def map_voice_to_google_tts(voice: str):
    """Mapea voces chilenas a equivalentes disponibles en Google Cloud TTS."""
    mapping = {
        'es-CL-CatalinaNeural': {
            'languageCode': 'es-US',
            'name': 'es-US-Neural2-A',
            'ssmlGender': 'FEMALE',
        },
        'es-CL-LorenzoNeural': {
            'languageCode': 'es-US',
            'name': 'es-US-Neural2-B',
            'ssmlGender': 'MALE',
        },
    }
    return mapping.get(voice)

def merge_mp3_files(temp_files, output_file):
    """Une varios MP3 sin recodificarlos usando ffmpeg concat."""
    if not temp_files:
        raise RuntimeError('No hay fragmentos de audio para unir')

    if len(temp_files) == 1:
        shutil.move(temp_files[0], output_file)
        return

    concat_file = tempfile.mktemp(suffix="_concat.txt")
    try:
        with open(concat_file, 'w', encoding='utf-8') as f:
            for temp_path in temp_files:
                escaped_path = temp_path.replace('\\', '/').replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        ffmpeg_cmd = [
            get_ffmpeg_bin(), '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_file, '-c', 'copy', output_file
        ]
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        raise RuntimeError(f"No se pudo unir el audio final con ffmpeg: {e}") from e
    finally:
        if os.path.exists(concat_file):
            os.remove(concat_file)

def text_to_speech_azure(full_text: str, output_file: str, voice: str):
    """Proveedor de producción via Azure Speech REST API."""
    speech_key = os.getenv('AZURE_SPEECH_KEY')
    speech_region = os.getenv('AZURE_SPEECH_REGION')
    if not speech_key or not speech_region:
        raise RuntimeError('Azure Speech no está configurado. Faltan AZURE_SPEECH_KEY o AZURE_SPEECH_REGION')

    fragments = split_text_by_dot(full_text, max_length=2500)
    temp_files = []
    endpoint = f"https://{speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"

    try:
        print(f"[azure] Generando audio con Azure Speech usando la voz: {voice}")
        for idx, fragment in enumerate(fragments):
            fragment = fragment.strip()
            if not fragment:
                continue

            ssml = (
                "<speak version='1.0' xml:lang='es-CL'>"
                f"<voice name='{voice}'>"
                f"{escape(fragment)}"
                "</voice></speak>"
            )

            response = requests.post(
                endpoint,
                headers={
                    'Ocp-Apim-Subscription-Key': speech_key,
                    'Content-Type': 'application/ssml+xml',
                    'X-Microsoft-OutputFormat': 'audio-24khz-96kbitrate-mono-mp3',
                    'User-Agent': 'pdf-a-audio',
                },
                data=ssml.encode('utf-8'),
                timeout=60,
            )
            response.raise_for_status()

            temp_fd, temp_path = tempfile.mkstemp(suffix=f"_azure_{idx}.mp3")
            os.close(temp_fd)
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            temp_files.append(temp_path)
            print(f"  Fragmento Azure {idx+1}/{len(fragments)} generado.")

        merge_mp3_files(temp_files, output_file)
        print(f"\nAudio completo guardado en: {output_file}")
        return {
            'provider': 'azure-speech',
            'voice_requested': voice,
            'voice_used': voice,
        }
    except requests.HTTPError as e:
        body = ''
        if e.response is not None:
            try:
                body = e.response.text.strip()
            except Exception:
                body = ''
        detail = body or str(e)
        raise RuntimeError(f'Azure Speech devolvió error HTTP: {detail}') from e
    except Exception as e:
        raise RuntimeError(f'Fallo Azure Speech: {e}') from e
    finally:
        for temp_path in temp_files:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

def text_to_speech_google_cloud(full_text: str, output_file: str, voice: str):
    """Proveedor oficial Google Cloud Text-to-Speech via REST."""
    credentials = get_google_tts_credentials()
    if credentials is None:
        raise RuntimeError('Google Cloud TTS no está configurado. Falta GOOGLE_APPLICATION_CREDENTIALS o GOOGLE_CLOUD_TTS_CREDENTIALS_JSON')

    google_voice = map_voice_to_google_tts(voice)
    if google_voice is None:
        raise RuntimeError(f'No existe mapeo de Google Cloud TTS para la voz solicitada: {voice}')

    fragments = split_text_by_dot(full_text, max_length=2500)
    temp_files = []
    credentials.refresh(Request())
    access_token = credentials.token

    try:
        print(f"[google-cloud] Generando audio con Google Cloud TTS para la voz solicitada: {voice}")
        for idx, fragment in enumerate(fragments):
            fragment = fragment.strip()
            if not fragment:
                continue

            response = requests.post(
                'https://texttospeech.googleapis.com/v1/text:synthesize',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json; charset=utf-8',
                },
                json={
                    'input': {'text': fragment},
                    'voice': google_voice,
                    'audioConfig': {'audioEncoding': 'MP3'},
                },
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            audio_content = payload.get('audioContent')
            if not audio_content:
                raise RuntimeError('Google Cloud TTS no devolvió audioContent')

            temp_fd, temp_path = tempfile.mkstemp(suffix=f"_google_{idx}.mp3")
            os.close(temp_fd)
            with open(temp_path, 'wb') as f:
                f.write(base64.b64decode(audio_content))
            temp_files.append(temp_path)
            print(f"  Fragmento Google Cloud {idx+1}/{len(fragments)} generado.")

        merge_mp3_files(temp_files, output_file)
        print(f"\nAudio completo guardado en: {output_file}")
        return {
            'provider': 'google-cloud-tts',
            'voice_requested': voice,
            'voice_used': google_voice['name'],
        }
    except requests.HTTPError as e:
        body = ''
        if e.response is not None:
            try:
                body = e.response.text.strip()
            except Exception:
                body = ''
        detail = body or str(e)
        raise RuntimeError(f'Google Cloud TTS devolvió error HTTP: {detail}') from e
    except Exception as e:
        raise RuntimeError(f'Fallo Google Cloud TTS: {e}') from e
    finally:
        for temp_path in temp_files:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

def text_to_speech_piper(full_text: str, output_file: str, voice: str):
    """Proveedor offline usando Piper TTS y ffmpeg para MP3."""
    piper_voice = map_voice_to_piper(voice)
    if piper_voice is None:
        raise RuntimeError(f'No existe mapeo Piper para la voz solicitada: {voice}')

    model_path, _ = ensure_piper_voice(piper_voice['voice_code'])
    fragments = split_text_by_dot(full_text, max_length=1800)
    temp_files = []

    try:
        print(f"[piper] Generando audio offline con Piper para la voz solicitada: {voice}")
        for idx, fragment in enumerate(fragments):
            fragment = fragment.strip()
            if not fragment:
                continue

            temp_txt = tempfile.mktemp(suffix=f'_piper_{idx}.txt')
            temp_wav = tempfile.mktemp(suffix=f'_piper_{idx}.wav')
            temp_mp3 = tempfile.mktemp(suffix=f'_piper_{idx}.mp3')

            with open(temp_txt, 'w', encoding='utf-8') as f:
                f.write(fragment)

            piper_cmd = [
                os.path.join(os.path.dirname(__file__), 'env', 'Scripts', 'piper.exe')
                if os.path.exists(os.path.join(os.path.dirname(__file__), 'env', 'Scripts', 'piper.exe'))
                else 'piper',
                '--model', str(model_path),
                '--input_file', temp_txt,
                '--output_file', temp_wav,
                '--speaker', piper_voice['speaker'],
                '--length_scale', piper_voice['length_scale'],
                '--data-dir', str(model_path.parent),
            ]
            subprocess.run(piper_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            ffmpeg_cmd = [
                get_ffmpeg_bin(), '-y', '-i', temp_wav,
                '-codec:a', 'libmp3lame', '-q:a', '2', temp_mp3
            ]
            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            temp_files.append(temp_mp3)

            for temp_path in [temp_txt, temp_wav]:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception:
                    pass

            print(f"  Fragmento Piper {idx+1}/{len(fragments)} generado.")

        merge_mp3_files(temp_files, output_file)
        print(f"\nAudio completo guardado en: {output_file}")
        return {
            'provider': 'piper-offline',
            'voice_requested': voice,
            'voice_used': piper_voice['display_voice'],
        }
    except Exception as e:
        raise RuntimeError(f'Fallo Piper offline: {e}') from e
    finally:
        for temp_path in temp_files:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass


def voice_to_locale_prefix(voice: str) -> str:
    """Extrae un locale tipo es-CL desde un nombre de voz edge."""
    voice = (voice or '').strip()
    parts = voice.split('-')
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return 'es-ES'

def list_windows_voices():
    """Lista voces locales disponibles via System.Speech."""
    script = r"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$installed = $synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo }
$installed | ForEach-Object {
    Write-Output ($_.Name + "|" + $_.Culture.Name)
}
$synth.Dispose()
"""

    cmd = [
        'powershell',
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-Command', script,
    ]
    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')

    voices = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or '|' not in line:
            continue
        name, locale = line.split('|', 1)
        voices.append({
            'name': name.strip(),
            'locale': locale.strip(),
        })
    return voices

def text_to_speech_windows(full_text: str, output_file: str, voice: str):
    """Fallback local usando System.Speech en Windows y ffmpeg para MP3."""
    locale = voice_to_locale_prefix(voice)
    lang_prefix = locale.split('-')[0]
    temp_text_path = tempfile.mktemp(suffix="_tts_input.txt")
    temp_wav_path = tempfile.mktemp(suffix="_tts_output.wav")
    temp_script_path = tempfile.mktemp(suffix="_tts_script.ps1")

    script = r"""
Add-Type -AssemblyName System.Speech
$textPath = $args[0]
$wavPath = $args[1]
$locale = $args[2]
$langPrefix = $args[3]
$text = [System.IO.File]::ReadAllText($textPath, [System.Text.Encoding]::UTF8)
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

$installed = $synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo }
$selectedVoice = $installed | Where-Object { $_.Culture.Name -eq $locale } | Select-Object -First 1
if (-not $selectedVoice) {
    $selectedVoice = $installed | Where-Object { $_.Culture.Name -like "$langPrefix-*" } | Select-Object -First 1
}
if (-not $selectedVoice) {
    $availableCultures = ($installed | ForEach-Object { $_.Culture.Name } | Sort-Object -Unique) -join ", "
    throw "No hay una voz instalada compatible con el locale solicitado ($locale). Culturas disponibles: $availableCultures"
}

$synth.SelectVoice($selectedVoice.Name)
$synth.SetOutputToWaveFile($wavPath)
$synth.Speak($text)
$synth.Dispose()
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output ("VOICE_NAME=" + $selectedVoice.Name)
Write-Output ("VOICE_CULTURE=" + $selectedVoice.Culture.Name)
"""

    try:
        print(f"[fallback] Intentando fallback local de Windows para locale: {locale}")
        with open(temp_text_path, 'w', encoding='utf-8') as f:
            f.write(full_text)
        with open(temp_script_path, 'w', encoding='utf-8') as f:
            f.write(script)

        cmd = [
            'powershell',
            '-NoProfile',
            '-ExecutionPolicy', 'Bypass',
            '-File', temp_script_path,
            temp_text_path,
            temp_wav_path,
            locale,
            lang_prefix,
        ]
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')

        if not os.path.exists(temp_wav_path) or os.path.getsize(temp_wav_path) == 0:
            raise RuntimeError('System.Speech no generó un WAV válido')

        ffmpeg_cmd = [
            get_ffmpeg_bin(), '-y', '-i', temp_wav_path,
            '-codec:a', 'libmp3lame', '-q:a', '2', output_file
        ]
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        voice_name = None
        voice_culture = None
        for line in result.stdout.splitlines():
            if line.startswith('VOICE_NAME='):
                voice_name = line.split('=', 1)[1].strip()
            elif line.startswith('VOICE_CULTURE='):
                voice_culture = line.split('=', 1)[1].strip()

        print(f"\nAudio completo guardado en: {output_file}")
        return {
            'provider': 'windows-speech',
            'voice_requested': voice,
            'voice_used': voice_name or voice_culture or locale,
        }
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or '').strip()
        stdout = (e.stdout or '').strip()
        details = stderr or stdout or str(e)
        raise RuntimeError(f"Fallo el fallback local de Windows: {details}") from e
    except Exception as e:
        raise RuntimeError(f"Fallo el fallback local de Windows: {e}") from e
    finally:
        for temp_path in [temp_text_path, temp_wav_path, temp_script_path]:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

async def text_to_speech(text_file: str, output_file: str, voice: str):
    """
    Convierte un archivo de texto a MP3 usando Azure Speech si está configurado,
    luego edge-tts y finalmente fallback local de Windows si existe voz compatible.
    """
    # 1. Leer el texto completo del archivo
    with open(text_file, 'r', encoding='utf-8') as f:
        full_text = f.read()

    if not full_text.strip():
        print("El archivo de texto está vacío. No se generará audio.")
        return {
            'provider': None,
            'voice_requested': voice,
            'voice_used': None,
        }

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
            print(f"[error] Error en fragmento {idx+1} (profundidad {profundidad}): {e}\nIntentando limpiar y reintentar...")
            fragment_limpio = limpiar_texto(fragment)
            if fragment_limpio != fragment:
                try:
                    communicate = edge_tts.Communicate(fragment_limpio, voice)
                    await asyncio.wait_for(communicate.save(temp_path), timeout=60)
                    print(f"  Fragmento {idx+1} generado tras limpieza.")
                    return [temp_path]
                except Exception as e2:
                    print(f"[error] Error tras limpieza: {e2}")
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
                        print(f"[error] Error en subfragmento de {idx+1}: {sub_e}")
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

    if is_azure_tts_configured():
        return text_to_speech_azure(full_text, output_file, voice)

    if is_google_tts_configured():
        return text_to_speech_google_cloud(full_text, output_file, voice)

    return text_to_speech_piper(full_text, output_file, voice)

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
