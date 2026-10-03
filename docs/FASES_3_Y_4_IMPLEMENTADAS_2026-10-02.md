# Fases 3 y 4 implementadas

## Fase 3 — Datos, IA y privacidad

- Se centralizó la validación de adjuntos: máximo cinco por solicitud, 15 MB por archivo, extensiones permitidas, nombre seguro y firmas comprobadas para PDF/PNG/JPEG/WebP.
- Los documentos de chat se etiquetan como contenido no confiable y el prompt establece que no pueden autorizar herramientas ni alterar reglas del agente.
- Los documentos subidos a la base de conocimiento ahora se asocian a su usuario creador.
- Se añadieron rutas autenticadas para exportar el historial propio (`GET /v1/privacy/export`) y eliminar chats/conocimiento propio (`DELETE /v1/privacy/chat-data`) con la confirmación literal `DELETE_MY_CHAT_DATA`.

## Fase 4 — Calidad y operación

- Se añadieron `/health` (liveness) y `/ready` (conectividad PostgreSQL), además de `X-Request-ID` y logs JSON de método, ruta, estado y latencia. No registran cuerpos, credenciales ni tokens.
- El contenedor ahora ejecuta como usuario no root y puede ejecutar Alembic de manera controlada mediante `RUN_MIGRATIONS=true`.
- Se añadió CI de GitHub Actions: compilación Python, pruebas unitarias, auditoría de dependencias, formato Dart, análisis Flutter y pruebas Flutter.
- Se reemplazó la prueba Flutter de plantilla por una prueba de renderizado real del login y se añadieron pruebas para validación de adjuntos.

## Límites pendientes

- La eliminación no borra objetos de almacenamiento externo porque el proyecto aún persiste adjuntos como URI base64/URLs sin una capa de almacenamiento privada gestionada. La siguiente iteración debe migrarlos a object storage con URLs firmadas y reglas de retención.
- La exportación no incluye documentos de tenant sin propietario porque sería inseguro atribuirlos automáticamente a un usuario.
- La protección contra prompt injection no sustituye los controles deterministas de la fase 2. Las mutaciones remotas siguen bloqueadas.
- Antes de habilitar `RUN_MIGRATIONS` en múltiples réplicas se necesita un mecanismo de exclusión mutua o un job de migración único.
