# Referencia REST API de MikroTik RouterOS v7

> Esta referencia corresponde exclusivamente a **RouterOS v7.x** (la REST API en sí solo existe desde v7.1beta4+). Donde v7 rediseñó un módulo respecto a v6 (BGP, OSPF, routing-mark → routing/table) se usa la sintaxis y los menús **nuevos de v7**; los menús legacy de v6 (`routing/bgp/instance`, `routing/bgp/peer`, `routing/bgp/network`) quedaron obsoletos y no se incluyen aquí.
> Requiere el servicio `www-ssl` (HTTPS, recomendado) o `www` (HTTP, solo desde v7.9, no recomendado en producción).
> Base URL: `https://<ip_router>/rest` — Auth: HTTP Basic Auth (mismo usuario/clave que la consola).

## Principio fundamental

La REST API **no es una lista cerrada de endpoints** — es un espejo 1:1 del árbol completo de menús de la CLI de RouterOS. Cualquier path de consola se traduce directamente:

```
Consola:  /ip/address/print          →  REST:  GET  /rest/ip/address
Consola:  /interface/wireless/print  →  REST:  GET  /rest/interface/wireless
Consola:  /ip/firewall/filter/print  →  REST:  GET  /rest/ip/firewall/filter
```

### Verbos HTTP y su equivalente en consola

| Verbo HTTP | CRUD | Comando consola | Descripción |
|---|---|---|---|
| `GET` | Read | `print` | Lista o retorna un registro |
| `PUT` | Create | `add` | Crea un nuevo registro (solo uno por request) |
| `PATCH` | Update | `set` | Modifica un registro existente por `.id` |
| `DELETE` | Delete | `remove` | Elimina un registro por `.id` |
| `POST` | Universal | cualquier comando | Acceso a **cualquier** comando de consola, incluyendo acciones sin CRUD (ping, export, reboot, move, etc.) |

### Filtros, proplist y query (GET/POST)

```
# Filtrar por campo
GET /rest/ip/address?network=10.155.101.0&dynamic=true

# Retornar solo columnas específicas
GET /rest/ip/address?.proplist=address,disabled

# Query compuesto vía POST (equivalente a múltiples ?filtros con lógica OR/AND)
POST /rest/interface/print
{".query": ["type=ether", "type=vlan", "#|!"]}
```

### Timeout
Las requests via POST tienen **60 segundos** de timeout fijo — no configurable por parámetros del comando. Para comandos "monitor" continuos, usar el parámetro `once`.

---

## 1. Sistema

| Path | Descripción |
|---|---|
| `GET /rest/system/resource` | CPU, RAM, uptime, versión, arquitectura |
| `GET /rest/system/identity` | Nombre del router |
| `PATCH /rest/system/identity` | Cambiar nombre |
| `GET /rest/system/clock` | Fecha/hora del sistema |
| `GET /rest/system/routerboard` | Info de hardware (modelo, serial, firmware) |
| `POST /rest/system/routerboard/upgrade` | Actualizar firmware de RouterBOARD |
| `GET /rest/system/health` | Voltaje, temperatura (según modelo) |
| `GET /rest/system/license` | Nivel de licencia |
| `POST /rest/system/reboot` | Reiniciar el equipo |
| `POST /rest/system/shutdown` | Apagar el equipo |
| `POST /rest/system/backup/save` | Crear backup binario |
| `POST /rest/system/backup/load` | Restaurar backup |
| `POST /rest/export` | Exportar configuración a `.rsc` (`{"compact":"","file":"nombre.rsc"}`) |
| `GET /rest/system/package` | Paquetes instalados |
| `POST /rest/system/package/update/check-for-updates` | Buscar actualizaciones de RouterOS |
| `GET /rest/system/script` | Scripts guardados |
| `POST /rest/system/script/run` | Ejecutar script por `.id` |
| `POST /rest/execute` | Ejecutar comando/script inline: `{"script":"/log/info test"}` |
| `POST /rest/password` | Cambiar contraseña del usuario activo |

## 2. Usuarios y acceso

| Path | Descripción |
|---|---|
| `GET/PUT/PATCH/DELETE /rest/user` | Usuarios de RouterOS |
| `GET /rest/user/active` | Sesiones activas |
| `GET/PUT/DELETE /rest/user/group` | Grupos de permisos |
| `GET/PUT/PATCH/DELETE /rest/user/ssh-keys` | Llaves SSH públicas |
| `GET /rest/ip/service` | Servicios habilitados (www, www-ssl, ssh, telnet, api, winbox) |
| `PATCH /rest/ip/service/{.id}` | Habilitar/deshabilitar/restringir por IP un servicio |
| `GET/PUT/DELETE /rest/certificate` | Certificados (necesarios para www-ssl) |

## 3. Interfaces

| Path | Descripción |
|---|---|
| `GET /rest/interface` | Todas las interfaces (físicas + virtuales) |
| `PATCH /rest/interface/{.id}` | Habilitar/deshabilitar, cambiar nombre/comentario |
| `GET /rest/interface/ethernet` | Interfaces Ethernet |
| `POST /rest/interface/ethernet/monitor` | Estado de enlace en tiempo real (usar `once`) |
| `GET/PUT/PATCH/DELETE /rest/interface/vlan` | Interfaces VLAN |
| `GET/PUT/PATCH/DELETE /rest/interface/bridge` | Bridges |
| `GET/PUT/DELETE /rest/interface/bridge/port` | Puertos asignados a un bridge |
| `GET /rest/interface/bridge/host` | Tabla de hosts aprendidos (MAC) por bridge |
| `GET/PUT/PATCH/DELETE /rest/interface/bonding` | Bonding/LACP |
| `GET/PUT/PATCH/DELETE /rest/interface/pppoe-client` | Cliente PPPoE (uplink) |
| `GET/PUT/PATCH/DELETE /rest/interface/wireguard` | Interfaces WireGuard |
| `GET/PUT/PATCH/DELETE /rest/interface/wireguard/peers` | Peers WireGuard |
| `GET/PUT/PATCH/DELETE /rest/interface/eoip` | Túneles EoIP |
| `GET/PUT/PATCH/DELETE /rest/interface/vxlan` | Túneles VXLAN |
| `GET/PUT/PATCH/DELETE /rest/interface/list` | Listas de interfaces (para firewall/routing) |
| `GET/PUT/DELETE /rest/interface/list/member` | Miembros de una lista de interfaces |

## 4. IP — Direccionamiento y servicios básicos

| Path | Descripción |
|---|---|
| `GET/PUT/PATCH/DELETE /rest/ip/address` | Direcciones IP asignadas a interfaces |
| `GET/PUT/PATCH/DELETE /rest/ip/pool` | Pools de direcciones (DHCP/PPP) |
| `GET/PUT/PATCH/DELETE /rest/ip/dhcp-server` | Servidores DHCP |
| `GET/PUT/PATCH/DELETE /rest/ip/dhcp-server/network` | Redes DHCP (gateway, DNS, opciones) |
| `GET /rest/ip/dhcp-server/lease` | Leases activos |
| `PATCH /rest/ip/dhcp-server/lease/{.id}` | Convertir lease dinámico en estático (`make-static`) vía POST |
| `GET/PUT/PATCH/DELETE /rest/ip/dhcp-client` | Cliente DHCP |
| `GET/PUT/PATCH/DELETE /rest/ip/dns` | Configuración DNS del router |
| `GET/PUT/PATCH/DELETE /rest/ip/dns/static` | Entradas DNS estáticas |
| `POST /rest/ip/dns/cache/flush` | Limpiar caché DNS |
| `GET/PUT/PATCH/DELETE /rest/ip/route` | Tabla de rutas estáticas |
| `GET /rest/ip/route/cache` | Caché de rutas |
| `GET/PUT/PATCH/DELETE /rest/ip/arp` | Tabla ARP |
| `GET/PUT/PATCH/DELETE /rest/ip/settings` | Ajustes generales IP (forwarding, RP filter, etc.) |
| `GET/PUT/PATCH/DELETE /rest/ip/cloud` | MikroTik Cloud DDNS |
| `GET/PUT/PATCH/DELETE /rest/ip/hotspot` | Servidores Hotspot |
| `GET /rest/ip/hotspot/active` | Usuarios conectados al hotspot |
| `GET/PUT/PATCH/DELETE /rest/ip/hotspot/user` | Usuarios hotspot |

## 5. Firewall y NAT

| Path | Descripción |
|---|---|
| `GET/PUT/PATCH/DELETE /rest/ip/firewall/filter` | Reglas de filtrado (input/forward/output) |
| `GET/PUT/PATCH/DELETE /rest/ip/firewall/nat` | Reglas NAT (masquerade, dst-nat, src-nat) |
| `GET/PUT/PATCH/DELETE /rest/ip/firewall/mangle` | Marcado de paquetes/conexiones (routing/QoS) |
| `GET/PUT/PATCH/DELETE /rest/ip/firewall/address-list` | Listas de direcciones (usadas por filter/mangle) |
| `GET/PUT/PATCH/DELETE /rest/ip/firewall/layer7-protocol` | Firmas L7 |
| `GET/PUT/PATCH/DELETE /rest/ip/firewall/raw` | Reglas raw (prerouting antes de conntrack) |
| `GET /rest/ip/firewall/connection` | Tabla de conexiones activas (conntrack) |
| `POST /rest/ip/firewall/nat/move` | Reordenar reglas (`{".id":"*9",".id":"*C"}`) |
| `GET/PUT/PATCH/DELETE /rest/ip/firewall/service-port` | Ayudantes NAT por protocolo (ftp, pptp, sip, etc.) |
| `GET/PUT/PATCH/DELETE /rest/ipv6/firewall/filter` | Firewall IPv6 |

## 6. Routing dinámico

| Path | Descripción |
|---|---|
| `GET/PUT/PATCH/DELETE /rest/routing/ospf/instance` | Instancias OSPF |
| `GET/PUT/PATCH/DELETE /rest/routing/ospf/area` | Áreas OSPF |
| `GET/PUT/PATCH/DELETE /rest/routing/ospf/interface-template` | Config OSPF por interfaz (v7 hace *match* de interfaces contra templates) |
| `GET /rest/routing/ospf/interface` | Estado de interfaces OSPF (solo lectura) |
| `GET /rest/routing/ospf/neighbor` | Vecinos OSPF y su estado de adyacencia (solo lectura) |
| `GET/PUT/PATCH/DELETE /rest/routing/bgp/connection` | Peers/conexiones BGP — reemplaza el antiguo `bgp/peer` de v6 |
| `GET/PUT/PATCH/DELETE /rest/routing/bgp/template` | Templates BGP (config común reutilizable entre conexiones) |
| `GET /rest/routing/bgp/session` | Estado de sesiones BGP activas/caídas (solo lectura, reemplaza el monitoreo de v6) |
| `GET /rest/routing/stats` | Estadísticas generales de todos los procesos de ruteo |
| `GET/PUT/PATCH/DELETE /rest/routing/filter/rule` | Filtros de ruteo — en v7 usan sintaxis tipo script (`if .. then`) |
| `GET/PUT/PATCH/DELETE /rest/routing/table` | Tablas de ruteo (VRF-like, reemplaza `routing-mark` de v6) |

> **Nota v7:** los prefijos que un router anuncia por BGP ya **no se declaran en `routing/bgp/network`** (eso era v6) — en v7 se agregan a una `ip/firewall/address-list` y se referencian desde `routing/bgp/connection`.

## 7. Wireless / CAPsMAN / WiFi (paquete `wifi`, RouterOS v7.13+)

| Path | Descripción |
|---|---|
| `GET/PUT/PATCH/DELETE /rest/interface/wireless` | Interfaces wireless legacy (wave1/wave2) |
| `GET /rest/interface/wireless/registration-table` | Clientes conectados (legacy) |
| `POST /rest/interface/wireless/monitor` | Estado de enlace/señal (usar `once`) |
| `GET/PUT/PATCH/DELETE /rest/interface/wifi` | Interfaces WiFi (driver nuevo) |
| `GET /rest/interface/wifi/registration-table` | Clientes conectados (driver nuevo) |
| `POST /rest/interface/wifi/monitor` | Monitor de radio (usar `once`) |
| `GET/PUT/PATCH/DELETE /rest/interface/wifi/security` | Perfiles de seguridad WiFi |
| `GET/PUT/PATCH/DELETE /rest/caps-man/manager` | CAPsMAN — gestor central |
| `GET/PUT/PATCH/DELETE /rest/caps-man/configuration` | Perfiles de configuración CAPsMAN |
| `GET /rest/caps-man/registration-table` | Clientes conectados vía CAPsMAN |
| `GET/PUT/PATCH/DELETE /rest/caps-man/provisioning` | Reglas de aprovisionamiento de APs |

## 8. PPP / PPPoE (clave para ISP)

| Path | Descripción |
|---|---|
| `GET/PUT/PATCH/DELETE /rest/interface/pppoe-server/server` | Servidor(es) PPPoE |
| `GET /rest/ppp/active` | Sesiones PPP activas (incluye PPPoE) |
| `POST /rest/ppp/active/remove` | Desconectar sesión activa por `.id` |
| `GET/PUT/PATCH/DELETE /rest/ppp/secret` | Usuarios PPP/PPPoE (credenciales) |
| `GET/PUT/PATCH/DELETE /rest/ppp/profile` | Perfiles PPP (rate-limit, pool, DNS local) |
| `GET/PUT/PATCH/DELETE /rest/interface/l2tp-server/server` | Servidor L2TP |
| `GET/PUT/PATCH/DELETE /rest/interface/sstp-server/server` | Servidor SSTP |

## 9. Queues / QoS

| Path | Descripción |
|---|---|
| `GET/PUT/PATCH/DELETE /rest/queue/simple` | Colas simples (límite por IP/cliente) |
| `GET/PUT/PATCH/DELETE /rest/queue/tree` | Colas jerárquicas (QoS avanzado, requiere mangle) |
| `GET/PUT/PATCH/DELETE /rest/queue/type` | Tipos de cola (PCQ, etc.) |
| `GET /rest/queue/simple` con `?.proplist=name,rate` | Monitoreo liviano de consumo por cliente |

## 10. Herramientas de diagnóstico

| Path | Descripción |
|---|---|
| `POST /rest/ping` | Ping (`{"address":"...", "count":"4"}` — obligatorio limitar count/duration por el timeout de 60s) |
| `POST /rest/tool/traceroute` | Traceroute |
| `POST /rest/tool/bandwidth-test` | Test de ancho de banda entre routers MikroTik |
| `POST /rest/tool/torch` | Captura de tráfico en tiempo real por interfaz (usar `once` o duración corta) |
| `GET/PUT/PATCH/DELETE /rest/tool/netwatch` | Monitoreo de disponibilidad de hosts |
| `GET/PUT/DELETE /rest/tool/graphing` | Configuración de graphing (RRD) |
| `POST /rest/tool/fetch` | Descargar archivos vía HTTP/FTP desde el router |
| `GET /rest/tool/mac-server` | Servidor MAC-Winbox/Telnet |

## 11. Logs

| Path | Descripción |
|---|---|
| `GET /rest/log` | Logs del sistema (soporta `.proplist` y `.query` para filtrar por topic) |
| `GET/PUT/PATCH/DELETE /rest/system/logging` | Reglas de logging (qué se registra) |
| `GET/PUT/PATCH/DELETE /rest/system/logging/action` | Acciones de logging (disk, remote syslog, email) |

## 12. Archivos y respaldo

| Path | Descripción |
|---|---|
| `GET/DELETE /rest/file` | Archivos en el router (backups, scripts, certificados) |
| `POST /rest/file/print` con `oid` | Metadatos extendidos de archivos |

## 13. Contenedores (RouterOS v7.4+, requiere arquitectura ARM/ARM64/x86)

| Path | Descripción |
|---|---|
| `GET/PUT/PATCH/DELETE /rest/container` | Contenedores Docker-like |
| `GET/PUT/PATCH/DELETE /rest/container/config` | Configuración del registry/red de contenedores |
| `GET/PUT/DELETE /rest/container/mounts` | Volúmenes montados |

---

## Notas operativas importantes

- **No existe un comando "monitor" continuo vía REST** (a diferencia de la consola). Para `interface/monitor`, `wireless/monitor`, etc., siempre agregar el parámetro `"once":""` para obtener una sola lectura.
- **Un solo recurso por `PUT`.** No se pueden crear múltiples registros en una sola request.
- Todos los valores en las respuestas JSON vienen como **strings**, incluso números y booleanos (`"disabled":"false"`, no `false`).
- Para mover el orden de reglas (firewall, mangle, queue) se usa `POST /rest/<menu>/move` con dos `.id`.
- El error 406 (`Not Acceptable`) suele indicar que el comando existe pero el verbo HTTP usado no aplica a ese path (ej. intentar `DELETE` sobre algo que no es un registro individual).
- Con `www-ssl`, si usas certificado autofirmado, debes importarlo como confiable en el cliente o usar `-k` (curl) / `verify_none` solo en entornos de laboratorio — nunca en producción.
