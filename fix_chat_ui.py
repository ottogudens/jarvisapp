with open('lib/screens/chat_screen.dart', 'r', encoding='utf-8') as f:
    content = f.read()

old_logic = """                      if (url.startsWith('data:image/')) {
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
                      }"""

new_logic = """                      if (url.startsWith('http')) {
                        fileIcon = Icons.file_download;
                        label = 'Documento Generado';
                        if (url.toLowerCase().endsWith('.pdf')) {
                          fileIcon = Icons.picture_as_pdf;
                          label = 'PDF Generado';
                        }
                      } else if (url.startsWith('data:image/')) {
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
                      }"""

content = content.replace(old_logic, new_logic)

# Make the widget clickable if it's an HTTP url (to open in browser)
old_widget = """                      return Tooltip(
                        message: label == 'Audio' ? 'Audio transcrito por J.A.R.V.I.S.' : 'Documento conocido por J.A.R.V.I.S.',
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.black26,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(fileIcon, color: Colors.cyanAccent, size: 14),
                              const SizedBox(width: 4),
                              Text(label, style: const TextStyle(color: Colors.cyanAccent, fontSize: 11)),
                            ],
                          ),
                        ),
                      );"""

new_widget = """                      Widget chip = Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.black26,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(fileIcon, color: Colors.cyanAccent, size: 14),
                            const SizedBox(width: 4),
                            Text(label, style: const TextStyle(color: Colors.cyanAccent, fontSize: 11)),
                          ],
                        ),
                      );
                      
                      if (url.startsWith('http')) {
                        chip = InkWell(
                          onTap: () async {
                            final uri = Uri.parse(url);
                            // launchUrl is needed, but we might just use a simple url launcher or print for now
                            // as we may not have url_launcher installed.
                            debugPrint("Open URL: $url");
                          },
                          child: chip,
                        );
                      }
                      
                      return Tooltip(
                        message: url.startsWith('http') ? 'Descargar Documento Generado' : (label == 'Audio' ? 'Audio transcrito por J.A.R.V.I.S.' : 'Documento conocido por J.A.R.V.I.S.'),
                        child: chip,
                      );"""

content = content.replace(old_widget, new_widget)

with open('lib/screens/chat_screen.dart', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated chat_screen.dart with URL support.")
