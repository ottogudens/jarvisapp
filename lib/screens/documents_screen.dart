import 'dart:convert';
import 'dart:html' as html;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:file_picker/file_picker.dart';
import '../brand.dart';
import 'login_screen.dart'; // Contiene kApiBaseUrl

class DocumentsScreen extends StatefulWidget {
  const DocumentsScreen({super.key});

  @override
  State<DocumentsScreen> createState() => _DocumentsScreenState();
}

class _DocumentsScreenState extends State<DocumentsScreen> with SingleTickerProviderStateMixin {
  bool _isLoading = true;
  List<Map<String, dynamic>> _documentos = [];
  List<Map<String, dynamic>> _conocimiento = [];
  List<Map<String, dynamic>> _carpetas = [];
  String? _currentFolderId;
  String _searchQuery = '';
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _cargarDocumentos();
    _cargarConocimiento();
  }
  
  @override
  void dispose() {
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
          });
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

  Future<void> _abrirOriginal(Map<String, dynamic> doc) async {
    final url = doc['url']?.toString();
    if (url == null || url.isEmpty) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('El archivo original no está disponible')));
      return;
    }
    try {
      if (url.startsWith('data:')) {
        // Abrir una data URI directamente produce una pestaña vacía en varios
        // navegadores. Un Blob conserva el binario y su tipo MIME real.
        final parts = url.split('base64,');
        if (parts.length != 2) throw const FormatException('Formato de archivo inválido');
        final mime = parts.first.substring(5).split(';').first;
        final bytes = base64Decode(parts.last);
        final blobUrl = html.Url.createObjectUrlFromBlob(html.Blob([bytes], mime));
        final opened = html.window.open(blobUrl, '_blank');
        if (opened == null) throw Exception('El navegador bloqueó la ventana emergente');
        return;
      }
      final ok = await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
      if (!ok) throw Exception('No se pudo abrir la URL');
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
        IconData icono = Icons.insert_drive_file;
        if (tipo.contains('pdf')) icono = Icons.picture_as_pdf;
        if (tipo.contains('image')) icono = Icons.image;
        if (esGenerado) icono = Icons.auto_awesome;

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
              'Sesión: ${doc['titulo_sesion']}\nTipo: $tipo\n${doc['created_at']?.split('T')[0] ?? ''}',
              style: const TextStyle(color: Colors.white54, fontSize: 12),
            ),
            isThreeLine: true,
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  icon: const Icon(Icons.visibility, color: BonsoBrand.aqua),
                  onPressed: () => _verContenido(doc),
                  tooltip: 'Ver contenido',
                ),
                IconButton(
                  icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
                  onPressed: () => _eliminarDocumento(doc['id_mensaje']),
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
          body: jsonEncode({'nombre': result}),
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
          content: SizedBox(
            width: 680,
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

  Widget _buildKnowledgeList() {
    final itemsToShow = _currentFolderId == null
        ? _conocimiento.where((d) => d['id_folder'] == null).toList()
        : _conocimiento.where((d) => d['id_folder'] == _currentFolderId).toList();

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
        Expanded(
          child: _carpetas.isEmpty && _conocimiento.isEmpty
            ? const Center(child: Text('La memoria de Bonso está vacía', style: TextStyle(color: Colors.white54)))
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_currentFolderId == null)
                    ..._carpetas.map((c) => Card(
                      color: BonsoBrand.surface,
                      margin: const EdgeInsets.only(bottom: 12),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: BonsoBrand.aqua.withOpacity(0.3))),
                      child: ListTile(
                        leading: const Icon(Icons.folder, color: BonsoBrand.aqua, size: 40),
                        title: Text(c['nombre'], style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                        subtitle: const Text('Carpeta', style: TextStyle(color: Colors.white54, fontSize: 12)),
                        onTap: () => setState(() => _currentFolderId = c['id_folder']),
                        trailing: IconButton(
                          icon: const Icon(Icons.delete, color: Colors.redAccent),
                          onPressed: () => _eliminarCarpeta(c['id_folder']),
                        ),
                      ),
                    )),
                  ...itemsToShow.map((doc) => Card(
                    color: BonsoBrand.surface,
                    margin: const EdgeInsets.only(bottom: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: Colors.white.withOpacity(0.05))),
                    child: ListTile(
                      leading: CircleAvatar(backgroundColor: Colors.purple.withOpacity(0.2), child: const Icon(Icons.memory, color: Colors.purpleAccent)),
                      title: Text(doc['nombre'] ?? 'Documento RAG', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold), maxLines: 1, overflow: TextOverflow.ellipsis),
                      subtitle: Text('Fecha: ${doc['created_at']?.split('T')[0] ?? ''}', style: const TextStyle(color: Colors.white54, fontSize: 12)),
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          IconButton(icon: const Icon(Icons.visibility_outlined, color: Colors.white70), tooltip: 'Ver contenido procesado', onPressed: () => _verMemoria(doc)),
                          IconButton(icon: const Icon(Icons.refresh, color: Colors.amberAccent), tooltip: 'Reprocesar con observaciones', onPressed: () => _reprocesarDocumento(doc)),
                          IconButton(icon: const Icon(Icons.drive_file_move, color: BonsoBrand.aqua), onPressed: () => _moverDocumento(doc['id_document'])),
                          IconButton(icon: const Icon(Icons.delete_outline, color: Colors.redAccent), onPressed: () => _eliminarConocimiento(doc['id_document'])),
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
        allowedExtensions: ['pdf', 'txt', 'csv', 'md', 'png', 'jpg', 'jpeg', 'webp'],
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
