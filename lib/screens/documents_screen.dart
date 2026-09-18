import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:file_picker/file_picker.dart';
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
        final data = jsonDecode(resp.body) as List;
        if (mounted) {
          setState(() => _conocimiento = data.map((e) => Map<String, dynamic>.from(e)).toList());
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
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Eliminar documento', style: TextStyle(color: Colors.white)),
        content: const Text(
          'Este documento será eliminado permanentemente y J.A.R.V.I.S. dejará de tenerlo como conocimiento.',
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
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Eliminar memoria', style: TextStyle(color: Colors.white)),
        content: const Text(
          'Este documento será eliminado permanentemente de la memoria RAG y J.A.R.V.I.S. dejará de tenerlo como conocimiento.',
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
        backgroundColor: const Color(0xFF1E293B),
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
              Text('Contenido Extraído', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.cyanAccent)),
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
                      backgroundColor: Colors.cyan,
                      foregroundColor: Colors.white,
                    ),
                    onPressed: () async {
                      final url = doc['url'];
                      if (url != null && url.toString().startsWith('http')) {
                        final uri = Uri.parse(url);
                        if (await canLaunchUrl(uri)) {
                          await launchUrl(uri, mode: LaunchMode.externalApplication);
                        } else {
                          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('No se pudo abrir el archivo original')));
                        }
                      } else {
                         // Fallback for base64
                         ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('El archivo original no está disponible (formato base64)')));
                      }
                    },
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
          color: const Color(0xFF1E293B),
          margin: const EdgeInsets.only(bottom: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: BorderSide(color: Colors.white.withOpacity(0.05)),
          ),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: esGenerado ? Colors.cyan.withOpacity(0.2) : Colors.cyanAccent.withOpacity(0.1),
              child: Icon(icono, color: esGenerado ? Colors.cyan : Colors.cyanAccent),
            ),
            title: Text(
              doc['id_mensaje'] ?? 'Documento',
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
                  icon: const Icon(Icons.visibility, color: Colors.cyanAccent),
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

  Widget _buildKnowledgeList() {
    if (_conocimiento.isEmpty) {
      return const Center(child: Text('La memoria de JARVIS está vacía', style: TextStyle(color: Colors.white54)));
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _conocimiento.length,
      itemBuilder: (context, i) {
        final doc = _conocimiento[i];
        return Card(
          color: const Color(0xFF1E293B),
          margin: const EdgeInsets.only(bottom: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: BorderSide(color: Colors.white.withOpacity(0.05)),
          ),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: Colors.purple.withOpacity(0.2),
              child: const Icon(Icons.memory, color: Colors.purpleAccent),
            ),
            title: Text(
              doc['nombre'] ?? 'Documento RAG',
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: Text(
              'Fecha de almacenamiento: ${doc['created_at']?.split('T')[0] ?? ''}',
              style: const TextStyle(color: Colors.white54, fontSize: 12),
            ),
            trailing: IconButton(
              icon: const Icon(Icons.delete_outline, color: Colors.redAccent),
              onPressed: () => _eliminarConocimiento(doc['id_document']),
              tooltip: 'Olvidar',
            ),
          ),
        );
      },
    );
  }

  Future<void> _subirDocumentoRAG() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'txt', 'csv', 'md'],
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
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        title: const Text('Mis Documentos', style: TextStyle(color: Colors.white)),
        backgroundColor: const Color(0xFF1E293B),
        iconTheme: const IconThemeData(color: Colors.white),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.cyanAccent,
          labelColor: Colors.cyanAccent,
          unselectedLabelColor: Colors.white54,
          tabs: const [
            Tab(icon: Icon(Icons.upload_file), text: 'Subidos'),
            Tab(icon: Icon(Icons.auto_awesome), text: 'Generados por JARVIS'),
            Tab(icon: Icon(Icons.memory), text: 'Memoria JARVIS'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Colors.cyanAccent))
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
        backgroundColor: Colors.cyanAccent,
        icon: const Icon(Icons.upload_file, color: Colors.black),
        label: const Text('Subir a Memoria', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
      ),
    );
  }
}
