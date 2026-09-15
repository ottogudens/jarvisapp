import json
import base64

with open('lib/screens/chat_screen.dart', 'r', encoding='utf-8') as f:
    content = f.read()

replacement = """  Future<void> _loadPreferences() async {
    final prefs = await SharedPreferences.getInstance();
    
    // Extraer userId del token
    String userId = '';
    final token = prefs.getString('jwt_token');
    if (token != null) {
      try {
        final parts = token.split('.');
        if (parts.length == 3) {
          import 'dart:convert';
          final payload = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))));
          userId = payload['sub']?.toString() ?? '';
        }
      } catch (_) {}
    }

    if (mounted) {
      setState(() {
        _voiceId = prefs.getString('jarvis_voice_id_$userId') ?? '';
        _sarcasmLevel = prefs.getString('jarvis_sarcasm_level_$userId') ?? '';
        _customPrompt = prefs.getString('jarvis_custom_prompt_$userId') ?? '';
        _handsFreeMode = prefs.getBool('jarvis_hands_free_$userId') ?? false;
      });
    }
  }"""

import re
content = re.sub(r'  Future<void> _loadPreferences\(\) async \{.*?(?=  @override\n  Widget build\(BuildContext context\))', replacement + '\n\n', content, flags=re.DOTALL)

# There is also one more occurrence around line 608: prefs.setBool('jarvis_hands_free', _handsFreeMode);
content = content.replace("prefs.setBool('jarvis_hands_free', _handsFreeMode);", "// prefs.setBool('jarvis_hands_free', _handsFreeMode); // Obsoleta, se maneja desde settings")

with open('lib/screens/chat_screen.dart', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated chat_screen.dart with user prefixed keys")
