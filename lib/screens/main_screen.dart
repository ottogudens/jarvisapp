/// J.A.R.V.I.S. — Pantalla operativa con Push-to-Talk y streaming de audio
///
/// Correcciones aplicadas:
/// - Fix #19: Código Dart correctamente formateado (era una sola línea)
/// - Fix #20: URL del servidor configurable via constante
/// - Fix #21: id_orden dinámico (recibido como parámetro del widget)
/// - Fix #22: Manejo de permisos de micrófono denegados con feedback al usuario

import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart' show kIsWeb;

import 'package:flutter/material.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'package:http/http.dart' as http;
import 'package:audioplayers/audioplayers.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'stats_screen.dart';

/// URL base del servidor J.A.R.V.I.S.
/// Fix #20: Reemplazar con el dominio real de Railway en producción.
const String kApiBaseUrl = 'https://jarvisapp-production-f259.up.railway.app';

class JarvisMainScreen extends StatefulWidget {
  /// Fix #21: id_orden dinámico, recibido como parámetro.
  final String idOrden;

  const JarvisMainScreen({Key? key, this.idOrden = 'OT-1002'}) : super(key: key);

  @override
  State<JarvisMainScreen> createState() => _JarvisMainScreenState();
}

class _JarvisMainScreenState extends State<JarvisMainScreen> with SingleTickerProviderStateMixin {
  late final AudioRecorder _recorder;
  final AudioPlayer _player = AudioPlayer();
  bool _isListening = false;
  String _status = 'Mantenga presionado el micrófono para hablar con J.A.R.V.I.S.';
  String? _audioPath;
  String? _transcripcion;
  String? _diagnostico;

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
    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.2).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
  }

  @override
  void dispose() {
    _recorder.dispose();
    _player.dispose();
    _pulseController.dispose();
    super.dispose();
  }

  // ------------------------------------------------------------------
  // Grabación de audio
  // ------------------------------------------------------------------

  Future<void> _start() async {
    // Fix #22: manejar permisos denegados
    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      setState(() {
        _status = '⚠️ Permiso de micrófono denegado. Habilítelo en Configuración.';
      });
      return;
    }

    final dir = await getTemporaryDirectory();
    _audioPath = '${dir.path}/audio_${DateTime.now().millisecondsSinceEpoch}.m4a';

    setState(() {
      _isListening = true;
      _status = 'Escuchando...';
    });
    _pulseController.repeat(reverse: true);

    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.aacLc, sampleRate: 16000),
      path: _audioPath!,
    );
  }

  Future<void> _stop() async {
    await _recorder.stop();
    setState(() {
      _isListening = false;
      _status = 'J.A.R.V.I.S. está pensando...';
    });
    _pulseController.stop();
    _pulseController.value = 0.0;
    if (_audioPath != null) {
      await _send(_audioPath!);
    }
  }

  // ------------------------------------------------------------------
  // Envío al backend y reproducción de respuesta
  // ------------------------------------------------------------------

  Future<void> _send(String path) async {
    try {
      // Fix #20: URL configurable
      final uri = Uri.parse('$kApiBaseUrl/v1/jarvis/mecanico/procesar-completo');
      var request = http.MultipartRequest('POST', uri);

      if (kIsWeb) {
        // Fix para Web: Leer los bytes desde la URL blob generada por el recorder
        final blobResponse = await http.get(Uri.parse(path));
        request.files.add(
          http.MultipartFile.fromBytes('audio_file', blobResponse.bodyBytes, filename: 'audio.m4a'),
        );
      } else {
        request.files.add(
          await http.MultipartFile.fromPath('audio_file', path),
        );
      }
      // Fix #21: id_orden dinámico
      request.fields['id_orden'] = widget.idOrden;

      // Leer token y agregarlo
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';
      request.headers['Authorization'] = 'Bearer $token';

      var streamedResponse = await request.send();

      if (streamedResponse.statusCode == 200) {
        var res = await http.Response.fromStream(streamedResponse);

        // Fix #13: parsear respuesta JSON (ya no viene en headers)
        final body = jsonDecode(res.body) as Map<String, dynamic>;

        setState(() {
          _status = body['respuesta_texto'] as String? ?? 'Listo.';
          _transcripcion = body['transcripcion'] as String?;
          _diagnostico = body['diagnostico_ia'] as String?;
        });

        // Decodificar audio base64 y reproducir
        final audioB64 = body['audio_base64'] as String?;
        if (audioB64 != null && audioB64.isNotEmpty) {
          final audioBytes = base64Decode(audioB64);
          await _player.play(BytesSource(audioBytes));
        }
      } else {
        setState(() {
          _status = 'Error del servidor (${streamedResponse.statusCode}).';
        });
      }
    } catch (e) {
      setState(() {
        _status = 'Error de red. Verifique su conexión.';
      });
      debugPrint('Error en _send: $e');
    }
  }

  // ------------------------------------------------------------------
  // UI
  // ------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        title: const Text('J.A.R.V.I.S. — Automotriz ProService'),
        backgroundColor: const Color(0xFF1E293B),
        actions: [
          IconButton(
            icon: const Icon(Icons.analytics),
            tooltip: 'Dashboard Comercial',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const JarvisStatsScreen()),
            ),
          ),
        ],
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                _isListening ? Icons.hearing : Icons.smart_toy,
                size: 64,
                color: _isListening ? Colors.red : Colors.cyan,
              ),
              const SizedBox(height: 24),
              Text(
                _status,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 16,
                  color: Colors.cyan,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 60),
              GestureDetector(
                onLongPress: _start,
                onLongPressUp: _stop,
                child: AnimatedBuilder(
                  animation: _pulseAnimation,
                  builder: (context, child) {
                    return Transform.scale(
                      scale: _isListening ? _pulseAnimation.value : 1.0,
                      child: Container(
                        width: 120,
                        height: 120,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: const LinearGradient(
                            colors: [Colors.cyan, Colors.blueAccent],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          boxShadow: [
                            if (_isListening)
                              BoxShadow(
                                color: Colors.cyanAccent.withOpacity(0.6),
                                blurRadius: 30,
                                spreadRadius: 10,
                              )
                            else
                              BoxShadow(
                                color: Colors.cyan.withOpacity(0.3),
                                blurRadius: 15,
                                spreadRadius: 2,
                              ),
                          ],
                        ),
                        child: Icon(
                          _isListening ? Icons.mic : Icons.mic_none,
                          size: 64,
                          color: Colors.white,
                        ),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(height: 40),
              if (_transcripcion != null) ...[
                const Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    'Tú dijiste:',
                    style: TextStyle(color: Colors.white54, fontSize: 14),
                  ),
                ),
                const SizedBox(height: 4),
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    '"$_transcripcion"',
                    style: const TextStyle(color: Colors.white, fontSize: 16, fontStyle: FontStyle.italic),
                  ),
                ),
                const SizedBox(height: 16),
              ],
              if (_diagnostico != null) ...[
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.cyan.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.cyan.withOpacity(0.3)),
                  ),
                  width: double.infinity,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(Icons.build_circle, color: Colors.cyan, size: 20),
                          SizedBox(width: 8),
                          Text('Diagnóstico IA', style: TextStyle(color: Colors.cyan, fontWeight: FontWeight.bold)),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        _diagnostico!,
                        style: const TextStyle(color: Colors.white, fontSize: 14, height: 1.5),
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 30),
            ],
          ),
        ),
      ),
    );
  }
}
