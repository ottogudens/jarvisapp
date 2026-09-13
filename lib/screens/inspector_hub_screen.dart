/// J.A.R.V.I.S. — Hub del Inspector Fiscal DGC
///
/// Dashboard principal del perfil Inspector con:
/// - Métricas de inspecciones
/// - Lista de inspecciones pendientes (mock)
/// - Botón para iniciar nueva inspección por voz

import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'inspector_screen.dart';
import 'login_screen.dart';
import 'chat_list_screen.dart';

class InspectorHubScreen extends StatefulWidget {
  const InspectorHubScreen({Key? key}) : super(key: key);

  @override
  State<InspectorHubScreen> createState() => _InspectorHubScreenState();
}

class _InspectorHubScreenState extends State<InspectorHubScreen> {
  String _organizacion = '';

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _organizacion = prefs.getString('nombre_organizacion') ?? 'Organización';
    });
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
        title: const Text('J.A.R.V.I.S. Inspector', style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1)),
        backgroundColor: const Color(0xFF1E293B),
        actions: [
          IconButton(
            icon: const Icon(Icons.chat_bubble_outline, color: Colors.amber),
            tooltip: 'Chat con JARVIS',
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const ChatListScreen()));
            },
          ),
          IconButton(
            icon: const Icon(Icons.logout, color: Colors.white54),
            onPressed: _logout,
          ),
        ],
      ),
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Bienvenido, Señor Inspector',
                      style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _organizacion,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            color: Colors.amber.withOpacity(0.8),
                          ),
                    ),
                    const SizedBox(height: 32),
                    _buildMetricCards(),
                    const SizedBox(height: 32),

                    // Botón principal de acción
                    SizedBox(
                      width: double.infinity,
                      height: 56,
                      child: ElevatedButton.icon(
                        onPressed: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(builder: (_) => const InspectorScreen()),
                          );
                        },
                        icon: const Icon(Icons.mic, size: 28),
                        label: const Text(
                          'INICIAR INSPECCIÓN POR VOZ',
                          style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1, fontSize: 15),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.amber,
                          foregroundColor: Colors.black87,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                          elevation: 4,
                        ),
                      ),
                    ),

                    const SizedBox(height: 40),
                    Text(
                      'INSPECCIONES RECIENTES',
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                            color: Colors.white54,
                            letterSpacing: 1.5,
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                    const SizedBox(height: 16),
                  ],
                ),
              ),
            ),
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 24.0),
              sliver: SliverList(
                delegate: SliverChildBuilderDelegate(
                  (context, index) {
                    final inspecciones = [
                      {'id': 'INSP-2024-001', 'local': 'Supermercado Express', 'estado': 'Pendiente', 'gravedad': 'Grave'},
                      {'id': 'INSP-2024-002', 'local': 'Farmacia del Pueblo', 'estado': 'Cerrada', 'gravedad': 'Leve'},
                      {'id': 'INSP-2024-003', 'local': 'Restaurant La Esquina', 'estado': 'En Proceso', 'gravedad': 'Gravísima'},
                    ];
                    final insp = inspecciones[index];
                    return _buildInspectionCard(
                      id: insp['id']!,
                      local: insp['local']!,
                      estado: insp['estado']!,
                      gravedad: insp['gravedad']!,
                    );
                  },
                  childCount: 3,
                ),
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: Colors.amber,
        onPressed: () {
          Navigator.push(context, MaterialPageRoute(builder: (_) => const ChatListScreen()));
        },
        icon: const Icon(Icons.chat, color: Colors.black),
        label: const Text('Chat con JARVIS', style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
      ),
    );
  }

  Widget _buildMetricCards() {
    return Row(
      children: [
        Expanded(
          child: _buildGlassCard(
            title: 'Pendientes',
            value: '5',
            icon: Icons.assignment_late_outlined,
            color: Colors.orangeAccent,
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _buildGlassCard(
            title: 'Completadas',
            value: '23',
            icon: Icons.assignment_turned_in_outlined,
            color: Colors.amber,
          ),
        ),
      ],
    );
  }

  Widget _buildGlassCard({required String title, required String value, required IconData icon, required Color color}) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
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
              Icon(icon, color: color, size: 28),
              const SizedBox(height: 16),
              Text(
                value,
                style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.white),
              ),
              const SizedBox(height: 4),
              Text(
                title,
                style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 14),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildInspectionCard({required String id, required String local, required String estado, required String gravedad}) {
    Color estadoColor;
    Color gravedadColor;

    switch (estado) {
      case 'Pendiente':
        estadoColor = Colors.orangeAccent;
        break;
      case 'En Proceso':
        estadoColor = Colors.amber;
        break;
      default:
        estadoColor = Colors.greenAccent;
    }

    switch (gravedad) {
      case 'Gravísima':
        gravedadColor = Colors.redAccent;
        break;
      case 'Grave':
        gravedadColor = Colors.orangeAccent;
        break;
      default:
        gravedadColor = Colors.greenAccent;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const InspectorScreen()),
            );
          },
          borderRadius: BorderRadius.circular(16),
          child: Ink(
            decoration: BoxDecoration(
              color: const Color(0xFF1E293B),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.amber.withOpacity(0.1)),
            ),
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.amber.withOpacity(0.1),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.policy, color: Colors.amber),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          id,
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          local,
                          style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 14),
                        ),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: estadoColor.withOpacity(0.2),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          estado,
                          style: TextStyle(color: estadoColor, fontSize: 11, fontWeight: FontWeight.bold),
                        ),
                      ),
                      const SizedBox(height: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: gravedadColor.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          gravedad,
                          style: TextStyle(color: gravedadColor, fontSize: 11, fontWeight: FontWeight.bold),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
