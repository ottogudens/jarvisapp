import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import '../brand.dart';
import 'login_screen.dart';

class MarketingScreen extends StatefulWidget {
  const MarketingScreen({super.key});
  @override
  State<MarketingScreen> createState() => _MarketingScreenState();
}

class _MarketingScreenState extends State<MarketingScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabs;
  List<dynamic> _connections = [], _inbox = [], _content = [];
  bool _loading = true;

  @override
  void initState() { super.initState(); _tabs = TabController(length: 3, vsync: this); _load(); }
  @override
  void dispose() { _tabs.dispose(); super.dispose(); }

  Future<String?> _token() async => (await SharedPreferences.getInstance()).getString('jwt_token');

  Future<void> _load() async {
    final token = await _token();
    try {
      final responses = await Future.wait([
        http.get(Uri.parse('$kApiBaseUrl/v1/marketing/connections'), headers: {'Authorization': 'Bearer $token'}),
        http.get(Uri.parse('$kApiBaseUrl/v1/marketing/inbox'), headers: {'Authorization': 'Bearer $token'}),
        http.get(Uri.parse('$kApiBaseUrl/v1/marketing/content'), headers: {'Authorization': 'Bearer $token'}),
      ]);
      if (responses[0].statusCode == 200) _connections = jsonDecode(responses[0].body);
      if (responses[1].statusCode == 200) _inbox = jsonDecode(responses[1].body);
      if (responses[2].statusCode == 200) _content = jsonDecode(responses[2].body);
    } finally { if (mounted) setState(() => _loading = false); }
  }

  Future<void> _whatsappGuide() async {
    final response = await http.get(Uri.parse('$kApiBaseUrl/v1/marketing/whatsapp-guide'), headers: {'Authorization': 'Bearer ${await _token()}'});
    if (response.statusCode != 200 || !mounted) return;
    final data = jsonDecode(response.body);
    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: Text('${data['title']}', style: const TextStyle(color: Colors.white)),
        content: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 600),
          child: SingleChildScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: (data['steps'] as List).asMap().entries.map((item) => Padding(padding: const EdgeInsets.only(bottom: 12), child: Text('${item.key + 1}. ${item.value}', style: const TextStyle(color: Colors.white70)))).toList())),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Entendido'))],
      ),
    );
  }

  Future<void> _connectMeta(String provider) async {
    final response = await http.post(Uri.parse('$kApiBaseUrl/v1/marketing/connections/meta/start/$provider'), headers: {'Authorization': 'Bearer ${await _token()}'});
    if (response.statusCode != 200) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Conexión no disponible: ${response.body}')));
      return;
    }
    await launchUrl(Uri.parse(jsonDecode(response.body)['authorization_url']), mode: LaunchMode.externalApplication);
  }

  Future<void> _createContent() async {
    final title = TextEditingController(), body = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: const Text('Nuevo contenido', style: TextStyle(color: Colors.white)),
        content: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: title, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Título')),
            TextField(controller: body, maxLines: 5, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Copy o borrador')),
          ])),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar')), TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Guardar'))],
      ),
    );
    if (confirmed != true || title.text.trim().isEmpty) return;
    await http.post(Uri.parse('$kApiBaseUrl/v1/marketing/content'), headers: {'Authorization': 'Bearer ${await _token()}', 'Content-Type': 'application/json'}, body: jsonEncode({'title': title.text.trim(), 'body': body.text.trim()}));
    _load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: BonsoBrand.ink,
    appBar: AppBar(title: const Text('Marketing Hub'), actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh), tooltip: 'Actualizar')], bottom: TabBar(controller: _tabs, isScrollable: true, tabs: const [Tab(text: 'Canales'), Tab(text: 'Bandeja'), Tab(text: 'Contenido')])),
    body: _loading ? const Center(child: CircularProgressIndicator()) : TabBarView(controller: _tabs, children: [_channels(), _inboxView(), _contentView()]),
  );

  Widget _channels() => ListView(padding: const EdgeInsets.all(16), children: [
    SizedBox(width: double.infinity, child: ElevatedButton.icon(onPressed: _whatsappGuide, icon: const Icon(Icons.chat), label: const Text('Conectar WhatsApp Business'), style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.lime, foregroundColor: Colors.black, minimumSize: const Size(0, 48)))),
    const SizedBox(height: 12),
    Wrap(spacing: 8, runSpacing: 8, children: [
      OutlinedButton.icon(onPressed: () => _connectMeta('instagram'), icon: const Icon(Icons.photo_camera), label: const Text('Instagram')),
      OutlinedButton.icon(onPressed: () => _connectMeta('messenger'), icon: const Icon(Icons.forum), label: const Text('Messenger')),
      OutlinedButton.icon(onPressed: () => _connectMeta('facebook_ads'), icon: const Icon(Icons.ads_click), label: const Text('Meta Ads')),
    ]),
    const SizedBox(height: 12),
    const Text('Las conexiones de Meta se autorizan con OAuth/Embedded Signup; no compartas tokens por chat.', style: TextStyle(color: Colors.white54)),
    const SizedBox(height: 12),
    ..._connections.map((item) => Card(color: BonsoBrand.surface, child: ListTile(leading: const Icon(Icons.link, color: BonsoBrand.aqua), title: Text('${item['account_name']}', style: const TextStyle(color: Colors.white)), subtitle: Text('${item['provider']} · ${item['status']}', style: const TextStyle(color: Colors.white70))))),
  ]);

  Widget _inboxView() => ListView(padding: const EdgeInsets.all(16), children: _inbox.isEmpty ? [const ListTile(title: Text('Aún no hay conversaciones conectadas', style: TextStyle(color: Colors.white54)))] : _inbox.map((item) => Card(color: BonsoBrand.surface, child: ListTile(title: Text('${item['customer']}', style: const TextStyle(color: Colors.white)), subtitle: Text('${item['channel']} · ${item['status']}', style: const TextStyle(color: Colors.white70)), trailing: const Icon(Icons.chevron_right, color: BonsoBrand.aqua)))).toList());

  Widget _contentView() => ListView(padding: const EdgeInsets.all(16), children: [
    SizedBox(width: double.infinity, child: ElevatedButton.icon(onPressed: _createContent, icon: const Icon(Icons.add), label: const Text('Crear borrador'), style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.aqua, foregroundColor: Colors.black, minimumSize: const Size(0, 48)))),
    const SizedBox(height: 12),
    ..._content.map((item) => Card(color: BonsoBrand.surface, child: ListTile(title: Text('${item['title']}', style: const TextStyle(color: Colors.white)), subtitle: Text('${item['body']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white70)), trailing: Text('${item['status']}', style: const TextStyle(color: BonsoBrand.aqua))))),
  ]);
}
