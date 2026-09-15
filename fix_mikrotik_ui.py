with open('lib/screens/settings_screen.dart', 'r', encoding='utf-8') as f:
    content = f.read()

state_vars = """
  // MikroTik
  List<dynamic> _mikrotikRouters = [];
  final _mkNameController = TextEditingController();
  final _mkIpController = TextEditingController();
  final _mkPortController = TextEditingController(text: '443');
  final _mkUserController = TextEditingController();
  final _mkPasswordController = TextEditingController();
"""

content = content.replace("  // IoT Config", state_vars + "  // IoT Config")

init_state = """    _loadSettings();
    _loadIoTConfig();
    _loadMikrotikRouters();"""
content = content.replace("    _loadSettings();\n    _loadIoTConfig();", init_state)

mikrotik_logic = """
  Future<void> _loadMikrotikRouters() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    try {
      final response = await http.get(
        Uri.parse('$kApiBaseUrl/v1/mikrotik/routers'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (response.statusCode == 200) {
        setState(() {
          _mikrotikRouters = jsonDecode(response.body);
        });
      }
    } catch (e) {
      debugPrint('Error loading mikrotik: $e');
    }
  }

  Future<void> _addMikrotikRouter() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    try {
      final response = await http.post(
        Uri.parse('$kApiBaseUrl/v1/mikrotik/routers'),
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'nombre': _mkNameController.text.trim(),
          'ip_address': _mkIpController.text.trim(),
          'api_port': int.tryParse(_mkPortController.text) ?? 443,
          'username': _mkUserController.text.trim(),
          'password': _mkPasswordController.text.trim(),
        }),
      );
      if (response.statusCode == 200) {
        _mkNameController.clear();
        _mkIpController.clear();
        _mkPortController.text = '443';
        _mkUserController.clear();
        _mkPasswordController.clear();
        _loadMikrotikRouters();
      }
    } catch (e) {
      debugPrint('Error adding mikrotik: $e');
    }
  }

  Future<void> _deleteMikrotikRouter(int id) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    try {
      final response = await http.delete(
        Uri.parse('$kApiBaseUrl/v1/mikrotik/routers/$id'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (response.statusCode == 200) {
        _loadMikrotikRouters();
      }
    } catch (e) {
      debugPrint('Error deleting mikrotik: $e');
    }
  }
"""
import re
content = re.sub(r'  Future<void> _saveSettings\(\) async \{', mikrotik_logic + '\n  Future<void> _saveSettings() async {', content, count=1)


mikrotik_ui = """
                const SizedBox(height: 32),
                _buildSectionTitle('Integración de Red (MikroTik)'),
                const SizedBox(height: 14),
                if (_mikrotikRouters.isNotEmpty)
                  ..._mikrotikRouters.map((r) => ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text(r['nombre'], style: const TextStyle(color: Colors.white)),
                    subtitle: Text('${r['ip_address']}:${r['api_port']}', style: TextStyle(color: Colors.white54)),
                    trailing: IconButton(
                      icon: const Icon(Icons.delete, color: Colors.redAccent),
                      onPressed: () => _deleteMikrotikRouter(r['id_router']),
                    ),
                  )),
                const SizedBox(height: 10),
                ExpansionTile(
                  title: const Text('Agregar Nuevo Router', style: TextStyle(color: Colors.cyanAccent)),
                  iconColor: Colors.cyanAccent,
                  collapsedIconColor: Colors.cyanAccent,
                  childrenPadding: const EdgeInsets.all(8),
                  children: [
                    _buildTextField(_mkNameController, 'Nombre (Ej: Oficina Principal)', Icons.router),
                    const SizedBox(height: 10),
                    _buildTextField(_mkIpController, 'IP Address', Icons.computer),
                    const SizedBox(height: 10),
                    _buildTextField(_mkPortController, 'Puerto API REST (Por defecto 443)', Icons.settings_ethernet, TextInputType.number),
                    const SizedBox(height: 10),
                    _buildTextField(_mkUserController, 'Usuario', Icons.person),
                    const SizedBox(height: 10),
                    _buildTextField(_mkPasswordController, 'Contraseña', Icons.password, TextInputType.text, true),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: _addMikrotikRouter,
                      style: ElevatedButton.styleFrom(backgroundColor: Colors.cyan),
                      child: const Text('Guardar Router', style: TextStyle(color: Colors.black)),
                    )
                  ],
                ),
"""

content = content.replace("                const SizedBox(height: 48),\n                SizedBox(\n                  height: 52,", mikrotik_ui + "                const SizedBox(height: 48),\n                SizedBox(\n                  height: 52,")

with open('lib/screens/settings_screen.dart', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated settings_screen.dart with mikrotik UI")
