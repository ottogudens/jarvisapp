# Fases 0 y 1 implementadas

Esta entrega aplica contención y control de acceso sin tocar datos reales ni proveedores externos.

## Fase 0: contención

- Se eliminó el reset destructivo `RESET_DB` del arranque de la API.
- El script de reset ya no contiene credenciales ni datos personales versionados; exige variables de entorno y una confirmación explícita de destrucción.
- En producción, el backend rechaza iniciar si falta `JWT_SECRET_KEY`, `APP_ENCRYPTION_KEY`, o si CORS incluye `*`.
- Las mutaciones remotas de MikroTik están bloqueadas hasta que exista una confirmación transaccional de servidor. Las operaciones de lectura quedan disponibles.
- MQTT y MikroTik verifican TLS por defecto. La desactivación de TLS queda rechazada en producción.

## Fase 1: identidad, tenants y secretos

- La identidad, tenant, rol y perfiles activos se recalculan desde PostgreSQL en cada petición autenticada. Un token anterior no mantiene permisos tras cambiar el usuario o sus perfiles.
- Solo personal staff puede cambiar datos organizacionales y perfiles activos; esos perfiles además se validan contra los asignados al tenant.
- Las rutas de MikroTik e IoT validan que la funcionalidad esté habilitada en el plan.
- Las herramientas MikroTik usadas por el LLM reciben el tenant desde el servidor y filtran routers por tenant.
- Los secretos de IoT y de proveedores IA se cifran al guardarse y no se devuelven en rutas GET.
- Telegram cifra el token del bot, elimina el token de la URL del webhook y verifica el `secret_token` de Telegram.
- Los códigos de vinculación Telegram ahora son aleatorios y expiran a los diez minutos.

## Acciones operativas requeridas antes de desplegar

1. Revocar la contraseña de superadministrador expuesta históricamente y rotar toda clave de OpenAI, Gemini, ElevenLabs, Telegram, Home Assistant, MQTT y MercadoPago que haya podido estar expuesta.
2. Crear `APP_ENCRYPTION_KEY` con Fernet y configurarla en el secret manager de cada entorno. No la subas al repositorio.
3. Configurar `APP_ENV=production`, `JWT_SECRET_KEY` de alta entropía y orígenes concretos en `CORS_ORIGINS`.
4. Ejecutar `alembic upgrade head` para añadir el secreto de webhook de Telegram.
5. Ejecutar una vez `python -m backend.scripts.migrate_encrypt_secrets` con `CONFIRM_ENCRYPTION_MIGRATION=ENCRYPT_EXISTING_SECRETS`.
6. Reconfigurar cada bot de Telegram desde el panel para registrar su nuevo webhook autenticado.

No ejecutes el script de migración sin un backup verificado de la base de datos.
