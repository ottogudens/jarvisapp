import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'login_screen.dart'; // Contiene kApiBaseUrl

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({Key? key}) : super(key: key);

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _voiceIdController = TextEditingController();
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

  final List<String> _sarcasmOptions = ['Bajo', 'Medio', 'Alto', 'Extremo'];

  @override
  void initState() {
    super.initState();
    _loadSettings();
    _loadIoTConfig();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    final savedPrompt = prefs.getString('jarvis_custom_prompt');

    setState(() {
      _voiceIdController.text = prefs.getString('jarvis_voice_id') ?? '';
      _sarcasmLevel = prefs.getString('jarvis_sarcasm_level') ?? 'Medio';
      _handsFreeMode = prefs.getBool('jarvis_hands_free') ?? false;
    });

    // Cargar prompt por defecto desde el servidor si no hay uno guardado o para tenerlo de referencia
    if (token != null) {
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

  Future<void> _saveSettings() async {
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
    }

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Configuración guardada exitosamente', style: TextStyle(color: Colors.black)),
        backgroundColor: Colors.cyanAccent,
      ),
    );
  }

  void _restoreDefaultPrompt() {
    if (_defaultPrompt.isNotEmpty) {
      setState(() {
        _promptController.text = _defaultPrompt;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Rol restaurado al predeterminado del sistema')),
      );
    }
  }

  @override
  void dispose() {
    _voiceIdController.dispose();
    _promptController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        title: const Text('Configuración J.A.R.V.I.S.', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
        backgroundColor: const Color(0xFF1E293B),
        elevation: 0,
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Colors.cyanAccent))
          : ListView(
              padding: const EdgeInsets.all(24.0),
              children: [
                _buildSectionTitle('Rol e Instrucciones del Agente'),
                const SizedBox(height: 8),
                Text(
                  'Personaliza cómo debe pensar y actuar J.A.R.V.I.S. Puedes redefinir su rol completo a continuación:',
                  style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 13),
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: _promptController,
                  maxLines: 8,
                  style: const TextStyle(color: Colors.white, fontSize: 14, height: 1.4),
                  decoration: InputDecoration(
                    labelText: 'Instrucciones del Sistema (Rol Actual)',
                    alignLabelWithHint: true,
                    labelStyle: TextStyle(color: Colors.cyanAccent.withOpacity(0.8)),
                    filled: true,
                    fillColor: const Color(0xFF1E293B),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(color: Colors.cyan.withOpacity(0.2)),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: const BorderSide(color: Colors.cyanAccent),
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    onPressed: _restoreDefaultPrompt,
                    icon: const Icon(Icons.restore, color: Colors.cyanAccent, size: 16),
                    label: const Text('Restaurar rol predeterminado', style: TextStyle(color: Colors.cyanAccent, fontSize: 12)),
                  ),
                ),

                const SizedBox(height: 24),
                _buildSectionTitle('Voz y Audio'),
                const SizedBox(height: 14),
                TextField(
                  controller: _voiceIdController,
                  style: const TextStyle(color: Colors.white),
                  decoration: InputDecoration(
                    labelText: 'ElevenLabs Voice ID (Opcional)',
                    labelStyle: TextStyle(color: Colors.white.withOpacity(0.5)),
                    hintText: 'Ej: 21m00Tcm4TlvDq8ikWAM',
                    hintStyle: TextStyle(color: Colors.white.withOpacity(0.2)),
                    filled: true,
                    fillColor: const Color(0xFF1E293B),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide.none,
                    ),
                    prefixIcon: const Icon(Icons.record_voice_over, color: Colors.cyanAccent),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  'Déjalo en blanco para usar la voz por defecto configurada en el servidor.',
                  style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12),
                ),

                const SizedBox(height: 32),
                _buildSectionTitle('Personalidad de IA'),
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1E293B),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.psychology, color: Colors.cyanAccent),
                      const SizedBox(width: 16),
                      Expanded(
                        child: DropdownButtonHideUnderline(
                          child: DropdownButton<String>(
                            value: _sarcasmLevel,
                            dropdownColor: const Color(0xFF1E293B),
                            style: const TextStyle(color: Colors.white, fontSize: 16),
                            icon: const Icon(Icons.arrow_drop_down, color: Colors.cyanAccent),
                            isExpanded: true,
                            items: _sarcasmOptions.map((String value) {
                              return DropdownMenuItem<String>(
                                value: value,
                                child: Text('Nivel de Sarcasmo: $value'),
                              );
                            }).toList(),
                            onChanged: (newValue) {
                              if (newValue != null) {
                                setState(() => _sarcasmLevel = newValue);
                              }
                            },
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  'Controla la cantidad de ironía y estilo británico en las respuestas.',
                  style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12),
                ),

                const SizedBox(height: 32),
                _buildSectionTitle('Interacción Manos Libres'),
                const SizedBox(height: 14),
                SwitchListTile(
                  title: const Text('Modo Manos Libres Activo', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600)),
                  subtitle: const Text(
                    'Respuesta automática por voz y control con el botón del auricular inalámbrico (inicia grabación, y envía tras 3s de silencio o nuevo clic).',
                    style: TextStyle(color: Colors.white54, fontSize: 12),
                  ),
                  value: _handsFreeMode,
                  activeColor: Colors.cyanAccent,
                  tileColor: const Color(0xFF1E293B),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  secondary: const Icon(Icons.headset_mic, color: Colors.cyanAccent),
                  onChanged: (value) {
                    setState(() => _handsFreeMode = value);
                  },
                ),

                const SizedBox(height: 32),
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

                const SizedBox(height: 48),
                SizedBox(
                  height: 52,
                  child: ElevatedButton.icon(
                    onPressed: _saveSettings,
                    icon: const Icon(Icons.save, color: Colors.black87),
                    label: const Text('GUARDAR CONFIGURACIÓN', style: TextStyle(color: Colors.black87, fontWeight: FontWeight.bold, letterSpacing: 1)),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.cyanAccent,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
                const SizedBox(height: 32),
              ],
            ),
    );
  }

  Widget _buildSectionTitle(String title) {
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
}
