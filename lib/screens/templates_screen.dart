import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../brand.dart';
import 'login_screen.dart';

class TemplatesScreen extends StatefulWidget {
  const TemplatesScreen({super.key});

  @override
  State<TemplatesScreen> createState() => _TemplatesScreenState();
}

class _TemplatesScreenState extends State<TemplatesScreen> {
  static const _editableExtensions = {'.html', '.htm', '.md', '.txt'};
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;

  Future<String> get _token async =>
      (await SharedPreferences.getInstance()).getString('jwt_token') ?? '';

  Future<Map<String, String>> get _headers async => {'Authorization': 'Bearer ${await _token}'};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (mounted) setState(() => _loading = true);
    try {
      final response = await http.get(Uri.parse('$kApiBaseUrl/v1/templates'), headers: await _headers);
      if (response.statusCode != 200) throw Exception(_detail(response));
      if (mounted) setState(() => _items = List<Map<String, dynamic>>.from(jsonDecode(response.body)));
    } catch (error) {
      _message('No se pudieron cargar las plantillas: $error', error: true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _detail(http.Response response) {
    try {
      return jsonDecode(response.body)['detail']?.toString() ?? 'Error ${response.statusCode}';
    } catch (_) {
      return 'Error ${response.statusCode}';
    }
  }

  void _message(String text, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text), backgroundColor: error ? Colors.redAccent : Colors.green));
  }

  Future<void> _upload({Map<String, dynamic>? replacing}) async {
    final picked = await FilePicker.platform.pickFiles(type: FileType.custom, allowedExtensions: const ['docx', 'dotx', 'xlsx', 'xltx', 'csv', 'html', 'htm', 'md', 'txt', 'pdf'], withData: true);
    if (picked == null || picked.files.isEmpty) return;
    final file = picked.files.single;
    if (file.bytes == null) {
      _message('No fue posible leer el archivo seleccionado.', error: true);
      return;
    }
    try {
      final url = replacing == null ? '$kApiBaseUrl/v1/templates/upload' : '$kApiBaseUrl/v1/templates/${replacing['id_template']}/file';
      final request = http.MultipartRequest(replacing == null ? 'POST' : 'PUT', Uri.parse(url));
      request.headers['Authorization'] = 'Bearer ${await _token}';
      request.files.add(http.MultipartFile.fromBytes('file', file.bytes!, filename: file.name));
      final response = await http.Response.fromStream(await request.send());
      if (response.statusCode < 200 || response.statusCode >= 300) throw Exception(_detail(response));
      _message(replacing == null ? 'Plantilla subida correctamente.' : 'Archivo de plantilla actualizado.');
      await _load();
    } catch (error) {
      _message('No se pudo guardar la plantilla: $error', error: true);
    }
  }

  Future<void> _rename(Map<String, dynamic> item) async {
    final controller = TextEditingController(text: '${item['nombre'] ?? ''}');
    final newName = await showDialog<String>(context: context, builder: (context) => AlertDialog(backgroundColor: BonsoBrand.surface, title: const Text('Renombrar plantilla', style: TextStyle(color: Colors.white)), content: TextField(controller: controller, autofocus: true, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Nombre', labelStyle: TextStyle(color: Colors.white70))), actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar')), FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Guardar'))]));
    if (newName == null || newName.isEmpty) return;
    try {
      final response = await http.put(Uri.parse('$kApiBaseUrl/v1/templates/${item['id_template']}'), headers: {...await _headers, 'Content-Type': 'application/json'}, body: jsonEncode({'nombre': newName}));
      if (response.statusCode != 200) throw Exception(_detail(response));
      _message('Nombre actualizado.');
      await _load();
    } catch (error) {
      _message('No se pudo renombrar: $error', error: true);
    }
  }

  Future<void> _editContent(Map<String, dynamic> item) async {
    try {
      final response = await http.get(Uri.parse('$kApiBaseUrl/v1/templates/${item['id_template']}/content'), headers: await _headers);
      if (response.statusCode != 200) throw Exception(_detail(response));
      final source = Map<String, dynamic>.from(jsonDecode(response.body));
      if (!mounted) return;
      final name = TextEditingController(text: '${source['nombre']}');
      final content = TextEditingController(text: '${source['contenido']}');
      final saved = await showDialog<bool>(context: context, builder: (dialogContext) => Dialog(backgroundColor: BonsoBrand.surface, insetPadding: const EdgeInsets.all(16), child: SizedBox(width: 760, height: MediaQuery.sizeOf(dialogContext).height * .82, child: Padding(padding: const EdgeInsets.all(20), child: Column(children: [const Row(children: [Icon(Icons.edit_note, color: BonsoBrand.aqua), SizedBox(width: 10), Text('Editar plantilla', style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold))]), const SizedBox(height: 16), TextField(controller: name, style: const TextStyle(color: Colors.white), decoration: const InputDecoration(labelText: 'Nombre de archivo', labelStyle: TextStyle(color: Colors.white70))), const SizedBox(height: 12), Expanded(child: TextField(controller: content, expands: true, maxLines: null, minLines: null, textAlignVertical: TextAlignVertical.top, style: const TextStyle(color: Colors.white, fontFamily: 'monospace'), decoration: const InputDecoration(labelText: 'Contenido', alignLabelWithHint: true, labelStyle: TextStyle(color: Colors.white70), border: OutlineInputBorder()))), const SizedBox(height: 8), const Text('Usa {{nombre_del_campo}} para crear campos rellenables.', style: TextStyle(color: Colors.white54, fontSize: 12)), const SizedBox(height: 12), Row(mainAxisAlignment: MainAxisAlignment.end, children: [TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancelar')), const SizedBox(width: 8), FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Guardar cambios'))])])))));
      if (saved != true) return;
      final update = await http.put(Uri.parse('$kApiBaseUrl/v1/templates/${item['id_template']}/content'), headers: {...await _headers, 'Content-Type': 'application/json'}, body: jsonEncode({'nombre': name.text.trim(), 'contenido': content.text}));
      if (update.statusCode != 200) throw Exception(_detail(update));
      _message('Contenido y campos actualizados.');
      await _load();
    } catch (error) {
      _message('No se pudo editar el contenido: $error', error: true);
    }
  }

  Future<void> _delete(Map<String, dynamic> item) async {
    final confirmed = await showDialog<bool>(context: context, builder: (context) => AlertDialog(backgroundColor: BonsoBrand.surface, title: const Text('Enviar a papelera', style: TextStyle(color: Colors.white)), content: Text('¿Enviar “${item['nombre']}” a la papelera?', style: const TextStyle(color: Colors.white70)), actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')), FilledButton(style: FilledButton.styleFrom(backgroundColor: Colors.redAccent), onPressed: () => Navigator.pop(context, true), child: const Text('Eliminar'))]));
    if (confirmed != true) return;
    try {
      final response = await http.delete(Uri.parse('$kApiBaseUrl/v1/templates/${item['id_template']}'), headers: await _headers);
      if (response.statusCode != 200) throw Exception(_detail(response));
      _message('Plantilla enviada a la papelera.');
      await _load();
    } catch (error) {
      _message('No se pudo eliminar: $error', error: true);
    }
  }

  Future<void> _reprocess(Map<String, dynamic> item) async {
    try {
      final response = await http.post(Uri.parse('$kApiBaseUrl/v1/templates/${item['id_template']}/reprocess'), headers: await _headers);
      if (response.statusCode != 200) throw Exception(_detail(response));
      final result = Map<String, dynamic>.from(jsonDecode(response.body));
      final fields = List<String>.from(result['campos'] ?? []);
      final added = List<String>.from(result['added_fields'] ?? []);
      final removed = List<String>.from(result['removed_fields'] ?? []);
      if (!mounted) return;
      await showDialog<void>(context: context, builder: (context) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: const Text('Resultado del reprocesamiento', style: TextStyle(color: Colors.white)),
        content: SingleChildScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
          Text('${fields.length} ${fields.length == 1 ? 'campo detectado' : 'campos detectados'}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          const SizedBox(height: 10),
          Text(fields.isEmpty ? 'No se encontraron campos. Usa marcadores como {{cliente}} o campos rellenables en un PDF.' : fields.map((field) => '{{${field}}}').join(', '), style: const TextStyle(color: Colors.white70)),
          if (added.isNotEmpty) ...[const SizedBox(height: 12), Text('Nuevos: ${added.join(', ')}', style: const TextStyle(color: Colors.greenAccent))],
          if (removed.isNotEmpty) ...[const SizedBox(height: 8), Text('Eliminados: ${removed.join(', ')}', style: const TextStyle(color: Colors.orangeAccent))],
        ])),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cerrar'))],
      ));
      await _load();
    } catch (error) {
      _message('No se pudo reprocesar la plantilla: $error', error: true);
    }
  }

  Future<void> _generateFields(Map<String, dynamic> item) async {
    try {
      final suggestionsResponse = await http.post(Uri.parse('$kApiBaseUrl/v1/templates/${item['id_template']}/field-suggestions'), headers: await _headers);
      if (suggestionsResponse.statusCode != 200) throw Exception(_detail(suggestionsResponse));
      final result = Map<String, dynamic>.from(jsonDecode(suggestionsResponse.body));
      final suggestions = List<Map<String, dynamic>>.from((result['suggestions'] ?? []).map((value) => Map<String, dynamic>.from(value)));
      if (!mounted) return;
      if (suggestions.isEmpty) {
        await showDialog<void>(context: context, builder: (context) => AlertDialog(backgroundColor: BonsoBrand.surface, title: const Text('Sin sugerencias automáticas', style: TextStyle(color: Colors.white)), content: Text('${result['warning'] ?? 'No se identificaron etiquetas para generar campos.'}\n\nUsa etiquetas como “VIN:”, “Patente:” o “Nombre:” para que Bonso pueda proponer campos.', style: const TextStyle(color: Colors.white70)), actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cerrar'))]));
        return;
      }
      final selected = List<bool>.filled(suggestions.length, true);
      final names = suggestions.map((field) => TextEditingController(text: '${field['name']}')).toList();
      final create = await showDialog<bool>(context: context, builder: (dialogContext) => StatefulBuilder(builder: (context, setDialogState) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: const Text('Generar campos sugeridos', style: TextStyle(color: Colors.white)),
        content: SizedBox(width: 520, child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Revisa los campos antes de crear una copia rellenable. El original no se modifica.', style: TextStyle(color: Colors.white70)),
          const SizedBox(height: 12),
          SizedBox(height: 320, child: ListView.builder(itemCount: suggestions.length, itemBuilder: (_, index) => CheckboxListTile(
            value: selected[index], activeColor: BonsoBrand.aqua, onChanged: (value) => setDialogState(() => selected[index] = value ?? false),
            title: Text('${suggestions[index]['label']}', style: const TextStyle(color: Colors.white)),
            subtitle: TextField(controller: names[index], enabled: selected[index], style: const TextStyle(color: Colors.white70), decoration: const InputDecoration(labelText: 'Nombre del campo', labelStyle: TextStyle(color: Colors.white54))),
          ))),
        ])),
        actions: [TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancelar')), FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Crear copia rellenable'))],
      )));
      if (create != true) return;
      final fields = <Map<String, dynamic>>[];
      for (var index = 0; index < suggestions.length; index++) {
        if (!selected[index]) continue;
        final field = Map<String, dynamic>.from(suggestions[index]);
        field['name'] = names[index].text.trim();
        fields.add(field);
      }
      if (fields.isEmpty) {
        _message('Selecciona al menos un campo.', error: true);
        return;
      }
      final response = await http.post(Uri.parse('$kApiBaseUrl/v1/templates/${item['id_template']}/generate-fields'), headers: {...await _headers, 'Content-Type': 'application/json'}, body: jsonEncode({'fields': fields}));
      if (response.statusCode != 200) throw Exception(_detail(response));
      _message('Se creó una copia rellenable de la plantilla.');
      await _load();
    } catch (error) {
      _message('No se pudieron generar los campos: $error', error: true);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: BonsoBrand.ink,
    appBar: AppBar(backgroundColor: BonsoBrand.surface, title: const Text('Plantillas', style: TextStyle(color: Colors.white))),
    floatingActionButton: FloatingActionButton.extended(onPressed: _upload, backgroundColor: BonsoBrand.aqua, icon: const Icon(Icons.upload_file, color: Colors.black), label: const Text('Subir plantilla', style: TextStyle(color: Colors.black))),
    body: _loading ? const Center(child: CircularProgressIndicator()) : _items.isEmpty ? const Center(child: Padding(padding: EdgeInsets.all(32), child: Text('Aún no hay plantillas. Sube una para reutilizarla y generar documentos.', textAlign: TextAlign.center, style: TextStyle(color: Colors.white70, fontSize: 16)))) : RefreshIndicator(onRefresh: _load, child: ListView.separated(padding: const EdgeInsets.fromLTRB(16, 16, 16, 100), itemCount: _items.length, separatorBuilder: (_, __) => const SizedBox(height: 10), itemBuilder: (_, index) {
      final item = _items[index];
      final extension = '${item['extension'] ?? ''}'.toLowerCase();
      final fields = List.from(item['campos'] ?? []);
      return Card(color: BonsoBrand.surface, child: ListTile(contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8), leading: const Icon(Icons.description_outlined, color: BonsoBrand.aqua), title: Text('${item['nombre']}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600)), subtitle: Padding(padding: const EdgeInsets.only(top: 4), child: Text('$extension · ${fields.length} ${fields.length == 1 ? 'campo' : 'campos'}', style: const TextStyle(color: Colors.white54))), trailing: PopupMenuButton<String>(color: BonsoBrand.surfaceRaised, icon: const Icon(Icons.more_vert, color: Colors.white70), onSelected: (value) { if (value == 'rename') _rename(item); if (value == 'edit') _editContent(item); if (value == 'generate') _generateFields(item); if (value == 'reprocess') _reprocess(item); if (value == 'replace') _upload(replacing: item); if (value == 'delete') _delete(item); }, itemBuilder: (_) => [const PopupMenuItem(value: 'rename', child: ListTile(leading: Icon(Icons.drive_file_rename_outline), title: Text('Renombrar'))), if (_editableExtensions.contains(extension)) const PopupMenuItem(value: 'edit', child: ListTile(leading: Icon(Icons.edit_outlined), title: Text('Editar contenido'))), if (fields.isEmpty && {'.pdf', '.docx', '.dotx', '.xlsx', '.xltx'}.contains(extension)) const PopupMenuItem(value: 'generate', child: ListTile(leading: Icon(Icons.auto_fix_high_outlined), title: Text('Generar campos'))), const PopupMenuItem(value: 'reprocess', child: ListTile(leading: Icon(Icons.find_replace_outlined), title: Text('Reprocesar campos'))), const PopupMenuItem(value: 'replace', child: ListTile(leading: Icon(Icons.upload_file_outlined), title: Text('Reemplazar archivo'))), const PopupMenuDivider(), const PopupMenuItem(value: 'delete', child: ListTile(leading: Icon(Icons.delete_outline, color: Colors.redAccent), title: Text('Enviar a papelera', style: TextStyle(color: Colors.redAccent))))])));
    })),
  );
}
