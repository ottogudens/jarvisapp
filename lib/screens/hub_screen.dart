import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'login_screen.dart';
import 'chat_list_screen.dart';
import 'settings_screen.dart';

class HubScreen extends StatefulWidget {
  const HubScreen({Key? key}) : super(key: key);

  @override
  State<HubScreen> createState() => _HubScreenState();
}

class _HubScreenState extends State<HubScreen> {
  String _perfil = 'Usuario';
  String _organizacion = 'Organización';

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _perfil = prefs.getString('perfil_jarvis') ?? 'Usuario';
      _organizacion = prefs.getString('nombre_organizacion') ?? 'Organización';
      
      // Limpiar el nombre para la UI si es Inspector_DGC
      if (_perfil == 'Inspector_DGC') {
        _perfil = 'Inspector';
      }
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
        title: const Text('Workspace', style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1)),
        backgroundColor: const Color(0xFF1E293B),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings, color: Colors.white70),
            tooltip: 'Configuración de J.A.R.V.I.S.',
            onPressed: () {
              Navigator.push(context, MaterialPageRoute(builder: (_) => const SettingsScreen()));
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
                      'Hola, $_perfil',
                      style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                          ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _organizacion,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            color: Colors.cyanAccent.withOpacity(0.8),
                          ),
                    ),
                    const SizedBox(height: 32),
                    _buildMetricCards(),
                    const SizedBox(height: 40),
                    Text(
                      'ACTIVIDADES RECIENTES',
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
                    return _buildActivityCard(
                      id: 'ACT-100${index + 1}',
                      descripcion: _perfil == 'Inspector' 
                          ? 'Inspección Local Comercial ${index + 1}' 
                          : 'Revisión Vehículo ${index + 1}',
                      estado: index == 0 ? 'En curso' : 'Pendiente',
                    );
                  },
                  childCount: 3, // Mock activities
                ),
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: Colors.cyan,
        onPressed: () {
          Navigator.push(context, MaterialPageRoute(builder: (_) => const ChatListScreen()));
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
            title: 'Pendientes',
            value: '3',
            icon: Icons.pending_actions,
            color: Colors.orangeAccent,
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: _buildGlassCard(
            title: 'Completadas',
            value: '12',
            icon: Icons.check_circle_outline,
            color: Colors.cyanAccent,
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

  Widget _buildActivityCard({required String id, required String descripcion, required String estado}) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const ChatListScreen()),
            );
          },
          borderRadius: BorderRadius.circular(16),
          child: Ink(
            decoration: BoxDecoration(
              color: const Color(0xFF1E293B),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.cyan.withOpacity(0.1)),
            ),
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.cyan.withOpacity(0.1),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.assignment, color: Colors.cyanAccent),
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
                          descripcion,
                          style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 14),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: estado == 'Pendiente' ? Colors.orange.withOpacity(0.2) : Colors.blue.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      estado,
                      style: TextStyle(
                        color: estado == 'Pendiente' ? Colors.orangeAccent : Colors.blueAccent,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
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
