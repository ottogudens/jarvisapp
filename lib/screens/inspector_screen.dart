/// J.A.R.V.I.S. — Pantalla PTT del Inspector Fiscal DGC
///
/// Pantalla operativa de Push-to-Talk para el perfil Inspector.
/// Utiliza el endpoint /v1/jarvis/inspector/procesar-completo
/// y muestra resultados estructurados de inspección.

import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'package:http/http.dart' as http;
import 'package:audioplayers/audioplayers.dart';
import 'package:shared_preferences/shared_preferences.dart';

const String kApiBaseUrl = 'https://jarvisapp-production-f259.up.railway.app';

class InspectorScreen extends StatefulWidget {
  const InspectorScreen({Key? key}) : super(key: key);

  @override
  State<InspectorScreen> createState() => _InspectorScreenState();
}

class _InspectorScreenState extends State<InspectorScreen> with SingleTickerProviderStateMixin {
  late final AudioRecorder _recorder;
  final AudioPlayer _player = AudioPlayer();
  bool _isListening = false;
  String _status = 'Mantenga presionado el micrófono para dictar su inspección.';
  String? _transcripcion;
  String? _tipoInfraccion;
  String? _hallazgo;
  String? _normativa;
  String? _gravedad;
  String? _accion;

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
    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) {
      setState(() {
        _status = '⚠️ Permiso de micrófono denegado. Habilítelo en Configuración.';
      });
      return;
    }

    String? audioPath;
    if (!kIsWeb) {
      final dir = await getTemporaryDirectory();
      audioPath = '\${dir.path}/audio_\${DateTime.now().millisecondsSinceEpoch}.m4a';
    }

    setState(() {
      _isListening = true;
      _status = 'Escuchando...';
    });
    _pulseController.repeat(reverse: true);

    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.aacLc, sampleRate: 16000),
      path: audioPath ?? '',
    );
  }

  Future<void> _stop() async {
    if (!await _recorder.isRecording()) return;

    try {
      final path = await _recorder.stop();

      setState(() {
        _isListening = false;
        _status = 'J.A.R.V.I.S. está analizando la inspección...';
      });
      _pulseController.stop();
      _pulseController.value = 0.0;

      if (path != null) {
        await _send(path);
      }
    } catch (e) {
      setState(() {
        _isListening = false;
        _status = 'Error al detener grabación.';
      });
    }
  }

  // ------------------------------------------------------------------
  // Envío al backend
  // ------------------------------------------------------------------

  Future<void> _send(String path) async {
    try {
      final uri = Uri.parse('\$kApiBaseUrl/v1/jarvis/inspector/procesar-completo');
      var request = http.MultipartRequest('POST', uri);

      if (kIsWeb) {
        final blobResponse = await http.get(Uri.parse(path));
        request.files.add(
          http.MultipartFile.fromBytes('audio_file', blobResponse.bodyBytes, filename: 'audio.m4a'),
        );
      } else {
        request.files.add(
          await http.MultipartFile.fromPath('audio_file', path),
        );
      }

      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('jwt_token') ?? '';
      request.headers['Authorization'] = 'Bearer \$token';

      var streamedResponse = await request.send();

      if (streamedResponse.statusCode == 200) {
        var res = await http.Response.fromStream(streamedResponse);
        final body = jsonDecode(res.body) as Map<String, dynamic>;

        setState(() {
          _status = body['respuesta_texto'] as String? ?? 'Listo.';
          _transcripcion = body['transcripcion'] as String?;

          // Parsear el diagnóstico estructurado
          final diagnostico = body['diagnostico_ia'] as String?;
          if (diagnostico != null) {
            final lines = diagnostico.split('\n');
            for (final line in lines) {
              if (line.startsWith('Tipo: ')) _tipoInfraccion = line.substring(6);
              if (line.startsWith('Hallazgo: ')) _hallazgo = line.substring(10);
              if (line.startsWith('Normativa: ')) _normativa = line.substring(11);
              if (line.startsWith('Gravedad: ')) _gravedad = line.substring(10);
              if (line.startsWith('Acción: ')) _accion = line.substring(8);
            }
          }
        });

        // Reproducir audio
        final audioB64 = body['audio_base64'] as String?;
        if (audioB64 != null && audioB64.isNotEmpty) {
          final audioBytes = base64Decode(audioB64);
          await _player.play(BytesSource(audioBytes));
        }
      } else {
        setState(() {
          _status = 'Error del servidor (\${streamedResponse.statusCode}).';
        });
      }
    } catch (e) {
      setState(() {
        _status = 'Error de red. Verifique su conexión.';
      });
      debugPrint('Error en _send: \$e');
    }
  }

  // ------------------------------------------------------------------
  // Helpers UI
  // ------------------------------------------------------------------

  Color _gravedadColor(String? gravedad) {
    switch (gravedad) {
      case 'Gravísima':
        return Colors.redAccent;
      case 'Grave':
        return Colors.orangeAccent;
      case 'Leve':
        return Colors.greenAccent;
      default:
        return Colors.amber;
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
        title: const Text('Inspección Fiscal'),
        backgroundColor: const Color(0xFF1E293B),
        foregroundColor: Colors.amber,
      ),
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            children: [
              Icon(
                _isListening ? Icons.hearing : Icons.policy,
                size: 64,
                color: _isListening ? Colors.red : Colors.amber,
              ),
              const SizedBox(height: 24),
              Text(
                _status,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 16,
                  color: Colors.amber,
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 40),

              // Botón PTT
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
                            colors: [Colors.amber, Colors.deepOrange],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          boxShadow: [
                            if (_isListening)
                              BoxShadow(
                                color: Colors.amber.withOpacity(0.6),
                                blurRadius: 30,
                                spreadRadius: 10,
                              )
                            else
                              BoxShadow(
                                color: Colors.amber.withOpacity(0.3),
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

              // Transcripción
              if (_transcripcion != null) ...[
                const Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    'Usted dictó:',
                    style: TextStyle(color: Colors.white54, fontSize: 14),
                  ),
                ),
                const SizedBox(height: 4),
                Align(
                  alignment: Alignment.centerLeft,
                  child: Text(
                    '"\$_transcripcion"',
                    style: const TextStyle(color: Colors.white, fontSize: 16, fontStyle: FontStyle.italic),
                  ),
                ),
                const SizedBox(height: 24),
              ],

              // Panel de Resultados de Inspección
              if (_tipoInfraccion != null) ...[
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    color: Colors.amber.withOpacity(0.08),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: Colors.amber.withOpacity(0.3)),
                  ),
                  width: double.infinity,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(Icons.gavel, color: Colors.amber, size: 22),
                          SizedBox(width: 8),
                          Text(
                            'Resultado de Inspección',
                            style: TextStyle(color: Colors.amber, fontWeight: FontWeight.bold, fontSize: 16),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Gravedad badge
                      if (_gravedad != null) ...[
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: _gravedadColor(_gravedad).withOpacity(0.2),
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Text(
                            'Gravedad: \$_gravedad',
                            style: TextStyle(
                              color: _gravedadColor(_gravedad),
                              fontWeight: FontWeight.bold,
                              fontSize: 13,
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),
                      ],

                      _buildInfoRow(Icons.category, 'Tipo de Infracción', _tipoInfraccion!),
                      const SizedBox(height: 12),
                      if (_hallazgo != null)
                        _buildInfoRow(Icons.search, 'Hallazgo', _hallazgo!),
                      if (_hallazgo != null)
                        const SizedBox(height: 12),
                      if (_normativa != null)
                        _buildInfoRow(Icons.balance, 'Normativa Aplicable', _normativa!),
                      if (_normativa != null)
                        const SizedBox(height: 12),
                      if (_accion != null)
                        _buildInfoRow(Icons.recommend, 'Acción Recomendada', _accion!),
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

  Widget _buildInfoRow(IconData icon, String label, String value) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: Colors.white38, size: 18),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(color: Colors.white38, fontSize: 12)),
              const SizedBox(height: 2),
              Text(value, style: const TextStyle(color: Colors.white, fontSize: 14, height: 1.4)),
            ],
          ),
        ),
      ],
    );
  }
}
