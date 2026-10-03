# Despliegue: Railway + Vercel

## Estado detectado

- Railway: proyecto `Jarvis`, entorno `production`, servicio `backend`. Está desplegando desde `ottogudens/jarvisapp`, rama `main`, con Dockerfile. El dominio público actual es `https://jarvisapp-production-f259.up.railway.app`.
- Vercel: proyecto `jarvisapp`, equipo `skale1`, dominio de producción `https://jarvis.skale.cl`. El build activo ejecuta `bash build.sh` por el `vercel.json` del repositorio.

## Cambios incluidos para el despliegue

- `backend/scripts/start_api.sh` escucha `${PORT:-8000}`, compatible con el puerto inyectado por Railway.
- El frontend admite `--dart-define=API_BASE_URL=...`; `build.sh` lo inyecta cuando existe la variable `API_BASE_URL` de Vercel.
- Flutter se fija por defecto en la versión `3.47.5` para evitar cambios inesperados de la rama `stable`.
- Los endpoints `/health` y `/ready` están disponibles para configurar el health check de Railway.

## Rollout seguro

1. **Revocar tokens Telegram inmediatamente.** Los registros históricos de Railway contenían tokens de bots dentro de rutas de webhook. Deben considerarse expuestos. Genera tokens nuevos en BotFather; no los reutilices.
2. En Railway / `Jarvis` / `backend` / `production`, añade o verifica estos nombres de variables sin exponer sus valores:
   - `APP_ENV=production`
   - `APP_ENCRYPTION_KEY` (Fernet; puede coexistir temporalmente con `MIKROTIK_ENCRYPTION_KEY`)
   - `CORS_ORIGINS=https://jarvis.skale.cl,https://jarvisapp-skale1.vercel.app,https://jarvisapp-git-main-skale1.vercel.app`
   - `RUN_MIGRATIONS=true` **solo para una única réplica** durante el primer despliegue.
   - Conserva las variables actuales de base de datos y proveedores; rótalas si estuvieron expuestas.
3. En Vercel / `jarvisapp`, define para Production:
   - `API_BASE_URL=https://jarvisapp-production-f259.up.railway.app`
   No es un secreto. Configura el mismo valor en Preview únicamente si deseas que los previews llamen a producción; de lo contrario usa un backend de staging.
4. Haz commit y push a `main`. Railway y Vercel están conectados al repositorio y deberían crear un despliegue nuevo.
5. Cuando Railway termine correctamente, configura el health check del servicio como `/health` y valida:
   - `GET https://jarvisapp-production-f259.up.railway.app/health` → 200.
   - `GET https://jarvisapp-production-f259.up.railway.app/ready` → 200.
   - Abre `https://jarvis.skale.cl`, inicia sesión y confirma que no hay errores CORS.
6. Reconfigura cada bot Telegram desde el panel de la aplicación. Esto registra la nueva URL de webhook autenticada y el `secret_token`.
7. Ejecuta la migración de cifrado de secretos una vez, después de un backup verificado:
   ```bash
   CONFIRM_ENCRYPTION_MIGRATION=ENCRYPT_EXISTING_SECRETS \
   python -m backend.scripts.migrate_encrypt_secrets
   ```
   Después, deja `RUN_MIGRATIONS=false` o elimínala si el despliegue deja de necesitar migraciones automáticas.

## Límites

No se debe activar el health check `/health` en Railway hasta que el backend con estos cambios esté desplegado, porque la versión actualmente activa no implementa esa ruta. Las mutaciones de MikroTik siguen bloqueadas intencionalmente hasta completar la fase 2.
