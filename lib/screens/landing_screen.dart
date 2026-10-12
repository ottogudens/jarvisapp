import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../brand.dart';
import 'login_screen.dart';

/// Página pública de producto. Mantiene el lenguaje visual de SKALE IA y
/// dirige a acceso/registro sin requerir autenticación.
class LandingScreen extends StatefulWidget {
  const LandingScreen({super.key});

  @override
  State<LandingScreen> createState() => _LandingScreenState();
}

class _LandingScreenState extends State<LandingScreen> {
  final _scrollController = ScrollController();
  final _solutionsKey = GlobalKey();
  final _howKey = GlobalKey();

  @override
  void dispose() { _scrollController.dispose(); super.dispose(); }

  void _goTo(GlobalKey key) {
    final context = key.currentContext;
    if (context != null) Scrollable.ensureVisible(context, duration: const Duration(milliseconds: 450), curve: Curves.easeOutCubic);
  }

  void _access({bool register = false}) => Navigator.of(context).push(MaterialPageRoute(builder: (_) => LoginScreen(openRegistration: register)));

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: BonsoBrand.ink,
    body: SafeArea(
      child: Stack(children: [
        SingleChildScrollView(
          controller: _scrollController,
          child: Column(children: [
            _header(),
            _hero(),
            _intro(),
            Container(key: _solutionsKey, child: _solutions()),
            _proof(),
            Container(key: _howKey, child: _howItWorks()),
            _cta(),
            _footer(),
          ]),
        ),
      ]),
    ),
  );

  Widget _header() => _Section(
    child: LayoutBuilder(builder: (context, constraints) {
      final compact = constraints.maxWidth < 720;
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 18),
        child: Wrap(alignment: WrapAlignment.spaceBetween, crossAxisAlignment: WrapCrossAlignment.center, runSpacing: 12, children: [
          Row(mainAxisSize: MainAxisSize.min, children: [
            Container(width: 34, height: 34, decoration: BoxDecoration(color: BonsoBrand.lime, borderRadius: BorderRadius.circular(10)), child: const Icon(Icons.auto_awesome, color: BonsoBrand.ink, size: 19)),
            const SizedBox(width: 10),
            const Text('BONSO', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, letterSpacing: 2)),
            const SizedBox(width: 9),
            const Text('por SKALE IA', style: TextStyle(color: Colors.white54, fontSize: 12)),
          ]),
          if (!compact) Row(mainAxisSize: MainAxisSize.min, children: [
            TextButton(onPressed: () => _goTo(_solutionsKey), child: const Text('Soluciones')),
            TextButton(onPressed: () => _goTo(_howKey), child: const Text('Cómo funciona')),
          ]),
          Row(mainAxisSize: MainAxisSize.min, children: [
            TextButton(onPressed: _access, child: const Text('Ingresar')),
            const SizedBox(width: 6),
            ElevatedButton(onPressed: () => _access(register: true), style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.lime, foregroundColor: BonsoBrand.ink, minimumSize: const Size(0, 42)), child: const Text('Prueba gratis')),
          ]),
        ]),
      );
    }),
  );

  Widget _hero() => _Section(
    child: Padding(
      padding: const EdgeInsets.only(top: 58, bottom: 80),
      child: LayoutBuilder(builder: (context, constraints) {
        final desktop = constraints.maxWidth >= 860;
        final message = Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const _Eyebrow('✳  IA QUE TRABAJA CON TU NEGOCIO'),
          const SizedBox(height: 22),
          Text('Tu operación,\ncon una IA que\nsí conoce el contexto.', style: TextStyle(fontSize: desktop ? 62 : 44, height: .98, letterSpacing: -2.2, color: BonsoBrand.text, fontWeight: FontWeight.w800)),
          const SizedBox(height: 24),
          ConstrainedBox(constraints: const BoxConstraints(maxWidth: 570), child: const Text('Bonso convierte documentos, plantillas, imágenes, páginas web y conversaciones en conocimiento útil. Tu equipo responde, crea y automatiza desde un asistente personalizado.', style: TextStyle(color: Colors.white70, fontSize: 18, height: 1.5))),
          const SizedBox(height: 30),
          Wrap(spacing: 12, runSpacing: 12, children: [
            ElevatedButton.icon(onPressed: () => _access(register: true), icon: const Icon(Icons.arrow_forward), label: const Text('Crear cuenta gratis'), style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.lime, foregroundColor: BonsoBrand.ink, minimumSize: const Size(0, 52), padding: const EdgeInsets.symmetric(horizontal: 20))),
            OutlinedButton(onPressed: _access, style: OutlinedButton.styleFrom(foregroundColor: Colors.white, side: BorderSide(color: Colors.white.withOpacity(.35)), minimumSize: const Size(0, 52), padding: const EdgeInsets.symmetric(horizontal: 20)), child: const Text('Ya tengo una cuenta')),
          ]),
          const SizedBox(height: 16),
          const Text('7 días sin costo · 5.000 tokens diarios · Sin tarjeta', style: TextStyle(color: BonsoBrand.aqua, fontSize: 13)),
        ]);
        final visual = Container(
          width: desktop ? 370 : double.infinity,
          margin: EdgeInsets.only(top: desktop ? 0 : 42),
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(color: BonsoBrand.surface, borderRadius: BorderRadius.circular(24), border: Border.all(color: BonsoBrand.aqua.withOpacity(.28))),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('BONSO / EN ACCIÓN', style: TextStyle(color: BonsoBrand.aqua, fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 1.2)),
            const SizedBox(height: 22),
            _chatBubble('Analiza este informe, el VIN y los datos del scanner.', false),
            const SizedBox(height: 14),
            _chatBubble('Listo. Encontré los códigos relevantes, posibles causas y el siguiente diagnóstico.', true),
            const SizedBox(height: 20),
            Row(children: const [Icon(Icons.bolt, color: BonsoBrand.lime, size: 18), SizedBox(width: 8), Text('Conocimiento + documentos + integraciones', style: TextStyle(color: Colors.white70, fontSize: 12))]),
          ]),
        );
        return desktop ? Row(crossAxisAlignment: CrossAxisAlignment.center, children: [Expanded(child: message), const SizedBox(width: 48), visual]) : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [message, visual]);
      }),
    ),
  );

  Widget _intro() => Container(
    color: BonsoBrand.surface,
    child: _Section(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 64),
        child: LayoutBuilder(
          builder: (context, constraints) => constraints.maxWidth >= 760
              ? Row(children: [const Expanded(child: _Eyebrow('01  —  QUÉ ES BONSO')), const SizedBox(width: 40), Expanded(flex: 2, child: _introText())])
              : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [const _Eyebrow('01  —  QUÉ ES BONSO'), const SizedBox(height: 20), _introText()]),
        ),
      ),
    ),
  );

  Widget _introText() => const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text('Una IA que entiende\ntu forma de trabajar.', style: TextStyle(color: BonsoBrand.text, fontSize: 34, fontWeight: FontWeight.w700, height: 1.08)),
    SizedBox(height: 14),
    Text('No es un chat genérico. Cada asistente combina su perfil, instrucciones, documentos, fuentes web y herramientas para responder según el contexto real de tu operación.', style: TextStyle(color: Colors.white70, fontSize: 16, height: 1.5)),
  ]);

  Widget _solutions() => _Section(child: Padding(padding: const EdgeInsets.symmetric(vertical: 80), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const _Eyebrow('02  —  LO QUE HACE'),
    const SizedBox(height: 16),
    const Text('Todo conectado.\nTodo bajo control.', style: TextStyle(color: BonsoBrand.text, fontSize: 42, height: 1.05, fontWeight: FontWeight.w700)),
    const SizedBox(height: 16),
    const Text('Una base organizada para que tu asistente trabaje con información útil, segura y actualizable.', style: TextStyle(color: Colors.white70, fontSize: 16)),
    const SizedBox(height: 30),
    LayoutBuilder(builder: (context, constraints) { final columns = constraints.maxWidth > 900 ? 3 : constraints.maxWidth > 560 ? 2 : 1; final width = (constraints.maxWidth - ((columns - 1) * 14)) / columns; return Wrap(spacing: 14, runSpacing: 14, children: [
      _solutionCard(width, '01 / MEMORIA', 'Conocimiento que se consulta', 'Sube PDF, Word, Excel, CSV e imágenes. Bonso los indexa para responder con citas y contexto.', Icons.menu_book_outlined),
      _solutionCard(width, '02 / DOCUMENTOS', 'Proyectos ordenados y accionables', 'Organiza carpetas, archivos, plantillas y páginas web. Edita, reutiliza, mueve o recupera contenido desde la papelera.', Icons.folder_copy_outlined),
      _solutionCard(width, '03 / ASISTENTES', 'Perfiles listos para cada trabajo', 'Crea asistentes con instrucciones y capacidades propias: soporte, ventas, operaciones o diagnóstico automotriz.', Icons.psychology_alt_outlined),
      _solutionCard(width, '04 / CANALES', 'La misma memoria, donde te escriban', 'Atiende desde la aplicación y Telegram con el mismo conocimiento. Conecta WhatsApp y redes sociales según tu plan.', Icons.forum_outlined),
      _solutionCard(width, '05 / INTEGRACIONES', 'Herramientas conectadas a tu flujo', 'Centraliza Gmail, Calendar, Meta, TikTok, MikroTik, Home Assistant y MQTT con guías de conexión por servicio.', Icons.extension_outlined),
      _solutionCard(width, '06 / CONTROL', 'Seguridad y operación medible', 'Gestiona perfiles, permisos, tokens, límites de documentos, planes, facturación y actividad desde un solo lugar.', Icons.insights_outlined),
    ]); }),
  ])));

  Widget _proof() => Container(color: BonsoBrand.surfaceRaised, child: _Section(child: Padding(padding: const EdgeInsets.symmetric(vertical: 42), child: Wrap(alignment: WrapAlignment.spaceAround, runSpacing: 24, children: const [
    _Stat('PDF · Word · Excel', 'conocimiento desde tus archivos'), _Stat('OCR', 'contenido legible desde imágenes'), _Stat('9 integraciones', 'canales y herramientas conectables'), _Stat('SKALE IA', 'tecnología aplicada'),
  ]))));

  Widget _howItWorks() => _Section(child: Padding(padding: const EdgeInsets.symmetric(vertical: 80), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const _Eyebrow('03  —  CÓMO FUNCIONA'),
    const SizedBox(height: 16),
    const Text('De tu necesidad\na un asistente útil.', style: TextStyle(color: BonsoBrand.text, fontSize: 42, height: 1.05, fontWeight: FontWeight.w700)),
    const SizedBox(height: 36),
    LayoutBuilder(builder: (context, constraints) { final wide = constraints.maxWidth > 760; final steps = [
      _step('01', 'Configura', 'Crea tu organización y elige o diseña el perfil de asistente que necesitas.'),
      _step('02', 'Entrega contexto', 'Carga documentos, imágenes, plantillas y fuentes web; ordénalos por proyecto o carpeta.'),
      _step('03', 'Conecta', 'Activa Telegram, correo, calendario, redes o equipos según las integraciones de tu plan.'),
      _step('04', 'Trabaja y mejora', 'Consulta, crea documentos, revisa el uso y ajusta las instrucciones cuando tu operación cambie.'),
    ]; return wide ? Row(children: steps.map((step) => Expanded(child: step)).toList()) : Column(children: steps); }),
  ])));

  Widget _cta() => Container(
    color: BonsoBrand.lime,
    child: _Section(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 64),
        child: LayoutBuilder(
          builder: (context, constraints) => constraints.maxWidth > 760
              ? Row(children: [Expanded(child: _ctaText()), const SizedBox(width: 32), _ctaButtons()])
              : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [_ctaText(), const SizedBox(height: 24), _ctaButtons()]),
        ),
      ),
    ),
  );
  Widget _ctaText() => const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('Empieza con una\nconversación útil.', style: TextStyle(fontSize: 42, height: 1.04, fontWeight: FontWeight.w800, color: BonsoBrand.ink)), SizedBox(height: 10), Text('Crea tu cuenta y prepara tu primer asistente en minutos.', style: TextStyle(fontSize: 16, color: BonsoBrand.ink))]);
  Widget _ctaButtons() => Wrap(spacing: 10, runSpacing: 10, children: [ElevatedButton(onPressed: () => _access(register: true), style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.ink, foregroundColor: Colors.white, minimumSize: const Size(0, 50)), child: const Text('Crear cuenta gratis')), OutlinedButton(onPressed: () => launchUrl(Uri.parse('https://www.skale.cl/#contacto'), mode: LaunchMode.externalApplication), style: OutlinedButton.styleFrom(foregroundColor: BonsoBrand.ink, side: const BorderSide(color: BonsoBrand.ink), minimumSize: const Size(0, 50)), child: const Text('Hablar con SKALE'))]);

  Widget _footer() => _Section(child: Padding(padding: const EdgeInsets.symmetric(vertical: 34), child: Wrap(alignment: WrapAlignment.spaceBetween, runSpacing: 12, children: const [Text('BONSO  ·  Tecnología aplicada por SKALE IA', style: TextStyle(color: Colors.white70)), Text('Hecho para avanzar  ✳', style: TextStyle(color: BonsoBrand.aqua))])));
  Widget _chatBubble(String message, bool assistant) => Align(alignment: assistant ? Alignment.centerLeft : Alignment.centerRight, child: Container(padding: const EdgeInsets.all(13), decoration: BoxDecoration(color: assistant ? BonsoBrand.aqua.withOpacity(.18) : Colors.white.withOpacity(.07), borderRadius: BorderRadius.circular(14)), child: Text(message, style: const TextStyle(color: Colors.white, height: 1.35))));
  Widget _solutionCard(double width, String eyebrow, String title, String description, IconData icon) => SizedBox(
    width: width,
    child: Container(
      height: 280,
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(color: BonsoBrand.surface, borderRadius: BorderRadius.circular(18), border: Border.all(color: Colors.white.withOpacity(.08))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: BonsoBrand.aqua, size: 30),
        const Spacer(),
        Text(eyebrow, style: const TextStyle(color: BonsoBrand.aqua, fontSize: 11, letterSpacing: 1.1)),
        const SizedBox(height: 10),
        Text(title, style: const TextStyle(color: Colors.white, fontSize: 21, height: 1.1, fontWeight: FontWeight.bold)),
        const SizedBox(height: 10),
        Text(description, style: const TextStyle(color: Colors.white70, height: 1.4)),
      ]),
    ),
  );
  Widget _step(String number, String title, String description) => Padding(padding: const EdgeInsets.only(right: 16, bottom: 18), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('$number  ✳', style: const TextStyle(color: BonsoBrand.aqua, fontWeight: FontWeight.bold)), const SizedBox(height: 13), Text(title, style: const TextStyle(color: Colors.white, fontSize: 21, fontWeight: FontWeight.bold)), const SizedBox(height: 8), Text(description, style: const TextStyle(color: Colors.white70, height: 1.4))]));
}

class _Section extends StatelessWidget { final Widget child; const _Section({required this.child}); @override Widget build(BuildContext context) => Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 1180), child: Padding(padding: const EdgeInsets.symmetric(horizontal: 22), child: child))); }
class _Eyebrow extends StatelessWidget { final String text; const _Eyebrow(this.text); @override Widget build(BuildContext context) => Text(text, style: const TextStyle(color: BonsoBrand.aqua, fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 1.2)); }
class _Stat extends StatelessWidget { final String value, label; const _Stat(this.value, this.label); @override Widget build(BuildContext context) => SizedBox(width: 180, child: Column(children: [Text(value, style: const TextStyle(color: BonsoBrand.lime, fontSize: 27, fontWeight: FontWeight.bold)), const SizedBox(height: 4), Text(label, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white70))])); }
