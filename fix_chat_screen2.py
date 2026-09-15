with open('lib/screens/chat_screen.dart', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("          import 'dart:convert';", "")

with open('lib/screens/chat_screen.dart', 'w', encoding='utf-8') as f:
    f.write(content)
print("Removed block import dart:convert")
