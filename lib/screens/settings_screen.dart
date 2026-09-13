import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({Key? key}) : super(key: key);

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _voiceIdController = TextEditingController();
  String _sarcasmLevel = 'Medio';
  bool _handsFreeMode = false;
  bool _isLoading = true;

  final List<String> _sarcasmOptions = ['Bajo', 'Medio', 'Alto', 'Extremo'];

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _voiceIdController.text = prefs.getString('jarvis_voice_id') ?? '';
      _sarcasmLevel = prefs.getString('jarvis_sarcasm_level') ?? 'Medio';
      _handsFreeMode = prefs.getBool('jarvis_hands_free') ?? false;
      _isLoading = false;
    });
  }

  Future<void> _saveSettings() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('jarvis_voice_id', _voiceIdController.text.trim());
    await prefs.setString('jarvis_sarcasm_level', _sarcasmLevel);
    await prefs.setBool('jarvis_hands_free', _handsFreeMode);

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Configuración guardada exitosamente', style: TextStyle(color: Colors.black)), backgroundColor: Colors.cyanAccent),
    );
  }

  @override
  void dispose() {
    _voiceIdController.dispose();
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
              _buildSectionTitle('Voz y Audio'),
              const SizedBox(height: 16),
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
              const SizedBox(height: 8),
              Text(
                'Déjalo en blanco para usar la voz por defecto del servidor.',
                style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12),
              ),
              
              const SizedBox(height: 32),
              _buildSectionTitle('Personalidad de IA'),
              const SizedBox(height: 16),
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
              const SizedBox(height: 8),
              Text(
                'Controla la cantidad de ironía en las respuestas de J.A.R.V.I.S.',
                style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12),
              ),

              const SizedBox(height: 32),
              _buildSectionTitle('Interacción'),
              const SizedBox(height: 16),
              SwitchListTile(
                title: const Text('Modo Manos Libres', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w500)),
                subtitle: const Text('J.A.R.V.I.S. auto-reproducirá audios y encenderá el micrófono al terminar de hablar.', style: TextStyle(color: Colors.white54, fontSize: 12)),
                value: _handsFreeMode,
                activeColor: Colors.cyanAccent,
                tileColor: const Color(0xFF1E293B),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                secondary: const Icon(Icons.headset_mic, color: Colors.cyanAccent),
                onChanged: (value) {
                  setState(() => _handsFreeMode = value);
                },
              ),

              const SizedBox(height: 48),
              SizedBox(
                height: 50,
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
}
