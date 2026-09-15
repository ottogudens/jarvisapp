from backend.database import SessionLocal
from backend.models import MikrotikRouter
from backend.mikrotik_service import MikrotikService

def obtener_estado_red_mikrotik(router_id: int) -> dict:
    """Obtiene el estado general de la red, uso de CPU, uptime y memoria del router MikroTik especificado."""
    with SessionLocal() as db:
        router = db.query(MikrotikRouter).filter(MikrotikRouter.id_router == router_id).first()
        if not router: return {"error": "Router no encontrado"}
        svc = MikrotikService(router.ip_address, router.username, router.password, router.api_port)
        return svc.get_system_resource()

def listar_interfaces_mikrotik(router_id: int) -> dict:
    """Obtiene la lista de interfaces de red del router MikroTik especificado y su estado actual (link, trafico)."""
    with SessionLocal() as db:
        router = db.query(MikrotikRouter).filter(MikrotikRouter.id_router == router_id).first()
        if not router: return {"error": "Router no encontrado"}
        svc = MikrotikService(router.ip_address, router.username, router.password, router.api_port)
        return svc.get_interfaces()

def ver_clientes_dhcp_mikrotik(router_id: int) -> dict:
    """Obtiene la lista de dispositivos conectados a la red del router MikroTik especificado a través del servidor DHCP."""
    with SessionLocal() as db:
        router = db.query(MikrotikRouter).filter(MikrotikRouter.id_router == router_id).first()
        if not router: return {"error": "Router no encontrado"}
        svc = MikrotikService(router.ip_address, router.username, router.password, router.api_port)
        return svc.get_dhcp_leases()

def comando_mikrotik_avanzado(router_id: int, path: str, parametros: dict = None) -> dict:
    """Ejecuta cualquier ruta arbitraria de la API REST de MikroTik (ej. /ip/firewall/filter/add). Usar solo si las demás herramientas no son suficientes."""
    with SessionLocal() as db:
        router = db.query(MikrotikRouter).filter(MikrotikRouter.id_router == router_id).first()
        if not router: return {"error": "Router no encontrado"}
        svc = MikrotikService(router.ip_address, router.username, router.password, router.api_port)
        return svc.execute_raw(path, parametros)

mikrotik_tools = [
    obtener_estado_red_mikrotik,
    listar_interfaces_mikrotik,
    ver_clientes_dhcp_mikrotik,
    comando_mikrotik_avanzado
]
