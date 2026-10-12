import 'dart:html' as html;

/// Detecta una ventana abierta desde la instalación PWA.
///
/// `display-mode: standalone` está soportado por navegadores PWA modernos,
/// incluido Safari instalado. Evitamos acceder dinámicamente a
/// `navigator.standalone`, ya que dicha propiedad no existe en Chrome y
/// Dart2JS la interpreta como una llamada, provocando un NoSuchMethodError.
bool get launchedAsInstalledPwa {
  final fromManifest = Uri.base.queryParameters['source'] == 'pwa';
  final displayStandalone = html.window.matchMedia('(display-mode: standalone)').matches;
  return fromManifest || displayStandalone;
}
