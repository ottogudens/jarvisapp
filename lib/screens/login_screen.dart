import 'dart:convert';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'hub_screen.dart';
import 'admin_console_screen.dart';
import '../brand.dart';

const String kApiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'https://jarvisapp-production-f259.up.railway.app',
);

class LoginScreen extends StatefulWidget {
  const LoginScreen({Key? key}) : super(key: key);

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  @override
  void initState() {
    super.initState();
    _checkAutoLogin();
  }

  Future<void> _checkAutoLogin() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token != null && token.isNotEmpty) {
      if (!mounted) return;
      Widget destination = const HubScreen();
      try {
        final payload = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(token.split('.')[1]))));
        if (['admin', 'superadmin'].contains(payload['rol'])) destination = const AdminConsoleScreen();
      } catch (_) {}
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => destination),
      );
    }
  }

  final _emailController = TextEditingController(text: '');
  final _passwordController = TextEditingController(text: '');
  bool _isLoading = false;
  bool _obscurePassword = true;
  String _errorMessage = '';

  Future<void> _login() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      final response = await http.post(
        Uri.parse('$kApiBaseUrl/v1/auth/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'email': _emailController.text.trim(),
          'password': _passwordController.text,
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final token = data['access_token'];
        final perfil = data['perfil_jarvis'] ?? '';
        final organizacion = data['nombre_organizacion'] ?? '';

        // Guardar token y datos de perfil (limpiar caché previo)
        final prefs = await SharedPreferences.getInstance();
        await prefs.clear();

        await prefs.setString('jwt_token', token);
        await prefs.setString('perfil_jarvis', perfil);
        await prefs.setString('nombre_organizacion', organizacion);

        if (!mounted) return;

        // Ruteo unificado
        final role = data['rol']?.toString();
        Widget destino = ['admin', 'superadmin'].contains(role) ? const AdminConsoleScreen() : const HubScreen();

        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => destino),
        );
      } else {
        setState(() {
          _errorMessage = 'Credenciales incorrectas.';
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Error de conexión con el servidor.';
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [BonsoBrand.ink, BonsoBrand.surface],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 32.0),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(24),
              child: BackdropFilter(
                filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
                child: Container(
                  padding: const EdgeInsets.all(32),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.05),
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: Colors.white.withOpacity(0.1)),
                  ),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                      Image.asset('assets/branding/bonso-mark.png', width: 64, height: 64, semanticLabel: 'Bonso, desarrollado por SKALE IA'),
                      const SizedBox(height: 16),
                      Text(
                        'BONSO',
                        style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                              letterSpacing: 2,
                            ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Inteligencia aplicada por SKALE IA',
                        style: TextStyle(
                          color: BonsoBrand.lime.withOpacity(0.85),
                          fontSize: 16,
                        ),
                      ),
                      const SizedBox(height: 48),
                      _buildTextField(
                        controller: _emailController,
                        hint: 'Email',
                        icon: Icons.email_outlined,
                        keyboardType: TextInputType.emailAddress,
                        autofillHints: const [AutofillHints.username, AutofillHints.email],
                      ),
                      const SizedBox(height: 16),
                      _buildTextField(
                        controller: _passwordController,
                        hint: 'Contraseña',
                        icon: Icons.lock_outline,
                        isObscure: _obscurePassword,
                        autofillHints: const [AutofillHints.password],
                        onTogglePassword: () => setState(() => _obscurePassword = !_obscurePassword),
                      ),
                      const SizedBox(height: 24),
                      if (_errorMessage.isNotEmpty) ...[
                        Text(
                          _errorMessage,
                          style: const TextStyle(color: Colors.redAccent, fontSize: 13),
                        ),
                        const SizedBox(height: 16),
                      ],
                      SizedBox(
                        width: double.infinity,
                        height: 50,
                        child: ElevatedButton(
                          onPressed: _isLoading ? null : _login,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: BonsoBrand.lime,
                            foregroundColor: BonsoBrand.ink,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                            elevation: 0,
                          ),
                          child: _isLoading
                              ? const SizedBox(
                                  width: 24,
                                  height: 24,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: BonsoBrand.ink,
                                  ),
                                )
                              : const Text(
                                  'INICIAR SESIÓN',
                                  style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1),
                                ),
                        ),
                      ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String hint,
    required IconData icon,
    bool isObscure = false,
    TextInputType? keyboardType,
    Iterable<String>? autofillHints,
    VoidCallback? onTogglePassword,
  }) {
    return TextFormField(
      controller: controller,
      obscureText: isObscure,
      keyboardType: keyboardType,
      autofillHints: autofillHints,
      textInputAction: isObscure ? TextInputAction.done : TextInputAction.next,
      onFieldSubmitted: (_) => isObscure ? _login() : FocusScope.of(context).nextFocus(),
      validator: (value) {
        final text = value?.trim() ?? '';
        if (text.isEmpty) return 'Este campo es obligatorio.';
        if (keyboardType == TextInputType.emailAddress && !text.contains('@')) return 'Ingresa un email válido.';
        return null;
      },
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: TextStyle(color: Colors.white.withOpacity(0.4)),
        prefixIcon: Icon(icon, color: BonsoBrand.aqua),
        suffixIcon: onTogglePassword == null ? null : IconButton(
          tooltip: isObscure ? 'Mostrar contraseña' : 'Ocultar contraseña',
          onPressed: onTogglePassword,
          icon: Icon(isObscure ? Icons.visibility_outlined : Icons.visibility_off_outlined, color: Colors.white70),
        ),
        filled: true,
        fillColor: Colors.black.withOpacity(0.2),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: Colors.white.withOpacity(0.05)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: BonsoBrand.lime, width: 1),
        ),
      ),
    );
  }
}
