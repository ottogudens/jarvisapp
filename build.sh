#!/bin/bash

# Salir si ocurre un error
set -e

echo "Descargando e instalando Flutter (stable)..."
git clone https://github.com/flutter/flutter.git -b stable --depth 1

# Exportar flutter al PATH
export PATH="$PATH:`pwd`/flutter/bin"

echo "Verificando instalación de Flutter..."
flutter --version

echo "Instalando dependencias del proyecto..."
flutter pub get

echo "Construyendo la versión Web..."
flutter build web --release

echo "¡Construcción terminada exitosamente!"
