with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

import_statement = "from backend.auth import router as auth_router\nfrom backend.mikrotik import router as mikrotik_router"
content = content.replace("from backend.auth import router as auth_router", import_statement)

include_statement = "app.include_router(auth_router)\napp.include_router(mikrotik_router)"
content = content.replace("app.include_router(auth_router)", include_statement)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated main.py with mikrotik router")
