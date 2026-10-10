import 'dart:convert';
import 'dart:async';
import 'dart:html' as html;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:file_picker/file_picker.dart';
import '../brand.dart';
import 'login_screen.dart'; // Contiene kApiBaseUrl

class DocumentsScreen extends StatefulWidget {
  final int initialTab;

  const DocumentsScreen({super.key, this.initialTab = 0});

  @override
  State<DocumentsScreen> createState() => _DocumentsScreenState();
}

class _DocumentsScreenState extends State<DocumentsScreen> with SingleTickerProviderStateMixin {
  bool _isLoading = true;
  List<Map<String, dynamic>> _documentos = [];
  List<Map<String, dynamic>> _conocimiento = [];
  List<Map<String, dynamic>> _carpetas = [];
  Map<String, dynamic> _quota = {};
  String? _currentFolderId;
  String _searchQuery = '';
  late TabController _tabController;
  Timer? _knowledgeStatusPoll;

  String _formatBytes(dynamic value) {
    final bytes = (value as num?)?.toInt() ?? 0;
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(0)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this, initialIndex: widget.initialTab.clamp(0, 2) as int);
    _cargarDocumentos();
    _cargarConocimiento();
  }
  
  @override
  void dispose() {
    _knowledgeStatusPoll?.cancel();
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _cargarDocumentos() async {
    setState(() => _isLoading = true);
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';
      final resp = await http.get(
        Uri.parse('$kApiBaseUrl/v1/chat/sessions/documents/all'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as List;
        if (mounted) {
          setState(() => _documentos = data.map((e) => Map<String, dynamic>.from(e)).toList());
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error cargando documentos: $e')));
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _cargarConocimiento() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';
      final resp = await http.get(
        Uri.parse('$kApiBaseUrl/v1/knowledge/all'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body);
        if (mounted) {
          setState(() {
            _carpetas = List<Map<String, dynamic>>.from(data['carpetas'] ?? []);
            _conocimiento = List<Map<String, dynamic>>.from(data['documentos'] ?? []);
            _quota = Map<String, dynamic>.from(data['quota'] ?? {});
          });
          _syncKnowledgeStatusPolling();
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error cargando conocimiento: $e')));
      }
    }
  }

  Future<void> _eliminarDocumento(String idMensaje) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: const Text('Eliminar documento', style: TextStyle(color: Colors.white)),
        content: const Text(
          'Este documento será eliminado permanentemente y Bonso dejará de tenerlo como conocimiento.',
          style: TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar', style: TextStyle(color: Colors.white54)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Eliminar', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (confirm != true) return;

    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';
      final resp = await http.delete(
        Uri.parse('$kApiBaseUrl/v1/chat/messages/$idMensaje'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (resp.statusCode == 200) {
        if (mounted) {
          setState(() => _documentos.removeWhere((d) => d['id_mensaje'] == idMensaje));
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Documento eliminado'), backgroundColor: Colors.green),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  Future<void> _eliminarConocimiento(String idDocument) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: const Text('Eliminar memoria', style: TextStyle(color: Colors.white)),
        content: const Text(
          'Este documento será eliminado permanentemente de la memoria RAG y Bonso dejará de tenerlo como conocimiento.',
          style: TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar', style: TextStyle(color: Colors.white54)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Eliminar', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (confirm != true) return;

    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';
      final resp = await http.delete(
        Uri.parse('$kApiBaseUrl/v1/knowledge/$idDocument'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (resp.statusCode == 200) {
        if (mounted) {
          setState(() => _conocimiento.removeWhere((d) => d['id_document'] == idDocument));
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Conocimiento eliminado'), backgroundColor: Colors.green),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  Future<void> _verContenido(Map<String, dynamic> doc) async {
    showDialog(
      context: context,
      builder: (_) => Dialog(
        backgroundColor: BonsoBrand.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: Container(
          padding: const EdgeInsets.all(24),
          constraints: BoxConstraints(
            maxHeight: MediaQuery.of(context).size.height * 0.8,
            maxWidth: 600,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Contenido Extraído', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: BonsoBrand.aqua)),
              const SizedBox(height: 16),
              Expanded(
                child: SingleChildScrollView(
                  child: Text(
                    doc['contenido'] ?? '(Sin contenido legible)',
                    style: const TextStyle(color: Colors.white70, fontSize: 14, height: 1.5),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Cerrar', style: TextStyle(color: Colors.white)),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: BonsoBrand.aqua,
                      foregroundColor: Colors.white,
                    ),
                    onPressed: () => _abrirOriginal(doc),
                    icon: const Icon(Icons.open_in_browser),
                    label: const Text('Abrir Original'),
                  )
                ],
              )
            ],
          ),
        ),
      ),
    );
  }

  void _syncKnowledgeStatusPolling() {
    final hasPending = _conocimiento.any((doc) => doc['status'] == 'queued' || doc['status'] == 'processing');
    if (hasPending && _knowledgeStatusPoll == null) {
      _knowledgeStatusPoll = Timer.periodic(const Duration(seconds: 4), (_) => _cargarConocimiento());
    } else if (!hasPending) {
      _knowledgeStatusPoll?.cancel();
      _knowledgeStatusPoll = null;
    }
  }

  Future<void> _abrirOriginal(Map<String, dynamic> doc) async {
    final url = doc['url']?.toString();
    if ((url == null || url.isEmpty) && (doc['id_mensaje'] == null || doc['file_index'] == null)) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('El archivo original no está disponible')));
      return;
    }
    try {
      if (url != null && url.startsWith('http')) {
        final ok = await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
        if (!ok) throw Exception('No se pudo abrir la URL');
        return;
      }
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';
      final response = await http.get(
        Uri.parse('$kApiBaseUrl/v1/chat/messages/${doc['id_mensaje']}/files/${doc['file_index']}'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (response.statusCode != 200) throw Exception('No se pudo descargar el archivo');
      final mime = response.headers['content-type']?.split(';').first ?? 'application/octet-stream';
      final blobUrl = html.Url.createObjectUrlFromBlob(html.Blob([response.bodyBytes], mime));
      final opened = html.window.open(blobUrl, '_blank');
      if (opened == null) throw Exception('El navegador bloqueó la ventana emergente');
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo abrir el archivo: $e')));
    }
  }

  Widget _buildList(List<Map<String, dynamic>> items) {
    if (items.isEmpty) {
      return const Center(child: Text('No hay documentos', style: TextStyle(color: Colors.white54)));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: items.length,
      itemBuilder: (context, i) {
        final doc = items[i];
        final tipo = doc['tipo'] ?? 'desconocido';
        final esGenerado = doc['rol'] == 'jarvis';
        final esDocumentoBiblioteca = doc['record_type'] == 'knowledge_document';
        IconData icono = Icons.insert_drive_file;
        if (tipo.contains('pdf')) icono = Icons.picture_as_pdf;
        if (tipo.contains('image')) icono = Icons.image;
        if (esGenerado) icono = Icons.auto_awesome;
        if (esDocumentoBiblioteca) icono = Icons.memory;
        final detalle = esDocumentoBiblioteca
            ? 'Origen: ${doc['source_channel'] ?? 'web'} · ${_statusLabel(doc['status'])}\nTipo: $tipo\n${doc['created_at']?.split('T')[0] ?? ''}'
            : 'Sesión: ${doc['titulo_sesion']}\nTipo: $tipo\n${doc['created_at']?.split('T')[0] ?? ''}';

        return Card(
          color: BonsoBrand.surface,
          margin: const EdgeInsets.only(bottom: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: BorderSide(color: Colors.white.withOpacity(0.05)),
          ),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: esGenerado ? BonsoBrand.aqua.withOpacity(0.2) : BonsoBrand.aqua.withOpacity(0.1),
              child: Icon(icono, color: esGenerado ? BonsoBrand.aqua : BonsoBrand.aqua),
            ),
            title: Text(
              doc['nombre_archivo'] ?? doc['id_mensaje'] ?? 'Documento',
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: Text(
              detalle,
              style: const TextStyle(color: Colors.white54, fontSize: 12),
            ),
            isThreeLine: true,
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  icon: const Icon(Icons.visibility, color: BonsoBrand.aqua),
                  onPressed: () => esDocumentoBiblioteca ? _verDetalleConocimiento(doc) : _verContenido(doc),
                  tooltip: esDocumentoBiblioteca ? 'Ver detalle de indexación' : 'Ver contenido',
                ),
                if (esDocumentoBiblioteca && doc['original_available'] == true)
                  IconButton(
                    icon: const Icon(Icons.download_outlined, color: BonsoBrand.aqua),
                    onPressed: () => _descargarOriginalConocimiento(doc),
                    tooltip: 'Descargar original',
                  ),
                IconButton(
                  icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                  onPressed: () => esDocumentoBiblioteca
                      ? _eliminarConocimiento(doc['id_document'])
                      : _eliminarDocumento(doc['id_mensaje']),
                  tooltip: 'Eliminar',
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _crearCarpeta() async {
    final TextEditingController nameController = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: const Text('Nueva Carpeta', style: TextStyle(color: Colors.white)),
        content: TextField(
          controller: nameController,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            hintText: 'Nombre de la carpeta',
            hintStyle: TextStyle(color: Colors.white54),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar', style: TextStyle(color: Colors.white54))),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.aqua),
            onPressed: () => Navigator.pop(context, nameController.text),
            child: const Text('Crear', style: TextStyle(color: Colors.black)),
          ),
        ],
      ),
    );

    if (result != null && result.isNotEmpty) {
      setState(() => _isLoading = true);
      try {
        final prefs = await SharedPreferences.getInstance();
        final token = prefs.getString('jwt_token') ?? '';
        final resp = await http.post(
          Uri.parse('$kApiBaseUrl/v1/knowledge/folders'),
          headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'},
          body: jsonEncode({'nombre': result, 'parent_id': _currentFolderId}),
        );
        if (resp.statusCode == 200) {
          _cargarConocimiento();
        }
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      } finally {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _eliminarCarpeta(String idFolder) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: const Text('Eliminar Carpeta', style: TextStyle(color: Colors.white)),
        content: const Text('¿Estás seguro? Los documentos dentro quedarán sin carpeta.', style: TextStyle(color: Colors.white70)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancelar')),
          ElevatedButton(onPressed: () => Navigator.pop(context, true), style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent), child: const Text('Eliminar')),
        ],
      ),
    );
    if (confirm != true) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';
      await http.delete(Uri.parse('$kApiBaseUrl/v1/knowledge/folders/$idFolder'), headers: {'Authorization': 'Bearer $token'});
      _cargarConocimiento();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  Future<void> _moverDocumento(String idDocument) async {
    final result = await showDialog<String?>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: const Text('Mover a...', style: TextStyle(color: Colors.white)),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView(
            shrinkWrap: true,
            children: [
              ListTile(
                leading: const Icon(Icons.home, color: BonsoBrand.aqua),
                title: const Text('Carpeta Principal', style: TextStyle(color: Colors.white)),
                onTap: () => Navigator.pop(context, 'ROOT'),
              ),
              ..._carpetas.map((c) => ListTile(
                leading: const Icon(Icons.folder, color: BonsoBrand.aqua),
                title: Text(c['nombre'], style: const TextStyle(color: Colors.white)),
                onTap: () => Navigator.pop(context, c['id_folder']),
              )),
            ],
          ),
        ),
      ),
    );

    if (result != null) {
      try {
        final prefs = await SharedPreferences.getInstance();
        final token = prefs.getString('jwt_token') ?? '';
        final folderId = result == 'ROOT' ? null : result;
        await http.put(
          Uri.parse('$kApiBaseUrl/v1/knowledge/$idDocument/move'),
          headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'},
          body: jsonEncode({'id_folder': folderId}),
        );
        _cargarConocimiento();
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  Future<void> _renombrarRecurso({required String title, required String currentName, required Uri uri, required Map<String, dynamic> body}) async {
    final controller = TextEditingController(text: currentName);
    final name = await showDialog<String>(context: context, builder: (_) => AlertDialog(
      backgroundColor: BonsoBrand.surface,
      title: Text(title, style: const TextStyle(color: Colors.white)),
      content: TextField(controller: controller, style: const TextStyle(color: Colors.white), autofocus: true),
      actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancelar')), ElevatedButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Guardar'))],
    ));
    if (name == null || name.isEmpty) return;
    try {
      final token = await _token();
      body['nombre'] = name;
      final response = await http.put(uri, headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'}, body: jsonEncode(body));
      if (response.statusCode != 200) throw Exception(response.body);
      await _cargarConocimiento();
    } catch (e) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo guardar: $e'))); }
  }

  Future<void> _verMemoria(Map<String, dynamic> doc) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';
      final response = await http.get(
        Uri.parse('$kApiBaseUrl/v1/knowledge/${doc['id_document']}/content'),
        headers: {'Authorization': 'Bearer $token'},
      );
      if (response.statusCode != 200) throw Exception('No se pudo cargar el contenido procesado');
      final data = jsonDecode(response.body);
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: BonsoBrand.surface,
          title: Text(data['nombre'] ?? 'Contenido procesado', style: const TextStyle(color: Colors.white)),
          content: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 680),
            child: SingleChildScrollView(
              child: SelectableText(
                '${data['content'] ?? ''}${data['truncated'] == true ? '\n\n[Vista previa limitada a 80.000 caracteres]' : ''}',
                style: const TextStyle(color: Colors.white70, height: 1.45),
              ),
            ),
          ),
          actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cerrar', style: TextStyle(color: BonsoBrand.aqua)))],
        ),
      );
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo abrir la memoria: $e'), backgroundColor: Colors.redAccent));
    }
  }

  Future<void> _reprocesarDocumento(Map<String, dynamic> doc) async {
    final observations = TextEditingController();
    final note = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: const Text('Reprocesar con observaciones', style: TextStyle(color: Colors.white)),
        content: TextField(
          controller: observations,
          autofocus: true,
          maxLines: 5,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            hintText: 'Ej.: Prioriza montos, identifica riesgos y usa nombres comerciales actualizados.',
            hintStyle: TextStyle(color: Colors.white38),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.aqua),
            onPressed: () => Navigator.pop(ctx, observations.text.trim()),
            child: const Text('Reprocesar', style: TextStyle(color: Colors.black)),
          ),
        ],
      ),
    );
    if (note == null || note.length < 3) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';
      final response = await http.post(
        Uri.parse('$kApiBaseUrl/v1/knowledge/${doc['id_document']}/reprocess'),
        headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'},
        body: jsonEncode({'observaciones': note}),
      );
      if (response.statusCode != 200) throw Exception(response.body);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Documento reprocesado con tus observaciones'), backgroundColor: Colors.green));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo reprocesar: $e'), backgroundColor: Colors.redAccent));
    }
  }

  Color _statusColor(String? status) {
    switch (status) {
      case 'ready': return Colors.greenAccent;
      case 'failed': return Colors.redAccent;
      case 'superseded': return Colors.white38;
      case 'processing': return Colors.amberAccent;
      default: return BonsoBrand.aqua;
    }
  }

  String _statusLabel(String? status) {
    switch (status) {
      case 'ready': return 'Listo para consultas';
      case 'failed': return 'Falló la indexación';
      case 'processing': return 'Procesando';
      case 'queued': return 'En cola';
      case 'superseded': return 'Versión anterior';
      default: return 'Pendiente';
    }
  }

  String _progressLabel(Map<String, dynamic> doc) {
    final job = doc['job'];
    if (job is! Map || (doc['status'] != 'queued' && doc['status'] != 'processing')) {
      return _statusLabel(doc['status']);
    }
    final progress = (job['progress_percent'] as num?)?.toInt() ?? 0;
    final processed = (job['processed_chunks'] as num?)?.toInt() ?? 0;
    final total = (job['total_chunks'] as num?)?.toInt() ?? 0;
    final stage = job['stage']?.toString() ?? 'queued';
    final stageLabel = {
      'queued': 'En cola',
      'extracting': 'Extrayendo contenido',
      'embedding': 'Preparando memoria',
      'finalizing': 'Guardando índice',
    }[stage] ?? _statusLabel(doc['status']);
    final fragments = total > 0 ? ' · $processed/$total fragmentos' : '';
    final retryAt = DateTime.tryParse(job['next_attempt_at']?.toString() ?? '');
    if (stage == 'queued' && retryAt != null && retryAt.isAfter(DateTime.now())) {
      final wait = retryAt.difference(DateTime.now());
      final seconds = wait.inSeconds.clamp(1, 3599).toInt();
      final when = seconds >= 60 ? '${(seconds / 60).ceil()} min' : '$seconds s';
      return 'Reintento automático en $when';
    }
    return '$stageLabel · $progress%$fragments';
  }

  Future<String> _token() async => (await SharedPreferences.getInstance()).getString('jwt_token') ?? '';

  Future<void> _descargarOriginalConocimiento(Map<String, dynamic> doc) async {
    try {
      final response = await http.get(
        Uri.parse('$kApiBaseUrl/v1/knowledge/${doc['id_document']}/download'),
        headers: {'Authorization': 'Bearer ${await _token()}'},
      );
      if (response.statusCode != 200) throw Exception('El original no está disponible');
      final url = jsonDecode(response.body)['url']?.toString();
      if (url == null || !await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication)) {
        throw Exception('No se pudo abrir la descarga');
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo descargar: $e'), backgroundColor: Colors.redAccent));
    }
  }

  Future<void> _reintentarConocimiento(Map<String, dynamic> doc) async {
    try {
      final response = await http.post(
        Uri.parse('$kApiBaseUrl/v1/knowledge/${doc['id_document']}/retry'),
        headers: {'Authorization': 'Bearer ${await _token()}'},
      );
      if (response.statusCode != 200) throw Exception(response.body);
      await _cargarConocimiento();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Documento enviado nuevamente a indexación'), backgroundColor: Colors.green));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo reintentar: $e'), backgroundColor: Colors.redAccent));
    }
  }

  Future<void> _reemplazarConocimiento(Map<String, dynamic> doc) async {
    final picked = await FilePicker.platform.pickFiles(type: FileType.custom, allowedExtensions: ['pdf', 'docx', 'xlsx', 'txt', 'csv', 'md']);
    if (picked == null || picked.files.isEmpty) return;
    final file = picked.files.single;
    try {
      final request = http.MultipartRequest('POST', Uri.parse('$kApiBaseUrl/v1/knowledge/${doc['id_document']}/replace'));
      request.headers['Authorization'] = 'Bearer ${await _token()}';
      if (file.bytes != null) {
        request.files.add(http.MultipartFile.fromBytes('file', file.bytes!, filename: file.name));
      } else if (file.path != null) {
        request.files.add(await http.MultipartFile.fromPath('file', file.path!));
      } else {
        throw Exception('No fue posible leer el archivo seleccionado');
      }
      final response = await http.Response.fromStream(await request.send());
      if (response.statusCode != 200) throw Exception(response.body);
      await _cargarConocimiento();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Nueva versión creada e incorporada a la cola'), backgroundColor: Colors.green));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo reemplazar: $e'), backgroundColor: Colors.redAccent));
    }
  }

  Future<void> _verDetalleConocimiento(Map<String, dynamic> doc) async {
    try {
      final response = await http.get(Uri.parse('$kApiBaseUrl/v1/knowledge/${doc['id_document']}/details'), headers: {'Authorization': 'Bearer ${await _token()}'});
      if (response.statusCode != 200) throw Exception('No se pudo obtener el detalle');
      final detail = Map<String, dynamic>.from(jsonDecode(response.body));
      if (!mounted) return;
      await showDialog<void>(context: context, builder: (_) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: Text(detail['nombre'] ?? 'Documento', style: const TextStyle(color: Colors.white)),
        content: SelectableText(
          'Estado: ${_statusLabel(detail['status'])}\nVersión: ${detail['version']}\nOrigen: ${detail['source_channel']}\nFragmentos: ${detail['chunk_count']}\n${detail['error_message'] != null ? '\nError: ${detail['error_message']}' : ''}',
          style: const TextStyle(color: Colors.white70, height: 1.5),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cerrar', style: TextStyle(color: BonsoBrand.aqua)))],
      ));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo ver el detalle: $e'), backgroundColor: Colors.redAccent));
    }
  }

  Widget _buildKnowledgeList() {
    final itemsToShow = _currentFolderId == null
        ? _conocimiento.where((d) => d['id_folder'] == null).toList()
        : _conocimiento.where((d) => d['id_folder'] == _currentFolderId).toList();
    final foldersToShow = _currentFolderId == null
        ? _carpetas.where((folder) => folder['parent_id'] == null).toList()
        : _carpetas.where((folder) => folder['parent_id'] == _currentFolderId).toList();

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
          child: Row(
            children: [
              if (_currentFolderId != null)
                IconButton(
                  icon: const Icon(Icons.arrow_back, color: BonsoBrand.aqua),
                  onPressed: () => setState(() => _currentFolderId = null),
                ),
              Text(
                _currentFolderId == null 
                  ? 'Carpeta Principal' 
                  : _carpetas.firstWhere((c) => c['id_folder'] == _currentFolderId, orElse: () => {'nombre': 'Carpeta'})['nombre'],
                style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
              ),
              if (_currentFolderId == null && _quota.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(left: 10),
                  child: Text('${_quota['documents_used'] ?? 0}/${_quota['documents_limit'] ?? '—'} documentos', style: const TextStyle(color: Colors.white54, fontSize: 12)),
                ),
              const Spacer(),
              if (_currentFolderId == null)
                TextButton.icon(
                  onPressed: _crearCarpeta,
                  icon: const Icon(Icons.create_new_folder, color: BonsoBrand.aqua),
                  label: const Text('Nueva Carpeta', style: TextStyle(color: BonsoBrand.aqua)),
                ),
            ],
          ),
        ),
        if (_currentFolderId == null && _quota.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(left: 16, right: 16, bottom: 4),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(
                '${_formatBytes(_quota['storage_used_bytes'])} de ${_formatBytes(_quota['storage_limit_bytes'])} usados · máximo ${_formatBytes(_quota['max_upload_bytes'])} por archivo',
                style: const TextStyle(color: Colors.white38, fontSize: 11),
              ),
            ),
          ),
        Expanded(
          child: _carpetas.isEmpty && _conocimiento.isEmpty
            ? const Center(child: Text('La memoria de Bonso está vacía', style: TextStyle(color: Colors.white54)))
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  ...foldersToShow.map((c) => Card(
                      color: BonsoBrand.surface,
                      margin: const EdgeInsets.only(bottom: 12),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: BonsoBrand.aqua.withOpacity(0.3))),
                      child: ListTile(
                        leading: const Icon(Icons.folder, color: BonsoBrand.aqua, size: 40),
                        title: Text(c['nombre'], style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                        subtitle: const Text('Carpeta', style: TextStyle(color: Colors.white54, fontSize: 12)),
                        onTap: () => setState(() => _currentFolderId = c['id_folder']),
                        trailing: PopupMenuButton<String>(color: BonsoBrand.surfaceRaised, onSelected: (value) {
                          if (value == 'rename') _renombrarRecurso(title: 'Renombrar carpeta', currentName: c['nombre'], uri: Uri.parse('$kApiBaseUrl/v1/knowledge/folders/${c['id_folder']}'), body: {'parent_id': c['parent_id']});
                          if (value == 'delete') _eliminarCarpeta(c['id_folder']);
                        }, itemBuilder: (_) => const [PopupMenuItem(value: 'rename', child: Text('Renombrar', style: TextStyle(color: Colors.white))), PopupMenuItem(value: 'delete', child: Text('Enviar a papelera', style: TextStyle(color: Colors.redAccent)))]),
                      ),
                    )),
                  ...itemsToShow.map((doc) => Card(
                    color: doc['status'] == 'superseded' ? BonsoBrand.surface.withOpacity(0.55) : BonsoBrand.surface,
                    margin: const EdgeInsets.only(bottom: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: Colors.white.withOpacity(0.05))),
                    child: ListTile(
                      leading: CircleAvatar(backgroundColor: _statusColor(doc['status']).withOpacity(0.16), child: Icon(Icons.memory, color: _statusColor(doc['status']))),
                      title: Text(doc['nombre'] ?? 'Documento RAG', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold), maxLines: 1, overflow: TextOverflow.ellipsis),
                      subtitle: Text('${_progressLabel(doc)} · v${doc['version'] ?? 1} · ${doc['chunk_count'] ?? 0} fragmentos\n${doc['error_message'] ?? 'Origen: ${doc['source_channel'] ?? 'web'}'}', style: TextStyle(color: doc['status'] == 'failed' ? Colors.redAccent : Colors.white54, fontSize: 12)),
                      isThreeLine: true,
                      onTap: () => _verDetalleConocimiento(doc),
                      trailing: PopupMenuButton<String>(
                        color: BonsoBrand.surfaceRaised,
                        icon: const Icon(Icons.more_vert, color: Colors.white70),
                        onSelected: (value) {
                          if (value == 'detail') _verDetalleConocimiento(doc);
                          if (value == 'view') _verMemoria(doc);
                          if (value == 'download') _descargarOriginalConocimiento(doc);
                          if (value == 'retry') _reintentarConocimiento(doc);
                          if (value == 'replace') _reemplazarConocimiento(doc);
                          if (value == 'reprocess') _reprocesarDocumento(doc);
                          if (value == 'move') _moverDocumento(doc['id_document']);
                          if (value == 'rename') _renombrarRecurso(title: 'Renombrar documento', currentName: doc['nombre'], uri: Uri.parse('$kApiBaseUrl/v1/knowledge/${doc['id_document']}'), body: {});
                          if (value == 'delete') _eliminarConocimiento(doc['id_document']);
                        },
                        itemBuilder: (_) => [
                          const PopupMenuItem(value: 'detail', child: Text('Ver detalle', style: TextStyle(color: Colors.white))),
                          if (doc['status'] == 'ready') const PopupMenuItem(value: 'view', child: Text('Ver contenido procesado', style: TextStyle(color: Colors.white))),
                          if (doc['original_available'] == true) const PopupMenuItem(value: 'download', child: Text('Descargar original', style: TextStyle(color: Colors.white))),
                          if (doc['status'] == 'failed') const PopupMenuItem(value: 'retry', child: Text('Reintentar indexación', style: TextStyle(color: Colors.white))),
                          const PopupMenuItem(value: 'replace', child: Text('Reemplazar por nueva versión', style: TextStyle(color: Colors.white))),
                          if (doc['status'] == 'ready') const PopupMenuItem(value: 'reprocess', child: Text('Reprocesar con observaciones', style: TextStyle(color: Colors.white))),
                          const PopupMenuItem(value: 'move', child: Text('Mover', style: TextStyle(color: Colors.white))),
                          const PopupMenuItem(value: 'rename', child: Text('Renombrar', style: TextStyle(color: Colors.white))),
                          const PopupMenuItem(value: 'delete', child: Text('Eliminar', style: TextStyle(color: Colors.redAccent))),
                        ],
                      ),
                    ),
                  )),
                ],
              ),
        ),
      ],
    );
  }

  Future<void> _subirDocumentoRAG() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
      allowedExtensions: ['pdf', 'docx', 'xlsx', 'txt', 'csv', 'md', 'png', 'jpg', 'jpeg', 'webp'],
      );

      if (result != null && result.files.isNotEmpty) {
        final file = result.files.first;
        if (file.size > 15 * 1024 * 1024) {
          if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('El archivo excede el límite de 15 MB')));
          return;
        }

        setState(() => _isLoading = true);

        final prefs = await SharedPreferences.getInstance();
        final token = prefs.getString('jwt_token') ?? '';
        
        var request = http.MultipartRequest('POST', Uri.parse('$kApiBaseUrl/v1/knowledge/upload'));
        request.headers['Authorization'] = 'Bearer $token';
        if (_currentFolderId != null) request.fields['folder_id'] = _currentFolderId!;

        if (file.bytes != null) {
          request.files.add(http.MultipartFile.fromBytes('files', file.bytes!, filename: file.name));
        } else if (file.path != null) {
          request.files.add(await http.MultipartFile.fromPath('files', file.path!));
        }

        var response = await request.send();
        
        if (response.statusCode == 200) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Documento subido a la memoria RAG exitosamente'), backgroundColor: Colors.green));
            _cargarConocimiento();
          }
        } else {
          final respStr = await response.stream.bytesToString();
          if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error al subir: $respStr'), backgroundColor: Colors.redAccent));
        }
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final subidos = _documentos.where((d) => d['rol'] == 'user').toList();
    final generados = _documentos.where((d) => d['rol'] == 'jarvis').toList();

    return Scaffold(
      backgroundColor: BonsoBrand.ink,
      appBar: AppBar(
        title: const Text('Mis Documentos', style: TextStyle(color: Colors.white)),
        backgroundColor: BonsoBrand.surface,
        iconTheme: const IconThemeData(color: Colors.white),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: BonsoBrand.aqua,
          isScrollable: true,
          labelColor: BonsoBrand.aqua,
          unselectedLabelColor: Colors.white54,
          tabs: const [
            Tab(icon: Icon(Icons.upload_file), text: 'Subidos'),
            Tab(icon: Icon(Icons.auto_awesome), text: 'Generados por Bonso'),
            Tab(icon: Icon(Icons.memory), text: 'Memoria Bonso'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: BonsoBrand.aqua))
          : TabBarView(
              controller: _tabController,
              children: [
                _buildList(subidos),
                _buildList(generados),
                _buildKnowledgeList(),
              ],
            ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _subirDocumentoRAG,
        backgroundColor: BonsoBrand.aqua,
        icon: const Icon(Icons.upload_file, color: Colors.black),
        label: const Text('Subir a Memoria', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
      ),
    );
  }
}
