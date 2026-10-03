# Auditoría inicial de J.A.R.V.I.S.

**Fecha:** 2 de octubre de 2026
**Alcance de esta fase:** inspección estática del repositorio, configuración versionada, historial Git reciente y verificaciones no destructivas. No se usaron credenciales ni se llamó a servicios externos.

## Resumen ejecutivo

La aplicación implementa un SaaS de asistentes de voz con Flutter, FastAPI, PostgreSQL, Gemini/otros LLMs, ElevenLabs, Telegram, MQTT, Home Assistant y MikroTik. La superficie de ataque es alta porque combina datos sensibles, acciones remotas e IA con herramientas.

Se identificaron riesgos críticos que hacen desaconsejable desplegar la versión actual a producción sin una corrección urgente: una contraseña de superadministrador versionada y recreable al arrancar, un mecanismo de borrado completo activable por una variable de entorno, y herramientas MikroTik que no aplican el aislamiento por tenant ni una confirmación de servidor vinculada al usuario.

## Arquitectura observada

```text
Flutter/Web ──JWT──> FastAPI ──> PostgreSQL / pgvector
                       ├──> Gemini, OpenAI, Anthropic o DeepSeek mediante LiteLLM
                       ├──> ElevenLabs
                       ├──> Telegram webhook
                       ├──> Home Assistant / MQTT
                       └──> MikroTik REST
```

Los mensajes y adjuntos se almacenan en PostgreSQL; algunos adjuntos se conservan como URI `data:` codificados en base64 dentro de `chat_messages`. El contenido de documentos se fragmenta y vectoriza para RAG.

## Hallazgos priorizados

| ID | Severidad | Hallazgo | Evidencia | Riesgo |
|---|---|---|---|---|
| SEC-01 | Crítica | Credencial conocida de superadministrador en código e historial Git. | `backend/main.py:95`; `backend/scripts/reset_superadmin.py:39`; commit `c22a4fd`. | Cualquier persona con acceso al repositorio conoce la contraseña que se recrea tras un reset. Debe considerarse comprometida y rotarse. |
| SEC-02 | Crítica | El arranque ejecuta `TRUNCATE ... CASCADE` y recrea una cuenta privilegiada cuando `RESET_DB=true`. | `backend/main.py:54-107`. | Un error de configuración, una modificación indebida de variables o un reinicio puede borrar datos de todos los tenants. |
| SEC-03 | Crítica | Las herramientas MikroTik buscan el router solo por `id_router`, sin validar tenant ni usuario. | `backend/mikrotik_tools.py:7-21`; invocación desde `backend/ai_service.py`. | Un usuario que induzca al LLM a usar un ID ajeno puede consultar o controlar routers de otro tenant. |
| SEC-04 | Crítica | La aprobación de comandos MikroTik depende de que el LLM envíe `confirmar=true`; no existe un desafío de confirmación firmado, de un solo uso y asociado a usuario/router/comando. | `backend/mikrotik_tools.py:55-83`; `backend/ai_service.py`. | Prompt injection o una mala decisión del modelo puede ejecutar cambios de red destructivos. |
| SEC-05 | Alta | CORS permite cualquier origen por defecto junto con credenciales. | `backend/main.py:132-137`; `.env.example`. | Configuración insegura y potencialmente incompatible con navegadores; facilita exposición accidental de la API. |
| SEC-06 | Alta | El JWT usa una clave estática predecible si falta configuración y la autorización confía en roles/tenant del token sin consultar el estado actual del usuario. | `backend/auth.py:22-30`, `91-122`. | En una configuración incompleta se pueden falsificar tokens; además, revocar rol, usuario o tenant no invalida sesiones vigentes. |
| SEC-07 | Alta | Secretos de Home Assistant y MQTT se almacenan sin cifrado y se devuelven al cliente por GET. | `backend/models.py:278-284`; `backend/main.py:1259-1275`. | Exposición de credenciales y acceso lateral a sistemas IoT. |
| SEC-08 | Alta | TLS se desactiva para MikroTik y MQTT; además, MikroTik permite HTTP según puerto. | `backend/mikrotik_service.py:36`; `backend/iot_service.py:95-98`; `backend/main.py:1438-1441`. | Intercepción de credenciales y comandos, especialmente en redes no confiables. |
| SEC-09 | Alta | Las claves de proveedores IA se guardan en texto plano en `system_settings`, se devuelven a personal staff y se copian al entorno del proceso. | `backend/admin.py:118-142`; `backend/ai_service.py:113-119`. | Todo usuario staff puede exfiltrar claves globales; las claves pueden persistir en memoria/logs y no hay segregación por tenant. |
| SEC-10 | Alta | El endpoint de perfil permite a cualquier usuario autenticado modificar datos del tenant y sus perfiles activos. | `backend/auth.py:177-211`. | Un usuario cliente puede alterar el nombre/contacto de su organización y habilitar perfiles no autorizados; el control de funciones depende de perfiles incluidos en el JWT. |
| SEC-11 | Alta | El webhook de Telegram lleva el token del bot en la URL y no valida un secreto de webhook de Telegram. | `backend/telegram_router.py:33-63`, `201+`. | El token queda en rutas, proxies y logs; un tercero que lo obtenga puede inyectar actualizaciones o controlar el bot. |
| SEC-12 | Alta | El código de vinculación Telegram es de seis dígitos, no expira, no limita intentos y vive solo en memoria. | `backend/telegram_router.py:19`, `104-117`, `171+`. | Posible fuerza bruta / vinculación indebida y comportamiento no fiable al reiniciar o escalar horizontalmente. |
| SEC-13 | Media | Archivos y audio se aceptan según `content_type`/extensión, se cargan completos en memoria y no hay escaneo antivirus, límite de cantidad ni control de descompresión de PDF. | `backend/main.py:552-665`, `887+`; `backend/telegram_router.py`. | Denegación de servicio, consumo de IA y procesamiento de contenido malicioso. |
| SEC-14 | Media | Datos de adjuntos se guardan como URI base64 en la BD y los PDFs enviados por Telegram se persisten automáticamente. | `backend/main.py:916+`; `backend/telegram_router.py:300+`. | Crecimiento de BD, backups con contenido sensible, retención no consentida y dificultad de eliminación. |
| SEC-15 | Media | No hay límites de tasa, bloqueo progresivo de login, refresh/revocación de tokens ni registro de auditoría de acciones críticas. | `backend/auth.py`; routers de administración, IoT y MikroTik. | Fuerza bruta, abuso de coste y falta de trazabilidad forense. |
| REL-01 | Media | Operaciones síncronas de red, IA y TTS se ejecutan dentro de rutas async; no hay cola ni límite de concurrencia. | `backend/main.py`; `backend/ai_service.py`; `backend/mikrotik_service.py`. | Bloqueo de workers, picos de latencia y fallos en cascada. |
| REL-02 | Media | El esquema se muta al inicio mediante `create_all` y sentencias `ALTER TABLE` capturadas de forma amplia, aunque Alembic también existe. | `backend/database.py:38-168`. | Despliegues no reproducibles, errores silenciosos y migraciones difíciles de revertir. |
| QA-01 | Media | No hay pruebas de backend ni de seguridad; la única prueba Flutter es el contador de la plantilla y no corresponde a la app. | `test/widget_test.dart`. | No hay red de seguridad para cambios en autorización, pagos, IA o integraciones. |
| PRIV-01 | Media | No existe política implementada de consentimiento, retención, exportación o borrado de audio, chat, datos clínicos y RAG. | Modelos y rutas de chat/RAG. | Riesgo de privacidad y cumplimiento, especialmente para el perfil de paliativos. |

## Riesgos de IA y agentes

- El modelo dispone de herramientas que cambian el estado de Home Assistant, MQTT, documentos y MikroTik. Las reglas escritas en prompts no son un control de seguridad suficiente.
- Las instrucciones de perfiles y documentos subidos se concatenan al contexto del modelo. Todo contenido externo debe tratarse como no confiable y no puede autorizar uso de herramientas.
- Debe existir una capa de política determinista fuera del LLM: identidad del usuario, tenant, permisos, allowlists de recursos, validación de argumentos, presupuestos de coste, y confirmación criptográfica para acciones de riesgo.
- Para el perfil clínico: prohibir diagnóstico/tratamiento autónomo, mostrar límites de uso y definir la derivación a un profesional humano ante señales de urgencia.

## Plan de remediación propuesto

### Fase 0 — Contención inmediata (antes de producción)

1. Revocar y rotar la contraseña versionada, claves de proveedores y cualquier token del bot que haya estado expuesto. Reescribir el historial si el repositorio fue público o compartido ampliamente.
2. Eliminar el reset automático de runtime. Sustituirlo por una operación administrativa fuera de producción, con backup verificado, autenticación fuerte y doble confirmación.
3. Deshabilitar temporalmente las acciones remotas de MikroTik/IoT hasta implementar autorización de servidor y confirmación transaccional.
4. Rechazar el arranque de producción si faltan `JWT_SECRET_KEY`, cifrado de secretos, CORS explícito, URL pública HTTPS y credenciales requeridas.

### Fase 1 — Identidad, tenants y secretos

1. Resolver el usuario y el tenant desde la base de datos en cada petición autenticada; validar estado activo y rol actual.
2. Separar permisos: cliente, operador, administrador de tenant y superadministrador. Solo roles administrativos deben modificar perfiles, integraciones y organización.
3. Cifrar secretos de Telegram, Home Assistant, MQTT y proveedores con KMS/secret manager. Las respuestas API deben devolver solo indicadores de configuración, nunca los valores.
4. Implementar expiración corta, refresh token con rotación, revocación y rate limiting de autenticación.

### Fase 2 — Integraciones y agentes seguros

1. Cambiar todas las herramientas a APIs que reciban contexto autenticado de servidor y que filtren recursos por tenant; nunca aceptar un `id_router` aislado.
2. Usar allowlists de comandos MikroTik y entidades Home Assistant/MQTT. Bloquear comandos raw hasta disponer de una política revisada.
3. Crear solicitudes de confirmación persistentes, con TTL, hash de argumentos, usuario, tenant y recurso; ejecutar únicamente una solicitud aprobada una vez.
4. Requerir TLS verificado por defecto y permitir certificados privados únicamente mediante CA/certificado explícitamente configurado.
5. Configurar Telegram con `secret_token`, no colocar el token del bot en la ruta y aplicar límites de tamaño, tipos y frecuencia.

### Fase 3 — Datos, IA y cumplimiento

1. Definir clasificación de datos, consentimiento, plazos de retención, borrado en cascada verificable y exportación.
2. Guardar binarios en almacenamiento de objetos privado con URLs firmadas; no en columnas base64. Cifrar datos sensibles y backups.
3. Añadir filtros de contenido, límites de archivo/cantidad, procesamiento asíncrono, cuarentena y métricas de coste por tenant.
4. Versionar prompts y evaluaciones; separar datos no confiables de instrucciones y registrar acciones de herramientas.

### Fase 4 — Calidad, operación y rendimiento

1. Reemplazar migraciones en runtime por Alembic en CI/CD y desplegar migraciones de forma controlada.
2. Añadir pruebas unitarias, API, autorización multi-tenant, regresión de herramientas, webhook y E2E Flutter.
3. Incorporar CI con formato, lint, tipos, pruebas, SAST, escaneo de dependencias y secretos.
4. Añadir logs estructurados sin PII/secrets, trazas, métricas, alertas, backups y simulacros de restauración.

## Verificaciones ejecutadas

| Verificación | Resultado |
|---|---|
| Compilación sintáctica Python (`python -m compileall -q backend`) | Correcta. No sustituye pruebas de ejecución. |
| Análisis Flutter | No ejecutado: Flutter no está disponible en el `PATH` de este entorno. |
| Revisión de cambios (`git diff --check`) | Sin errores de espacio en los archivos añadidos durante esta auditoría. |
| Escaneo básico de secretos versionados | Detectó la contraseña de superadministrador en los dos archivos indicados y en el historial. No reemplaza un escáner dedicado como Gitleaks. |

## Límites de esta fase

No se verificaron proveedores, Railway, Supabase, Vercel, base de datos real, secretos actuales, configuración de red ni comportamiento de producción. La auditoría dinámica y la corrección de los hallazgos críticos requieren un entorno de staging aislado y datos sintéticos.
