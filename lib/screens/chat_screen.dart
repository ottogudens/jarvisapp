import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:file_picker/file_picker.dart';
import 'login_screen.dart'; // Contiene kApiBaseUrl

class ChatScreen extends StatefulWidget {
  final String sessionId;
  final String title;

  const ChatScreen({
    Key? key,
    required this.sessionId,
    required this.title,
  }) : super(key: key);

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  
  List<Map<String, dynamic>> _messages = [];
  bool _isLoading = true;
  bool _isSending = false;
  List<PlatformFile> _selectedFiles = [];

  @override
  void initState() {
    super.initState();
    _fetchMessages();
  }

  Future<void> _fetchMessages() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';

      final response = await http.get(
        Uri.parse('$kApiBaseUrl/v1/chat/sessions/${widget.sessionId}/messages'),
        headers: {
          'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        setState(() {
          _messages = data.cast<Map<String, dynamic>>();
          _isLoading = false;
        });
        _scrollToBottom();
      } else {
        setState(() => _isLoading = false);
      }
    } catch (e) {
      setState(() => _isLoading = false);
    }
  }

  Future<void> _pickFiles() async {
    final result = await FilePicker.platform.pickFiles(
      allowMultiple: true,
      withData: true,
    );
    if (result != null) {
      setState(() {
        _selectedFiles.addAll(result.files);
      });
    }
  }

  Future<void> _sendMessage() async {
    final text = _messageController.text.trim();
    if (text.isEmpty && _selectedFiles.isEmpty) return;

    final userText = text;
    _messageController.clear();

    setState(() {
      _isSending = true;
      _messages.add({
        'id_mensaje': DateTime.now().millisecondsSinceEpoch.toString(),
        'rol': 'user',
        'contenido': userText.isEmpty ? '(Archivo adjunto)' : userText,
        'file_urls': _selectedFiles.map((f) => f.name).toList(),
        'created_at': DateTime.now().toIso8601String(),
      });
    });
    _scrollToBottom();

    final filesToSend = List<PlatformFile>.from(_selectedFiles);
    setState(() => _selectedFiles.clear());

    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';

      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$kApiBaseUrl/v1/chat/sessions/${widget.sessionId}/send'),
      );
      request.headers['Authorization'] = 'Bearer $token';
      request.fields['mensaje'] = userText;

      for (var file in filesToSend) {
        if (file.bytes != null) {
          request.files.add(
            http.MultipartFile.fromBytes(
              'files',
              file.bytes!,
              filename: file.name,
            ),
          );
        }
      }

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final jarvisMsg = jsonDecode(response.body);
        setState(() {
          _messages.add(jarvisMsg);
        });
        _scrollToBottom();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error del servidor: ${response.statusCode}')),
        );
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error enviando mensaje: $e')),
      );
    } finally {
      setState(() => _isSending = false);
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E293B),
        elevation: 2,
        title: Row(
          children: [
            const CircleAvatar(
              backgroundColor: Colors.cyan,
              radius: 16,
              child: Icon(Icons.smart_toy, size: 18, color: Colors.black),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                widget.title,
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator(color: Colors.cyanAccent))
                : _messages.isEmpty
                    ? _buildEmptyState()
                    : ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.all(16),
                        itemCount: _messages.length,
                        itemBuilder: (context, index) {
                          final msg = _messages[index];
                          final isUser = msg['rol'] == 'user';
                          return _buildMessageBubble(msg, isUser);
                        },
                      ),
          ),
          if (_isSending)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: const [
                  SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.cyanAccent)),
                  SizedBox(width: 10),
                  Text('J.A.R.V.I.S. está procesando...', style: TextStyle(color: Colors.cyanAccent, fontSize: 12, fontStyle: FontStyle.italic)),
                ],
              ),
            ),
          if (_selectedFiles.isNotEmpty) _buildSelectedFilesPreview(),
          _buildInputBar(),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: const [
          Icon(Icons.chat_bubble_outline, size: 64, color: Colors.white24),
          SizedBox(height: 16),
          Text(
            'Inicia la conversación con J.A.R.V.I.S.',
            style: TextStyle(color: Colors.white54, fontSize: 16),
          ),
          SizedBox(height: 8),
          Text(
            'Puedes enviar texto, imágenes y documentos.',
            style: TextStyle(color: Colors.white30, fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(Map<String, dynamic> msg, bool isUser) {
    final fileUrls = (msg['file_urls'] as List?)?.cast<String>() ?? [];
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 6),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
        decoration: BoxDecoration(
          color: isUser ? const Color(0xFF0284C7) : const Color(0xFF1E293B),
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(16),
            topRight: const Radius.circular(16),
            bottomLeft: Radius.circular(isUser ? 16 : 4),
            bottomRight: Radius.circular(isUser ? 4 : 16),
          ),
          border: Border.all(
            color: isUser ? Colors.cyan.withOpacity(0.5) : const Color(0xFF334155),
            width: 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (!isUser)
              const Padding(
                padding: EdgeInsets.only(bottom: 4),
                child: Text('J.A.R.V.I.S.', style: TextStyle(color: Colors.cyanAccent, fontWeight: FontWeight.bold, fontSize: 11)),
              ),
            Text(
              msg['contenido'] ?? '',
              style: const TextStyle(color: Colors.white, fontSize: 14, height: 1.4),
            ),
            if (fileUrls.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Wrap(
                  spacing: 6,
                  children: fileUrls.map((url) {
                    return Container(
                      padding: const EdgeInsets.all(6),
                      decoration: BoxDecoration(
                        color: Colors.black26,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.attach_file, size: 14, color: Colors.cyanAccent),
                          const SizedBox(width: 4),
                          Text(
                            url.length > 20 ? '${url.substring(0, 15)}...' : url,
                            style: const TextStyle(color: Colors.white70, fontSize: 10),
                          ),
                        ],
                      ),
                    );
                  }).toList(),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildSelectedFilesPreview() {
    return Container(
      color: const Color(0xFF1E293B),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      height: 44,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: _selectedFiles.length,
        itemBuilder: (context, index) {
          final file = _selectedFiles[index];
          return Container(
            margin: const EdgeInsets.only(right: 8),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.cyan.withOpacity(0.2),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.cyanAccent),
            ),
            child: Row(
              children: [
                const Icon(Icons.insert_drive_file, size: 16, color: Colors.cyanAccent),
                const SizedBox(width: 6),
                Text(file.name, style: const TextStyle(color: Colors.white, fontSize: 12)),
                const SizedBox(width: 6),
                GestureDetector(
                  onTap: () {
                    setState(() => _selectedFiles.removeAt(index));
                  },
                  child: const Icon(Icons.close, size: 16, color: Colors.white54),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildInputBar() {
    return Container(
      padding: const EdgeInsets.all(12),
      color: const Color(0xFF1E293B),
      child: SafeArea(
        child: Row(
          children: [
            IconButton(
              icon: const Icon(Icons.attach_file, color: Colors.cyanAccent),
              onPressed: _pickFiles,
            ),
            Expanded(
              child: TextField(
                controller: _messageController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: 'Escribe un mensaje a JARVIS...',
                  hintStyle: const TextStyle(color: Colors.white38),
                  filled: true,
                  fillColor: const Color(0xFF0F172A),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                ),
                onSubmitted: (_) => _sendMessage(),
              ),
            ),
            const SizedBox(width: 8),
            CircleAvatar(
              backgroundColor: Colors.cyan,
              radius: 22,
              child: IconButton(
                icon: const Icon(Icons.send, color: Colors.black, size: 20),
                onPressed: _sendMessage,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
