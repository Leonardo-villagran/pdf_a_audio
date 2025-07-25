
# Frontend - PDF a Audio

> **Nota:** El backend del proyecto utiliza Python 3.13.2 en un entorno virtual (`backend/env`).
> El backend ahora maneja robustamente la conversión de texto a audio: divide el texto en fragmentos, limpia y subdivide fragmentos problemáticos, y detiene el proceso si algún fragmento no puede ser procesado tras todos los intentos. La variable FFMPEG_PATH en el archivo `.env` del backend debe estar correctamente configurada.

> **Advertencia:** Actualmente este frontend está pensado para funcionar en Windows junto al backend del proyecto. El soporte para otras plataformas podría añadirse en el futuro.

Este frontend es una aplicación React + TypeScript creada con Vite. Permite subir archivos PDF y convertirlos a audio usando el backend Flask.

## Requisitos
- Node.js >= 16
- npm >= 7

## Instalación y ejecución local

1. Navega a la carpeta `frontend`:
   ```sh
   cd frontend
   ```
2. Instala las dependencias:
   ```sh
   npm install
   ```
3. Crea un archivo `.env` en la raíz de `frontend` con la URL de tu backend:
   ```env
   VITE_API_BASE_URL=http://localhost:5000
   ```
   (Cambia la URL si tu backend está en otro host o puerto)
4. Inicia la aplicación:
   ```sh
   npm start
   ```

La app estará disponible en `http://localhost:3000`.

## Despliegue en Render

- **Servicio:** Static Site
- **Root Directory:** `frontend`
- **Build Command:** `npm install && npm run build`
- **Publish Directory:** `dist`
- **Variable de entorno:**
  - `VITE_API_BASE_URL` con la URL de tu backend desplegado

---

Este proyecto utiliza Vite para desarrollo rápido y recarga en caliente (HMR). Puedes personalizar la configuración en `vite.config.ts` y los estilos en `src/App.css` o `src/index.css`.
