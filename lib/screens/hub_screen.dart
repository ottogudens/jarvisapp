import 'dart:convert';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:file_picker/file_picker.dart';
import 'package:fl_chart/fl_chart.dart';
import 'login_screen.dart';
import 'chat_list_screen.dart';
import 'chat_screen.dart';
import 'settings_screen.dart';
import 'documents_screen.dart';
import 'custom_profile_screen.dart';
import 'billing_screen.dart';
import 'marketing_screen.dart';
import 'templates_screen.dart';
import '../brand.dart';

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
  int _tokensConsumidos = 0;
  int _tokensLimit = 0;
  int _plantillas = 0;
  List<Map<String, dynamic>> _dailyTokens = [];
  List<dynamic> _perfilesDisponibles = [];
  List<int> _activeProfileIds = [];

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

    await Future.wait([
      _refreshProfile(prefs),
      _fetchActivities(),
      _fetchFileStats(),
      _fetchDashboardSummary(),
    ]);

    if (mounted) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _refreshProfile(SharedPreferences prefs) async {
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
          final customProfile = data['active_custom_profile'] as Map?;
          final activeIds = data['active_profile_ids'] as List? ?? [];
          final perfs = data['perfiles'] as List? ?? [];
          if (customProfile != null) {
            newProfile = customProfile['nombre']?.toString() ?? newProfile;
          } else if (activeIds.isNotEmpty) {
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
              _perfilesDisponibles = perfs;
              _activeProfileIds = List<int>.from(activeIds);
            });
          }
        }
      } catch (e) {}
    }
  }

  Future<void> _fetchDashboardSummary() async {
    if (_token == null) return;
    try {
      final response = await http.get(
        Uri.parse('$kApiBaseUrl/v1/dashboard/summary'),
        headers: {'Authorization': 'Bearer $_token'},
      );
      if (response.statusCode == 200 && mounted) {
        final data = jsonDecode(response.body);
        setState(() {
          _tokensConsumidos = data['tokens_total'] ?? 0;
          _tokensLimit = data['tokens_limit'] ?? 0;
          _plantillas = data['templates'] ?? 0;
          _dailyTokens = List<Map<String, dynamic>>.from(data['daily_tokens'] ?? []);
        });
      }
    } catch (e) {
      debugPrint('Error al cargar resumen del dashboard: $e');
    }
  }

  Future<void> _selectProfile() async {
    if (_perfilesDisponibles.length < 2 || _token == null) return;
    int? selected = _activeProfileIds.isEmpty ? null : _activeProfileIds.first;
    final result = await showDialog<int>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: BonsoBrand.surface,
        title: const Text('¿Con qué perfil trabajamos?', style: TextStyle(color: Colors.white)),
        content: StatefulBuilder(builder: (ctx, setDialogState) => Column(
          mainAxisSize: MainAxisSize.min,
          children: _perfilesDisponibles.map((p) {
            final id = p['id_perfil'] as int;
            return RadioListTile<int>(
              value: id,
              groupValue: selected,
              activeColor: BonsoBrand.aqua,
              title: Text(p['nombre'] ?? 'Perfil', style: const TextStyle(color: Colors.white)),
              onChanged: (value) => setDialogState(() => selected = value),
            );
          }).toList(),
        )),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.aqua),
            onPressed: selected == null ? null : () => Navigator.pop(ctx, selected),
            child: const Text('Usar este perfil', style: TextStyle(color: Colors.black)),
          ),
        ],
      ),
    );
    if (result == null) return;
    final response = await http.put(
      Uri.parse('$kApiBaseUrl/v1/auth/profile'),
      headers: {'Authorization': 'Bearer $_token', 'Content-Type': 'application/json'},
      body: jsonEncode({'active_profile_ids': [result]}),
    );
    if (response.statusCode == 200) {
      final profile = _perfilesDisponibles.firstWhere((p) => p['id_perfil'] == result);
      final name = profile['nombre']?.toString() ?? 'Usuario';
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('perfil_jarvis', name);
      if (mounted) {
        setState(() { _activeProfileIds = [result]; _perfil = name; });
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Bonso responderá como $name'), backgroundColor: BonsoBrand.aqua));
      }
    }
  }

  Future<void> _uploadTemplate() async {
    final result = await FilePicker.platform.pickFiles(type: FileType.custom, allowedExtensions: ['docx', 'html', 'htm', 'md', 'txt', 'pdf']);
    if (result == null || result.files.isEmpty || _token == null) return;
    final file = result.files.first;
    try {
      final request = http.MultipartRequest('POST', Uri.parse('$kApiBaseUrl/v1/templates/upload'));
      request.headers['Authorization'] = 'Bearer $_token';
      if (file.bytes != null) {
        request.files.add(http.MultipartFile.fromBytes('file', file.bytes!, filename: file.name));
      } else if (file.path != null) {
        request.files.add(await http.MultipartFile.fromPath('file', file.path!));
      }
      final response = await request.send();
      if (response.statusCode != 200) throw Exception(await response.stream.bytesToString());
      await _fetchDashboardSummary();
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Plantilla disponible para Bonso'), backgroundColor: Colors.green));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('No se pudo subir la plantilla: $e'), backgroundColor: Colors.redAccent));
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
        backgroundColor: BonsoBrand.surface,
        title: const Text('Renombrar Actividad', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        content: TextField(
          controller: titleController,
          autofocus: true,
          style: const TextStyle(color: Colors.white),
          decoration: const InputDecoration(
            hintText: 'Nuevo nombre de actividad',
            hintStyle: TextStyle(color: Colors.white30),
            enabledBorder: UnderlineInputBorder(borderSide: BorderSide(color: BonsoBrand.aqua)),
            focusedBorder: UnderlineInputBorder(borderSide: BorderSide(color: BonsoBrand.aqua, width: 2)),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('CANCELAR', style: TextStyle(color: Colors.white54)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: BonsoBrand.aqua),
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
            const SnackBar(content: Text('Actividad renombrada exitosamente'), backgroundColor: BonsoBrand.aqua),
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
        backgroundColor: BonsoBrand.surface,
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
        backgroundColor: BonsoBrand.surface,
        title: Text('Gestión de $tipo', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        content: Text(
          'Actualmente tienes contabilizados $tipo asociados a tus sesiones con Bonso.\nPuedes gestionar o eliminar los archivos asociados eliminando o limpiando la sesión correspondiente.',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('ENTENDIDO', style: TextStyle(color: BonsoBrand.aqua)),
          ),
        ],
      ),
    );
  }

  void _logout() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('jwt_token');
    if (token != null && token.isNotEmpty) {
      try {
        await http.post(
          Uri.parse('$kApiBaseUrl/v1/auth/logout'),
          headers: {'Authorization': 'Bearer $token'},
        );
      } catch (_) {
        // Limpiamos igualmente el dispositivo; el token expira de forma normal
        // si no hubo conectividad para notificar al servidor.
      }
    }
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
      backgroundColor: BonsoBrand.ink,
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Image.asset(
              'assets/branding/bonso-mark.png',
              width: 26,
              height: 26,
              semanticLabel: 'Bonso',
            ),
            const SizedBox(width: 9),
            const Text('BONSO', style: TextStyle(fontWeight: FontWeight.w800, letterSpacing: 1.6)),
          ],
        ),
        backgroundColor: BonsoBrand.surface,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: BonsoBrand.aqua),
            tooltip: 'Actualizar',
            onPressed: () {
              setState(() => _isLoading = true);
              _loadProfileAndData();
            },
          ),
          IconButton(
            icon: const Icon(Icons.settings, color: Colors.white70),
            tooltip: 'Configuración de Bonso',
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen())).then((_) {
                _loadProfileAndData();
              });
            },
          ),
          IconButton(
            icon: const Icon(Icons.logout, color: Colors.white54),
            onPressed: _logout,
            tooltip: 'Cerrar sesión',
          ),
        ],
      ),
      body: SafeArea(
        child: _isLoading
            ? const Center(child: CircularProgressIndicator(color: BonsoBrand.aqua))
            : RefreshIndicator(
                color: BonsoBrand.aqua,
                backgroundColor: BonsoBrand.surface,
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
                                    color: BonsoBrand.text,
                                    fontWeight: FontWeight.bold,
                                  ),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              '$_organizacion - $_perfil',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                    color: BonsoBrand.aqua.withOpacity(0.8),
                                  ),
                            ),
                            const SizedBox(height: 16),
                            if (_perfilesDisponibles.length > 1)
                              OutlinedButton.icon(
                                onPressed: _selectProfile,
                                icon: const Icon(Icons.person_search, size: 18),
                                label: Text('Perfil activo: $_perfil · Cambiar'),
                                style: OutlinedButton.styleFrom(foregroundColor: BonsoBrand.aqua, side: const BorderSide(color: BonsoBrand.aqua)),
                              ),
                            const SizedBox(height: 20),
                            _buildQuickActions(),
                            const SizedBox(height: 24),
                            _buildMetricCards(),
                            const SizedBox(height: 20),
                            _buildUsageChart(),
                            const SizedBox(height: 32),
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
                                    style: const TextStyle(color: BonsoBrand.aqua, fontSize: 12),
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
                              'Inicia una conversación con Bonso para comenzar.',
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
    );
  }

  Widget _buildMetricCards() {
    return LayoutBuilder(builder: (context, constraints) {
      final narrow = constraints.maxWidth < 520;
      final uploaded = _buildGlassCard(
            title: 'Archivos Subidos',
            value: '$_archivosSubidos',
            icon: Icons.cloud_upload_outlined,
            color: BonsoBrand.aqua,
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const DocumentsScreen()),
            ).then((_) => _fetchFileStats()),
          );
      final generated = _buildGlassCard(
            title: 'Archivos Generados',
            value: '$_archivosGenerados',
            icon: Icons.auto_awesome,
            color: Colors.amberAccent,
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const DocumentsScreen(initialTab: 1)),
            ).then((_) => _fetchFileStats()),
          );
      final tokens = _buildGlassCard(
            title: 'Tokens consumidos',
            value: _formatTokens(_tokensConsumidos),
            icon: Icons.data_usage_outlined,
            color: Colors.deepPurpleAccent,
            onTap: _showTokenDetails,
          );
      final templates = _buildGlassCard(
            title: 'Plantillas',
            value: '$_plantillas',
            icon: Icons.description_outlined,
            color: Colors.orangeAccent,
            onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const TemplatesScreen())).then((_) => _fetchDashboardSummary()),
          );
      if (narrow) {
        return Column(children: [uploaded, const SizedBox(height: 12), generated, const SizedBox(height: 12), tokens, const SizedBox(height: 12), templates]);
      }
      return Column(children: [
        Row(children: [Expanded(child: uploaded), const SizedBox(width: 16), Expanded(child: generated)]),
        const SizedBox(height: 16),
        Row(children: [Expanded(child: tokens), const SizedBox(width: 16), Expanded(child: templates)]),
      ]);
    });
  }

  String _formatTokens(int value) => value >= 1000 ? '${(value / 1000).toStringAsFixed(1)}k' : '$value';

  void _showTokenDetails() {
    final percent = _tokensLimit > 0 ? (_tokensConsumidos / _tokensLimit * 100).clamp(0, 100).toStringAsFixed(1) : '—';
    showModalBottomSheet(context: context, backgroundColor: BonsoBrand.surface, shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))), builder: (_) => SafeArea(child: Padding(padding: const EdgeInsets.all(24), child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [const Text('Uso de tokens', style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)), const SizedBox(height: 8), const Text('Los tokens miden el procesamiento de tus conversaciones y documentos.', style: TextStyle(color: Colors.white70)), const SizedBox(height: 22), Text('${_formatTokens(_tokensConsumidos)} usados', style: const TextStyle(color: BonsoBrand.aqua, fontSize: 28, fontWeight: FontWeight.bold)), Text(_tokensLimit > 0 ? 'de ${_formatTokens(_tokensLimit)} incluidos este mes · $percent%' : 'Sin límite mensual informado', style: const TextStyle(color: Colors.white54)), const SizedBox(height: 16), LinearProgressIndicator(value: _tokensLimit > 0 ? (_tokensConsumidos / _tokensLimit).clamp(0, 1) : 0, color: BonsoBrand.aqua, backgroundColor: Colors.white12), const SizedBox(height: 20), const Text('Incluye consultas, análisis de archivos y generación de respuestas. El detalle diario está disponible en el gráfico del inicio.', style: TextStyle(color: Colors.white70, height: 1.4))]))));
  }

  Widget _buildQuickActions() {
    final List<(IconData, String, VoidCallback)> actions = [
      (Icons.add_comment_outlined, 'Nueva consulta', () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ChatListScreen())).then((_) => _loadProfileAndData())),
      (Icons.upload_file_outlined, 'Subir plantilla', _uploadTemplate),
      (Icons.folder_open_outlined, 'Documentos', () => Navigator.push(context, MaterialPageRoute(builder: (_) => const DocumentsScreen()))),
      (Icons.tune_outlined, 'Configuración', () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen())).then((_) => _loadProfileAndData())),
      (Icons.person_add_alt_1_outlined, 'Crear asistente', () => Navigator.push(context, MaterialPageRoute(builder: (_) => const CustomProfileScreen())).then((_) => _loadProfileAndData())),
      (Icons.receipt_long_outlined, 'Plan y facturación', () => Navigator.push(context, MaterialPageRoute(builder: (_) => const BillingScreen()))),
      (Icons.campaign_outlined, 'Marketing Hub', () => Navigator.push(context, MaterialPageRoute(builder: (_) => const MarketingScreen()))),
    ];
    return LayoutBuilder(builder: (context, constraints) {
      final width = (constraints.maxWidth - 10) / 2;
      return Wrap(spacing: 10, runSpacing: 10, children: actions.map((action) => SizedBox(width: width, child: OutlinedButton.icon(onPressed: action.$3, icon: Icon(action.$1, size: 18), label: Text(action.$2, overflow: TextOverflow.ellipsis), style: OutlinedButton.styleFrom(alignment: Alignment.centerLeft, foregroundColor: BonsoBrand.aqua, side: BorderSide(color: BonsoBrand.aqua.withOpacity(.45)), padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14)))).toList());
    });
  }

  Widget _buildUsageChart() {
    final maxValue = _dailyTokens.fold<double>(1, (max, item) => (item['tokens'] as num? ?? 0).toDouble() > max ? (item['tokens'] as num).toDouble() : max);
    return Container(
      height: 210,
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      decoration: BoxDecoration(color: BonsoBrand.surface, borderRadius: BorderRadius.circular(16), border: Border.all(color: Colors.white.withOpacity(.08))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('CONSUMO DE TOKENS · ÚLTIMOS 7 DÍAS', style: TextStyle(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 1)),
        const SizedBox(height: 14),
        Expanded(child: BarChart(BarChartData(
          maxY: maxValue * 1.2,
          gridData: const FlGridData(show: false),
          borderData: FlBorderData(show: false),
          titlesData: FlTitlesData(
            leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            bottomTitles: AxisTitles(sideTitles: SideTitles(showTitles: true, reservedSize: 26, getTitlesWidget: (value, meta) {
              if (value < 0 || value >= _dailyTokens.length) return const SizedBox.shrink();
              final date = (_dailyTokens[value.toInt()]['date'] ?? '').toString();
              return Padding(padding: const EdgeInsets.only(top: 6), child: Text(date.length >= 10 ? date.substring(8, 10) : '', style: const TextStyle(color: Colors.white54, fontSize: 10)));
            })),
          ),
          barGroups: List.generate(_dailyTokens.length, (index) => BarChartGroupData(x: index, barRods: [BarChartRodData(toY: (_dailyTokens[index]['tokens'] as num? ?? 0).toDouble(), color: BonsoBrand.aqua, width: 14, borderRadius: BorderRadius.circular(4))])),
        ))),
      ]),
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
        color: BonsoBrand.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: BonsoBrand.aqua.withOpacity(0.12)),
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
                    color: BonsoBrand.aqua.withOpacity(0.1),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.assignment_outlined, color: BonsoBrand.aqua, size: 22),
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
                  color: BonsoBrand.surface,
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
                          Icon(Icons.edit, color: BonsoBrand.aqua, size: 18),
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
