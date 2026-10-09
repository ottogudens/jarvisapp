import 'dart:convert';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../brand.dart';
import 'login_screen.dart';
import 'chat_list_screen.dart';

class CustomProfileScreen extends StatefulWidget {
  const CustomProfileScreen({super.key});

  @override
  State<CustomProfileScreen> createState() => _CustomProfileScreenState();
}

class _CustomProfileScreenState extends State<CustomProfileScreen> {
  final _name = TextEditingController();
  final _personality = TextEditingController(text: 'Profesional, cercano, claro y proactivo');
  final _goal = TextEditingController();
  final _audience = TextEditingController(text: 'Clientes y equipo interno');
  final _functions = TextEditingController();
  final _limits = TextEditingController();
  final _prompt = TextEditingController();
  String? _profileId;
  bool _busy = false;
  int _sources = 0;

  @override
  void dispose() {
    for (final controller in [_name, _personality, _goal, _audience, _functions, _limits, _prompt]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<String?> _token() async => (await SharedPreferences.getInstance()).getString('jwt_token');

  void _message(String text, {bool error = false}) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text), backgroundColor: error ? Colors.redAccent : BonsoBrand.aqua));
  }

  Future<void> _saveDraft() async {
    if (_name.text.trim().length < 2 || _goal.text.trim().length < 10) {
      _message('Indica el nombre y el objetivo del asistente.', error: true); return;
    }
    setState(() => _busy = true);
    try {
      final token = await _token();
      final response = await http.post(Uri.parse('$kApiBaseUrl/v1/custom-profiles/draft'), headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'}, body: jsonEncode({
        'nombre': _name.text.trim(), 'personalidad': _personality.text.trim(), 'objetivo': _goal.text.trim(),
        'audiencia': _audience.text.trim(), 'funciones': _functions.text.split('\n').map((item) => item.trim()).where((item) => item.isNotEmpty).toList(),
        'limites': _limits.text.trim(), 'idioma': 'Español',
      }));
      if (response.statusCode != 200) throw Exception(response.body);
      final data = jsonDecode(response.body);
      setState(() { _profileId = data['id_profile']; _prompt.text = data['master_prompt'] ?? ''; });
      _message('Borrador creado. Ya puedes adjuntar conocimiento o generar el prompt maestro.');
    } catch (e) { _message('No se pudo crear el borrador: $e', error: true); }
    finally { if (mounted) setState(() => _busy = false); }
  }

  Future<void> _uploadSources() async {
    if (_profileId == null) { _message('Primero crea el borrador.', error: true); return; }
    final selection = await FilePicker.platform.pickFiles(allowMultiple: true, type: FileType.custom, allowedExtensions: ['pdf', 'docx', 'xlsx', 'txt', 'csv', 'md', 'png', 'jpg', 'jpeg', 'webp']);
    if (selection == null || selection.files.isEmpty) return;
    setState(() => _busy = true);
    try {
      final token = await _token();
      final request = http.MultipartRequest('POST', Uri.parse('$kApiBaseUrl/v1/knowledge/upload'));
      request.headers['Authorization'] = 'Bearer $token'; request.fields['profile_id'] = _profileId!;
      for (final file in selection.files) {
        if (file.bytes != null) request.files.add(http.MultipartFile.fromBytes('files', file.bytes!, filename: file.name));
        else if (file.path != null) request.files.add(await http.MultipartFile.fromPath('files', file.path!));
      }
      final response = await request.send();
      if (response.statusCode != 200) throw Exception(await response.stream.bytesToString());
      final data = jsonDecode(await response.stream.bytesToString());
      setState(() => _sources += (data['document_ids'] as List? ?? []).length);
      _message('Fuentes procesadas y asociadas al perfil.');
    } catch (e) { _message('No se pudieron procesar los archivos: $e', error: true); }
    finally { if (mounted) setState(() => _busy = false); }
  }

  Future<void> _generatePrompt() async {
    if (_profileId == null) { _message('Primero crea el borrador.', error: true); return; }
    setState(() => _busy = true);
    try {
      final token = await _token();
      final response = await http.post(Uri.parse('$kApiBaseUrl/v1/custom-profiles/$_profileId/generate'), headers: {'Authorization': 'Bearer $token'});
      if (response.statusCode != 200) throw Exception(response.body);
      setState(() => _prompt.text = jsonDecode(response.body)['master_prompt'] ?? '');
      _message('Prompt maestro generado. Revísalo antes de activarlo.');
    } catch (e) { _message('No se pudo generar el prompt: $e', error: true); }
    finally { if (mounted) setState(() => _busy = false); }
  }

  Future<void> _addWebSource() async {
    if (_profileId == null) { _message('Primero crea el borrador.', error: true); return; }
    final controller = TextEditingController();
    final url = await showDialog<String>(context: context, builder: (ctx) => AlertDialog(
      backgroundColor: BonsoBrand.surface, title: const Text('Agregar página web', style: TextStyle(color: Colors.white)),
      content: TextField(controller: controller, keyboardType: TextInputType.url, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(hintText: 'https://empresa.cl/preguntas-frecuentes', hintStyle: TextStyle(color: Colors.white38))),
      actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')), ElevatedButton(onPressed: () => Navigator.pop(ctx, controller.text.trim()), child: const Text('Procesar'))],
    ));
    if (url == null || url.isEmpty) return;
    setState(() => _busy = true);
    try {
      final token = await _token();
      final response = await http.post(Uri.parse('$kApiBaseUrl/v1/custom-profiles/$_profileId/web-source'), headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'}, body: jsonEncode({'url': url}));
      if (response.statusCode != 200) throw Exception(response.body);
      setState(() => _sources++); _message('Página web procesada y asociada al perfil.');
    } catch (e) { _message('No se pudo procesar la página: $e', error: true); }
    finally { if (mounted) setState(() => _busy = false); }
  }

  Future<void> _activate() async {
    if (_profileId == null || _prompt.text.trim().length < 50) { _message('Crea y revisa el prompt maestro antes de activar.', error: true); return; }
    setState(() => _busy = true);
    try {
      final token = await _token();
      final headers = {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'};
      final update = await http.put(Uri.parse('$kApiBaseUrl/v1/custom-profiles/$_profileId/prompt'), headers: headers, body: jsonEncode({'master_prompt': _prompt.text.trim()}));
      if (update.statusCode != 200) throw Exception(update.body);
      final response = await http.post(Uri.parse('$kApiBaseUrl/v1/custom-profiles/$_profileId/activate'), headers: headers);
      if (response.statusCode != 200) throw Exception(response.body);
      _message('${_name.text} está activo. Puedes probarlo ahora.');
    } catch (e) { _message('No se pudo activar el perfil: $e', error: true); }
    finally { if (mounted) setState(() => _busy = false); }
  }

  Widget _field(String label, TextEditingController controller, {int lines = 1, String? hint}) => Padding(
    padding: const EdgeInsets.only(bottom: 14),
    child: TextField(controller: controller, maxLines: lines, style: const TextStyle(color: Colors.white), decoration: InputDecoration(labelText: label, hintText: hint, labelStyle: const TextStyle(color: BonsoBrand.aqua), hintStyle: const TextStyle(color: Colors.white38), filled: true, fillColor: BonsoBrand.surface, border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)))),
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: BonsoBrand.ink,
    appBar: AppBar(backgroundColor: BonsoBrand.surface, title: const Text('Crear asistente personalizado')),
    body: _busy ? const Center(child: CircularProgressIndicator(color: BonsoBrand.aqua)) : ListView(padding: const EdgeInsets.all(20), children: [
      const Text('1. Identidad y necesidades', style: TextStyle(color: BonsoBrand.aqua, fontSize: 18, fontWeight: FontWeight.bold)), const SizedBox(height: 14),
      _field('Nombre del asistente', _name, hint: 'Ej.: Sofía, asesora de ventas'),
      _field('Personalidad y tono', _personality, lines: 2), _field('Objetivo principal', _goal, lines: 3, hint: '¿Qué debe resolver y para quién?'),
      _field('Audiencia', _audience), _field('Funciones deseadas (una por línea)', _functions, lines: 4, hint: 'Responder cotizaciones\nPreparar informes'),
      _field('Límites y reglas', _limits, lines: 3, hint: 'Qué no puede hacer, cuándo debe escalar a una persona'),
      ElevatedButton.icon(onPressed: _saveDraft, icon: const Icon(Icons.save), label: const Text('Guardar borrador'), style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.aqua, foregroundColor: Colors.black)),
      const SizedBox(height: 28), const Text('2. Fuentes de conocimiento', style: TextStyle(color: BonsoBrand.aqua, fontSize: 18, fontWeight: FontWeight.bold)),
      Text('Adjunta documentos, imágenes, manuales o planillas. Fuentes asociadas: $_sources', style: const TextStyle(color: Colors.white70)), const SizedBox(height: 10),
      Wrap(spacing: 10, runSpacing: 10, children: [
        OutlinedButton.icon(onPressed: _uploadSources, icon: const Icon(Icons.upload_file), label: const Text('Agregar archivos')),
        OutlinedButton.icon(onPressed: _addWebSource, icon: const Icon(Icons.language), label: const Text('Agregar página web')),
      ]),
      const SizedBox(height: 28), const Text('3. Prompt maestro y activación', style: TextStyle(color: BonsoBrand.aqua, fontSize: 18, fontWeight: FontWeight.bold)), const SizedBox(height: 10),
      OutlinedButton.icon(onPressed: _generatePrompt, icon: const Icon(Icons.auto_awesome), label: const Text('Generar prompt maestro con IA')),
      const SizedBox(height: 12), _field('Prompt maestro (editable)', _prompt, lines: 12),
      ElevatedButton.icon(onPressed: _activate, icon: const Icon(Icons.verified), label: const Text('Aprobar y activar'), style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.lime, foregroundColor: Colors.black)),
      TextButton.icon(onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ChatListScreen())), icon: const Icon(Icons.chat, color: BonsoBrand.aqua), label: const Text('Probar en el chat', style: TextStyle(color: BonsoBrand.aqua))),
    ]),
  );
}
