with open('lib/screens/chat_screen.dart', 'r', encoding='utf-8') as f:
    content = f.read()

# add import url_launcher
if "import 'package:url_launcher/url_launcher.dart';" not in content:
    content = content.replace("import 'package:file_picker/file_picker.dart';", "import 'package:file_picker/file_picker.dart';\nimport 'package:url_launcher/url_launcher.dart';")

# update the InkWell onTap logic
old_tap = """                          onTap: () async {
                            final uri = Uri.parse(url);
                            // launchUrl is needed, but we might just use a simple url launcher or print for now
                            // as we may not have url_launcher installed.
                            debugPrint("Open URL: $url");
                          },"""

new_tap = """                          onTap: () async {
                            final uri = Uri.parse(url);
                            if (await canLaunchUrl(uri)) {
                              await launchUrl(uri, mode: LaunchMode.externalApplication);
                            } else {
                              debugPrint("Could not launch $url");
                            }
                          },"""

content = content.replace(old_tap, new_tap)

with open('lib/screens/chat_screen.dart', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated chat_screen with url_launcher logic.")
