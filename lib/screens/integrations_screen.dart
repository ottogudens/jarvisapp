import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../brand.dart';
import 'login_screen.dart';
import 'settings_screen.dart';

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
  bool _iotEnabled = false;
  bool _mikrotikEnabled = false;

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
      ]);
      if (!mounted) return;
      final profile = responses[0].statusCode == 200 ? jsonDecode(responses[0].body) : <String, dynamic>{};
      final telegram = responses[1].statusCode == 200 ? jsonDecode(responses[1].body) : <String, dynamic>{};
      final routers = responses[2].statusCode == 200 ? jsonDecode(responses[2].body) as List : <dynamic>[];
      final features = profile['plan_features'] as Map? ?? {};
      setState(() {
        _telegramEnabled = features['telegram'] == true;
        _iotEnabled = features['iot'] == true;
        _mikrotikEnabled = features['mikrotik'] == true;
        _telegramConnected = telegram['linked'] == true || telegram['connected'] == true || telegram['configured'] == true;
        _routerCount = routers.length;
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

  Widget _integrationCard({required String title, required String description, required IconData icon, required Color color, required String section, required String status, bool enabled = true}) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      color: BonsoBrand.surface,
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => _open(section),
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
                  _integrationCard(title: 'Home Assistant', description: 'Consulta y controla dispositivos de tu instalación.', icon: Icons.home_work_outlined, color: Colors.tealAccent, section: 'iot', status: _iotEnabled ? 'CONFIGURAR' : 'PLAN SUPERIOR', enabled: _iotEnabled),
                  _integrationCard(title: 'MQTT Broker', description: 'Recibe telemetría y automatiza acciones IoT.', icon: Icons.hub_outlined, color: Colors.amberAccent, section: 'iot', status: _iotEnabled ? 'CONFIGURAR' : 'PLAN SUPERIOR', enabled: _iotEnabled),
                  _integrationCard(title: 'MikroTik', description: 'Monitorea y consulta tus routers de red.', icon: Icons.router_outlined, color: Colors.deepPurpleAccent, section: 'mikrotik', status: _mikrotikEnabled ? (_routerCount > 0 ? '$_routerCount ${_routerCount == 1 ? 'ROUTER' : 'ROUTERS'}' : 'SIN ROUTERS') : 'PLAN SUPERIOR', enabled: _mikrotikEnabled),
                  const SizedBox(height: 16),
                  Container(padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: Colors.white.withOpacity(.05), borderRadius: BorderRadius.circular(14), border: Border.all(color: Colors.white12)), child: const Row(children: [Icon(Icons.add_link, color: BonsoBrand.aqua), SizedBox(width: 12), Expanded(child: Text('Las nuevas integraciones aparecerán automáticamente en este menú.', style: TextStyle(color: Colors.white70, height: 1.3)))])),
                ]),
        ),
      );
}
