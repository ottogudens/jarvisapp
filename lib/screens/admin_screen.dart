import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'login_screen.dart';


class AdminScreen extends StatefulWidget {
  const AdminScreen({super.key});

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  Map<String, dynamic>? _dashboardData;
  List<dynamic> _plans = [];
  List<dynamic> _tenants = [];
  List<dynamic> _profiles = [];
  bool _isLoading = true;
  Map<String, dynamic>? _aiStats;
  Map<String, dynamic> _aiKeys = {};

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 5, vsync: this);
    _loadAllData();
  }

  Future<String?> _getToken() async {
    return (await SharedPreferences.getInstance()).getString('jwt_token');
  }

  Future<void> _loadAllData() async {
    setState(() => _isLoading = true);
    await Future.wait([
      _loadDashboard(),
      _loadPlans(),
      _loadTenants(),
      _loadProfiles(),
      _loadAiStats(),
      _loadAiKeys(),
    ]);
    if (mounted) setState(() => _isLoading = false);
  }

  Future<void> _loadAiStats() async {
    final token = await _getToken();
    if (token == null) return;
    try {
      final res = await http.get(Uri.parse('$kApiBaseUrl/v1/admin/ai-stats'), headers: {'Authorization': 'Bearer $token'});
      if (res.statusCode == 200) _aiStats = jsonDecode(res.body);
    } catch (e) { debugPrint("Error ai-stats: $e"); }
  }

  Future<void> _loadProfiles() async {
    final token = await _getToken();
    if (token == null) return;
    try {
      final res = await http.get(Uri.parse('$kApiBaseUrl/v1/admin/profiles'), headers: {'Authorization': 'Bearer $token'});
      if (res.statusCode == 200) _profiles = jsonDecode(res.body);
    } catch (e) { debugPrint("Error loading profiles: $e"); }
  }

  Future<void> _loadAiKeys() async {
    final token = await _getToken();
    if (token == null) return;
    try {
      final res = await http.get(Uri.parse('$kApiBaseUrl/v1/admin/ai-keys'), headers: {'Authorization': 'Bearer $token'});
      if (res.statusCode == 200) _aiKeys = jsonDecode(res.body);
    } catch (e) { debugPrint("Error ai-keys: $e"); }
  }

  Future<void> _saveAiKeys(Map<String, String> newKeys) async {
    final token = await _getToken();
    if (token == null) return;
    try {
      final res = await http.post(
        Uri.parse('$kApiBaseUrl/v1/admin/ai-keys'),
        headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'},
        body: jsonEncode(newKeys),
      );
      if (res.statusCode == 200) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Claves IA guardadas')));
        _loadAiKeys();
      }
    } catch (e) { debugPrint("Error guardando ai keys: $e"); }
  }

  Future<void> _loadDashboard() async {
    final token = await _getToken();
    if (token == null) return;
    try {
      final res = await http.get(Uri.parse('$kApiBaseUrl/v1/admin/dashboard'), headers: {
        'Authorization': 'Bearer $token'
      });
      if (res.statusCode == 200) {
        _dashboardData = jsonDecode(res.body);
      }
    } catch (e) {
      debugPrint("Error dashboard: $e");
    }
  }

  Future<void> _loadPlans() async {
    final token = await _getToken();
    if (token == null) return;
    try {
      final res = await http.get(Uri.parse('$kApiBaseUrl/v1/admin/plans'), headers: {
        'Authorization': 'Bearer $token'
      });
      if (res.statusCode == 200) {
        _plans = jsonDecode(res.body);
      }
    } catch (e) {
      debugPrint("Error plans: $e");
    }
  }

  Future<void> _loadTenants() async {
    final token = await _getToken();
    if (token == null) return;
    try {
      final res = await http.get(Uri.parse('$kApiBaseUrl/v1/admin/tenants'), headers: {
        'Authorization': 'Bearer $token'
      });
      if (res.statusCode == 200) {
        _tenants = jsonDecode(res.body);
      }
    } catch (e) {
      debugPrint("Error tenants: $e");
    }
  }

  // ─── Plan Editor ────────────────────────────────────────────

  void _showPlanEditor({Map<String, dynamic>? planToEdit}) {
    final isNew = planToEdit == null;
    final nameCtrl = TextEditingController(text: planToEdit?['nombre_plan'] ?? '');
    bool pErp = planToEdit?['permite_erp'] ?? false;
    bool pIns = planToEdit?['permite_inspeccion'] ?? false;
    bool pIot = planToEdit?['permite_iot'] ?? false;
    bool pMk = planToEdit?['permite_mikrotik'] ?? false;

    showDialog(context: context, builder: (ctx) {
      return StatefulBuilder(builder: (ctx, setDialogState) {
        return AlertDialog(
          backgroundColor: const Color(0xFF1E293B),
          title: Text(isNew ? 'Nuevo Plan' : 'Editar Plan', style: const TextStyle(color: Colors.white)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameCtrl,
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(labelText: 'Nombre del Plan', labelStyle: TextStyle(color: Colors.cyan)),
                ),
                SwitchListTile(title: const Text('ERP', style: TextStyle(color: Colors.white)), value: pErp, onChanged: (val) => setDialogState(() => pErp = val)),
                SwitchListTile(title: const Text('Inspección', style: TextStyle(color: Colors.white)), value: pIns, onChanged: (val) => setDialogState(() => pIns = val)),
                SwitchListTile(title: const Text('IoT', style: TextStyle(color: Colors.white)), value: pIot, onChanged: (val) => setDialogState(() => pIot = val)),
                SwitchListTile(title: const Text('MikroTik', style: TextStyle(color: Colors.white)), value: pMk, onChanged: (val) => setDialogState(() => pMk = val)),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar', style: TextStyle(color: Colors.grey))),
            ElevatedButton(
              onPressed: () async {
                final token = await _getToken();
                final body = jsonEncode({
                  'nombre_plan': nameCtrl.text,
                  'permite_erp': pErp,
                  'permite_inspeccion': pIns,
                  'permite_iot': pIot,
                  'permite_mikrotik': pMk,
                });
                
                if (isNew) {
                  await http.post(Uri.parse('$kApiBaseUrl/v1/admin/plans'), headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'}, body: body);
                } else {
                  await http.put(Uri.parse('$kApiBaseUrl/v1/admin/plans/${planToEdit['id_plan']}'), headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'}, body: body);
                }
                Navigator.pop(ctx);
                _loadPlans();
              },
              child: const Text('Guardar'),
            )
          ],
        );
      });
    });
  }

  // ─── Tenant/Client Editor ───────────────────────────────────

  void _showTenantEditor({Map<String, dynamic>? tenantToEdit}) {
    final isNew = tenantToEdit == null;
    final orgCtrl = TextEditingController(text: tenantToEdit?['nombre_organizacion'] ?? '');
    final contactoCtrl = TextEditingController(text: tenantToEdit?['nombre_contacto'] ?? '');
    final telefonoCtrl = TextEditingController(text: tenantToEdit?['telefono'] ?? '');
    final emailCtrl = TextEditingController(text: tenantToEdit?['email_admin'] ?? '');
    final passCtrl = TextEditingController();
    
    // Convertir perfiles existentes a Set de IDs
    Set<int> selectedProfiles = {};
    if (!isNew && tenantToEdit?['perfiles'] != null) {
      for (var p in tenantToEdit!['perfiles']) {
        selectedProfiles.add(p['id_perfil']);
      }
    }
    
    int? selectedPlanId = tenantToEdit?['id_plan'] ?? (_plans.isNotEmpty ? _plans[0]['id_plan'] : null);
    String aiProvider = tenantToEdit?['ai_provider'] ?? 'gemini';
    String aiModel = tenantToEdit?['ai_model'] ?? 'gemini-1.5-flash';

    showDialog(context: context, builder: (ctx) {
      return StatefulBuilder(builder: (ctx, setDialogState) {
        return AlertDialog(
          backgroundColor: const Color(0xFF1E293B),
          title: Text(isNew ? 'Agregar Cliente' : 'Editar Cliente', style: const TextStyle(color: Colors.white)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildTextField(orgCtrl, 'Nombre de la Organización'),
                const SizedBox(height: 12),
                _buildTextField(contactoCtrl, 'Nombre de Contacto (Opcional)'),
                const SizedBox(height: 12),
                _buildTextField(telefonoCtrl, 'Teléfono (Opcional)'),
                const SizedBox(height: 12),
                if (isNew) ...[
                  _buildTextField(emailCtrl, 'Email del Administrador'),
                  const SizedBox(height: 12),
                  _buildTextField(passCtrl, 'Contraseña (Opcional)', obscure: true),
                  const SizedBox(height: 12),
                ],
                // Perfiles multi-select
                const Align(
                  alignment: Alignment.centerLeft,
                  child: Text("Perfiles Asignados:", style: TextStyle(color: Colors.cyan)),
                ),
                Container(
                  height: 120,
                  margin: const EdgeInsets.only(top: 8, bottom: 12),
                  decoration: BoxDecoration(
                    border: Border.all(color: Colors.white24),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: ListView.builder(
                    itemCount: _profiles.length,
                    itemBuilder: (context, i) {
                      final p = _profiles[i];
                      final pId = p['id_perfil'];
                      return CheckboxListTile(
                        title: Text(p['nombre'], style: const TextStyle(color: Colors.white)),
                        value: selectedProfiles.contains(pId),
                        activeColor: Colors.cyanAccent,
                        checkColor: Colors.black,
                        onChanged: (val) {
                          setDialogState(() {
                            if (val == true) {
                              selectedProfiles.add(pId);
                            } else {
                              selectedProfiles.remove(pId);
                            }
                          });
                        },
                      );
                    },
                  ),
                ),
                DropdownButtonFormField<int>(
                  value: selectedPlanId,
                  dropdownColor: const Color(0xFF1E293B),
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(labelText: 'Plan', labelStyle: TextStyle(color: Colors.cyan)),
                  items: _plans.map<DropdownMenuItem<int>>((p) {
                    return DropdownMenuItem<int>(value: p['id_plan'], child: Text(p['nombre_plan']));
                  }).toList(),
                  onChanged: (val) => setDialogState(() => selectedPlanId = val),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: aiProvider,
                  dropdownColor: const Color(0xFF1E293B),
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(labelText: 'Proveedor IA', labelStyle: TextStyle(color: Colors.cyan)),
                  items: ['gemini', 'openai', 'claude', 'deepseek'].map((p) => DropdownMenuItem(value: p, child: Text(p.toUpperCase()))).toList(),
                  onChanged: (v) => setDialogState(() => aiProvider = v ?? aiProvider),
                ),
                const SizedBox(height: 12),
                _buildTextField(TextEditingController(text: aiModel), 'Modelo IA (ej. gpt-4o-mini)'),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar', style: TextStyle(color: Colors.grey))),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: Colors.cyanAccent, foregroundColor: Colors.black),
              onPressed: () async {
                final token = await _getToken();
                if (isNew) {
                  if (orgCtrl.text.isEmpty || emailCtrl.text.isEmpty || selectedPlanId == null) {
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Nombre org, email y plan son requeridos')));
                    return;
                  }
                  final res = await http.post(
                    Uri.parse('$kApiBaseUrl/v1/admin/tenants'),
                    headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'},
                    body: jsonEncode({
                      'nombre_organizacion': orgCtrl.text.trim(),
                      'nombre_contacto': contactoCtrl.text.trim(),
                      'telefono': telefonoCtrl.text.trim(),
                      'email': emailCtrl.text.trim(),
                      'password': passCtrl.text.isNotEmpty ? passCtrl.text : null,
                      'id_plan': selectedPlanId,
                      'ai_provider': aiProvider,
                      'ai_model': aiModel,
                      'perfiles_ids': selectedProfiles.toList(),
                    }),
                  );
                  if (res.statusCode == 200) {
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Cliente creado exitosamente'), backgroundColor: Colors.green));
                  } else {
                    final err = jsonDecode(res.body);
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: ${err['detail'] ?? 'Desconocido'}')));
                  }
                } else {
                  final res = await http.put(
                    Uri.parse('$kApiBaseUrl/v1/admin/tenants/${tenantToEdit['id_tenant']}'),
                    headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'},
                    body: jsonEncode({
                      'nombre_organizacion': orgCtrl.text.trim(),
                      'nombre_contacto': contactoCtrl.text.trim(),
                      'telefono': telefonoCtrl.text.trim(),
                      'id_plan': selectedPlanId,
                      'ai_provider': aiProvider,
                      'ai_model': aiModel,
                      'perfiles_ids': selectedProfiles.toList(),
                    }),
                  );
                  if (res.statusCode == 200) {
                    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Cliente actualizado'), backgroundColor: Colors.green));
                  }
                }
                if (mounted) Navigator.pop(ctx);
                _loadAllData();
              },
              child: Text(isNew ? 'Crear Cliente' : 'Guardar Cambios'),
            )
          ],
        );
      });
    });
  }

  Future<void> _deleteTenant(int tenantId, String name) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Confirmar Eliminación', style: TextStyle(color: Colors.redAccent)),
        content: Text('¿Estás seguro de eliminar al cliente "$name" y todos sus datos? Esta acción no se puede deshacer.',
            style: const TextStyle(color: Colors.white70)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar', style: TextStyle(color: Colors.grey))),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Eliminar', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    final token = await _getToken();
    try {
      final res = await http.delete(
        Uri.parse('$kApiBaseUrl/v1/admin/tenants/$tenantId'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (res.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Cliente eliminado'), backgroundColor: Colors.green));
        _loadAllData();
      } else {
        final err = jsonDecode(res.body);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: ${err['detail'] ?? 'Desconocido'}')));
      }
    } catch (e) {
      debugPrint("Error deleting tenant: $e");
    }
  }

  // ─── BUILD ─────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        title: const Text("Panel de Control (SuperAdmin)"),
        backgroundColor: const Color(0xFF1E293B),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.cyanAccent,
          tabs: const [
            Tab(icon: Icon(Icons.dashboard), text: "Dashboard"),
            Tab(icon: Icon(Icons.business), text: "Clientes"),
            Tab(icon: Icon(Icons.card_membership), text: "Planes"),
            Tab(icon: Icon(Icons.person), text: "Perfiles"),
            Tab(icon: Icon(Icons.memory), text: "IA (API Keys)"),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Colors.cyanAccent))
          : TabBarView(
              controller: _tabController,
              children: [
                _buildDashboardTab(),
                _buildTenantsTab(),
                _buildPlansTab(),
                _buildProfilesTab(),
                _buildAiKeysTab(),
              ],
            ),
    );
  }

  Widget _buildDashboardTab() {
    if (_dashboardData == null) return const Center(child: Text("Error cargando dashboard", style: TextStyle(color: Colors.white)));
    
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(child: _buildMetricCard("Clientes", _dashboardData!['total_clientes'].toString(), Icons.business)),
              const SizedBox(width: 16),
              Expanded(child: _buildMetricCard("Agentes", _dashboardData!['total_agentes'].toString(), Icons.person)),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(child: _buildMetricCard("Tokens Consumidos", _dashboardData!['tokens_consumidos'].toString(), Icons.token, color: Colors.orange)),
            ],
          ),
          const SizedBox(height: 16),
          _buildAiChart(),
        ],
      ),
    );
  }

  Widget _buildMetricCard(String title, String value, IconData icon, {Color color = Colors.cyanAccent}) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          Icon(icon, color: color, size: 40),
          const SizedBox(height: 12),
          Text(title, style: const TextStyle(color: Colors.grey, fontSize: 16)),
          const SizedBox(height: 8),
          Text(value, style: const TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Widget _buildTenantsTab() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.cyanAccent,
              foregroundColor: Colors.black,
              minimumSize: const Size(double.infinity, 50),
            ),
            icon: const Icon(Icons.person_add),
            label: const Text("Agregar Nuevo Cliente"),
            onPressed: () => _showTenantEditor(),
          ),
        ),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: _tenants.length,
            itemBuilder: (ctx, i) {
              final t = _tenants[i];
              return Card(
                color: const Color(0xFF1E293B),
                margin: const EdgeInsets.only(bottom: 10),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              t['nombre_organizacion'] ?? 'Sin nombre',
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                icon: const Icon(Icons.edit, color: Colors.cyanAccent, size: 20),
                                tooltip: 'Editar',
                                onPressed: () => _showTenantEditor(tenantToEdit: t),
                              ),
                              IconButton(
                                icon: const Icon(Icons.delete, color: Colors.redAccent, size: 20),
                                tooltip: 'Eliminar',
                                onPressed: () => _deleteTenant(t['id_tenant'], t['nombre_organizacion']),
                              ),
                            ],
                          ),
                        ],
                      ),
                      const Divider(color: Colors.white12),
                      Row(
                        children: [
                          const Icon(Icons.email, color: Colors.white38, size: 14),
                          const SizedBox(width: 6),
                          Text(t['email_admin'] ?? '', style: const TextStyle(color: Colors.white60, fontSize: 13)),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.cyan.withOpacity(0.15),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(t['nombre_plan'] ?? 'Sin plan', style: const TextStyle(color: Colors.cyanAccent, fontSize: 11, fontWeight: FontWeight.w600)),
                          ),
                          const SizedBox(width: 10),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.orange.withOpacity(0.15),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text('${t['perfil_jarvis'] ?? 'N/A'}', style: const TextStyle(color: Colors.orangeAccent, fontSize: 11, fontWeight: FontWeight.w600)),
                          ),
                          const Spacer(),
                          Text('${t['tokens_consumidos'] ?? 0} tokens', style: const TextStyle(color: Colors.white38, fontSize: 11)),
                        ],
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildPlansTab() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: ElevatedButton.icon(
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.cyanAccent,
              foregroundColor: Colors.black,
              minimumSize: const Size(double.infinity, 50),
            ),
            icon: const Icon(Icons.add),
            label: const Text("Crear Nuevo Plan"),
            onPressed: () => _showPlanEditor(),
          ),
        ),
        Expanded(
          child: ListView.builder(
            itemCount: _plans.length,
            itemBuilder: (ctx, i) {
              final p = _plans[i];
              return Card(
                color: const Color(0xFF1E293B),
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: ListTile(
                  title: Text(p['nombre_plan'], style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  subtitle: Text("ERP: ${p['permite_erp']} | IoT: ${p['permite_iot']} | MT: ${p['permite_mikrotik']}", style: const TextStyle(color: Colors.grey)),
                  trailing: IconButton(
                    icon: const Icon(Icons.edit, color: Colors.cyanAccent),
                    onPressed: () => _showPlanEditor(planToEdit: p),
                  ),
                ),
              );
            },
          ),
        )
      ],
    );
  }

  Widget _buildProfilesTab() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: ElevatedButton.icon(
            onPressed: () => _showProfileDialog(),
            icon: const Icon(Icons.add),
            label: const Text("Crear Perfil"),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.cyanAccent, foregroundColor: Colors.black),
          ),
        ),
        Expanded(
          child: ListView.builder(
            itemCount: _profiles.length,
            itemBuilder: (context, i) {
              final p = _profiles[i];
              return Card(
                color: const Color(0xFF1E293B),
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                child: ListTile(
                  title: Text(p['nombre'], style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  subtitle: Text("ID: ${p['id_perfil']}", style: const TextStyle(color: Colors.white70)),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        icon: const Icon(Icons.edit, color: Colors.blueAccent),
                        onPressed: () => _showProfileDialog(profileToEdit: p),
                      ),
                      IconButton(
                        icon: const Icon(Icons.delete, color: Colors.redAccent),
                        onPressed: () => _deleteProfile(p['id_perfil']),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  void _showProfileDialog({Map<String, dynamic>? profileToEdit}) {
    final isEdit = profileToEdit != null;
    final nameCtrl = TextEditingController(text: isEdit ? profileToEdit['nombre'] : '');
    final instructionsCtrl = TextEditingController(text: isEdit ? profileToEdit['instrucciones_base'] : '');

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: const Color(0xFF1E293B),
          title: Text(isEdit ? "Editar Perfil" : "Nuevo Perfil", style: const TextStyle(color: Colors.white)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildTextField(nameCtrl, "Nombre"),
                const SizedBox(height: 16),
                TextField(
                  controller: instructionsCtrl,
                  maxLines: 5,
                  style: const TextStyle(color: Colors.white),
                  decoration: const InputDecoration(
                    labelText: "Instrucciones Base",
                    labelStyle: TextStyle(color: Colors.white70),
                    enabledBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
                    focusedBorder: OutlineInputBorder(borderSide: BorderSide(color: Colors.cyanAccent)),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text("Cancelar", style: TextStyle(color: Colors.white70)),
            ),
            ElevatedButton(
              onPressed: () async {
                final token = await _getToken();
                final body = jsonEncode({
                  "nombre": nameCtrl.text,
                  "instrucciones_base": instructionsCtrl.text,
                });
                
                try {
                  if (isEdit) {
                    await http.put(Uri.parse('$kApiBaseUrl/v1/admin/profiles/${profileToEdit['id_perfil']}'), headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'}, body: body);
                  } else {
                    await http.post(Uri.parse('$kApiBaseUrl/v1/admin/profiles'), headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'}, body: body);
                  }
                  if (mounted) Navigator.pop(context);
                  _loadProfiles();
                } catch (e) {
                  debugPrint("Error save profile: $e");
                }
              },
              style: ElevatedButton.styleFrom(backgroundColor: Colors.cyanAccent, foregroundColor: Colors.black),
              child: const Text("Guardar"),
            ),
          ],
        );
      }
    );
  }

  Future<void> _deleteProfile(int id) async {
    final token = await _getToken();
    await http.delete(Uri.parse('$kApiBaseUrl/v1/admin/profiles/$id'), headers: {'Authorization': 'Bearer $token'});
    _loadProfiles();
  }

  Widget _buildTextField(TextEditingController controller, String label, {bool obscure = false}) {
    return TextField(
      controller: controller,
      obscureText: obscure,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Colors.white70),
        enabledBorder: const OutlineInputBorder(borderSide: BorderSide(color: Colors.white24)),
        focusedBorder: const OutlineInputBorder(borderSide: BorderSide(color: Colors.cyanAccent)),
      ),
    );
  }

  Widget _buildAiChart() {
    if (_aiStats == null || _aiStats!['providers'] == null) return const SizedBox();
    List<dynamic> providers = _aiStats!['providers'];
    if (providers.isEmpty) return const SizedBox();
    
    return Container(
      height: 200,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: const Color(0xFF1E293B), borderRadius: BorderRadius.circular(12)),
      child: Column(
        children: [
          const Text('Consumo por Proveedor IA (Tokens)', style: TextStyle(color: Colors.white)),
          const SizedBox(height: 16),
          Expanded(
            child: PieChart(
              PieChartData(
                sections: providers.map((p) {
                  final providerName = p['provider'].toString().toLowerCase();
                  Color c = Colors.blue;
                  if (providerName == 'gemini') c = Colors.purple;
                  if (providerName == 'openai') c = Colors.green;
                  if (providerName == 'deepseek') c = Colors.orange;
                  return PieChartSectionData(
                    value: (p['tokens'] as int).toDouble(),
                    title: p['provider'],
                    color: c,
                    radius: 50,
                  );
                }).toList(),
              )
            )
          )
        ],
      )
    );
  }

  Widget _buildAiKeyRow(String providerName, TextEditingController controller) {
    return Row(
      children: [
        Expanded(child: _buildTextField(controller, '$providerName API Key', obscure: true)),
        const SizedBox(width: 8),
        ElevatedButton(
          onPressed: () => _testAiKey(providerName, controller.text),
          style: ElevatedButton.styleFrom(backgroundColor: Colors.blueGrey, foregroundColor: Colors.white),
          child: const Text('Test'),
        ),
      ],
    );
  }

  Future<void> _testAiKey(String provider, String key) async {
    if (key.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('La clave no puede estar vacía')));
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Probando $provider...')));
    final token = await _getToken();
    try {
      final res = await http.post(
        Uri.parse('$kApiBaseUrl/v1/admin/ai-keys/test'),
        headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'},
        body: jsonEncode({"provider": provider.toLowerCase(), "api_key": key}),
      );
      if (res.statusCode == 200) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('✅ $provider: Clave válida y funcionando'), backgroundColor: Colors.green));
      } else {
        final err = jsonDecode(res.body);
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('❌ Error en $provider: ${err["detail"]}'), backgroundColor: Colors.redAccent));
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('❌ Error de red: $e'), backgroundColor: Colors.redAccent));
    }
  }

  Widget _buildAiKeysTab() {
    final openaiCtrl = TextEditingController(text: _aiKeys['openai_api_key'] ?? '');
    final anthropicCtrl = TextEditingController(text: _aiKeys['anthropic_api_key'] ?? '');
    final deepseekCtrl = TextEditingController(text: _aiKeys['deepseek_api_key'] ?? '');
    final geminiCtrl = TextEditingController(text: _aiKeys['gemini_api_key'] ?? '');
    
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: ListView(
        children: [
          const Text('Configuración de API Keys', style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 16),
          _buildAiKeyRow('OpenAI', openaiCtrl),
          const SizedBox(height: 12),
          _buildAiKeyRow('Anthropic', anthropicCtrl),
          const SizedBox(height: 12),
          _buildAiKeyRow('DeepSeek', deepseekCtrl),
          const SizedBox(height: 12),
          _buildAiKeyRow('Gemini', geminiCtrl),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: () {
              _saveAiKeys({
                'openai_api_key': openaiCtrl.text,
                'anthropic_api_key': anthropicCtrl.text,
                'deepseek_api_key': deepseekCtrl.text,
                'gemini_api_key': geminiCtrl.text,
              });
            },
            child: const Text('Guardar Claves'),
          )
        ],
      ),
    );
  }
}
