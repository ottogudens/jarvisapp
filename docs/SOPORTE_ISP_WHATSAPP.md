# Soporte ISP por WhatsApp — primera etapa

Implementa un piloto determinista de diagnóstico y creación de tickets. No incluye
facturación, pagos, notificaciones proactivas ni herramientas administrativas MikroTik.

## Activación

1. Ejecutar `alembic upgrade head` desde `backend`, con respaldo previo de la BD.
   La nueva revisión une las dos cabeceras existentes sin reescribirlas.
2. Guardar la conexión WhatsApp con el mecanismo existente de canales:
   `phone_number_id` y token Meta cifrado. Configurar `APP_ENCRYPTION_KEY`.
3. Definir `ISP_SUPPORT_CONNECTION_ID` con esa conexión, `META_APP_SECRET`,
   `META_WEBHOOK_VERIFY_TOKEN` y `META_GRAPH_API_VERSION` (versión vigente de su app).
4. Configurar `MIKROWISP_BASE_URL=https://DOMINIO/api/v1`, `MIKROWISP_API_TOKEN`
   y el departamento de soporte. Guardar secretos en configuración del servidor.
5. Configurar callback HTTPS `/v1/isp-support/webhook` en Meta y suscribir `messages`.
   GET valida challenge/token; POST exige firma SHA-256 del cuerpo original.
6. Un administrador verifica identidad mediante atención y usa `PUT
   /v1/isp-support/bindings`, con su JWT y cuerpo:
   `{"customer_phone":"56912345678","id_cliente":33,"identity_verified":true}`.
   Además de la verificación humana, se exige coincidencia exacta del móvil
   internacional registrado en Mikrowisp. Un RUT o ID escrito en el chat no vincula.
7. Probar desde el número vinculado: SOPORTE, TODOS, SI, NO, NO; describir problema,
   fecha AAAA-MM-DD, MAÑANA/TARDE y CONFIRMAR. Verificar ticket en Mikrowisp.

## Comportamiento

- Compara dispositivos, alimentación y luces, y propone un reinicio sin RESET ni
  manipular fibra. LOS roja o ausencia de energía derivan a atención.
- TECNICO permite saltar la guía. CANCELAR descarta un borrador.
- Fecha/turno son preferencias; la respuesta nunca promete visita confirmada.
- NewTicket se llama solo después de CONFIRMAR, con ID de cliente del vínculo
  verificado y contenido escapado para el HTML de Mikrowisp.
- Persistencia por conexión/teléfono; bloqueo de fila y deduplicación por ID Meta.
- Se reserva el registro antes de llamar a Mikrowisp. Un timeout o caída puede
  dejar `submitting`/`unknown`: no se reintenta automáticamente porque la API
  no documenta claves de idempotencia. Tampoco CANCELAR elimina esa reserva.
- Tras revisar tickets en Mikrowisp, un administrador del mismo tenant puede
  `POST /v1/isp-support/review-and-reset` con customer_phone,
  checked_in_mikrowisp=true y review_note (mínimo 10 caracteres). Sirve también
  para habilitar una nueva incidencia después de resolver la anterior.
- Se mantienen hasta diez revisiones administrativas en el estado. No exponer
  estas tablas al cliente ni registrar cuerpos de Mikrowisp: incluyen datos sensibles.

## Límites y operación

Desactivado por defecto. Selecciona una conexión por despliegue; no configura todos
los tenants automáticamente. No se ha probado con credenciales reales ni desplegado.
La guía se entrega como texto; audio/imágenes solicitan una respuesta textual.
Los eventos de estado de entrega se ignoran; no se afirma entrega al dispositivo.

El piloto procesa mensajes en el request del webhook. Los eventos se reservan una
sola vez: si el proceso cae o Meta rechaza el envío, un operador debe revisar
`isp_support_events` (processing/sending/delivery_unknown) y el estado del ticket.
No hay cola durable de recuperación automática, bandeja UI nueva ni reenvíos
proactivos. Antes de alto volumen, mover la ejecución a un worker durable con
conciliación manual de efectos inciertos; aplicar retención operativa a eventos.
Eventos con más de 23 horas se ignoran para no responder texto libre fuera de la
ventana de atención. No se incluyen plantillas de avisos fuera de esa ventana.

El manual es genérico: validar los pasos con el ISP y sus equipos antes de activar.
La guía no realiza un diagnóstico automático de red ni confirma una avería.

## Verificación local

`python -m pytest backend/tests/test_isp_support.py -q`

Las pruebas cubren confirmación, recuperación, fechas inválidas, cancelación,
firma alterada, separación por tenant, duplicados y resultados ambiguos.
La prueba real pendiente requiere Meta, Mikrowisp y PostgreSQL del entorno de pruebas.

Referencias: blueprint `mikrowisp.apib` entregado por el cliente (GetClientsDetails,
NewTicket); validación Meta https://whatsapp.github.io/WhatsApp-Nodejs-SDK/api-reference/webhooks/start/ .

## Comprobar configuración antes del piloto

Un administrador autenticado puede llamar a `GET /v1/isp-support/configuration`
con su JWT. Funciona incluso si `ISP_SUPPORT_CONNECTION_ID` todavía está vacío.
Devuelve `configured`, un mapa de comprobaciones booleanas y
`external_connectivity: "not_tested"`. No devuelve valores de tokens ni claves,
no envía mensajes, no crea tickets y no consulta servicios externos.

Comprueba la conexión WhatsApp del tenant autenticado, presencia de las dos
tablas de soporte, secretos Meta, formato de versión Graph, identificador de
teléfono, descifrado de la credencial, URL/token de Mikrowisp y departamento
 positivo. No sustituye verificar la revisión de Alembic ni comprobar permisos,
 vigencia de credenciales, versión Graph admitida o conectividad real.
Una conexión seleccionada de otro tenant devuelve 404; un usuario cliente recibe
403. `configured: true` solo indica configuración local completa.

El token de WhatsApp debe estar cifrado con la clave del despliegue. Este módulo
rechaza credenciales heredadas en texto plano, cifrado corrupto y claves distintas.
Si falla esa comprobación, volver a guardar la credencial mediante la conexión de
canales con la clave correcta y reiniciar el backend si se cambió su configuración.
Mikrowisp exige URL HTTPS terminada en `/api/v1`, sin credenciales en URL, query
ni fragmento. Guardar el token exclusivamente en `MIKROWISP_API_TOKEN`.

Después del chequeo, completar la prueba de extremo a extremo con un número
vinculado: verificar una única creación de ticket, repetir el mismo evento Meta
y confirmar que no aparece un duplicado. Un chequeo local correcto no activa ni
certifica ese flujo real.
