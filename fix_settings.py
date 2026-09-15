with open('lib/screens/settings_screen.dart', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace shared_preferences keys
content = content.replace("prefs.getString('jarvis_voice_id')", "prefs.getString('jarvis_voice_id_$_userId')")
content = content.replace("prefs.getString('jarvis_sarcasm_level')", "prefs.getString('jarvis_sarcasm_level_$_userId')")
content = content.replace("prefs.getBool('jarvis_hands_free')", "prefs.getBool('jarvis_hands_free_$_userId')")
content = content.replace("prefs.getString('jarvis_custom_prompt')", "prefs.getString('jarvis_custom_prompt_$_userId')")

content = content.replace("prefs.setString('jarvis_voice_id', ", "prefs.setString('jarvis_voice_id_$_userId', ")
content = content.replace("prefs.setString('jarvis_sarcasm_level', ", "prefs.setString('jarvis_sarcasm_level_$_userId', ")
content = content.replace("prefs.setBool('jarvis_hands_free', ", "prefs.setBool('jarvis_hands_free_$_userId', ")
content = content.replace("prefs.setString('jarvis_custom_prompt', ", "prefs.setString('jarvis_custom_prompt_$_userId', ")

# Add state variables
state_vars = """  String _userId = '';
  
  // Profile Config
  final _orgNameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();"""
content = content.replace("String _defaultPrompt = '';", "String _defaultPrompt = '';\n" + state_vars)

# Load profile logic
load_settings = """  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token != null) {
      try {
        final parts = token.split('.');
        if (parts.length == 3) {
          final payload = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))));
          _userId = payload['sub']?.toString() ?? '';
        }
      } catch (_) {}
    }
    
    final savedPrompt = prefs.getString('jarvis_custom_prompt_$_userId');

    setState(() {
      _voiceIdController.text = prefs.getString('jarvis_voice_id_$_userId') ?? '';
      _sarcasmLevel = prefs.getString('jarvis_sarcasm_level_$_userId') ?? 'Medio';
      _handsFreeMode = prefs.getBool('jarvis_hands_free_$_userId') ?? false;
    });

    if (token != null) {
      try {
        final profileResp = await http.get(
          Uri.parse('$kApiBaseUrl/v1/auth/profile'),
          headers: {'Authorization': 'Bearer $token'},
        );
        if (profileResp.statusCode == 200) {
          final data = jsonDecode(profileResp.body);
          _orgNameController.text = data['nombre_organizacion'] ?? '';
          _emailController.text = data['email'] ?? '';
        }
      } catch (e) {
        debugPrint('Error perfil: $e');
      }

      try {
        final response = await http.get(
          Uri.parse('$kApiBaseUrl/v1/agent/prompt'),
          headers: {'Authorization': 'Bearer $token'},
        );
        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          _defaultPrompt = data['prompt'] ?? '';
        }
      } catch (e) {
        debugPrint('Error al obtener prompt por defecto: $e');
      }
    }

    if (savedPrompt != null && savedPrompt.isNotEmpty) {
      _promptController.text = savedPrompt;
    } else if (_defaultPrompt.isNotEmpty) {
      _promptController.text = _defaultPrompt;
    }

    if (mounted) {
      setState(() => _isLoading = false);
    }
  }"""

# Inject load settings (we just completely replace it)
import re
content = re.sub(r'  Future<void> _loadSettings\(\) async \{.*?(?=\n  Future<void> _loadIoTConfig\(\))', load_settings, content, flags=re.DOTALL)

# Add save profile logic
save_profile = """
    // Guardar perfil
    if (token != null) {
      try {
        await http.put(
          Uri.parse('$kApiBaseUrl/v1/auth/profile'),
          headers: {
            'Authorization': 'Bearer $token',
            'Content-Type': 'application/json',
          },
          body: jsonEncode({
            'nombre_organizacion': _orgNameController.text.trim(),
            'email': _emailController.text.trim(),
            'password': _passwordController.text.isNotEmpty ? _passwordController.text : null,
          }),
        );
      } catch (e) {
        debugPrint('Error saving profile: $e');
      }
    }
"""
content = content.replace("    if (!mounted) return;\n    ScaffoldMessenger.of(context).showSnackBar", save_profile + "\n    if (!mounted) return;\n    ScaffoldMessenger.of(context).showSnackBar")

# Add UI sections
ui_sections = """
                _buildSectionTitle('Información de la Cuenta'),
                const SizedBox(height: 14),
                _buildTextField(_orgNameController, 'Nombre de la Empresa', Icons.business),
                const SizedBox(height: 10),
                _buildTextField(_emailController, 'Correo Electrónico', Icons.email),
                const SizedBox(height: 10),
                _buildTextField(_passwordController, 'Nueva Contraseña (Opcional)', Icons.lock, TextInputType.text, true),
                
                const SizedBox(height: 32),
"""
content = content.replace("                _buildSectionTitle('Rol e Instrucciones del Agente'),", ui_sections + "                _buildSectionTitle('Rol e Instrucciones del Agente'),")

with open('lib/screens/settings_screen.dart', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated settings_screen.dart")
