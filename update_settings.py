with open('lib/screens/settings_screen.dart', 'r', encoding='utf-8') as f:
    content = f.read()

state_vars = """  final _voiceIdController = TextEditingController();
  final _promptController = TextEditingController();
  String _sarcasmLevel = 'Medio';
  bool _handsFreeMode = false;
  bool _isLoading = true;
  String _defaultPrompt = '';

  // IoT Config
  final _haUrlController = TextEditingController();
  final _haTokenController = TextEditingController();
  final _mqttBrokerController = TextEditingController();
  final _mqttPortController = TextEditingController(text: '1883');
  final _mqttUserController = TextEditingController();
  final _mqttPasswordController = TextEditingController();
"""
content = content.replace(
    "  final _voiceIdController = TextEditingController();\n  final _promptController = TextEditingController();\n  String _sarcasmLevel = 'Medio';\n  bool _handsFreeMode = false;\n  bool _isLoading = true;\n  String _defaultPrompt = '';",
    state_vars.strip('\n')
)

load_iot = """    if (mounted) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _loadIoTConfig() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    try {
      final response = await http.get(
        Uri.parse('$kApiBaseUrl/v1/iot/config'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _haUrlController.text = data['ha_url'] ?? '';
          _haTokenController.text = data['ha_token'] ?? '';
          _mqttBrokerController.text = data['mqtt_broker'] ?? '';
          _mqttPortController.text = data['mqtt_port']?.toString() ?? '1883';
          _mqttUserController.text = data['mqtt_user'] ?? '';
          _mqttPasswordController.text = data['mqtt_password'] ?? '';
        });
      }
    } catch (e) {
      debugPrint('Error loading IoT config: $e');
    }
  }
"""

content = content.replace(
    "    if (mounted) {\n      setState(() => _isLoading = false);\n    }\n  }",
    load_iot.strip('\n')
)

init_state_replace = """  @override
  void initState() {
    super.initState();
    _loadSettings();
    _loadIoTConfig();
  }"""

content = content.replace(
    "  @override\n  void initState() {\n    super.initState();\n    _loadSettings();\n  }",
    init_state_replace
)

save_iot = """  Future<void> _saveSettings() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('jarvis_voice_id', _voiceIdController.text.trim());
    await prefs.setString('jarvis_sarcasm_level', _sarcasmLevel);
    await prefs.setBool('jarvis_hands_free', _handsFreeMode);
    await prefs.setString('jarvis_custom_prompt', _promptController.text.trim());

    final token = prefs.getString('jwt_token');
    if (token != null) {
      try {
        await http.post(
          Uri.parse('$kApiBaseUrl/v1/iot/config'),
          headers: {
            'Authorization': 'Bearer $token',
            'Content-Type': 'application/json',
          },
          body: jsonEncode({
            'ha_url': _haUrlController.text.trim(),
            'ha_token': _haTokenController.text.trim(),
            'mqtt_broker': _mqttBrokerController.text.trim(),
            'mqtt_port': int.tryParse(_mqttPortController.text) ?? 1883,
            'mqtt_user': _mqttUserController.text.trim(),
            'mqtt_password': _mqttPasswordController.text.trim(),
          }),
        );
      } catch (e) {
        debugPrint('Error saving IoT config: $e');
      }
    }"""

content = content.replace(
    "  Future<void> _saveSettings() async {\n    final prefs = await SharedPreferences.getInstance();\n    await prefs.setString('jarvis_voice_id', _voiceIdController.text.trim());\n    await prefs.setString('jarvis_sarcasm_level', _sarcasmLevel);\n    await prefs.setBool('jarvis_hands_free', _handsFreeMode);\n    await prefs.setString('jarvis_custom_prompt', _promptController.text.trim());",
    save_iot
)

ui_section = """                const SizedBox(height: 32),
                _buildSectionTitle('Integración IoT (Domótica)'),
                const SizedBox(height: 14),
                _buildTextField(_haUrlController, 'Home Assistant URL', Icons.home_work),
                const SizedBox(height: 10),
                _buildTextField(_haTokenController, 'Home Assistant Token (Long-Lived)', Icons.key),
                const SizedBox(height: 10),
                _buildTextField(_mqttBrokerController, 'MQTT Broker Host', Icons.router),
                const SizedBox(height: 10),
                _buildTextField(_mqttPortController, 'MQTT Broker Port', Icons.settings_ethernet, TextInputType.number),
                const SizedBox(height: 10),
                _buildTextField(_mqttUserController, 'MQTT User (Opcional)', Icons.person),
                const SizedBox(height: 10),
                _buildTextField(_mqttPasswordController, 'MQTT Password (Opcional)', Icons.password, TextInputType.text, true),

                const SizedBox(height: 48),"""

content = content.replace(
    "                const SizedBox(height: 48),",
    ui_section
)

text_field_helper = """  Widget _buildSectionTitle(String title) {
    return Text(
      title.toUpperCase(),
      style: const TextStyle(
        color: Colors.cyan,
        fontWeight: FontWeight.bold,
        letterSpacing: 1.5,
        fontSize: 13,
      ),
    );
  }

  Widget _buildTextField(TextEditingController controller, String label, IconData icon, [TextInputType type = TextInputType.text, bool obscure = false]) {
    return TextField(
      controller: controller,
      style: const TextStyle(color: Colors.white),
      keyboardType: type,
      obscureText: obscure,
      decoration: InputDecoration(
        labelText: label,
        labelStyle: TextStyle(color: Colors.white.withOpacity(0.5)),
        filled: true,
        fillColor: const Color(0xFF1E293B),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        prefixIcon: Icon(icon, color: Colors.cyanAccent),
      ),
    );
  }
"""

content = content.replace(
    "  Widget _buildSectionTitle(String title) {\n    return Text(\n      title.toUpperCase(),\n      style: const TextStyle(\n        color: Colors.cyan,\n        fontWeight: FontWeight.bold,\n        letterSpacing: 1.5,\n        fontSize: 13,\n      ),\n    );\n  }",
    text_field_helper.strip('\n')
)

with open('lib/screens/settings_screen.dart', 'w', encoding='utf-8') as f:
    f.write(content)
print("Settings updated successfully!")
