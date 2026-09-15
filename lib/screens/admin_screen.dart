import 'dart:convert';
import 'package:flutter/material.dart';
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
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadAllData();
  }

  Future<void> _loadAllData() async {
    setState(() => _isLoading = true);
    await Future.wait([
      _loadDashboard(),
      _loadPlans(),
      _loadTenants(),
    ]);
    if (mounted) setState(() => _isLoading = false);
  }

  Future<void> _loadDashboard() async {
    final token = (await SharedPreferences.getInstance()).getString('jwt_token');
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
    final token = (await SharedPreferences.getInstance()).getString('jwt_token');
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
    final token = (await SharedPreferences.getInstance()).getString('jwt_token');
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

  Future<void> _updateTenantPlan(int tenantId, int newPlanId) async {
    final token = (await SharedPreferences.getInstance()).getString('jwt_token');
    if (token == null) return;
    try {
      final res = await http.put(
        Uri.parse('$kApiBaseUrl/v1/admin/tenants/$tenantId'),
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json'
        },
        body: jsonEncode({'id_plan': newPlanId}),
      );
      if (res.statusCode == 200) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text("Plan actualizado correctamente")));
        _loadTenants();
      }
    } catch (e) {
      debugPrint("Error updating tenant: $e");
    }
  }

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
                SwitchListTile(
                  title: const Text('ERP', style: TextStyle(color: Colors.white)),
                  value: pErp,
                  onChanged: (val) => setDialogState(() => pErp = val),
                ),
                SwitchListTile(
                  title: const Text('Inspección', style: TextStyle(color: Colors.white)),
                  value: pIns,
                  onChanged: (val) => setDialogState(() => pIns = val),
                ),
                SwitchListTile(
                  title: const Text('IoT', style: TextStyle(color: Colors.white)),
                  value: pIot,
                  onChanged: (val) => setDialogState(() => pIot = val),
                ),
                SwitchListTile(
                  title: const Text('MikroTik', style: TextStyle(color: Colors.white)),
                  value: pMk,
                  onChanged: (val) => setDialogState(() => pMk = val),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancelar', style: TextStyle(color: Colors.grey)),
            ),
            ElevatedButton(
              onPressed: () async {
                final token = (await SharedPreferences.getInstance()).getString('jwt_token');
                final body = jsonEncode({
                  'nombre_plan': nameCtrl.text,
                  'permite_erp': pErp,
                  'permite_inspeccion': pIns,
                  'permite_iot': pIot,
                  'permite_mikrotik': pMk,
                });
                
                if (isNew) {
                  await http.post(
                    Uri.parse('$kApiBaseUrl/v1/admin/plans'),
                    headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'},
                    body: body,
                  );
                } else {
                  await http.put(
                    Uri.parse('$kApiBaseUrl/v1/admin/plans/${planToEdit['id_plan']}'),
                    headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'},
                    body: body,
                  );
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
          )
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
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _tenants.length,
      itemBuilder: (ctx, i) {
        final t = _tenants[i];
        final planActual = _plans.firstWhere((p) => p['id_plan'] == t['id_plan'], orElse: () => {'nombre_plan': 'Desconocido'});
        
        return Card(
          color: const Color(0xFF1E293B),
          child: ListTile(
            title: Text(t['nombre_organizacion'], style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
            subtitle: Text('Plan Actual: ${planActual['nombre_plan']}', style: const TextStyle(color: Colors.grey)),
            trailing: DropdownButton<int>(
              dropdownColor: const Color(0xFF1E293B),
              value: t['id_plan'],
              style: const TextStyle(color: Colors.cyanAccent),
              items: _plans.map<DropdownMenuItem<int>>((p) {
                return DropdownMenuItem<int>(
                  value: p['id_plan'],
                  child: Text(p['nombre_plan']),
                );
              }).toList(),
              onChanged: (newPlanId) {
                if (newPlanId != null) {
                  _updateTenantPlan(t['id_tenant'], newPlanId);
                }
              },
            ),
          ),
        );
      },
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
}
