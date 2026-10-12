import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import '../brand.dart';
import 'login_screen.dart';
import 'settings_screen.dart';
import 'marketing_screen.dart';

class IntegrationsScreen extends StatefulWidget {
  const IntegrationsScreen({super.key});

  @override
  State<IntegrationsScreen> createState() => _IntegrationsScreenState();
}

class _IntegrationsScreenState extends State<IntegrationsScreen> {
  bool _loading = true;
  bool _telegramConnected = false;
  int _routerCount = 0;
  bool _telegramEnabled = false;
  bool _whatsappEnabled = false;
  bool _iotEnabled = false;
  bool _mikrotikEnabled = false;
  bool _whatsappConnected = false;
  bool _googleConnected = false;
  bool _facebookConnected = false;
  bool _instagramConnected = false;
  bool _tiktokConnected = false;
  String? _googleAccount;

  @override
  void initState() {
    super.initState();
    _loadStatus();
  }

  Future<void> _loadStatus() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';
      final headers = {'Authorization': 'Bearer $token'};
      final responses = await Future.wait([
        http.get(Uri.parse('$kApiBaseUrl/v1/auth/profile'), headers: headers),
        http.get(Uri.parse('$kApiBaseUrl/v1/telegram/status'), headers: headers),
        http.get(Uri.parse('$kApiBaseUrl/v1/mikrotik/routers'), headers: headers),
        http.get(Uri.parse('$kApiBaseUrl/v1/marketing/connections'), headers: headers),
        http.get(Uri.parse('$kApiBaseUrl/v1/google-workspace/status'), headers: headers),
      ]);
      if (!mounted) return;
      final profile = responses[0].statusCode == 200 ? jsonDecode(responses[0].body) : <String, dynamic>{};
      final telegram = responses[1].statusCode == 200 ? jsonDecode(responses[1].body) : <String, dynamic>{};
      final routers = responses[2].statusCode == 200 ? jsonDecode(responses[2].body) as List : <dynamic>[];
      final connections = responses[3].statusCode == 200 ? jsonDecode(responses[3].body) as List : <dynamic>[];
      final google = responses[4].statusCode == 200 ? jsonDecode(responses[4].body) as Map<String, dynamic> : <String, dynamic>{};
      final features = profile['plan_features'] as Map? ?? {};
      setState(() {
        _telegramEnabled = features['telegram'] == true;
        _whatsappEnabled = features['whatsapp'] == true;
        _iotEnabled = features['iot'] == true;
        _mikrotikEnabled = features['mikrotik'] == true;
        _telegramConnected = telegram['linked'] == true || telegram['connected'] == true || telegram['configured'] == true;
        _routerCount = routers.length;
        _whatsappConnected = connections.any((connection) => connection['provider'] == 'whatsapp' && connection['status'] == 'connected');
        _facebookConnected = connections.any((connection) => connection['provider'] == 'facebook' && connection['status'] == 'connected');
        _instagramConnected = connections.any((connection) => connection['provider'] == 'instagram' && connection['status'] == 'connected');
        _tiktokConnected = connections.any((connection) => connection['provider'] == 'tiktok' && connection['status'] == 'connected');
        _googleConnected = google['connected'] == true;
        _googleAccount = google['account_name']?.toString();
      });
    } catch (_) {
      // La pantalla sigue siendo utilizable aunque una consulta de estado falle.
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _open(String section) {
    Navigator.push(context, MaterialPageRoute(builder: (_) => SettingsScreen(initialIntegration: section))).then((_) => _loadStatus());
  }

  Future<void> _connectGoogle() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final response = await http.post(Uri.parse('$kApiBaseUrl/v1/google-workspace/start'), headers: {'Authorization': 'Bearer ${prefs.getString('jwt_token') ?? ''}'});
      if (response.statusCode != 200) throw Exception(jsonDecode(response.body)['detail'] ?? 'No disponible');
      await launchUrl(Uri.parse(jsonDecode(response.body)['authorization_url']), mode: LaunchMode.externalApplication);
    } catch (error) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo iniciar la conexión con Google: $error'), backgroundColor: Colors.redAccent));
    }
  }

  Future<void> _connectMeta(String provider) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final response = await http.post(Uri.parse('$kApiBaseUrl/v1/marketing/connections/meta/start/$provider'), headers: {'Authorization': 'Bearer ${prefs.getString('jwt_token') ?? ''}'});
      if (response.statusCode != 200) throw Exception(jsonDecode(response.body)['detail'] ?? 'No disponible');
      await launchUrl(Uri.parse(jsonDecode(response.body)['authorization_url']), mode: LaunchMode.externalApplication);
    } catch (error) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo iniciar la conexión: $error'), backgroundColor: Colors.redAccent));
    }
  }

  Future<void> _connectTikTok() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final response = await http.post(Uri.parse('$kApiBaseUrl/v1/marketing/connections/tiktok/start'), headers: {'Authorization': 'Bearer ${prefs.getString('jwt_token') ?? ''}'});
      if (response.statusCode != 200) throw Exception(jsonDecode(response.body)['detail'] ?? 'No disponible');
      await launchUrl(Uri.parse(jsonDecode(response.body)['authorization_url']), mode: LaunchMode.externalApplication);
    } catch (error) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo iniciar TikTok: $error'), backgroundColor: Colors.redAccent));
    }
  }

  ({List<String> steps, List<String> functions}) _guide(String section) => switch (section) {
    'telegram' => (steps: ['Crea un bot con @BotFather.', 'Copia el token HTTP API.', 'Ábrelo en Bonso y genera el código de vinculación.', 'Envía /start seguido del código al bot.'], functions: ['Responder conversaciones desde Telegram.', 'Recibir y almacenar archivos en la memoria de Bonso.', 'Mantener el contexto del cliente por chat.']),
    'whatsapp' => (steps: ['Crea una app en Meta for Developers.', 'Activa WhatsApp Cloud API y registra el número.', 'Crea un token permanente y copia el Phone Number ID.', 'Guárdalos en Canales y contenido.', 'Configura el webhook de Meta hacia la API de Bonso.'], functions: ['Centralizar conversaciones de WhatsApp.', 'Preparar respuestas y derivarlas a un humano.', 'Registrar las conversaciones para seguimiento.']),
    'facebook' => (steps: ['Crea una app de Meta y agrega Facebook Login.', 'Registra la URL de redirección de Bonso.', 'Pulsa Conectar y autoriza las páginas solicitadas.', 'Confirma que la página aparece como conectada.'], functions: ['Consultar páginas autorizadas.', 'Preparar contenido para publicaciones.', 'Centralizar actividad del canal para seguimiento.']),
    'instagram' => (steps: ['Usa una cuenta profesional vinculada a una página de Facebook.', 'Crea o usa una app de Meta con permisos de Instagram.', 'Registra la URL de redirección.', 'Pulsa Conectar y acepta los permisos.'], functions: ['Consultar información de la cuenta autorizada.', 'Preparar contenido y respuestas para el canal.', 'Unificar la actividad con los demás canales.']),
    'tiktok' => (steps: ['Crea una app en TikTok for Developers.', 'Activa Login Kit y registra una URL HTTPS de redirección.', 'Solicita los scopes requeridos en TikTok.', 'Pulsa Conectar TikTok y autoriza la cuenta.'], functions: ['Identificar la cuenta conectada.', 'Consultar videos autorizados.', 'Preparar una base para análisis y publicación cuando TikTok apruebe los scopes.']),
    'google' => (steps: ['Crea credenciales OAuth Web en Google Cloud.', 'Habilita Gmail API y Google Calendar API.', 'Registra la URL de redirección exacta de Bonso.', 'Pulsa Conectar Google y acepta los permisos.'], functions: ['Leer correo autorizado.', 'Enviar correos con autorización.', 'Crear y gestionar eventos del calendario.']),
    'iot' => (steps: ['Obtén la URL y token de Home Assistant o los datos del broker MQTT.', 'Abre la configuración desde esta tarjeta.', 'Guarda los datos y prueba la conexión.', 'Añade tópicos MQTT si corresponde.'], functions: ['Consultar estados de dispositivos.', 'Leer telemetría IoT.', 'Ejecutar automatizaciones autorizadas.']),
    'mikrotik' => (steps: ['Habilita REST API HTTPS en el router.', 'Crea un usuario con los permisos mínimos.', 'Agrega IP, puerto y credenciales desde Bonso.', 'Prueba la conexión y revisa el certificado.'], functions: ['Consultar identidad y estado del router.', 'Apoyar diagnósticos de red.', 'Usar los datos del router como contexto del asistente.']),
    _ => (steps: const [], functions: const []),
  };

  void _showGuide(String section, String title) {
    final guide = _guide(section);
    showModalBottomSheet(context: context, backgroundColor: BonsoBrand.surface, isScrollControlled: true, builder: (_) => SafeArea(child: DraggableScrollableSheet(initialChildSize: .72, maxChildSize: .92, expand: false, builder: (_, controller) => ListView(controller: controller, padding: const EdgeInsets.all(24), children: [Text('Conectar $title', style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)), const SizedBox(height: 16), const Text('Paso a paso', style: TextStyle(color: BonsoBrand.aqua, fontWeight: FontWeight.bold)), const SizedBox(height: 8), ...guide.steps.asMap().entries.map((entry) => Padding(padding: const EdgeInsets.only(bottom: 10), child: Text('${entry.key + 1}. ${entry.value}', style: const TextStyle(color: Colors.white70, height: 1.35)))), const SizedBox(height: 10), const Text('Funciones disponibles para Bonso', style: TextStyle(color: BonsoBrand.aqua, fontWeight: FontWeight.bold)), const SizedBox(height: 8), ...guide.functions.map((item) => Padding(padding: const EdgeInsets.only(bottom: 8), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [const Icon(Icons.check_circle_outline, size: 18, color: BonsoBrand.aqua), const SizedBox(width: 8), Expanded(child: Text(item, style: const TextStyle(color: Colors.white70, height: 1.35)))]))), const SizedBox(height: 24)]))));
  }

  Widget _integrationCard({required String title, required String description, required IconData icon, required Color color, required String section, required String status, bool enabled = true, VoidCallback? onTap}) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      color: BonsoBrand.surface,
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap ?? () => _open(section),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(color: color.withOpacity(.14), borderRadius: BorderRadius.circular(14)),
              child: Icon(icon, color: color),
            ),
            const SizedBox(width: 14),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Text(description, style: const TextStyle(color: Colors.white60, height: 1.25)),
              const SizedBox(height: 9),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                decoration: BoxDecoration(color: enabled ? color.withOpacity(.14) : Colors.white10, borderRadius: BorderRadius.circular(99)),
                child: Text(status, style: TextStyle(color: enabled ? color : Colors.white54, fontSize: 11, fontWeight: FontWeight.bold)),
              ),
            ])),
            IconButton(icon: const Icon(Icons.help_outline, color: Colors.white54), tooltip: 'Guía de conexión', onPressed: () => _showGuide(section, title)),
            const Icon(Icons.chevron_right, color: Colors.white54),
          ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        backgroundColor: BonsoBrand.ink,
        appBar: AppBar(title: const Text('Integraciones', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)), backgroundColor: BonsoBrand.surface),
        body: RefreshIndicator(
          onRefresh: _loadStatus,
          child: _loading
              ? const Center(child: CircularProgressIndicator(color: BonsoBrand.aqua))
              : ListView(padding: const EdgeInsets.all(16), children: [
                  const Text('Conecta Bonso con las herramientas que utiliza tu negocio.', style: TextStyle(color: Colors.white70, fontSize: 15, height: 1.35)),
                  const SizedBox(height: 20),
                  _integrationCard(title: 'Telegram', description: 'Atiende clientes y recibe archivos desde tu bot.', icon: Icons.send_outlined, color: Colors.lightBlueAccent, section: 'telegram', status: _telegramConnected ? 'CONECTADO' : (_telegramEnabled ? 'SIN CONFIGURAR' : 'PLAN SUPERIOR'), enabled: _telegramEnabled),
                  _integrationCard(title: 'WhatsApp Business', description: 'Centraliza conversaciones de clientes mediante Meta Cloud API.', icon: Icons.chat_outlined, color: Colors.greenAccent, section: 'whatsapp', status: _whatsappConnected ? 'CONECTADO' : (_whatsappEnabled ? 'CONFIGURAR' : 'PLAN SUPERIOR'), enabled: _whatsappEnabled, onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const MarketingScreen())).then((_) => _loadStatus())),
                  _integrationCard(title: 'Facebook', description: 'Conecta páginas y contenido de Facebook mediante Meta.', icon: Icons.facebook_outlined, color: Colors.blueAccent, section: 'facebook', status: _facebookConnected ? 'CONECTADO' : 'CONECTAR FACEBOOK', onTap: () => _connectMeta('facebook')),
                  _integrationCard(title: 'Instagram', description: 'Vincula una cuenta profesional de Instagram.', icon: Icons.photo_camera_outlined, color: Colors.pinkAccent, section: 'instagram', status: _instagramConnected ? 'CONECTADO' : 'CONECTAR INSTAGRAM', onTap: () => _connectMeta('instagram')),
                  _integrationCard(title: 'TikTok', description: 'Autoriza la cuenta y sus videos permitidos mediante TikTok OAuth.', icon: Icons.music_note_outlined, color: Colors.cyanAccent, section: 'tiktok', status: _tiktokConnected ? 'CONECTADO' : 'CONECTAR TIKTOK', onTap: _connectTikTok),
                  _integrationCard(title: 'Gmail y Google Calendar', description: 'Permite a Bonso consultar correo y gestionar eventos autorizados.', icon: Icons.calendar_month_outlined, color: Colors.redAccent, section: 'google', status: _googleConnected ? (_googleAccount ?? 'CONECTADO').toUpperCase() : 'CONECTAR GOOGLE', onTap: _connectGoogle),
                  _integrationCard(title: 'Home Assistant', description: 'Consulta y controla dispositivos de tu instalación.', icon: Icons.home_work_outlined, color: Colors.tealAccent, section: 'iot', status: _iotEnabled ? 'CONFIGURAR' : 'PLAN SUPERIOR', enabled: _iotEnabled),
                  _integrationCard(title: 'MQTT Broker', description: 'Recibe telemetría y automatiza acciones IoT.', icon: Icons.hub_outlined, color: Colors.amberAccent, section: 'iot', status: _iotEnabled ? 'CONFIGURAR' : 'PLAN SUPERIOR', enabled: _iotEnabled),
                  _integrationCard(title: 'MikroTik', description: 'Monitorea y consulta tus routers de red.', icon: Icons.router_outlined, color: Colors.deepPurpleAccent, section: 'mikrotik', status: _mikrotikEnabled ? (_routerCount > 0 ? '$_routerCount ${_routerCount == 1 ? 'ROUTER' : 'ROUTERS'}' : 'SIN ROUTERS') : 'PLAN SUPERIOR', enabled: _mikrotikEnabled),
                  const SizedBox(height: 16),
                  Container(padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: Colors.white.withOpacity(.05), borderRadius: BorderRadius.circular(14), border: Border.all(color: Colors.white12)), child: const Row(children: [Icon(Icons.add_link, color: BonsoBrand.aqua), SizedBox(width: 12), Expanded(child: Text('Las nuevas integraciones aparecerán automáticamente en este menú.', style: TextStyle(color: Colors.white70, height: 1.3)))])),
                ]),
        ),
      );
}
