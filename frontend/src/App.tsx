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

const countryMap: { [key: string]: string } = {
  'AR': 'Argentina', 'BO': 'Bolivia', 'CL': 'Chile', 'CO': 'Colombia',
  'CR': 'Costa Rica', 'CU': 'Cuba', 'DO': 'Rep. Dominicana', 'EC': 'Ecuador',
  'SV': 'El Salvador', 'GQ': 'Guinea Ecuatorial', 'GT': 'Guatemala', 'HN': 'Honduras',
  'MX': 'México', 'NI': 'Nicaragua', 'PA': 'Panamá', 'PY': 'Paraguay',
  'PE': 'Perú', 'PR': 'Puerto Rico', 'ES': 'España', 'US': 'EE.UU.',
  'UY': 'Uruguay', 'VE': 'Venezuela'
};

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
  const [selectedVoice, setSelectedVoice] = useState<string>('');
  const [extractedText, setExtractedText] = useState<string>('');
  const [audioFileName, setAudioFileName] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingAudio, setLoadingAudio] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchVoices = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/voices`);
        const availableVoices: Voice[] = response.data;
        // Filtrar para que solo se muestren las voces en español
        const spanishVoices = availableVoices.filter(v => v.Locale.startsWith('es'));
        setVoices(spanishVoices);

      } catch (err) {
        setError('Error al cargar las voces.');
        console.error(err);
      }
    };
    fetchVoices();
  }, []);

  useEffect(() => {
    if (voices.length > 0) {
        // Prioritize a specific voice if available, e.g., Lorenzo for Spanish (Chile)
        const defaultVoice = voices.find(v => v.ShortName === 'es-CL-LorenzoNeural') || voices[0];
        setSelectedVoice(defaultVoice.ShortName);
    }
  }, [voices]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      setPdfFile(event.target.files[0]);
      setExtractedText('');
      setAudioFileName(null);
      setError(null);
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

    setLoadingAudio(true);
    setError(null);
    setAudioFileName(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/text-to-audio`, {
        text: extractedText,
        voice: selectedVoice
      }, {
        headers: { 'Content-Type': 'application/json' }
      });
      
      if (response.data.audio) {
        setAudioFileName(response.data.audio);
      } else {
        setError(response.data.error || 'Ocurrió un error desconocido al generar el audio.');
      }
    } catch (err) {
      setError('Error al generar el audio.');
      console.error(err);
    } finally {
      setLoadingAudio(false);
    }
  };
  
  // Todas las voces ya están filtradas para ser solo en español
  const filteredVoices = voices;

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
          <button onClick={handleTextToAudio} disabled={loadingAudio || !extractedText}>
            {loadingAudio ? 'Generando...' : 'Convertir a Audio'}
          </button>
          {loadingAudio && <div className="loader"></div>}
          {audioUrl && !loadingAudio && (
            <div className="result">
              <h3>¡Audio listo!</h3>
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
