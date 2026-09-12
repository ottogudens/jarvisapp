# 🤖 J.A.R.V.I.S. — Multi-Tenant SaaS Voice Assistant

> Sistema de asistentes virtuales de voz especializados por industria, potenciado por GPT-4, Whisper y ElevenLabs.

## 🏭 Perfiles Disponibles

| Perfil | Industria | Especialidad |
|--------|-----------|--------------|
| **Mecánico** | Taller Automotriz | Diagnóstico vehicular, órdenes de trabajo, ERP |
| **Inspector DGC** | Fiscalización | Actas de inspección, cumplimiento normativo |
| **Enfermera Paliativos** | Salud | Registro de signos vitales, protocolos de dolor |

## 📁 Estructura del Proyecto

```text
jarvis-saas-ecosystem/
├── backend/
│   ├── __init__.py           # Paquete Python
│   ├── main.py               # Servidor FastAPI, endpoints y pipeline IA
│   ├── models.py             # Modelos ORM SQLAlchemy (PostgreSQL)
│   ├── database.py           # Conexión, pooling y migración
│   ├── auth.py               # JWT, login, feature flags multi-tenant
│   └── requirements.txt      # Dependencias Python
├── lib/
│   ├── main.dart             # Entry point Flutter
│   └── screens/
│       ├── main_screen.dart  # Push-to-Talk y streaming de audio
│       └── stats_screen.dart # Dashboard comercial con gráficos
├── Dockerfile                # Build del contenedor backend
├── docker-compose.yml        # Orquestador (API + PostgreSQL local)
├── .env.example              # Plantilla de variables de entorno
├── .dockerignore             # Exclusiones del build context
└── README.md                 # Este archivo
```

## 🚀 Inicio Rápido

### 1. Clonar y Configurar

```bash
git clone <tu-repositorio>
cd jarvis-saas-ecosystem
cp .env.example .env
# Editar .env con tus claves reales
```

### 2. Desarrollo Local con Docker

```bash
docker compose up --build
```

Esto levanta:
- **API** en `http://localhost:8000`
- **PostgreSQL** en `localhost:5432`
- **Swagger UI** en `http://localhost:8000/docs`

### 3. Verificar Salud del Servicio

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"J.A.R.V.I.S. Core Engine","version":"1.0.0"}
```

## 🔐 Autenticación

### Obtener Token JWT

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "mecanico@proservice.cl", "password": "mi_clave"}'
```

### Usar Token en Endpoints

```bash
curl -X POST http://localhost:8000/v1/jarvis/mecanico/procesar-completo \
  -H "Authorization: Bearer <tu_token>" \
  -F "audio_file=@grabacion.m4a" \
  -F "id_orden=OT-1002"
```

## 🛠️ Despliegue en Producción

1. **Base de Datos**: Crear proyecto en [Supabase](https://supabase.com), copiar URI Pooler → `DATABASE_URL`
2. **Servidor**: Crear proyecto en [Railway](https://railway.app) apuntando al repo, agregar variables de entorno
3. **App Móvil**: Actualizar `kApiBaseUrl` en `main_screen.dart` y compilar:
   ```bash
   flutter build apk --release
   ```

## 📊 Pipeline de IA

```
Audio → Whisper (STT) → GPT-4 (Clasificación + Respuesta) → ElevenLabs (TTS) → Audio
```

Cada perfil recibe un system prompt especializado y contexto operativo del dominio.

## 🔑 Variables de Entorno Requeridas

| Variable | Descripción |
|----------|-------------|
| `DATABASE_URL` | URI de PostgreSQL (Supabase o local) |
| `OPENAI_API_KEY` | Clave de API de OpenAI |
| `ELEVENLABS_API_KEY` | Clave de API de ElevenLabs |
| `ELEVENLABS_VOICE_ID` | ID de la voz de ElevenLabs |
| `JWT_SECRET_KEY` | Clave secreta para firmar JWT |
| `MP_WEBHOOK_SECRET` | Secret del webhook de MercadoPago |
| `CORS_ORIGINS` | Orígenes permitidos (separados por coma) |

## 📄 Licencia

Propiedad privada. Todos los derechos reservados.
