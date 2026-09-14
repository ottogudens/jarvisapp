with open('pubspec.yaml', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("  shared_preferences: ^2.2.2\n", "  shared_preferences: ^2.2.2\n  url_launcher: ^6.2.6\n")

with open('pubspec.yaml', 'w', encoding='utf-8') as f:
    f.write(content)
print("Added url_launcher to pubspec.yaml")
