import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'login_screen.dart'; // Contiene kApiBaseUrl

class DocumentsScreen extends StatefulWidget {
  const DocumentsScreen({super.key});

  @override
  State<DocumentsScreen> createState() => _DocumentsScreenState();
}

class _DocumentsScreenState extends State<DocumentsScreen> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _documentos = [];
  String _searchQuery = '';

  @override
  void initState() {
    super.initState();
    _cargarDocumentos();
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

  Future<void> _eliminarDocumento(String idMensaje) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Eliminar documento', style: TextStyle(color: Colors.white)),
        content: const Text(
          'Este documento sera eliminado permanentemente y J.A.R.V.I.S. dejara de tenerlo como conocimiento.',
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

  Future<void> _verContenido(Map<String, dynamic> doc) async {
    showDialog(
      context: context,
      builder: (_) => Dialog(
        backgroundColor: const Color(0xFF1E293B),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(_iconForTipo(doc['tipo'] ?? ''), color: Colors.cyanAccent),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      doc['titulo_sesion'] ?? 'Documento',
                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close, color: Colors.white38),
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(_formatDate(doc['created_at'] ?? ''), style: const TextStyle(color: Colors.white38, fontSize: 11)),
              const Divider(color: Color(0xFF334155), height: 20),
              const Text('Contenido del mensaje:', style: TextStyle(color: Colors.white54, fontSize: 12)),
              const SizedBox(height: 6),
              Container(
                constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.4),
                child: SingleChildScrollView(
                  child: SelectableText(
                    doc['contenido'] ?? 'Sin contenido',
                    style: const TextStyle(color: Colors.white, fontSize: 13, height: 1.5),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cerrar', style: TextStyle(color: Colors.cyanAccent)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  IconData _iconForTipo(String tipo) {
    if (tipo.startsWith('image/')) return Icons.image;
    if (tipo.startsWith('audio/')) return Icons.mic;
    if (tipo == 'application/pdf') return Icons.picture_as_pdf;
    if (tipo.startsWith('text/')) return Icons.description;
    return Icons.attach_file;
  }

  Color _colorForTipo(String tipo) {
    if (tipo.startsWith('image/')) return Colors.orange;
    if (tipo.startsWith('audio/')) return Colors.greenAccent;
    if (tipo == 'application/pdf') return Colors.redAccent;
    if (tipo.startsWith('text/')) return Colors.lightBlueAccent;
    return Colors.cyanAccent;
  }

  String _formatDate(String isoDate) {
    try {
      final dt = DateTime.parse(isoDate).toLocal();
      return '${dt.day.toString().padLeft(2, '0')}/${dt.month.toString().padLeft(2, '0')}/${dt.year} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return isoDate;
    }
  }

  String _labelForTipo(String tipo) {
    if (tipo.startsWith('image/')) return 'Imagen';
    if (tipo.startsWith('audio/')) return 'Audio';
    if (tipo == 'application/pdf') return 'PDF';
    if (tipo.startsWith('text/')) return 'Texto';
    return 'Archivo';
  }

  List<Map<String, dynamic>> get _filteredDocs {
    if (_searchQuery.isEmpty) return _documentos;
    final q = _searchQuery.toLowerCase();
    return _documentos.where((d) {
      return (d['titulo_sesion'] ?? '').toLowerCase().contains(q) ||
          (d['tipo'] ?? '').toLowerCase().contains(q) ||
          (d['contenido'] ?? '').toLowerCase().contains(q);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E293B),
        elevation: 2,
        title: const Row(
          children: [
            Icon(Icons.folder_open, color: Colors.cyanAccent, size: 22),
            SizedBox(width: 10),
            Text('Mis Documentos', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white70),
            tooltip: 'Actualizar',
            onPressed: _cargarDocumentos,
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: 'Buscar documentos...',
                hintStyle: const TextStyle(color: Colors.white38),
                prefixIcon: const Icon(Icons.search, color: Colors.white38),
                filled: true,
                fillColor: const Color(0xFF1E293B),
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
              onChanged: (val) => setState(() => _searchQuery = val),
            ),
          ),
          if (!_isLoading)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
              child: Row(
                children: [
                  Text(
                    '${_filteredDocs.length} documento${_filteredDocs.length != 1 ? 's' : ''}',
                    style: const TextStyle(color: Colors.white38, fontSize: 12),
                  ),
                ],
              ),
            ),
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator(color: Colors.cyanAccent))
                : _filteredDocs.isEmpty
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: const [
                            Icon(Icons.folder_off, size: 64, color: Color(0xFF334155)),
                            SizedBox(height: 16),
                            Text('Sin documentos cargados', style: TextStyle(color: Colors.white38, fontSize: 16)),
                            SizedBox(height: 8),
                            Text(
                              'Adjunta PDFs, textos o audios en el chat\npara que J.A.R.V.I.S. los use como conocimiento.',
                              textAlign: TextAlign.center,
                              style: TextStyle(color: Colors.white24, fontSize: 12),
                            ),
                          ],
                        ),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                        itemCount: _filteredDocs.length,
                        itemBuilder: (context, index) {
                          final doc = _filteredDocs[index];
                          final tipo = doc['tipo'] as String? ?? '';
                          final color = _colorForTipo(tipo);
                          final icon = _iconForTipo(tipo);
                          final label = _labelForTipo(tipo);
                          final sesion = doc['titulo_sesion'] as String? ?? 'Conversacion';
                          final fecha = _formatDate(doc['created_at'] as String? ?? '');
                          final contenido = doc['contenido'] as String? ?? '';

                          return Container(
                            margin: const EdgeInsets.symmetric(vertical: 5),
                            decoration: BoxDecoration(
                              color: const Color(0xFF1E293B),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFF334155)),
                            ),
                            child: ListTile(
                              contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                              leading: Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: color.withOpacity(0.15),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Icon(icon, color: color, size: 20),
                              ),
                              title: Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: color.withOpacity(0.2),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(label, style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold)),
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      sesion,
                                      style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                ],
                              ),
                              subtitle: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const SizedBox(height: 4),
                                  Text(
                                    contenido.isEmpty ? '(sin descripcion)' : contenido,
                                    style: const TextStyle(color: Colors.white54, fontSize: 11),
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  const SizedBox(height: 4),
                                  Row(
                                    children: [
                                      const Icon(Icons.access_time, size: 11, color: Colors.white30),
                                      const SizedBox(width: 4),
                                      Text(fecha, style: const TextStyle(color: Colors.white30, fontSize: 10)),
                                    ],
                                  ),
                                ],
                              ),
                              trailing: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  IconButton(
                                    icon: const Icon(Icons.visibility_outlined, color: Colors.white38, size: 20),
                                    tooltip: 'Ver contenido',
                                    onPressed: () => _verContenido(doc),
                                  ),
                                  IconButton(
                                    icon: const Icon(Icons.delete_outline, color: Colors.redAccent, size: 20),
                                    tooltip: 'Eliminar',
                                    onPressed: () => _eliminarDocumento(doc['id_mensaje'] as String),
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
