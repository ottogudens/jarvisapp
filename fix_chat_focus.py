with open('lib/screens/chat_screen.dart', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. State variable
if "List<String> _focusedDocumentIds = [];" not in content:
    content = content.replace(
        "List<PlatformFile> _selectedFiles = [];",
        "List<PlatformFile> _selectedFiles = [];\n  List<String> _focusedDocumentIds = [];\n  List<Map<String,dynamic>> _availableDocsForFocus = [];"
    )

# 2. _showFocusBottomSheet method
focus_method = """  void _showFocusBottomSheet() {
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

  Future<void> _sendMessage"""

content = content.replace("  Future<void> _sendMessage", focus_method)

# 3. Add to _sendMessage
old_send = "request.fields['mensaje'] = userText;"
new_send = """request.fields['mensaje'] = userText;
      if (_focusedDocumentIds.isNotEmpty) {
        request.fields['focused_document_ids'] = jsonEncode(_focusedDocumentIds);
      }"""
content = content.replace(old_send, new_send)

# 4. Clear focus after send
old_clear = "setState(() => _selectedFiles.clear());"
new_clear = "setState(() { _selectedFiles.clear(); _focusedDocumentIds.clear(); });"
content = content.replace(old_clear, new_clear)

# 5. UI Button and Chips
old_ui = """                onPressed: _pickFiles,
              ),
              Expanded("""
new_ui = """                onPressed: _pickFiles,
              ),
              IconButton(
                icon: const Icon(Icons.manage_search, color: Colors.cyan),
                tooltip: 'Enfocar Documentos',
                onPressed: _showFocusBottomSheet,
              ),
              Expanded("""
content = content.replace(old_ui, new_ui)

old_wrap = """                  child: Wrap(
                    spacing: 6,
                    runSpacing: 4,"""
new_wrap = """                  child: Wrap(
                    spacing: 6,
                    runSpacing: 4,
                    children: [
                      ..._focusedDocumentIds.map((id) => Chip(
                        backgroundColor: Colors.cyan.withOpacity(0.2),
                        label: Text('Foco: Doc #${id.substring(id.length - 4)}', style: const TextStyle(color: Colors.cyanAccent, fontSize: 12)),
                        onDeleted: () => setState(() => _focusedDocumentIds.remove(id)),
                        deleteIconColor: Colors.cyanAccent,
                      )),
"""
content = content.replace(old_wrap, new_wrap + "                      ...fileUrls.map((url) {\n")

# Need to fix the closing brace for the children wrap we just broke
content = content.replace("}).toList(),\n                  ),", "}).toList(),\n                    ],\n                  ),")


with open('lib/screens/chat_screen.dart', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated chat_screen.dart with Focus Feature")
