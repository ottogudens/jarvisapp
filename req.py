with open('backend/requirements.txt', 'r', encoding='utf-8') as f:
    content = f.read()

if "pgvector" not in content:
    content += "\npgvector>=0.2.1\n"
    with open('backend/requirements.txt', 'w', encoding='utf-8') as f:
        f.write(content)
print("Updated requirements.txt")
