import 'dart:convert';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'login_screen.dart';
import 'chat_list_screen.dart';
import 'chat_screen.dart';
import 'settings_screen.dart';
import 'documents_screen.dart';

class HubScreen extends StatefulWidget {
  const HubScreen({Key? key}) : super(key: key);

  @override
  State<HubScreen> createState() => _HubScreenState();
}

class _HubScreenState extends State<HubScreen> {
  String _perfil = 'Usuario';
  String _organizacion = 'Organización';
  String _nombreContacto = '';
  String? _token;
  bool _isLoading = true;

  List<Map<String, dynamic>> _activities = [];
  int _archivosSubidos = 0;
  int _archivosGenerados = 0;

  @override
  void initState() {
    super.initState();
    _loadProfileAndData();
  }

  Future<void> _loadProfileAndData() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('jwt_token');
    
    setState(() {
      _perfil = prefs.getString('perfil_jarvis') ?? 'Usuario';
      _organizacion = prefs.getString('nombre_organizacion') ?? 'Organización';
      _nombreContacto = prefs.getString('nombre_contacto') ?? '';
      if (_perfil == 'Inspector_DGC') {
        _perfil = 'Inspector';
      }
    });

    if (_token != null) {
      try {
        final resp = await http.get(
          Uri.parse('$kApiBaseUrl/v1/auth/profile'),
          headers: {'Authorization': 'Bearer $_token'},
        );
        if (resp.statusCode == 200) {
          final data = jsonDecode(resp.body);
          final newOrg = data['nombre_organizacion'] ?? _organizacion;
          final newContact = data['nombre_contacto'] ?? '';
          String newProfile = _perfil;
          final activeIds = data['active_profile_ids'] as List? ?? [];
          final perfs = data['perfiles'] as List? ?? [];
          if (activeIds.isNotEmpty) {
            for (var p in perfs) {
              if (p['id_perfil'] == activeIds[0]) {
                newProfile = p['nombre'];
                break;
              }
            }
          }
          await prefs.setString('perfil_jarvis', newProfile);
          await prefs.setString('nombre_organizacion', newOrg);
          await prefs.setString('nombre_contacto', newContact);
          if (mounted) {
            setState(() {
              _perfil = newProfile == 'Inspector_DGC' ? 'Inspector' : newProfile;
              _organizacion = newOrg;
              _nombreContacto = newContact;
            });
          }
        }
      } catch (e) {}
    }

    await Future.wait([
      _fetchActivities(),
      _fetchFileStats(),
    ]);

    if (mounted) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _fetchActivities() async {
    if (_token == null) return;
    try {
      final response = await http.get(
        Uri.parse('$kApiBaseUrl/v1/chat/sessions'),
        headers: {
          'Authorization': 'Bearer $_token',
          'Content-Type': 'application/json',
        },
      );

      if (response.statusCode == 200) {
        final List data = jsonDecode(response.body);
        if (mounted) {
          setState(() {
            _activities = List<Map<String, dynamic>>.from(data);
          });
        }
      }
    } catch (e) {
      debugPrint('Error al cargar sesiones: $e');
    }
  }

  Future<void> _fetchFileStats() async {
    if (_token == null) return;
    try {
      final response = await http.get(
        Uri.parse('$kApiBaseUrl/v1/chat/sessions/all/files'),
        headers: {
          'Authorization': 'Bearer $_token',
        },
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (mounted) {
          setState(() {
            _archivosSubidos = data['archivos_subidos'] ?? 0;
            _archivosGenerados = data['archivos_generados'] ?? 0;
          });
        }
      }
    } catch (e) {
      debugPrint('Error al cargar métricas de archivos: $e');
    }
  }

  Future<void> _renameActivity(String sessionId, String currentTitle) async {
    final titleController = TextEditingController(text: currentTitle);
    final newTitle = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Renombrar Actividad', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        content: TextField(
          controller: titleController,
          autofocus: true,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            hintText: 'Nuevo nombre de actividad',
            hintStyle: TextStyle(color: Colors.white30),
            enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: Colors.cyanAccent)),
            focusedBorder: UnderlineInputBorder(borderSide: BorderSide(color: Colors.cyanAccent, width: 2)),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('CANCELAR', style: TextStyle(color: Colors.white54)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.cyanAccent),
            onPressed: () => Navigator.pop(ctx, titleController.text.trim()),
            child: const Text('GUARDAR', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );

    if (newTitle == null || newTitle.isEmpty || newTitle == currentTitle) return;

    try {
      final response = await http.patch(
        Uri.parse('$kApiBaseUrl/v1/chat/sessions/$sessionId'),
        headers: {
          'Authorization': 'Bearer $_token',
          'Content-Type': 'application/json',
        },
        body: jsonEncode({'titulo': newTitle}),
      );

      if (response.statusCode == 200) {
        _fetchActivities();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Actividad renombrada exitosamente'), backgroundColor: Colors.cyan),
          );
        }
      } else {
        throw Exception('Error al actualizar');
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('No se pudo renombrar: $e'), backgroundColor: Colors.redAccent),
        );
      }
    }
  }

  Future<void> _deleteActivity(String sessionId, String title) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text('Eliminar Actividad', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        content: Text(
          '¿Estás seguro de que deseas eliminar la actividad "$title"? Esta acción no se puede deshacer.',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('CANCELAR', style: TextStyle(color: Colors.white54)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('ELIMINAR', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    try {
      final response = await http.delete(
        Uri.parse('$kApiBaseUrl/v1/chat/sessions/$sessionId'),
        headers: {'Authorization': 'Bearer $_token'},
      );

      if (response.statusCode == 200) {
        _fetchActivities();
        _fetchFileStats();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Actividad eliminada'), backgroundColor: Colors.redAccent),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error al eliminar: $e'), backgroundColor: Colors.redAccent),
        );
      }
    }
  }

  void _showFileManagementDialog(String tipo) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: Text('Gestión de $tipo', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        content: Text(
          'Actualmente tienes contabilizados $tipo asociados a tus sesiones con J.A.R.V.I.S.\nPuedes gestionar o eliminar los archivos asociados eliminando o limpiando la sesión correspondiente.',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('ENTENDIDO', style: TextStyle(color: Colors.cyanAccent)),
          ),
        ],
      ),
    );
  }

  void _logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('jwt_token');
    await prefs.remove('perfil_jarvis');
    await prefs.remove('nombre_organizacion');
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        title: const Text('Workspace', style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1)),
        backgroundColor: const Color(0xFF1E293B),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.cyanAccent),
            tooltip: 'Actualizar',
            onPressed: () {
              setState(() => _isLoading = true);
              _loadProfileAndData();
            },
          ),
          IconButton(
            icon: const Icon(Icons.settings, color: Colors.white70),
            tooltip: 'Configuración de J.A.R.V.I.S.',
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen())).then((_) {
                _loadProfileAndData();
              });
            },
          ),
          IconButton(
            icon: const Icon(Icons.logout, color: Colors.white54),
            onPressed: _logout,
          ),
        ],
      ),
      body: SafeArea(
        child: _isLoading
            ? const Center(child: CircularProgressIndicator(color: Colors.cyanAccent))
            : RefreshIndicator(
                color: Colors.cyanAccent,
                backgroundColor: const Color(0xFF1E293B),
                onRefresh: _loadProfileAndData,
                child: CustomScrollView(
                  slivers: [
                    SliverToBoxAdapter(
                      child: Padding(
                        padding: const EdgeInsets.all(24.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Hola, ${_nombreContacto.isNotEmpty ? _nombreContacto : _perfil}',
                              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                  ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              '$_organizacion - $_perfil',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                    color: Colors.cyanAccent.withOpacity(0.8),
                                  ),
                            ),
                            const SizedBox(height: 32),
                            _buildMetricCards(),
                            const SizedBox(height: 40),
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  'ACTIVIDADES RECIENTES',
                                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                        color: Colors.white54,
                                        letterSpacing: 1.5,
                                        fontWeight: FontWeight.bold,
                                      ),
                                ),
                                if (_activities.isNotEmpty)
                                  Text(
                                    '${_activities.length} activas',
                                    style: const TextStyle(color: Colors.cyanAccent, fontSize: 12),
                                  ),
                              ],
                            ),
                            const SizedBox(height: 16),
                          ],
                        ),
                      ),
                    ),
                    if (_activities.isEmpty)
                      SliverToBoxAdapter(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 24.0, vertical: 32.0),
                          child: Center(
                            child: Column(
                              children: [
                                Icon(Icons.chat_bubble_outline, size: 48, color: Colors.white.withOpacity(0.2)),
                                const SizedBox(height: 12),
                                const Text(
                                  'No hay actividades registradas.',
                                  style: TextStyle(color: Colors.white54, fontSize: 14),
                                ),
                                const SizedBox(height: 4),
                                const Text(
                                  'Inicia una conversación con J.A.R.V.I.S. para comenzar.',
                                  style: TextStyle(color: Colors.white30, fontSize: 12),
                                ),
                              ],
                            ),
                          ),
                        ),
                      )
                    else
                      SliverPadding(
                        padding: const EdgeInsets.symmetric(horizontal: 24.0),
                        sliver: SliverList(
                          delegate: SliverChildBuilderDelegate(
                            (context, index) {
                              final act = _activities[index];
                              return _buildActivityCard(
                                id: act['id_session'] ?? '',
                                titulo: act['titulo'] ?? 'Conversación',
                                fecha: act['updated_at'] != null
                                    ? act['updated_at'].toString().split('T')[0]
                                    : 'Reciente',
                              );
                            },
                            childCount: _activities.length,
                          ),
                        ),
                      ),
                    const SliverToBoxAdapter(
                      child: SizedBox(height: 80),
                    ),
                  ],
                ),
              ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: Colors.cyan,
        onPressed: () {
          Navigator.push(context, MaterialPageRoute(builder: (_) => const ChatListScreen())).then((_) {
            _loadProfileAndData();
          });
        },
        icon: const Icon(Icons.chat, color: Colors.black),
        label: const Text('Sesiones de J.A.R.V.I.S.', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
      ),
    );
  }

  Widget _buildMetricCards() {
    return Row(
      children: [
        Expanded(
          child: _buildGlassCard(
            title: 'Archivos Subidos',
            value: '$_archivosSubidos',
            icon: Icons.cloud_upload_outlined,
            color: Colors.cyanAccent,
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const DocumentsScreen()),
            ).then((_) => _fetchFileStats()),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _buildGlassCard(
            title: 'Archivos Generados',
            value: '$_archivosGenerados',
            icon: Icons.auto_awesome,
            color: Colors.amberAccent,
            onTap: () => _showFileManagementDialog('Archivos Generados por J.A.R.V.I.S.'),
          ),
        ),
      ],
    );
  }

  Widget _buildGlassCard({
    required String title,
    required String value,
    required IconData icon,
    required Color color,
    VoidCallback? onTap,
  }) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.05),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white.withOpacity(0.1)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Icon(icon, color: color, size: 28),
                    Icon(Icons.more_vert, color: Colors.white.withOpacity(0.3), size: 18),
                  ],
                ),
                const SizedBox(height: 16),
                Text(
                  value,
                  style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.white),
                ),
                const SizedBox(height: 4),
                Text(
                  title,
                  style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 13),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildActivityCard({
    required String id,
    required String titulo,
    required String fecha,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        color: const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.cyan.withOpacity(0.12)),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => ChatScreen(
                  sessionId: id,
                  title: titulo,
                ),
              ),
            ).then((_) => _loadProfileAndData());
          },
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.cyan.withOpacity(0.1),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.assignment_outlined, color: Colors.cyanAccent, size: 22),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        titulo,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.bold,
                          fontSize: 15,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Actualizado: $fecha',
                        style: TextStyle(color: Colors.white.withOpacity(0.5), fontSize: 12),
                      ),
                    ],
                  ),
                ),
                PopupMenuButton<String>(
                  icon: const Icon(Icons.more_vert, color: Colors.white54, size: 20),
                  color: const Color(0xFF1E293B),
                  onSelected: (value) {
                    if (value == 'rename') {
                      _renameActivity(id, titulo);
                    } else if (value == 'delete') {
                      _deleteActivity(id, titulo);
                    }
                  },
                  itemBuilder: (context) => [
                    const PopupMenuItem(
                      value: 'rename',
                      child: Row(
                        children: [
                          Icon(Icons.edit, color: Colors.cyanAccent, size: 18),
                          SizedBox(width: 10),
                          Text('Renombrar', style: TextStyle(color: Colors.white, fontSize: 14)),
                        ],
                      ),
                    ),
                    const PopupMenuItem(
                      value: 'delete',
                      child: Row(
                        children: [
                          Icon(Icons.delete, color: Colors.redAccent, size: 18),
                          SizedBox(width: 10),
                          Text('Eliminar', style: TextStyle(color: Colors.white, fontSize: 14)),
                        ],
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
