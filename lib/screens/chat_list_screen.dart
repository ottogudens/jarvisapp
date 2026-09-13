import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'login_screen.dart'; // Contiene kApiBaseUrl
import 'chat_screen.dart';

class ChatListScreen extends StatefulWidget {
  const ChatListScreen({Key? key}) : super(key: key);

  @override
  State<ChatListScreen> createState() => _ChatListScreenState();
}

class _ChatListScreenState extends State<ChatListScreen> {
  List<Map<String, dynamic>> _sessions = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchSessions();
  }

  Future<void> _fetchSessions() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';

      final response = await http.get(
        Uri.parse('$kApiBaseUrl/v1/chat/sessions'),
        headers: {
          'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        setState(() {
          _sessions = data.cast<Map<String, dynamic>>();
          _isLoading = false;
        });
      } else {
        setState(() => _isLoading = false);
      }
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _createNewSession() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';

      final response = await http.post(
        Uri.parse('$kApiBaseUrl/v1/chat/sessions'),
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: jsonEncode({'titulo': 'Nueva Conversación'}),
      );

      if (response.statusCode == 200) {
        final newSession = jsonDecode(response.body);
        if (!mounted) return;
        await Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => ChatScreen(
              sessionId: newSession['id_session'],
              title: newSession['titulo'],
            ),
          ),
        );
        _fetchSessions();
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error al crear conversación: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E293B),
        title: const Text(
          'Chats con J.A.R.V.I.S.',
          style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1),
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Colors.cyanAccent))
          : _sessions.isEmpty
              ? _buildEmptySessions()
              : RefreshIndicator(
                  onRefresh: _fetchSessions,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _sessions.length,
                    itemBuilder: (context, index) {
                      final session = _sessions[index];
                      return _buildSessionCard(session);
                    },
                  ),
                ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: Colors.cyan,
        onPressed: _createNewSession,
        icon: const Icon(Icons.add_comment, color: Colors.black),
        label: const Text(
          'Nuevo Chat',
          style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold),
        ),
      ),
    );
  }

  Widget _buildEmptySessions() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: Colors.cyan.withOpacity(0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.forum, size: 64, color: Colors.cyanAccent),
            ),
            const SizedBox(height: 24),
            const Text(
              'No tienes conversaciones guardadas',
              style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            const Text(
              'Inicia una sesión de chat multimodal para comunicarte con J.A.R.V.I.S. por texto y archivos.',
              style: TextStyle(color: Colors.white54, fontSize: 14),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.cyan,
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
              onPressed: _createNewSession,
              icon: const Icon(Icons.add, color: Colors.black),
              label: const Text(
                'Crear mi primer Chat',
                style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSessionCard(Map<String, dynamic> session) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.white10),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
        leading: const CircleAvatar(
          backgroundColor: Color(0xFF0F172A),
          child: Icon(Icons.chat, color: Colors.cyanAccent),
        ),
        title: Text(
          session['titulo'] ?? 'Conversación',
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16),
        ),
        subtitle: Text(
          'Actualizado: ${session['updated_at']?.toString().substring(0, 10) ?? ''}',
          style: const TextStyle(color: Colors.white38, fontSize: 12),
        ),
        trailing: const Icon(Icons.chevron_right, color: Colors.white54),
        onTap: () async {
          await Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => ChatScreen(
                sessionId: session['id_session'],
                title: session['titulo'] ?? 'Conversación',
              ),
            ),
          );
          _fetchSessions();
        },
      ),
    );
  }
}
