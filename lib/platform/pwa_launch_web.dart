import 'dart:html' as html;

/// Detecta una ventana abierta desde la instalación PWA, incluidos los casos
/// en que el navegador no conserva el parámetro de inicio del manifest.
bool get launchedAsInstalledPwa {
  final fromManifest = Uri.base.queryParameters['source'] == 'pwa';
  final displayStandalone = html.window.matchMedia('(display-mode: standalone)').matches;
  final dynamic navigator = html.window.navigator;
  final iosStandalone = navigator.standalone == true;
  return fromManifest || displayStandalone || iosStandalone;
}
