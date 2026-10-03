#!/bin/bash

# Salir si ocurre un error
set -e

echo "=== J.A.R.V.I.S. Flutter Web Build ==="

# Usar una versión reproducible. Se puede sobreescribir en Vercel con
# FLUTTER_VERSION tras validarla en CI.
FLUTTER_VERSION="${FLUTTER_VERSION:-3.47.5}"

# Descargar Flutter solo si no existe ya
if [ ! -d "flutter" ]; then
  echo "Descargando Flutter SDK ${FLUTTER_VERSION}..."
  git clone https://github.com/flutter/flutter.git -b "${FLUTTER_VERSION}" --depth 1
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
if [ -n "${API_BASE_URL:-}" ]; then
  flutter build web --release --dart-define=API_BASE_URL="${API_BASE_URL}"
else
  flutter build web --release
fi

echo "=== Build completado exitosamente ==="
