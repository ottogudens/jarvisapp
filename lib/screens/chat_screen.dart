import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:html' as html;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:file_picker/file_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
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

class _ChatScreenState extends State<ChatScreen> with SingleTickerProviderStateMixin {
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final AudioPlayer _player = AudioPlayer();
  late final AudioRecorder _recorder;
  
  List<Map<String, dynamic>> _messages = [];
  bool _isLoading = true;
  bool _isSending = false;
  bool _isRecording = false;
  bool _isPlayingAudio = false;
  List<PlatformFile> _selectedFiles = [];
  List<String> _focusedDocumentIds = [];
  List<Map<String,dynamic>> _availableDocsForFocus = [];
  
  // Ajustes de Agente
  String _voiceId = '';
  String _sarcasmLevel = '';
  String _customPrompt = '';
  bool _handsFreeMode = false;

  // Detección de silencio (VAD) para manos libres
  Timer? _silenceTimer;
  StreamSubscription<Amplitude>? _amplitudeSub;
  bool _hasSpokenInCurrentRecording = false;

  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _recorder = AudioRecorder();
    
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 1),
    );
    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.25).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );

    // Listener de fin de audio de J.A.R.V.I.S.
    _player.onPlayerComplete.listen((event) {
      if (mounted) {
        setState(() => _isPlayingAudio = false);
        if (_handsFreeMode) {
          // Iniciar grabación automáticamente para la siguiente consulta
          _startRecording();
        }
      }
    });

    _player.onPlayerStateChanged.listen((state) {
      if (mounted) {
        setState(() {
          _isPlayingAudio = (state == PlayerState.playing);
        });
      }
    });

    _initHeadsetListener();

    _loadSettings().then((_) {
      _fetchMessages();
    });
  }

  void _initHeadsetListener() {
    // 1. Escuchar eventos de teclas multimedia / auriculares (Bluetooth)
    HardwareKeyboard.instance.addHandler(_handleKeyEvent);

    // 2. En Web: registrar soporte para MediaSession API (botones de auriculares Bluetooth)
    if (kIsWeb) {
      try {
        final mediaSession = html.window.navigator.mediaSession;
        if (mediaSession != null) {
          mediaSession.setActionHandler('play', () {
            _onHeadsetButtonPressed();
          });
          mediaSession.setActionHandler('pause', () {
            _onHeadsetButtonPressed();
          });
          mediaSession.setActionHandler('stop', () {
            _stopSpeaking();
          });
        }
      } catch (e) {
        debugPrint('MediaSession no disponible: $e');
      }
    }
  }

  bool _handleKeyEvent(KeyEvent event) {
    if (event is KeyDownEvent) {
      final key = event.logicalKey;
      if (key == LogicalKeyboardKey.mediaPlayPause ||
          key == LogicalKeyboardKey.mediaPlay ||
          key == LogicalKeyboardKey.mediaPause ||
          key == LogicalKeyboardKey.mediaTrackNext ||
          key == LogicalKeyboardKey.headsetHook) {
        _onHeadsetButtonPressed();
        return true;
      }
    }
    return false;
  }

  void _onHeadsetButtonPressed() {
    if (_isPlayingAudio) {
      // Si JARVIS está hablando, cancelar lectura y empezar a escuchar
      _stopSpeaking();
      _startRecording();
    } else if (_isRecording) {
      // Si ya está grabando, un segundo clic envía inmediatamente
      _stopRecording();
    } else {
      // Si está en reposo, iniciar grabación
      _startRecording();
    }
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    String userId = '';
    final token = prefs.getString('jwt_token');
    if (token != null) {
      try {
        final parts = token.split('.');
        if (parts.length == 3) {
          final payload = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))));
          userId = payload['id_usuario']?.toString() ?? '';
        }
      } catch (_) {}
    }

    setState(() {
      _voiceId = prefs.getString('jarvis_voice_id_$userId') ?? '';
      _sarcasmLevel = prefs.getString('jarvis_sarcasm_level_$userId') ?? '';
      _customPrompt = prefs.getString('jarvis_custom_prompt_$userId') ?? '';
      _handsFreeMode = prefs.getBool('jarvis_hands_free_$userId') ?? false;
    });
  }

  @override
  void dispose() {
    HardwareKeyboard.instance.removeHandler(_handleKeyEvent);
    _silenceTimer?.cancel();
    _amplitudeSub?.cancel();
    _stopSpeaking();
    _player.dispose();
    _recorder.dispose();
    _pulseController.dispose();
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _fetchMessages() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';

      final response = await http.get(
        Uri.parse('$kApiBaseUrl/v1/chat/sessions/${widget.sessionId}/messages'),
        headers: {'Authorization': 'Bearer $token'},
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        if (mounted) {
          setState(() {
            _messages = data.cast<Map<String, dynamic>>();
            _isLoading = false;
          });
          _scrollToBottom();
        }
      } else {
        if (mounted) setState(() => _isLoading = false);
      }
    } catch (e) {
      if (mounted) setState(() => _isLoading = false);
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

  Future<void> _startRecording() async {
    if (_isRecording) return;
    
    // Si estaba hablando, detenerlo
    _stopSpeaking();

    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Permiso de micrófono denegado.')),
        );
      }
      return;
    }

    String path = '';
    if (!kIsWeb) {
      final dir = await getTemporaryDirectory();
      path = '${dir.path}/audio_${DateTime.now().millisecondsSinceEpoch}.m4a';
    }

    _hasSpokenInCurrentRecording = false;
    _silenceTimer?.cancel();

    setState(() => _isRecording = true);
    _pulseController.repeat(reverse: true);

    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.aacLc, sampleRate: 16000),
      path: path,
    );

    // Monitoreo de amplitud para detectar silencio por más de 3 segundos
    try {
      _amplitudeSub?.cancel();
      _amplitudeSub = _recorder
          .onAmplitudeChanged(const Duration(milliseconds: 200))
          .listen((amp) {
        // En general, valores superiores a -38 dB indican habla/voz
        if (amp.current > -45.0) {
          _hasSpokenInCurrentRecording = true;
          _resetSilenceTimer();
        }
      });
    } catch (e) {
      debugPrint('Amplitud no soportada en este entorno: $e');
    }
  }

  void _resetSilenceTimer() {
    _silenceTimer?.cancel();
    // Cuando deje de hablar por más de 3 segundos, se envía automáticamente
    _silenceTimer = Timer(const Duration(seconds: 3), () {
      if (_isRecording && _hasSpokenInCurrentRecording) {
        _stopRecording();
      }
    });
  }

  Future<void> _stopRecording() async {
    _silenceTimer?.cancel();
    _amplitudeSub?.cancel();

    if (!await _recorder.isRecording()) {
      if (mounted) {
        setState(() => _isRecording = false);
        _pulseController.stop();
        _pulseController.value = 0.0;
      }
      return;
    }

    final path = await _recorder.stop();
    if (mounted) {
      setState(() => _isRecording = false);
      _pulseController.stop();
      _pulseController.value = 0.0;
    }

    if (path != null) {
      await _sendMessage(audioPath: path);
    }
  }

  void _stopSpeaking() {
    try {
      _player.stop();
    } catch (_) {}

    if (kIsWeb) {
      try {
        html.window.speechSynthesis?.cancel();
      } catch (_) {}
    }

    if (mounted) {
      setState(() => _isPlayingAudio = false);
    }
  }

  void _showFocusBottomSheet() {
    // Collect all documents uploaded in this session
    final docs = _messages.where((m) => m['rol'] == 'user' && m['file_urls'] != null && (m['file_urls'] as List).isNotEmpty).toList();
    if (docs.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('No hay documentos previos en esta sesión.')));
      return;
    }

    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF1E293B),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            return Container(
              padding: const EdgeInsets.all(16),
              height: 400,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Enfocar Documentos', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  const Text('Selecciona los archivos sobre los que JARVIS debe basar su respuesta.', style: TextStyle(color: Colors.white70, fontSize: 13)),
                  const SizedBox(height: 16),
                  Expanded(
                    child: ListView.builder(
                      itemCount: docs.length,
                      itemBuilder: (context, index) {
                        final doc = docs[index];
                        final id = doc['id_mensaje'] as String;
                        final isSelected = _focusedDocumentIds.contains(id);
                        final urls = doc['file_urls'] as List;
                        final isPdf = urls.any((u) => u.toString().contains('pdf'));
                        
                        return CheckboxListTile(
                          activeColor: Colors.cyanAccent,
                          checkColor: Colors.black,
                          title: Text('Doc #${id.substring(id.length - 4)}', style: const TextStyle(color: Colors.white)),
                          subtitle: Text(doc['contenido'] ?? 'Archivo', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Colors.white54)),
                          secondary: Icon(isPdf ? Icons.picture_as_pdf : Icons.insert_drive_file, color: Colors.cyanAccent),
                          value: isSelected,
                          onChanged: (val) {
                            setSheetState(() {
                              if (val == true) {
                                _focusedDocumentIds.add(id);
                              } else {
                                _focusedDocumentIds.remove(id);
                              }
                            });
                            setState(() {}); // Update main UI
                          },
                        );
                      },
                    ),
                  ),
                  Align(
                    alignment: Alignment.centerRight,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(backgroundColor: Colors.cyan),
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Confirmar', style: TextStyle(color: Colors.white)),
                    ),
                  )
                ],
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _sendMessage({String? audioPath}) async {
    final text = _messageController.text.trim();
    if (text.isEmpty && _selectedFiles.isEmpty && audioPath == null) return;

    final userText = text;
    _messageController.clear();

    setState(() {
      _isSending = true;
      _messages.add({
        'id_mensaje': DateTime.now().millisecondsSinceEpoch.toString(),
        'rol': 'user',
        'contenido': audioPath != null ? '(Audio de voz)' : (userText.isEmpty ? '(Archivo adjunto)' : userText),
        'file_urls': _selectedFiles.map((f) => f.name).toList(),
        'created_at': DateTime.now().toIso8601String(),
      });
    });
    _scrollToBottom();

    final filesToSend = List<PlatformFile>.from(_selectedFiles);
    setState(() { _selectedFiles.clear(); _focusedDocumentIds.clear(); });

    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';

      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$kApiBaseUrl/v1/chat/sessions/${widget.sessionId}/send'),
      );
      request.headers['Authorization'] = 'Bearer $token';
      
      if (_voiceId.isNotEmpty) {
        request.headers['x-voice-id'] = _voiceId;
      }
      if (_sarcasmLevel.isNotEmpty) {
        request.headers['x-sarcasm-level'] = _sarcasmLevel;
      }
      if (_customPrompt.isNotEmpty) {
        // En navegadores web, los headers HTTP no admiten caracteres no-ASCII ni saltos de línea (\n).
        // Se codifica en Base64 seguro para evitar ClientException: Failed to execute 'fetch' on 'Window': Invalid value
        request.headers['x-custom-prompt'] = base64Encode(utf8.encode(_customPrompt));
      }
      
      request.fields['mensaje'] = userText;
      if (_focusedDocumentIds.isNotEmpty) {
        request.fields['focused_document_ids'] = jsonEncode(_focusedDocumentIds);
      }
      if (_customPrompt.isNotEmpty) {
        request.fields['custom_prompt'] = _customPrompt;
      }

      // Adjuntar archivos de texto/imagen
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

      // Adjuntar audio si lo hay
      if (audioPath != null) {
        if (kIsWeb) {
          final blobResponse = await http.get(Uri.parse(audioPath));
          request.files.add(
            http.MultipartFile.fromBytes('files', blobResponse.bodyBytes, filename: 'audio.m4a'),
          );
        } else {
          request.files.add(
            await http.MultipartFile.fromPath('files', audioPath),
          );
        }
      }

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final jarvisMsg = jsonDecode(response.body) as Map<String, dynamic>;
        final transcripcion = jarvisMsg['transcripcion_usuario'] as String? ?? '';
        if (mounted) {
          setState(() {
            // Si fue un mensaje de audio, actualizar el contenido del burbuja del usuario
            // con la transcripción real devuelta por el backend
            if (audioPath != null && transcripcion.isNotEmpty) {
              final lastUserIdx = _messages.lastIndexWhere((m) => m['rol'] == 'user');
              if (lastUserIdx != -1) {
                _messages[lastUserIdx] = {
                  ..._messages[lastUserIdx],
                  'contenido': transcripcion,
                  'id_mensaje': jarvisMsg['id_mensaje_usuario'] ?? _messages[lastUserIdx]['id_mensaje'],
                };
              }
            }
            _messages.add(jarvisMsg);
          });
          _scrollToBottom();
          if (_handsFreeMode) {
            _speakMessage(jarvisMsg);
          }
        }
      } else {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error del servidor: ${response.statusCode}')),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error al enviar mensaje: $e')),
        );
      }
    } finally {
      if (mounted) setState(() => _isSending = false);
    }
  }

  Future<void> _speakMessage(Map<String, dynamic> msg) async {
    _stopSpeaking();

    final audioB64 = msg['audio_base64'] as String?;
    if (audioB64 != null && audioB64.isNotEmpty) {
      try {
        final audioBytes = base64Decode(audioB64);
        setState(() => _isPlayingAudio = true);
        await _player.play(BytesSource(audioBytes));
        return;
      } catch (e) {
        debugPrint('Error reproduciendo audio base64: $e');
      }
    }
    
    // Fallback a Síntesis de voz del Navegador (Web Speech API)
    _speakTextWeb(msg['contenido'] ?? '');
  }

  void _speakTextWeb(String text) {
    if (kIsWeb) {
      try {
        final utterance = html.SpeechSynthesisUtterance(text);
        // Intentar español latinoamericano
        utterance.lang = 'es-419';
        utterance.rate = 1.05;
        
        utterance.onStart.listen((_) {
          if (mounted) setState(() => _isPlayingAudio = true);
        });

        utterance.onEnd.listen((_) {
          if (mounted) {
            setState(() => _isPlayingAudio = false);
            if (_handsFreeMode) {
              _startRecording();
            }
          }
        });

        html.window.speechSynthesis?.cancel();
        html.window.speechSynthesis?.speak(utterance);
      } catch (e) {
        debugPrint('Error Web Speech: $e');
      }
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
        actions: [
          IconButton(
            icon: Icon(
              _handsFreeMode ? Icons.headset_mic : Icons.headset_off,
              color: _handsFreeMode ? Colors.cyanAccent : Colors.white38,
            ),
            tooltip: _handsFreeMode ? 'Manos Libres Activo' : 'Manos Libres Inactivo',
            onPressed: () async {
              setState(() => _handsFreeMode = !_handsFreeMode);
              final prefs = await SharedPreferences.getInstance();
              // prefs.setBool('jarvis_hands_free', _handsFreeMode); // Obsoleta, se maneja desde settings
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      _handsFreeMode
                          ? 'Modo Manos Libres Activo: pulsa tu audífono o habla para interactuar'
                          : 'Modo Manos Libres Desactivado',
                    ),
                  ),
                );
              }
            },
          )
        ],
      ),
      body: Stack(
        children: [
          Column(
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

          // Botón flotante prominente para Cancelar / Detener Lectura de J.A.R.V.I.S.
          if (_isPlayingAudio)
            Positioned(
              bottom: 80,
              left: 0,
              right: 0,
              child: Center(
                child: FloatingActionButton.extended(
                  backgroundColor: Colors.redAccent,
                  elevation: 6,
                  icon: const Icon(Icons.stop_circle, color: Colors.white, size: 24),
                  label: const Text(
                    'CANCELAR LECTURA',
                    style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, letterSpacing: 1),
                  ),
                  onPressed: _stopSpeaking,
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.chat_bubble_outline, size: 64, color: Colors.white24),
          const SizedBox(height: 16),
          const Text(
            'Inicia la conversación con J.A.R.V.I.S.',
            style: TextStyle(color: Colors.white54, fontSize: 16),
          ),
          const SizedBox(height: 8),
          const Text(
            'Puedes hablar por manos libres, escribir o adjuntar documentos.',
            style: TextStyle(color: Colors.white30, fontSize: 12),
          ),
          const SizedBox(height: 24),
          if (_handsFreeMode)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                color: Colors.cyan.withOpacity(0.1),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: Colors.cyanAccent.withOpacity(0.4)),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.headset_mic, color: Colors.cyanAccent, size: 18),
                  SizedBox(width: 8),
                  Text('Presiona el botón de tu auricular para hablar', style: TextStyle(color: Colors.cyanAccent, fontSize: 13, fontWeight: FontWeight.w500)),
                ],
              ),
            )
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
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text('J.A.R.V.I.S.', style: TextStyle(color: Colors.cyanAccent, fontWeight: FontWeight.bold, fontSize: 11)),
                    IconButton(
                      constraints: const BoxConstraints(),
                      padding: EdgeInsets.zero,
                      icon: Icon(
                        _isPlayingAudio ? Icons.volume_up : Icons.volume_down,
                        color: _isPlayingAudio ? Colors.cyanAccent : Colors.white60,
                        size: 18,
                      ),
                      tooltip: 'Escuchar respuesta',
                      onPressed: () => _speakMessage(msg),
                    ),
                  ],
                ),
              ),
            if (msg['contenido'] == '(Audio de voz)')
               const Row(
                 children: [
                   Icon(Icons.mic, color: Colors.cyanAccent, size: 16),
                   SizedBox(width: 6),
                   Text('Procesando transcripción...', style: TextStyle(color: Colors.white70, fontStyle: FontStyle.italic)),
                 ],
               )
            else
              SelectableText(
                msg['contenido'] ?? '',
                style: const TextStyle(color: Colors.white, fontSize: 14, height: 1.4),
              ),
            if (fileUrls.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: fileUrls.map((url) {
                    // Determinar tipo de archivo desde data URI
                    IconData fileIcon = Icons.attach_file;
                    String label = 'Archivo';
                    if (url.startsWith('data:image/')) {
                      fileIcon = Icons.image;
                      label = 'Imagen';
                    } else if (url.startsWith('data:audio/')) {
                      fileIcon = Icons.mic;
                      label = 'Audio';
                    } else if (url.startsWith('data:application/pdf')) {
                      fileIcon = Icons.picture_as_pdf;
                      label = 'PDF';
                    } else if (url.startsWith('data:text/')) {
                      fileIcon = Icons.description;
                      label = 'Documento';
                    }
                    return Tooltip(
                      message: label == 'Audio' ? 'Audio transcrito por J.A.R.V.I.S.' : 'Documento conocido por J.A.R.V.I.S.',
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.black26,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: Colors.cyanAccent.withOpacity(0.4)),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(fileIcon, size: 14, color: Colors.cyanAccent),
                            const SizedBox(width: 4),
                            Text(label, style: const TextStyle(color: Colors.white70, fontSize: 10)),
                          ],
                        ),
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
              icon: const Icon(Icons.center_focus_strong, color: Colors.orangeAccent),
              onPressed: _showFocusBottomSheet,
              tooltip: 'Enfocar documentos',
            ),
            IconButton(
              icon: const Icon(Icons.attach_file, color: Colors.cyanAccent),
              onPressed: _pickFiles,
            ),
            Expanded(
              child: TextField(
                controller: _messageController,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: _isRecording ? 'Escuchando... (pausa de 3s envía)' : 'Escribe a J.A.R.V.I.S...',
                  hintStyle: TextStyle(
                    color: _isRecording ? Colors.redAccent : Colors.white38,
                    fontWeight: _isRecording ? FontWeight.bold : FontWeight.normal,
                  ),
                  filled: true,
                  fillColor: const Color(0xFF0F172A),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                ),
                onSubmitted: (_) => _sendMessage(),
                enabled: !_isRecording,
              ),
            ),
            const SizedBox(width: 8),
            
            // Botón de Micrófono / Auricular (Click 1: Graba, Click 2 o 3s de silencio: Envía)
            GestureDetector(
              onTap: () {
                if (_isRecording) {
                  _stopRecording();
                } else {
                  _startRecording();
                }
              },
              child: AnimatedBuilder(
                animation: _pulseAnimation,
                builder: (context, child) {
                  return Transform.scale(
                    scale: _isRecording ? _pulseAnimation.value : 1.0,
                    child: CircleAvatar(
                      backgroundColor: _isRecording ? Colors.redAccent : const Color(0xFF334155),
                      radius: 22,
                      child: Icon(
                        _isRecording ? Icons.mic : Icons.mic_none,
                        color: Colors.white,
                        size: 22,
                      ),
                    ),
                  );
                },
              ),
            ),
            
            const SizedBox(width: 8),
            CircleAvatar(
              backgroundColor: Colors.cyan,
              radius: 22,
              child: IconButton(
                icon: const Icon(Icons.send, color: Colors.black, size: 20),
                onPressed: () => _sendMessage(),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
