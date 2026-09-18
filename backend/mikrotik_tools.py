from backend.database import SessionLocal
from backend.models import MikrotikRouter
from backend.mikrotik_service import MikrotikService
from backend.crypto_utils import decrypt_secret


def _get_service(id_router: int):
    with SessionLocal() as db:
        router = db.query(MikrotikRouter).filter(MikrotikRouter.id_router == id_router).first()
        if not router:
            return None, {"error": "Router no encontrado"}
        password = decrypt_secret(router.password)
        use_https = False if router.api_port in (80, 8080) else True
        svc = MikrotikService(
            router.ip_address,
            router.username,
            password,
            router.api_port,
            use_https=use_https,
        )
        return svc, None


def obtener_estado_red_mikrotik(id_router: int, ping_target: str = None) -> dict:
    """Obtiene el estado general de la red, uso de CPU, uptime y memoria del router MikroTik especificado."""
    svc, err = _get_service(id_router)
    if err:
        return err
    resultado = svc.get_system_resource()
    if ping_target:
        ping = svc.execute_raw("/ping", {"address": ping_target, "count": "4"})
        if isinstance(resultado, list):
            resultado = {"system_resource": resultado, "ping": ping}
        elif isinstance(resultado, dict):
            resultado["ping"] = ping
    return resultado


def listar_interfaces_mikrotik(id_router: int, filter_name: str = None) -> dict:
    """Obtiene la lista de interfaces de red del router MikroTik especificado y su estado actual (link, trafico)."""
    svc, err = _get_service(id_router)
    if err:
        return err
    return svc.get_interfaces()


def ver_clientes_dhcp_mikrotik(id_router: int) -> dict:
    """Obtiene la lista de dispositivos conectados a la red del router MikroTik especificado a través del servidor DHCP."""
    svc, err = _get_service(id_router)
    if err:
        return err
    return svc.get_dhcp_leases()


def comando_mikrotik_avanzado(id_router: int, comando: str, parametros: dict = None, confirmar: bool = False) -> dict:
    """
    Ejecuta cualquier ruta arbitraria de la API REST de MikroTik (ej. /ip/address/print).
    Usar solo si las demás herramientas no son suficientes.

    IMPORTANTE PARA EL MODELO: si el comando es de solo lectura (print, monitor, etc.),
    se ejecuta de inmediato. Si el comando MODIFICA el router (rutas que terminan en
    /add, /set, /remove, /enable, /disable, /move, o acciones como /reboot,
    /shutdown, /backup/load, /routerboard/upgrade), esta función NO lo ejecutará a
    menos que `confirmar=True`. Si no confirmas, recibirás de vuelta una vista previa
    ("requiere_confirmacion") con el comando exacto que se ejecutaría — debes mostrar
    ese comando al usuario en texto claro y esperar su aprobación explícita antes de
    volver a llamar esta misma función con confirmar=True.
    """
    if comando.startswith("/rest"):
        comando = comando[5:]
        if not comando.startswith("/"):
            comando = "/" + comando
            
    svc, err = _get_service(id_router)
    if err:
        return err

    if MikrotikService.is_destructive(comando) and not confirmar:
        return {
            "requiere_confirmacion": True,
            "comando_propuesto": comando,
            "parametros_propuestos": parametros,
            "mensaje": (
                "Este comando modifica el estado del router. Muestra este comando y "
                "parámetros exactos al usuario y pide confirmación explícita antes de "
                "reintentar con confirmar=True."
            ),
        }

    return svc.execute_raw(comando, parametros)


mikrotik_tools = [
    obtener_estado_red_mikrotik,
    listar_interfaces_mikrotik,
    ver_clientes_dhcp_mikrotik,
    comando_mikrotik_avanzado,
]
