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

  // Telegram Config & Status
  bool _telegramConnected = false;
  String? _telegramUsername;
  String? _telegramChatId;
  String? _linkCode;
  bool _isGeneratingCode = false;
  bool _tenantBotConfigured = false;
  final _telegramBotTokenController = TextEditingController();
  bool _isConfiguringBot = false;

  // IoT Config & Connection Status
  final _haUrlController = TextEditingController();
  final _haTokenController = TextEditingController();
  bool? _haConnected;
  bool _testingHA = false;
  String? _haStatusMessage;

  final _mqttBrokerController = TextEditingController();
  final _mqttPortController = TextEditingController(text: '1883');
  final _mqttUserController = TextEditingController();
  final _mqttPasswordController = TextEditingController();
  bool? _mqttConnected;
  bool _testingMQTT = false;
  String? _mqttStatusMessage;

  // MikroTik
  List<dynamic> _mikrotikRouters = [];
  final _mkNameController = TextEditingController();
  final _mkIpController = TextEditingController();
  final _mkPortController = TextEditingController(text: '443');
  final _mkUserController = TextEditingController();
  final _mkPasswordController = TextEditingController();

  List<dynamic> _perfiles = [];
  int? _activeProfileId;

  bool _permiteTelegram = false;
  bool _permiteWhatsapp = false;
  bool _permiteIOT = false;
  bool _permiteMikrotik = false;
  bool _permiteERP = false;
  bool _permiteInspeccion = false;

  final List<String> _sarcasmOptions = ['Bajo', 'Medio', 'Alto', 'Extremo'];

  Widget _premiumBlock(Widget child, bool isPermitted) {
    if (isPermitted) return child;
    return Stack(
      children: [
        Opacity(
          opacity: 0.3,
          child: IgnorePointer(
            child: child,
          ),
        ),
        Positioned.fill(
          child: Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.lock, color: Colors.cyanAccent, size: 40),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  decoration: BoxDecoration(color: Colors.black87, borderRadius: BorderRadius.circular(20), border: Border.all(color: Colors.cyanAccent.withOpacity(0.5))),
                  child: const Text('Disponible en plan superior', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13)),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  @override
  void initState() {
    super.initState();
    _loadSettings();
    _loadIoTConfig();
    _loadMikrotikRouters();
    _loadTelegramStatus();
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
          
          if (data['plan_features'] != null) {
            _permiteTelegram = data['plan_features']['telegram'] ?? false;
            _permiteWhatsapp = data['plan_features']['whatsapp'] ?? false;
            _permiteIOT = data['plan_features']['iot'] ?? false;
            _permiteMikrotik = data['plan_features']['mikrotik'] ?? false;
            _permiteERP = data['plan_features']['erp'] ?? false;
            _permiteInspeccion = data['plan_features']['inspeccion'] ?? false;
          }
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

  Future<void> _loadTelegramStatus() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    try {
      final res = await http.get(
        Uri.parse('$kApiBaseUrl/v1/telegram/status'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        setState(() {
          _tenantBotConfigured = data['tenant_bot_configured'] ?? false;
          _telegramConnected = data['connected'] ?? false;
          _telegramChatId = data['telegram_chat_id']?.toString();
          _telegramUsername = data['telegram_username'];
        });
      }
    } catch (e) {
      debugPrint('Error loading Telegram status: $e');
    }
  }

  Future<void> _configurarNuevoBotTelegram() async {
    final tokenValue = _telegramBotTokenController.text.trim();
    if (tokenValue.isEmpty) return;
    
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    setState(() => _isConfiguringBot = true);
    
    try {
      final res = await http.post(
        Uri.parse('$kApiBaseUrl/v1/telegram/config'),
        headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'},
        body: jsonEncode({'bot_token': tokenValue}),
      );
      if (res.statusCode == 200) {
        setState(() => _tenantBotConfigured = true);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Bot SaaS desplegado y configurado exitosamente', style: TextStyle(color: Colors.white)), backgroundColor: Colors.green));
      } else {
        final body = jsonDecode(res.body);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(body['detail'] ?? 'Error configurando bot'), backgroundColor: Colors.redAccent));
      }
    } catch (e) {
      debugPrint('Error configurando bot: $e');
    } finally {
      setState(() => _isConfiguringBot = false);
    }
  }

  Future<void> _generateTelegramLinkCode() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    setState(() => _isGeneratingCode = true);
    try {
      final res = await http.post(
        Uri.parse('$kApiBaseUrl/v1/telegram/link-code'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        setState(() {
          _linkCode = data['link_code'];
        });
      }
    } catch (e) {
      debugPrint('Error generating link code: $e');
    } finally {
      if (mounted) setState(() => _isGeneratingCode = false);
    }
  }

  Future<void> _unlinkTelegram() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    try {
      final res = await http.post(
        Uri.parse('$kApiBaseUrl/v1/telegram/unlink'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (res.statusCode == 200) {
        setState(() {
          _telegramConnected = false;
          _telegramChatId = null;
          _telegramUsername = null;
          _linkCode = null;
        });
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Telegram desvinculado'), backgroundColor: Colors.orangeAccent),
          );
        }
      }
    } catch (e) {
      debugPrint('Error unlinking Telegram: $e');
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
        
        // Auto check MQTT if configured to persist the UI green badge after reload
        if (_mqttBrokerController.text.isNotEmpty) {
           _testMQTTConnection();
        }
      }
    } catch (e) {
      debugPrint('Error loading IoT config: $e');
    }
  }

  Future<void> _testHAConnection() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    setState(() {
      _testingHA = true;
      _haStatusMessage = null;
    });
    try {
      final res = await http.post(
        Uri.parse('$kApiBaseUrl/v1/iot/test-ha'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        setState(() {
          _haConnected = data['connected'] ?? false;
          _haStatusMessage = data['message'];
        });
      }
    } catch (e) {
      setState(() {
        _haConnected = false;
        _haStatusMessage = 'Error de conexión: $e';
      });
    } finally {
      if (mounted) setState(() => _testingHA = false);
    }
  }

  Future<void> _testMQTTConnection() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token == null) return;
    setState(() {
      _testingMQTT = true;
      _mqttStatusMessage = null;
    });
    try {
      final res = await http.post(
        Uri.parse('$kApiBaseUrl/v1/iot/test-mqtt'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        setState(() {
          _mqttConnected = data['connected'] ?? false;
          _mqttStatusMessage = data['message'];
        });
      }
    } catch (e) {
      setState(() {
        _mqttConnected = false;
        _mqttStatusMessage = 'Error de conexión: $e';
      });
    } finally {
      if (mounted) setState(() => _testingMQTT = false);
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
                  int.tryParse(portCtrl.text) ?? 80,
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
  void dispose() {
    _voiceIdController.dispose();
    _promptController.dispose();
    _haUrlController.dispose();
    _haTokenController.dispose();
    _mqttBrokerController.dispose();
    _mqttPortController.dispose();
    _mqttUserController.dispose();
    _mqttPasswordController.dispose();
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
                
                // INTEGRACIÓN TELEGRAM
                const SizedBox(height: 32),
                _buildSectionTitle('Integración Bot de Telegram'),
                const SizedBox(height: 14),
                _premiumBlock(Card(
                  color: const Color(0xFF1E293B),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  child: ExpansionTile(
                    leading: Icon(
                      Icons.send,
                      color: _telegramConnected ? Colors.lightBlueAccent : Colors.white38,
                    ),
                    title: Row(
                      children: [
                        const Text('Bot de Telegram', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                        const SizedBox(width: 8),
                        _buildStatusBadge(_telegramConnected),
                      ],
                    ),
                    subtitle: Text(
                       _tenantBotConfigured 
                          ? (_telegramConnected ? 'Conectado como admin${_telegramUsername != null ? ' (@$_telegramUsername)' : ''}' : 'Bot SaaS Operacional (Tu cuenta no está vinculada)')
                          : 'Bot Principal No Configurado',
                      style: TextStyle(color: _tenantBotConfigured ? Colors.greenAccent : Colors.orangeAccent, fontSize: 12),
                    ),
                    iconColor: Colors.cyanAccent,
                    collapsedIconColor: Colors.cyanAccent,
                    childrenPadding: const EdgeInsets.all(16),
                    children: [
                      if (!_tenantBotConfigured) ...[
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(color: const Color(0xFF0F172A), borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.cyanAccent.withOpacity(0.5))),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('Paso 1: Crea tu Bot', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14)),
                              const SizedBox(height: 8),
                              const Text('1. Busca a @BotFather en Telegram.\n2. Envíale el comando /newbot y ponle un nombre.\n3. Copia el "HTTP API Token" que te entregará.\n4. Pégalo debajo para desplegarlo de inmediato.', style: TextStyle(color: Colors.white70, fontSize: 13, height: 1.4)),
                              const SizedBox(height: 16),
                              _buildTextField(_telegramBotTokenController, 'Pega el Token (API Key)', Icons.key),
                              const SizedBox(height: 12),
                              ElevatedButton.icon(
                                onPressed: _isConfiguringBot ? null : _configurarNuevoBotTelegram,
                                icon: _isConfiguringBot ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black)) : const Icon(Icons.rocket_launch, color: Colors.black),
                                label: const Text('Conectar Bot', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                                style: ElevatedButton.styleFrom(backgroundColor: Colors.cyanAccent),
                              ),
                            ],
                          ),
                        ),
                      ] else ...[
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(color: Colors.cyan.withOpacity(0.1), border: Border.all(color: Colors.cyanAccent.withOpacity(0.5)), borderRadius: BorderRadius.circular(8)),
                          child: const Row(children: [Icon(Icons.check_circle, color: Colors.cyanAccent, size: 20), SizedBox(width: 8), Expanded(child: Text('El Bot Inteligente de tu organización está desplegado.', style: TextStyle(color: Colors.white, fontSize: 13)))]),
                        ),
                        const SizedBox(height: 16),
                        const Divider(color: Colors.white24),
                        const SizedBox(height: 12),
                        const Text('Vincular tu cuenta personal al ChatBot', style: TextStyle(color: Colors.cyanAccent, fontWeight: FontWeight.bold, fontSize: 14)),
                        const SizedBox(height: 8),
                      if (_telegramConnected) ...[
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: Colors.green.withOpacity(0.1),
                            border: Border.all(color: Colors.greenAccent.withOpacity(0.3)),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  const Icon(Icons.check_circle, color: Colors.greenAccent, size: 20),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      'Tu cuenta está vinculada exitosamente con Telegram.',
                                      style: TextStyle(color: Colors.white.withOpacity(0.9), fontSize: 13),
                                    ),
                                  ),
                                ],
                              ),
                              if (_telegramChatId != null) ...[
                                const SizedBox(height: 6),
                                Text('Chat ID: $_telegramChatId', style: const TextStyle(color: Colors.white54, fontSize: 12)),
                              ]
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        OutlinedButton.icon(
                          onPressed: _unlinkTelegram,
                          icon: const Icon(Icons.link_off, color: Colors.redAccent),
                          label: const Text('Desvincular Telegram', style: TextStyle(color: Colors.redAccent)),
                          style: OutlinedButton.styleFrom(
                            side: const BorderSide(color: Colors.redAccent),
                          ),
                        ),
                      ] else ...[
                        Text(
                          'Para conectar tu agente J.A.R.V.I.S. con Telegram, genera un código de vinculación e ingrésalo en tu bot.',
                          style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 13),
                        ),
                        const SizedBox(height: 16),
                        if (_linkCode != null) ...[
                          Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: const Color(0xFF0F172A),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: Colors.cyanAccent.withOpacity(0.5)),
                            ),
                            child: Column(
                              children: [
                                const Text('Código de Vinculación:', style: TextStyle(color: Colors.white54, fontSize: 12)),
                                const SizedBox(height: 6),
                                SelectableText(
                                  _linkCode!,
                                  style: const TextStyle(color: Colors.cyanAccent, fontSize: 28, fontWeight: FontWeight.bold, letterSpacing: 4),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  'Abre tu Bot de Telegram y envía el comando:\n/start $_linkCode',
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(color: Colors.white70, fontSize: 13),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 12),
                        ],
                        ElevatedButton.icon(
                          onPressed: _isGeneratingCode ? null : _generateTelegramLinkCode,
                          icon: _isGeneratingCode 
                              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                              : const Icon(Icons.qr_code, color: Colors.black),
                          label: Text(_linkCode == null ? 'Generar Código de Vinculación' : 'Regenerar Código', style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                          style: ElevatedButton.styleFrom(backgroundColor: Colors.cyanAccent),
                        ),
                      ],
                    ],
                  ],
                )),
                
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
                    'Respuesta automática por voz y control con el botón del auricular inalámbrico.',
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

                // INTEGRACIÓN IOT (DOMÓTICA)
                const SizedBox(height: 32),
                _buildSectionTitle('Integración IoT (Domótica)'),
                const SizedBox(height: 14),
                _premiumBlock(
                  Card(
                    color: const Color(0xFF1E293B),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  child: ExpansionTile(
                    leading: Icon(
                      Icons.home_work,
                      color: _haConnected == true ? Colors.greenAccent : Colors.cyanAccent,
                    ),
                    title: Row(
                      children: [
                        const Text('Home Assistant', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                        const SizedBox(width: 8),
                        _buildStatusBadge(_haConnected),
                      ],
                    ),
                    subtitle: Text(
                      _haUrlController.text.isNotEmpty ? _haUrlController.text : 'No configurado',
                      style: const TextStyle(color: Colors.white54, fontSize: 12),
                    ),
                    iconColor: Colors.cyanAccent,
                    collapsedIconColor: Colors.cyanAccent,
                    childrenPadding: const EdgeInsets.all(16),
                    children: [
                      _buildTextField(_haUrlController, 'Home Assistant URL', Icons.link),
                      const SizedBox(height: 10),
                      _buildTextField(_haTokenController, 'Home Assistant Token (Long-Lived)', Icons.key, TextInputType.text, true),
                      const SizedBox(height: 12),
                      if (_haStatusMessage != null) ...[
                        Text(
                          _haStatusMessage!,
                          style: TextStyle(
                            color: _haConnected == true ? Colors.greenAccent : Colors.redAccent,
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(height: 8),
                      ],
                      Align(
                        alignment: Alignment.centerRight,
                        child: OutlinedButton.icon(
                          onPressed: _testingHA ? null : _testHAConnection,
                          icon: _testingHA 
                              ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.cyanAccent))
                              : const Icon(Icons.network_check, color: Colors.cyanAccent, size: 18),
                          label: const Text('Probar Conexión HA', style: TextStyle(color: Colors.cyanAccent)),
                          style: OutlinedButton.styleFrom(side: const BorderSide(color: Colors.cyanAccent)),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
                Card(
                  color: const Color(0xFF1E293B),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  child: ExpansionTile(
                    leading: Icon(
                      Icons.hub,
                      color: _mqttConnected == true ? Colors.greenAccent : Colors.cyanAccent,
                    ),
                    title: Row(
                      children: [
                        const Text('MQTT Broker', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                        const SizedBox(width: 8),
                        _buildStatusBadge(_mqttConnected),
                      ],
                    ),
                    subtitle: Text(
                      _mqttBrokerController.text.isNotEmpty ? '${_mqttBrokerController.text}:${_mqttPortController.text}' : 'No configurado',
                      style: const TextStyle(color: Colors.white54, fontSize: 12),
                    ),
                    iconColor: Colors.cyanAccent,
                    collapsedIconColor: Colors.cyanAccent,
                    childrenPadding: const EdgeInsets.all(16),
                    children: [
                      _buildTextField(_mqttBrokerController, 'MQTT Broker Host', Icons.router),
                      const SizedBox(height: 10),
                      _buildTextField(_mqttPortController, 'MQTT Broker Port', Icons.settings_ethernet, TextInputType.number),
                      const SizedBox(height: 10),
                      _buildTextField(_mqttUserController, 'MQTT User (Opcional)', Icons.person),
                      const SizedBox(height: 10),
                      _buildTextField(_mqttPasswordController, 'MQTT Password (Opcional)', Icons.password, TextInputType.text, true),
                      const SizedBox(height: 12),
                      if (_mqttStatusMessage != null) ...[
                        Text(
                          _mqttStatusMessage!,
                          style: TextStyle(
                            color: _mqttConnected == true ? Colors.greenAccent : Colors.redAccent,
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(height: 8),
                      ],
                      Align(
                        alignment: Alignment.centerRight,
                        child: OutlinedButton.icon(
                          onPressed: _testingMQTT ? null : _testMQTTConnection,
                          icon: _testingMQTT 
                              ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.cyanAccent))
                              : const Icon(Icons.network_check, color: Colors.cyanAccent, size: 18),
                          label: const Text('Probar Conexión MQTT', style: TextStyle(color: Colors.cyanAccent)),
                          style: OutlinedButton.styleFrom(side: const BorderSide(color: Colors.cyanAccent)),
                        ),
                      ),
                    ],
                  ),
                ),
                _permiteIOT,
                ),

                // INTEGRACIÓN MIKROTIK
                const SizedBox(height: 32),
                _buildSectionTitle('Integración de Red (MikroTik)'),
                const SizedBox(height: 14),
                _premiumBlock(
                  Column(
                    children: [
                      if (_mikrotikRouters.isNotEmpty)
                  ..._mikrotikRouters.map((r) {
                    final bool isConnected = r['is_connected'] ?? false;
                    final String? lastError = r['last_error'];
                    return Card(
                      color: const Color(0xFF1E293B),
                      margin: const EdgeInsets.only(bottom: 8),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      child: ListTile(
                        leading: Icon(
                          Icons.circle,
                          color: isConnected ? Colors.greenAccent : Colors.redAccent,
                          size: 14,
                        ),
                        title: Text(r['nombre'], style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
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
                      ),
                    );
                  }),
                const SizedBox(height: 10),
                Card(
                  color: const Color(0xFF1E293B),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  child: ExpansionTile(
                    title: const Text('Agregar Nuevo Router', style: TextStyle(color: Colors.cyanAccent, fontWeight: FontWeight.bold)),
                    iconColor: Colors.cyanAccent,
                    collapsedIconColor: Colors.cyanAccent,
                    childrenPadding: const EdgeInsets.all(16),
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
                        child: const Text('Guardar Router', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                      )
                    ],
                  ),
                ),
                ],
              ),
              _permiteMikrotik,
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

  Widget _buildStatusBadge(bool? status) {
    if (status == null) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(color: Colors.white10, borderRadius: BorderRadius.circular(10)),
        child: const Text('Sin probar', style: TextStyle(color: Colors.white54, fontSize: 10, fontWeight: FontWeight.bold)),
      );
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: status ? Colors.green.withOpacity(0.2) : Colors.red.withOpacity(0.2),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: status ? Colors.greenAccent : Colors.redAccent, width: 0.8),
      ),
      child: Text(
        status ? 'Conectado' : 'Desconectado',
        style: TextStyle(color: status ? Colors.greenAccent : Colors.redAccent, fontSize: 10, fontWeight: FontWeight.bold),
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
        fillColor: const Color(0xFF0F172A),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        prefixIcon: Icon(icon, color: Colors.cyanAccent),
      ),
    );
  }
}
