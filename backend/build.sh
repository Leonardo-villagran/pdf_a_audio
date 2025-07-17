#!/usr/bin/env bash
# exit on error
set -o errexit

# Instalar las dependencias de Python
pip install -r requirements.txt

# Instalar Tesseract y el paquete de idioma español
# Esto es para sistemas basados en Debian/Ubuntu, que es lo que usa Render
apt-get update
apt-get install -y tesseract-ocr tesseract-ocr-spa