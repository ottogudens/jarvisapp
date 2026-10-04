import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../brand.dart';
import 'admin_screen.dart';
import 'login_screen.dart';

class AdminConsoleScreen extends StatefulWidget {
  const AdminConsoleScreen({super.key});

  @override
  State<AdminConsoleScreen> createState() => _AdminConsoleScreenState();
}

class _AdminConsoleScreenState extends State<AdminConsoleScreen> with SingleTickerProviderStateMixin {
  Map<String, dynamic>? _data;
  bool _loading = true;
  late final TabController _tabs;

  @override
  void initState() { super.initState(); _tabs = TabController(length: 4, vsync: this); _load(); }
  @override
  void dispose() { _tabs.dispose(); super.dispose(); }

  Future<String?> _token() async => (await SharedPreferences.getInstance()).getString('jwt_token');

  Future<void> _load() async {
    if (mounted) setState(() => _loading = true);
    try {
      final response = await http.get(Uri.parse('$kApiBaseUrl/v1/admin/operations/overview'), headers: {'Authorization': 'Bearer ${await _token()}'});
      if (response.statusCode == 200) _data = jsonDecode(response.body);
      else if (mounted) _message('No se pudo cargar la consola: ${response.statusCode}', error: true);
    } catch (_) { if (mounted) _message('No fue posible conectar con el servidor.', error: true); }
    finally { if (mounted) setState(() => _loading = false); }
  }

  void _message(String text, {bool error = false}) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text), backgroundColor: error ? Colors.redAccent : Colors.green));

  Future<void> _logout() async {
    await (await SharedPreferences.getInstance()).clear();
    if (mounted) Navigator.of(context).pushAndRemoveUntil(MaterialPageRoute(builder: (_) => const LoginScreen()), (_) => false);
  }

  Future<void> _changeCustomerStatus(Map<String, dynamic> customer) async {
    final activating = customer['active'] != true;
    String reason = '';
    final approved = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: Text(activating ? 'Activar cliente' : 'Suspender cliente', style: const TextStyle(color: Colors.white)),
        content: activating ? const Text('El cliente volverá a poder iniciar sesión y usar sus integraciones.', style: TextStyle(color: Colors.white70)) : TextField(
          autofocus: true,
          maxLength: 255,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(labelText: 'Motivo de suspensión', hintText: 'Ej.: pago pendiente'),
          onChanged: (value) => reason = value,
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar')), ElevatedButton(onPressed: () => Navigator.pop(context, true), style: ElevatedButton.styleFrom(backgroundColor: activating ? BonsoBrand.aqua : Colors.redAccent), child: Text(activating ? 'Activar' : 'Suspender', style: const TextStyle(color: Colors.black)))],
      ),
    );
    if (approved != true) return;
    final response = await http.post(
      Uri.parse('$kApiBaseUrl/v1/admin/operations/tenants/${customer['id_tenant']}/status'),
      headers: {'Authorization': 'Bearer ${await _token()}', 'Content-Type': 'application/json'},
      body: jsonEncode({'is_active': activating, 'reason': reason}),
    );
    if (response.statusCode == 200) { _message(activating ? 'Cliente activado.' : 'Cliente suspendido.'); _load(); }
    else { _message('No se pudo actualizar el cliente.', error: true); }
  }

  Future<void> _editCustomer(Map<String, dynamic> customer) async {
    final organization = TextEditingController(text: '${customer['organization'] ?? ''}');
    final contact = TextEditingController(text: '${customer['contact'] ?? ''}');
    final phone = TextEditingController(text: '${customer['phone'] ?? ''}');
    final email = TextEditingController(text: '${customer['email'] ?? ''}');
    String provider = '${customer['ai_provider'] ?? 'gemini'}';
    String model = '${customer['ai_model'] ?? 'gemini-1.5-flash'}';
    const models = {
      'gemini': ['gemini-1.5-flash', 'gemini-1.5-pro'],
      'openai': ['gpt-4o-mini', 'gpt-4o'],
      'anthropic': ['claude-3-haiku-20240307', 'claude-3-5-sonnet-20240620'],
      'deepseek': ['deepseek-chat', 'deepseek-coder'],
    };
    if (!(models[provider] ?? []).contains(model)) model = models[provider]!.first;
    final saved = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(builder: (context, setDialogState) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: Text('Editar ${customer['organization']}', style: const TextStyle(color: Colors.white)),
        content: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
            _editorField(organization, 'Organización', Icons.business),
            _editorField(contact, 'Contacto', Icons.person),
            _editorField(phone, 'Teléfono', Icons.phone, keyboardType: TextInputType.phone),
            _editorField(email, 'Correo del administrador', Icons.email_outlined, keyboardType: TextInputType.emailAddress),
            DropdownButtonFormField<String>(value: provider, dropdownColor: BonsoBrand.surface, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Proveedor de IA'), items: models.keys.map((item) => DropdownMenuItem(value: item, child: Text(item.toUpperCase()))).toList(), onChanged: (value) => setDialogState(() { provider = value ?? provider; model = models[provider]!.first; })),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(value: model, dropdownColor: BonsoBrand.surface, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Modelo'), items: models[provider]!.map((item) => DropdownMenuItem(value: item, child: Text(item))).toList(), onChanged: (value) => setDialogState(() => model = value ?? model)),
          ])),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar')), ElevatedButton(onPressed: () => Navigator.pop(context, true), style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.aqua), child: const Text('Guardar cambios', style: TextStyle(color: Colors.black)))],
      )),
    );
    if (saved != true) return;
    final response = await http.put(
      Uri.parse('$kApiBaseUrl/v1/admin/tenants/${customer['id_tenant']}'),
      headers: {'Authorization': 'Bearer ${await _token()}', 'Content-Type': 'application/json'},
      body: jsonEncode({'nombre_organizacion': organization.text.trim(), 'nombre_contacto': contact.text.trim(), 'telefono': phone.text.trim(), 'email': email.text.trim(), 'ai_provider': provider, 'ai_model': model}),
    );
    for (final controller in [organization, contact, phone, email]) { controller.dispose(); }
    if (response.statusCode == 200) { _message('Cliente actualizado.'); _load(); }
    else { _message('No se pudo editar el cliente.', error: true); }
  }

  Widget _editorField(TextEditingController controller, String label, IconData icon, {TextInputType? keyboardType}) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: TextField(controller: controller, keyboardType: keyboardType, style: const TextStyle(color: Colors.white), decoration: InputDecoration(labelText: label, prefixIcon: Icon(icon, color: BonsoBrand.aqua))),
  );

  Future<void> _editInvoiceAutomation() async {
    final automation = (_data?['invoice_automation'] as Map?) ?? {};
    bool enabled = automation['enabled'] == true;
    final day = TextEditingController(text: '${automation['day'] ?? 1}');
    final sender = TextEditingController(text: '${automation['sender_name'] ?? 'Bonso'}');
    final reply = TextEditingController(text: '${automation['reply_to'] ?? ''}');
    final saved = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(builder: (context, setState) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: const Text('Automatización de facturas', style: TextStyle(color: Colors.white)),
        content: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 460),
          child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
            SwitchListTile(value: enabled, activeColor: BonsoBrand.aqua, title: const Text('Programar envío mensual', style: TextStyle(color: Colors.white)), onChanged: (value) => setState(() => enabled = value)),
            TextField(controller: day, keyboardType: TextInputType.number, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Día de envío (1 a 28)')),
            TextField(controller: sender, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Nombre remitente')),
            TextField(controller: reply, keyboardType: TextInputType.emailAddress, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Correo de respuesta')),
          ])),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar')), ElevatedButton(onPressed: () => Navigator.pop(context, true), style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.aqua), child: const Text('Guardar', style: TextStyle(color: Colors.black)))],
      )),
    );
    if (saved != true) return;
    final response = await http.put(
      Uri.parse('$kApiBaseUrl/v1/admin/operations/config'),
      headers: {'Authorization': 'Bearer ${await _token()}', 'Content-Type': 'application/json'},
      body: jsonEncode({'invoice_automation_enabled': enabled, 'invoice_day': int.tryParse(day.text) ?? 1, 'invoice_sender_name': sender.text.trim(), 'invoice_reply_to': reply.text.trim()}),
    );
    for (final controller in [day, sender, reply]) { controller.dispose(); }
    if (response.statusCode == 200) { _message('Configuración de facturas actualizada.'); _load(); }
    else { _message('No se pudo guardar la configuración.', error: true); }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: BonsoBrand.ink,
    appBar: AppBar(
      title: const Text('Bonso · Administración SaaS'),
      actions: [IconButton(onPressed: _load, icon: const Icon(Icons.refresh), tooltip: 'Actualizar'), IconButton(onPressed: _logout, icon: const Icon(Icons.logout), tooltip: 'Cerrar sesión')],
      bottom: TabBar(controller: _tabs, isScrollable: true, tabs: const [Tab(icon: Icon(Icons.space_dashboard_outlined), text: 'Operación'), Tab(icon: Icon(Icons.groups_outlined), text: 'Clientes'), Tab(icon: Icon(Icons.receipt_long_outlined), text: 'Facturación'), Tab(icon: Icon(Icons.tune), text: 'Configuración')]),
    ),
    body: _loading && _data == null ? const Center(child: CircularProgressIndicator()) : TabBarView(controller: _tabs, children: [_overview(), _customers(), _billing(), _settings()]),
  );

  Widget _overview() {
    final kpis = (_data?['kpis'] as Map?) ?? {};
    final providers = (_data?['ai_providers'] as List?) ?? [];
    return RefreshIndicator(onRefresh: _load, child: ListView(padding: const EdgeInsets.all(16), children: [
      const Text('Visión general', style: TextStyle(fontSize: 26, color: Colors.white, fontWeight: FontWeight.bold)),
      const SizedBox(height: 6),
      const Text('Indicadores comerciales, operativos y de uso de IA.', style: TextStyle(color: Colors.white70)),
      const SizedBox(height: 18),
      Wrap(spacing: 12, runSpacing: 12, children: [
        _kpi('MRR estimado', '${kpis['mrr'] ?? 0} CLP', Icons.payments_outlined, BonsoBrand.lime),
        _kpi('Clientes activos', '${kpis['clientes_activos'] ?? 0}', Icons.groups_outlined, BonsoBrand.aqua),
        _kpi('Pruebas activas', '${kpis['pruebas_activas'] ?? 0}', Icons.timer_outlined, Colors.orangeAccent),
        _kpi('Cobros pendientes', '${kpis['cobros_pendientes'] ?? 0}', Icons.warning_amber_outlined, Colors.orangeAccent),
        _kpi('Clientes suspendidos', '${kpis['clientes_suspendidos'] ?? 0}', Icons.pause_circle_outline, Colors.redAccent),
        _kpi('Tokens acumulados', '${kpis['tokens'] ?? 0}', Icons.token_outlined, Colors.purpleAccent),
      ]),
      const SizedBox(height: 28),
      const Text('Consumo por proveedor de IA', style: TextStyle(fontSize: 18, color: Colors.white, fontWeight: FontWeight.bold)),
      const SizedBox(height: 10),
      if (providers.isEmpty) const _Empty('Aún no hay consumo registrado.') else ...providers.map((provider) => Card(color: BonsoBrand.surface, child: ListTile(leading: const Icon(Icons.auto_awesome, color: BonsoBrand.aqua), title: Text('${provider['provider']}', style: const TextStyle(color: Colors.white)), subtitle: Text('${provider['requests']} solicitudes · ${provider['tokens']} tokens', style: const TextStyle(color: Colors.white70))))),
      const SizedBox(height: 14),
      ElevatedButton.icon(onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AdminScreen())), icon: const Icon(Icons.admin_panel_settings), label: const Text('Administración avanzada de planes, perfiles y claves'), style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.aqua, foregroundColor: Colors.black, minimumSize: const Size(0, 48))),
    ]));
  }

  Widget _customers() {
    final customers = (_data?['customers'] as List?) ?? [];
    return RefreshIndicator(onRefresh: _load, child: ListView(padding: const EdgeInsets.all(16), children: [
      const Text('Clientes', style: TextStyle(fontSize: 26, color: Colors.white, fontWeight: FontWeight.bold)),
      const SizedBox(height: 6),
      const Text('Activa o suspende cuentas sin eliminar su información.', style: TextStyle(color: Colors.white70)),
      const SizedBox(height: 14),
      ...customers.map((customer) => Card(color: BonsoBrand.surface, child: Padding(padding: const EdgeInsets.all(8), child: ListTile(
        leading: CircleAvatar(backgroundColor: customer['active'] == true ? BonsoBrand.aqua : Colors.redAccent, child: Icon(customer['active'] == true ? Icons.business : Icons.pause, color: Colors.black)),
        title: Text('${customer['organization']}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
        subtitle: Text('${customer['plan']} · ${customer['tokens']} tokens\n${customer['trial'] == true ? 'Prueba gratuita' : 'Suscripción'} · ${customer['subscription_status']}', style: const TextStyle(color: Colors.white70)),
        isThreeLine: true,
        trailing: PopupMenuButton<String>(
          icon: const Icon(Icons.more_vert, color: Colors.white70),
          color: BonsoBrand.surfaceRaised,
          onSelected: (action) { final data = Map<String, dynamic>.from(customer); if (action == 'edit') _editCustomer(data); else _changeCustomerStatus(data); },
          itemBuilder: (context) => [
            const PopupMenuItem(value: 'edit', child: ListTile(leading: Icon(Icons.edit, color: BonsoBrand.aqua), title: Text('Editar cliente', style: TextStyle(color: Colors.white)))),
            PopupMenuItem(value: 'status', child: ListTile(leading: Icon(customer['active'] == true ? Icons.pause_circle_outline : Icons.play_circle_outline, color: customer['active'] == true ? Colors.orangeAccent : BonsoBrand.lime), title: Text(customer['active'] == true ? 'Suspender cliente' : 'Activar cliente', style: const TextStyle(color: Colors.white)))),
          ],
        ),
      )))),
      if (customers.isEmpty) const _Empty('No hay clientes registrados.'),
    ]));
  }

  Widget _billing() {
    final subscriptions = (_data?['subscriptions'] as List?) ?? [];
    final automation = (_data?['invoice_automation'] as Map?) ?? {};
    return RefreshIndicator(onRefresh: _load, child: ListView(padding: const EdgeInsets.all(16), children: [
      const Text('Facturación y cobros', style: TextStyle(fontSize: 26, color: Colors.white, fontWeight: FontWeight.bold)),
      const SizedBox(height: 12),
      Card(color: BonsoBrand.surface, child: ListTile(leading: Icon(automation['enabled'] == true ? Icons.schedule_send : Icons.schedule, color: BonsoBrand.lime), title: Text(automation['enabled'] == true ? 'Envío mensual programado el día ${automation['day']}' : 'Envío automático de facturas desactivado', style: const TextStyle(color: Colors.white)), subtitle: Text('Remitente: ${automation['sender_name'] ?? 'Bonso'}', style: const TextStyle(color: Colors.white70)), trailing: TextButton(onPressed: _editInvoiceAutomation, child: const Text('Configurar')))),
      const SizedBox(height: 16),
      const Text('Actividad de suscripciones', style: TextStyle(fontSize: 18, color: Colors.white, fontWeight: FontWeight.bold)),
      const SizedBox(height: 8),
      if (subscriptions.isEmpty) const _Empty('Aún no hay suscripciones registradas.') else ...subscriptions.map((subscription) => Card(color: BonsoBrand.surface, child: ListTile(leading: const Icon(Icons.receipt_long, color: BonsoBrand.aqua), title: Text('${subscription['organizacion']}', style: const TextStyle(color: Colors.white)), subtitle: Text('${subscription['amount']} ${subscription['currency']} · ${subscription['status']}', style: const TextStyle(color: Colors.white70)), trailing: const Icon(Icons.chevron_right, color: Colors.white54)))),
    ]));
  }

  Widget _settings() {
    final integrations = (_data?['integration_status'] as Map?) ?? {};
    return RefreshIndicator(onRefresh: _load, child: ListView(padding: const EdgeInsets.all(16), children: [
      const Text('Configuración operativa', style: TextStyle(fontSize: 26, color: Colors.white, fontWeight: FontWeight.bold)),
      const SizedBox(height: 6),
      const Text('Las credenciales permanecen protegidas en el servidor; aquí se muestra solo su estado.', style: TextStyle(color: Colors.white70)),
      const SizedBox(height: 16),
      _integrationCard('Mercado Pago', [
        _status('Access token', integrations['mercado_pago_access_token'] == true),
        _status('Firma de webhook', integrations['mercado_pago_webhook'] == true),
      ]),
      const SizedBox(height: 12),
      _integrationCard('Proveedores de IA', [
        _status('OpenAI', integrations['openai'] == true), _status('Anthropic', integrations['anthropic'] == true),
        _status('DeepSeek', integrations['deepseek'] == true), _status('Gemini', integrations['gemini'] == true),
      ]),
      const SizedBox(height: 16),
      ElevatedButton.icon(onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AdminScreen())), icon: const Icon(Icons.key), label: const Text('Gestionar proveedores, claves y planes'), style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.aqua, foregroundColor: Colors.black, minimumSize: const Size(0, 48))),
      const SizedBox(height: 8),
      const Text('Configura MP_ACCESS_TOKEN y MP_WEBHOOK_SECRET en el entorno de producción. Para emitir y enviar facturas reales, conecta el proveedor tributario y de correo en la infraestructura antes de activar el envío automático.', style: TextStyle(color: Colors.white54, height: 1.35)),
    ]));
  }

  Widget _kpi(String label, String value, IconData icon, Color color) => SizedBox(width: 172, child: Container(padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: BonsoBrand.surface, borderRadius: BorderRadius.circular(14)), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(icon, color: color), const SizedBox(height: 14), Text(value, style: const TextStyle(fontSize: 22, color: Colors.white, fontWeight: FontWeight.bold), overflow: TextOverflow.ellipsis), const SizedBox(height: 4), Text(label, style: const TextStyle(color: Colors.white70))])));
  Widget _status(String label, bool enabled) => ListTile(dense: true, contentPadding: EdgeInsets.zero, leading: Icon(enabled ? Icons.check_circle : Icons.error_outline, color: enabled ? BonsoBrand.lime : Colors.orangeAccent), title: Text(label, style: const TextStyle(color: Colors.white)), trailing: Text(enabled ? 'Configurado' : 'Pendiente', style: TextStyle(color: enabled ? BonsoBrand.lime : Colors.orangeAccent)));
  Widget _integrationCard(String title, List<Widget> rows) => Card(color: BonsoBrand.surface, child: Padding(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(title, style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)), const SizedBox(height: 8), ...rows])));
}

class _Empty extends StatelessWidget {
  final String text;
  const _Empty(this.text);
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.all(24), child: Text(text, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white54)));
}
