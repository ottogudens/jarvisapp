#!/bin/bash

# Salir si ocurre un error
set -e

echo "=== J.A.R.V.I.S. Flutter Web Build ==="

# Descargar Flutter solo si no existe ya
if [ ! -d "flutter" ]; then
  echo "Descargando Flutter SDK (stable)..."
  git clone https://github.com/flutter/flutter.git -b stable --depth 1
else
  echo "Flutter SDK ya existe, reutilizando..."
fi

# Exportar flutter al PATH
export PATH="$PATH:$(pwd)/flutter/bin"

echo "Verificando instalación de Flutter..."
flutter --version

# Desactivar analytics para evitar prompts interactivos
flutter config --no-analytics 2>/dev/null || true
dart --disable-analytics 2>/dev/null || true

echo "Instalando dependencias del proyecto..."
flutter pub get

echo "Construyendo la versión Web..."
flutter build web --release

echo "=== Build completado exitosamente ==="
