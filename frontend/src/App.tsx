import React, { useState, useEffect } from 'react';
import axios from 'axios';

// La URL base de la API. Para desarrollo, será una ruta relativa.
// En producción (Render), se establecerá a través de una variable de entorno.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
import './App.css';

interface Voice {
  Name: string;
  ShortName: string;
  Gender: string;
  Locale: string;
}

interface LocalVoice {
  name: string;
  locale: string;
}

interface TtsCapabilitiesResponse {
  azureConfigured: boolean;
  googleConfigured: boolean;
  piperConfigured: boolean;
  localVoices: LocalVoice[];
}

interface TextToAudioResponse {
  audio?: string;
  error?: string;
  provider?: string | null;
  voiceRequested?: string | null;
  voiceUsed?: string | null;
}

interface ApiErrorResponse {
  error?: string;
}

interface BrowserVoice {
  name: string;
  lang: string;
  voiceURI: string;
}

const countryMap: { [key: string]: string } = {
  'AR': 'Argentina', 'BO': 'Bolivia', 'CL': 'Chile', 'CO': 'Colombia',
  'CR': 'Costa Rica', 'CU': 'Cuba', 'DO': 'Rep. Dominicana', 'EC': 'Ecuador',
  'SV': 'El Salvador', 'GQ': 'Guinea Ecuatorial', 'GT': 'Guatemala', 'HN': 'Honduras',
  'MX': 'México', 'NI': 'Nicaragua', 'PA': 'Panamá', 'PY': 'Paraguay',
  'PE': 'Perú', 'PR': 'Puerto Rico', 'ES': 'España', 'US': 'EE.UU.',
  'UY': 'Uruguay', 'VE': 'Venezuela'
};

const OFFLINE_VOICE_OPTIONS: Voice[] = [
  {
    Name: 'Piper Latino Masculino',
    ShortName: 'es-LATAM-LorenzoOffline',
    Gender: 'Male',
    Locale: 'es-MX',
  },
  {
    Name: 'Piper Femenino',
    ShortName: 'es-LATAM-CatalinaOffline',
    Gender: 'Female',
    Locale: 'es-ES',
  },
];

function formatVoiceName(voice: Voice): string {
  const { Name, Gender } = voice;
  const localeParts = voice.Locale.split('-');
  const countryCode = localeParts[1];
  const countryName = countryMap[countryCode] || countryCode;
  
  // Extraer solo el nombre de la persona, ej: "Lorenzo" de "Microsoft Server Speech Text to Speech Voice (es-CL, LorenzoNeural)"
  const nameMatch = Name.match(/(\w+)Neural/);
  const cleanName = nameMatch ? nameMatch[1] : voice.ShortName.split('-').pop()?.replace('Neural', '');

  const genderSpanish = Gender === 'Male' ? 'Masculino' : 'Femenino';

  return `${countryName}: ${cleanName} (${genderSpanish})`;
}

function App() {
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [localVoices, setLocalVoices] = useState<LocalVoice[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<string>('');
  const [extractedText, setExtractedText] = useState<string>('');
  const [audioFileName, setAudioFileName] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingAudio, setLoadingAudio] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [audioProviderInfo, setAudioProviderInfo] = useState<string | null>(null);
  const [fallbackWarning, setFallbackWarning] = useState<string | null>(null);
  const [hasCompatibleLocalFallback, setHasCompatibleLocalFallback] = useState<boolean>(false);
  const [azureConfigured, setAzureConfigured] = useState<boolean>(false);
  const [googleConfigured, setGoogleConfigured] = useState<boolean>(false);
  const [piperConfigured, setPiperConfigured] = useState<boolean>(false);
  const [browserVoices, setBrowserVoices] = useState<BrowserVoice[]>([]);
  const [browserTtsInfo, setBrowserTtsInfo] = useState<string | null>(null);
  const [isBrowserSpeaking, setIsBrowserSpeaking] = useState<boolean>(false);

  useEffect(() => {
    const fetchVoices = async () => {
      try {
        const [remoteResponse, localResponse] = await Promise.all([
          axios.get<Voice[]>(`${API_BASE_URL}/api/voices`),
          axios.get<TtsCapabilitiesResponse>(`${API_BASE_URL}/api/tts-capabilities`)
        ]);
        void remoteResponse;
        setVoices(OFFLINE_VOICE_OPTIONS);
        setLocalVoices(localResponse.data.localVoices);
        setAzureConfigured(localResponse.data.azureConfigured);
        setGoogleConfigured(localResponse.data.googleConfigured);
        setPiperConfigured(localResponse.data.piperConfigured);
      } catch (err) {
        setError('Error al cargar las voces.');
        console.error(err);
      }
    };
    fetchVoices();
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return;
    }

    const loadBrowserVoices = () => {
      const voices = window.speechSynthesis.getVoices().map((voice) => ({
        name: voice.name,
        lang: voice.lang,
        voiceURI: voice.voiceURI,
      }));
      setBrowserVoices(voices);
    };

    loadBrowserVoices();
    window.speechSynthesis.onvoiceschanged = loadBrowserVoices;

    return () => {
      window.speechSynthesis.onvoiceschanged = null;
    };
  }, []);

  useEffect(() => {
    if (!selectedVoice) {
      setFallbackWarning(null);
      setHasCompatibleLocalFallback(false);
      return;
    }

    const voice = voices.find((item) => item.ShortName === selectedVoice);
    if (!voice) {
      setFallbackWarning(null);
      setHasCompatibleLocalFallback(false);
      return;
    }

    const exactLocale = voice.Locale;
    const baseLanguage = exactLocale.split('-')[0];
    const exactMatch = localVoices.find((item) => item.locale.toLowerCase() === exactLocale.toLowerCase());
    const languageMatch = localVoices.find((item) => item.locale.toLowerCase().startsWith(`${baseLanguage.toLowerCase()}-`));

    if (exactMatch) {
      setFallbackWarning(`Fallback local disponible para ${exactLocale} con la voz ${exactMatch.name}.`);
      setHasCompatibleLocalFallback(true);
      return;
    }

    if (languageMatch) {
      setFallbackWarning(`No hay voz local exacta para ${exactLocale}. Si falla el proveedor remoto, se usará la voz local ${languageMatch.name} (${languageMatch.locale}).`);
      setHasCompatibleLocalFallback(true);
      return;
    }

    if (azureConfigured) {
      setFallbackWarning(`Azure Speech está configurado para ${exactLocale}. Si fallan los proveedores gratuitos, se usará el proveedor de producción.`);
      setHasCompatibleLocalFallback(false);
      return;
    }

    if (googleConfigured) {
      setFallbackWarning(`Google Cloud TTS está configurado. Para ${exactLocale} se usará una voz equivalente de Google Cloud porque no hay voz chilena exacta en el mapeo actual.`);
      setHasCompatibleLocalFallback(false);
      return;
    }

    if (piperConfigured) {
      setFallbackWarning(`Piper offline está disponible sin API key. Para ${exactLocale} se usará una voz local en español equivalente y se generará MP3.`);
      setHasCompatibleLocalFallback(false);
      return;
    }

    setFallbackWarning(`No hay backend TTS compatible configurado para ${exactLocale}. Puedes usar la lectura local del navegador sin API key.`);
    setHasCompatibleLocalFallback(false);
  }, [selectedVoice, voices, localVoices, azureConfigured, googleConfigured, piperConfigured]);

  const findBrowserVoiceForSelection = (): SpeechSynthesisVoice | null => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return null;
    }

    const availableVoices = window.speechSynthesis.getVoices();
    if (!availableVoices.length) {
      return null;
    }

    const requestedLocale = selectedVoice.includes('LATAM') ? 'es-MX' : 'es';
    const exact = availableVoices.find((voice) => voice.lang.toLowerCase() === requestedLocale.toLowerCase());
    if (exact) {
      return exact;
    }

    const spanish = availableVoices.find((voice) => voice.lang.toLowerCase().startsWith('es'));
    return spanish || null;
  };

  useEffect(() => {
    if (voices.length > 0) {
        const defaultVoice = voices.find(v => v.ShortName === 'es-LATAM-LorenzoOffline') || voices[0];
        setSelectedVoice(defaultVoice.ShortName);
    }
  }, [voices]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setPdfFile(event.target.files[0]);
      setExtractedText('');
      setAudioFileName(null);
      setError(null);
      setAudioProviderInfo(null);
    }
  };

  const handleExtractText = async () => {
    if (!pdfFile) {
      setError('Por favor, selecciona un archivo PDF primero.');
      return;
    }
    
    const formData = new FormData();
    formData.append('pdf', pdfFile);
    // El idioma siempre será español
    formData.append('lang', 'spa');

    setLoading(true);
    setError(null);
    setExtractedText('');
    setAudioFileName(null);
    setAudioProviderInfo(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/pdf-to-text`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setExtractedText(response.data.text);
    } catch (err) {
      setError('Error al extraer el texto del PDF.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleTextToAudio = async () => {
    if (!extractedText || !selectedVoice) {
      setError('No hay texto para convertir o no se ha seleccionado una voz.');
      return;
    }

    if (!canAttemptAudioGeneration && canUseBrowserTts) {
      setError(null);
      handleBrowserSpeak();
      return;
    }

    setLoadingAudio(true);
    setError(null);
    setAudioFileName(null);
    setAudioProviderInfo(null);

    try {
      const response = await axios.post<TextToAudioResponse>(`${API_BASE_URL}/api/text-to-audio`, {
        text: extractedText,
        voice: selectedVoice
      }, {
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.data.audio) {
        setAudioFileName(response.data.audio);
        if (response.data.provider === 'edge-tts') {
          setAudioProviderInfo(`Audio generado con edge-tts usando la voz ${response.data.voiceUsed}.`);
        } else if (response.data.provider === 'azure-speech') {
          setAudioProviderInfo(`Audio generado con Azure Speech usando la voz ${response.data.voiceUsed}.`);
        } else if (response.data.provider === 'google-cloud-tts') {
          setAudioProviderInfo(`Audio generado con Google Cloud TTS. Voz solicitada: ${response.data.voiceRequested}. Voz usada por Google: ${response.data.voiceUsed}.`);
        } else if (response.data.provider === 'piper-offline') {
          setAudioProviderInfo(`Audio generado con Piper offline. Voz solicitada: ${response.data.voiceRequested}. Voz usada localmente: ${response.data.voiceUsed}.`);
        } else if (response.data.provider === 'windows-speech') {
          setAudioProviderInfo(`Audio generado con fallback local de Windows. Voz solicitada: ${response.data.voiceRequested}. Voz usada localmente: ${response.data.voiceUsed}.`);
        }
      } else {
        setError(response.data.error || 'Ocurrió un error desconocido al generar el audio.');
      }
    } catch (err) {
      if (axios.isAxiosError<ApiErrorResponse>(err)) {
        const backendError = err.response?.data?.error;
        if (canUseBrowserTts) {
          setError(`No se pudo generar MP3 en backend. Se activó la lectura local del navegador. Detalle: ${backendError || 'sin detalle'}`);
          handleBrowserSpeak();
        } else {
          setError(backendError || 'Error al generar el audio.');
        }
      } else {
        setError('Error al generar el audio.');
      }
      console.error(err);
    } finally {
      setLoadingAudio(false);
    }
  };

  const handleBrowserSpeak = () => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window) || !extractedText) {
      setError('El navegador no soporta síntesis de voz local.');
      return;
    }

    window.speechSynthesis.cancel();
    const voice = findBrowserVoiceForSelection();
    const utterance = new SpeechSynthesisUtterance(extractedText);
    utterance.lang = voice?.lang || 'es-ES';
    if (voice) {
      utterance.voice = voice;
      setBrowserTtsInfo(`Lectura local del navegador usando la voz ${voice.name} (${voice.lang}). Este modo no genera MP3.`);
    } else {
      setBrowserTtsInfo('Lectura local del navegador sin voz española exacta. Este modo no genera MP3.');
    }

    utterance.onstart = () => setIsBrowserSpeaking(true);
    utterance.onend = () => setIsBrowserSpeaking(false);
    utterance.onerror = () => {
      setIsBrowserSpeaking(false);
      setError('Falló la lectura local del navegador.');
    };

    window.speechSynthesis.speak(utterance);
  };

  const handleBrowserStop = () => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setIsBrowserSpeaking(false);
  };
  
  // Todas las voces mostradas corresponden a opciones offline reales disponibles
  const filteredVoices = voices;
  const canAttemptAudioGeneration = Boolean(extractedText) && !loadingAudio && (azureConfigured || googleConfigured || piperConfigured || hasCompatibleLocalFallback);
  const browserSpanishVoices = browserVoices.filter((voice) => voice.lang.toLowerCase().startsWith('es'));
  const canUseBrowserTts = Boolean(extractedText) && browserSpanishVoices.length > 0;

  const audioUrl = audioFileName ? `${API_BASE_URL}/api/output/${audioFileName}` : null;

  return (
    <div className="App">
      <h1 className="titulo-principal">PDF a Audio</h1>
      <div className="app-container">
        <div className="card">
          <h2>1. Cargar PDF y Extraer Texto</h2>
          <div className="form-group">
            <label htmlFor="pdf">Archivo PDF:</label>
            <input type="file" id="pdf" accept="application/pdf" onChange={handleFileChange} />
          </div>
          <button onClick={handleExtractText} disabled={loading || !pdfFile}>
            {loading ? 'Extrayendo...' : 'Extraer Texto'}
          </button>
          {loading && <div className="loader"></div>}
        </div>

        <div className="card">
          <h2>2. Editar Texto y Generar Audio</h2>
          <div className="form-group">
            <label htmlFor="extracted-text">Texto Extraído:</label>
            <textarea
              id="extracted-text"
              value={extractedText}
              onChange={e => setExtractedText(e.target.value)}
              placeholder="El texto del PDF aparecerá aquí después de la extracción..."
              disabled={!extractedText}
            />
          </div>
          <div className="form-group">
            <label htmlFor="voice">Voz:</label>
            <select id="voice" value={selectedVoice} onChange={e => setSelectedVoice(e.target.value)} required>
              <option value="">Selecciona una voz</option>
              {filteredVoices.map(voice => (
                <option key={voice.ShortName} value={voice.ShortName}>{formatVoiceName(voice)}</option>
              ))}
            </select>
          </div>
          {fallbackWarning && <p className="fallback-warning">{fallbackWarning}</p>}
          <button onClick={handleTextToAudio} disabled={!canAttemptAudioGeneration && !canUseBrowserTts}>
            {loadingAudio ? 'Generando...' : canAttemptAudioGeneration ? 'Generar MP3' : 'Escuchar Texto'}
          </button>
          <button type="button" onClick={handleBrowserSpeak} disabled={!canUseBrowserTts || isBrowserSpeaking}>
            {isBrowserSpeaking ? 'Reproduciendo...' : 'Escuchar en Navegador'}
          </button>
          <button type="button" onClick={handleBrowserStop} disabled={!isBrowserSpeaking}>
            Detener Voz
          </button>
          {browserTtsInfo && <p className="fallback-warning">{browserTtsInfo}</p>}
          {loadingAudio && <div className="loader"></div>}
          {audioUrl && !loadingAudio && (
            <div className="result">
              <h3>¡Audio listo!</h3>
              {audioProviderInfo && <p>{audioProviderInfo}</p>}
              <audio controls src={audioUrl}></audio>
              <a href={audioUrl} download>
                Descargar MP3
              </a>
            </div>
          )}
        </div>
      </div>
      {error && <p className="error">{error}</p>}
    </div>
  );
}

export default App;
