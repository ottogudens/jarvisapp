import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'login_screen.dart'; // Contiene kApiBaseUrl
import 'admin_screen.dart';

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
  String _userId = '';
  bool _isSuperAdmin = false;
  
  // Profile Config
  final _orgNameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();


  // MikroTik
  List<dynamic> _mikrotikRouters = [];
  final _mkNameController = TextEditingController();
  final _mkIpController = TextEditingController();
  final _mkPortController = TextEditingController(text: '443');
  final _mkUserController = TextEditingController();
  final _mkPasswordController = TextEditingController();
  // IoT Config
  final _haUrlController = TextEditingController();
  final _haTokenController = TextEditingController();
  final _mqttBrokerController = TextEditingController();
  final _mqttPortController = TextEditingController(text: '1883');
  final _mqttUserController = TextEditingController();
  final _mqttPasswordController = TextEditingController();

  List<dynamic> _perfiles = [];
  int? _activeProfileId;

  final List<String> _sarcasmOptions = ['Bajo', 'Medio', 'Alto', 'Extremo'];

  @override
  void initState() {
    super.initState();
    _loadSettings();
    _loadIoTConfig();
    _loadMikrotikRouters();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token != null) {
      try {
        final parts = token.split('.');
        if (parts.length == 3) {
          final payload = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))));
          _userId = payload['id_usuario']?.toString() ?? '';
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
          _isSuperAdmin = data['is_superadmin'] ?? false;
          _emailController.text = data['email'] ?? '';
          _activeProfileId = data['active_profile_id'];
          _perfiles = data['perfiles'] ?? [];
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

  Future<void> _updateMikrotikRouter(int id, String nombre, String ip, int port, String user, String pass) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    try {
      final body = {
        'nombre': nombre,
        'ip_address': ip,
        'api_port': port,
        'username': user,
      };
      if (pass.isNotEmpty) {
        body['password'] = pass;
      }
      final response = await http.put(
        Uri.parse('$kApiBaseUrl/v1/mikrotik/routers/$id'),
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: jsonEncode(body),
      );
      if (response.statusCode == 200) {
        _loadMikrotikRouters();
      }
    } catch (e) {
      debugPrint('Error updating mikrotik: $e');
    }
  }

  void _showEditMikrotikDialog(Map<String, dynamic> r) {
    final nameCtrl = TextEditingController(text: r['nombre']);
    final ipCtrl = TextEditingController(text: r['ip_address']);
    final portCtrl = TextEditingController(text: r['api_port'].toString());
    final userCtrl = TextEditingController(text: r['username']);
    final passCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          backgroundColor: const Color(0xFF1E293B),
          title: const Text('Editar Router', style: TextStyle(color: Colors.cyanAccent)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildTextField(nameCtrl, 'Nombre', Icons.router),
                const SizedBox(height: 10),
                _buildTextField(ipCtrl, 'IP Address', Icons.computer),
                const SizedBox(height: 10),
                _buildTextField(portCtrl, 'Puerto API', Icons.settings_ethernet, TextInputType.number),
                const SizedBox(height: 10),
                _buildTextField(userCtrl, 'Usuario', Icons.person),
                const SizedBox(height: 10),
                _buildTextField(passCtrl, 'Contraseña (en blanco para no cambiar)', Icons.password, TextInputType.text, true),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancelar', style: TextStyle(color: Colors.white54)),
            ),
            ElevatedButton(
              onPressed: () {
                _updateMikrotikRouter(
                  r['id_router'],
                  nameCtrl.text.trim(),
                  ipCtrl.text.trim(),
                  int.tryParse(portCtrl.text) ?? 443,
                  userCtrl.text.trim(),
                  passCtrl.text.trim(),
                );
                Navigator.pop(context);
              },
              style: ElevatedButton.styleFrom(backgroundColor: Colors.cyan),
              child: const Text('Guardar', style: TextStyle(color: Colors.black)),
            ),
          ],
        );
      },
    );
  }

  Future<void> _connectMikrotik(int id) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    try {
      final response = await http.post(
        Uri.parse('$kApiBaseUrl/v1/mikrotik/routers/$id/connect'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (response.statusCode == 200) {
        _loadMikrotikRouters();
      }
    } catch (e) {
      debugPrint('Error connecting mikrotik: $e');
    }
  }

  Future<void> _disconnectMikrotik(int id) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    try {
      final response = await http.post(
        Uri.parse('$kApiBaseUrl/v1/mikrotik/routers/$id/disconnect'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (response.statusCode == 200) {
        _loadMikrotikRouters();
      }
    } catch (e) {
      debugPrint('Error disconnecting mikrotik: $e');
    }
  }

  Future<void> _saveSettings() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('jarvis_voice_id_$_userId', _voiceIdController.text.trim());
    await prefs.setString('jarvis_sarcasm_level_$_userId', _sarcasmLevel);
    await prefs.setBool('jarvis_hands_free_$_userId', _handsFreeMode);
    await prefs.setString('jarvis_custom_prompt_$_userId', _promptController.text.trim());

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
            if (_activeProfileId != null) 'active_profile_id': _activeProfileId,
          }),
        );
      } catch (e) {
        debugPrint('Error saving profile: $e');
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

  Future<void> _saveProfileInstructions(int idPerfil, String? instruccionesExtra) async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    
    try {
      final res = await http.put(
        Uri.parse('$kApiBaseUrl/v1/admin/tenant/profiles'),
        headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'},
        body: jsonEncode({
          'id_perfil': idPerfil,
          'instrucciones_extra': instruccionesExtra ?? ''
        }),
      );
      if (res.statusCode == 200) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Instrucciones guardadas'), backgroundColor: Colors.green));
      } else {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Error al guardar instrucciones'), backgroundColor: Colors.redAccent));
      }
    } catch (e) {
      debugPrint('Error saving profile instructions: $e');
    }
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

                _buildSectionTitle('Información de la Cuenta'),
                const SizedBox(height: 14),
                _buildTextField(_orgNameController, 'Nombre de la Empresa', Icons.business),
                const SizedBox(height: 10),
                _buildTextField(_emailController, 'Correo Electrónico', Icons.email),
                const SizedBox(height: 10),
                _buildTextField(_passwordController, 'Nueva Contraseña (Opcional)', Icons.lock, TextInputType.text, true),

                if (_isSuperAdmin) ...[
                  const SizedBox(height: 24),
                  Container(
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFFF97316), Color(0xFFEA580C)],
                      ),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: ListTile(
                      leading: const Icon(Icons.admin_panel_settings, color: Colors.white, size: 28),
                      title: const Text('Panel de Control (SuperAdmin)', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                      trailing: const Icon(Icons.arrow_forward_ios, color: Colors.white, size: 16),
                      onTap: () {
                        Navigator.push(context, MaterialPageRoute(builder: (_) => const AdminScreen()));
                      },
                    ),
                  ),
                ],
                
                const SizedBox(height: 32),
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
                
                if (_perfiles.isNotEmpty) ...[
                  const SizedBox(height: 32),
                  _buildSectionTitle('Perfiles J.A.R.V.I.S. Asignados'),
                  const SizedBox(height: 8),
                  Text(
                    'Instrucciones extra aplicadas al rol de estos perfiles.',
                    style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 13),
                  ),
                  const SizedBox(height: 14),
                  if (_perfiles.length > 1) ...[
                    DropdownButtonFormField<int>(
                      value: _activeProfileId,
                      dropdownColor: const Color(0xFF1E293B),
                      style: const TextStyle(color: Colors.white),
                      decoration: InputDecoration(
                        labelText: 'Perfil Activo Actual',
                        labelStyle: TextStyle(color: Colors.cyanAccent.withOpacity(0.8)),
                        filled: true,
                        fillColor: const Color(0xFF0F172A),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                          borderSide: BorderSide(color: Colors.cyan.withOpacity(0.2)),
                        ),
                      ),
                      items: _perfiles.map<DropdownMenuItem<int>>((p) {
                        return DropdownMenuItem<int>(
                          value: p['id_perfil'],
                          child: Text(p['nombre']),
                        );
                      }).toList(),
                      onChanged: (val) {
                        setState(() {
                          _activeProfileId = val;
                        });
                      },
                    ),
                    const SizedBox(height: 16),
                  ],
                  ..._perfiles.map((p) => Padding(
                    padding: const EdgeInsets.only(bottom: 12.0),
                    child: ExpansionTile(
                      title: Text(p['nombre'], style: const TextStyle(color: Colors.cyanAccent)),
                      iconColor: Colors.cyanAccent,
                      collapsedIconColor: Colors.cyanAccent,
                      collapsedBackgroundColor: const Color(0xFF1E293B),
                      backgroundColor: const Color(0xFF1E293B),
                      childrenPadding: const EdgeInsets.all(12),
                      children: [
                        TextField(
                          controller: TextEditingController(text: p['instrucciones_extra'] ?? ''),
                          maxLines: 4,
                          style: const TextStyle(color: Colors.white, fontSize: 13),
                          decoration: InputDecoration(
                            labelText: 'Instrucciones Extra',
                            labelStyle: TextStyle(color: Colors.cyanAccent.withOpacity(0.8)),
                            filled: true,
                            fillColor: const Color(0xFF0F172A),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(8),
                              borderSide: BorderSide(color: Colors.cyan.withOpacity(0.2)),
                            ),
                          ),
                          onChanged: (val) {
                            p['instrucciones_extra'] = val;
                          },
                        ),
                        const SizedBox(height: 8),
                        Align(
                          alignment: Alignment.centerRight,
                          child: ElevatedButton(
                            onPressed: () => _saveProfileInstructions(p['id_perfil'], p['instrucciones_extra']),
                            style: ElevatedButton.styleFrom(backgroundColor: Colors.cyan, foregroundColor: Colors.black),
                            child: const Text('Guardar Instrucciones'),
                          ),
                        ),
                      ],
                    ),
                  )),
                ],

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


                const SizedBox(height: 32),
                _buildSectionTitle('Integración de Red (MikroTik)'),
                const SizedBox(height: 14),
                if (_mikrotikRouters.isNotEmpty)
                  ..._mikrotikRouters.map((r) {
                    final bool isConnected = r['is_connected'] ?? false;
                    final String? lastError = r['last_error'];
                    return ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(
                        Icons.circle,
                        color: isConnected ? Colors.greenAccent : Colors.redAccent,
                        size: 14,
                      ),
                      title: Text(r['nombre'], style: const TextStyle(color: Colors.white)),
                      subtitle: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${r['ip_address']}:${r['api_port']}', style: const TextStyle(color: Colors.white54)),
                          if (!isConnected && lastError != null)
                            Text('Error: $lastError', style: const TextStyle(color: Colors.redAccent, fontSize: 12)),
                        ],
                      ),
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (!isConnected)
                            IconButton(
                              icon: const Icon(Icons.link, color: Colors.cyanAccent),
                              tooltip: 'Conectar',
                              onPressed: () => _connectMikrotik(r['id_router']),
                            )
                          else
                            IconButton(
                              icon: const Icon(Icons.link_off, color: Colors.orangeAccent),
                              tooltip: 'Desconectar',
                              onPressed: () => _disconnectMikrotik(r['id_router']),
                            ),
                          IconButton(
                            icon: const Icon(Icons.edit, color: Colors.amberAccent),
                            tooltip: 'Editar',
                            onPressed: () => _showEditMikrotikDialog(r),
                          ),
                          IconButton(
                            icon: const Icon(Icons.delete, color: Colors.redAccent),
                            onPressed: () => _deleteMikrotikRouter(r['id_router']),
                          ),
                        ],
                      ),
                    );
                  }),
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
