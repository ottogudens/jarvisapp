with open('lib/screens/chat_screen.dart', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix auto playback: only speak automatically if handsFreeMode is true
old_speak = """          _scrollToBottom();
          _speakMessage(jarvisMsg);"""
new_speak = """          _scrollToBottom();
          if (_handsFreeMode) {
            _speakMessage(jarvisMsg);
          }"""
content = content.replace(old_speak, new_speak)

# Fix silence timer: only apply if handsFreeMode is true
old_timer = """    void _resetSilenceTimer() {
      _silenceTimer?.cancel();
      // Cuando deje de hablar por más de 3 segundos, se envía automáticamente
      _silenceTimer = Timer(const Duration(seconds: 3), () {
        if (_isRecording && _hasSpokenInCurrentRecording) {
          _stopRecording();
        }
      });
    }"""
new_timer = """    void _resetSilenceTimer() {
      _silenceTimer?.cancel();
      if (!_handsFreeMode) return;
      // Cuando deje de hablar por más de 3 segundos, se envía automáticamente
      _silenceTimer = Timer(const Duration(seconds: 3), () {
        if (_isRecording && _hasSpokenInCurrentRecording) {
          _stopRecording();
        }
      });
    }"""
content = content.replace(old_timer, new_timer)

with open('lib/screens/chat_screen.dart', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated chat_screen.dart hands_free constraints")
