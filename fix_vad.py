with open('lib/screens/chat_screen.dart', 'r', encoding='utf-8') as f:
    content = f.read()

# Change VAD threshold to -45.0 dB to be safer for headset mics
content = content.replace("amp.current > -38.0", "amp.current > -45.0")

with open('lib/screens/chat_screen.dart', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated VAD threshold")
