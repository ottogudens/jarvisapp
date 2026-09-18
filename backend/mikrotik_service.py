import requests
import urllib3

# Suprime warnings de certificados autofirmados (comunes en MikroTik) — no oculta
# errores de conexión, solo el warning de verificación de certificado.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Verbos/paths que RouterOS trata como mutación de estado. Se usa para clasificar
# si un comando raw requiere confirmación antes de ejecutarse (ver mikrotik_tools.py).
DESTRUCTIVE_SUFFIXES = ("/add", "/set", "/remove", "/enable", "/disable", "/move")
DESTRUCTIVE_KEYWORDS = (
    "/reboot", "/shutdown", "/backup/load", "/routerboard/upgrade",
    "/package/update", "/reset-configuration", "/password",
)


class MikrotikService:
    def __init__(self, ip: str, username: str, password: str, port: int = 443, use_https: bool = True, timeout: int = 25):
        self.ip = ip
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        scheme = "https" if use_https else "http"
        self.base_url = f"{scheme}://{self.ip}:{self.port}/rest"

    def _request(self, method: str, path: str, data=None, query: dict = None):
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method,
                url,
                auth=(self.username, self.password),
                json=data if method != "GET" else None,
                params=query if method == "GET" else None,
                verify=False,
                timeout=self.timeout,
            )
            # Intenta parsear el cuerpo de la respuesta SIEMPRE, incluso en error,
            # porque RouterOS devuelve detalle útil (ej. {"error":404,"message":"No such command"})
            try:
                body = response.json()
            except ValueError:
                body = response.text

            if not response.ok:
                return {
                    "error": True,
                    "status_code": response.status_code,
                    "detail": body,
                }
            return body
        except requests.exceptions.SSLError as e:
            return {"error": True, "status_code": None, "detail": f"Error SSL/TLS: {e}. Verifica que 'www-ssl' esté habilitado en /ip/service del router."}
        except requests.exceptions.ConnectionError as e:
            return {"error": True, "status_code": None, "detail": f"No se pudo conectar al router ({self.base_url}): {e}. Verifica IP/puerto y que el servicio REST esté habilitado y accesible."}
        except requests.exceptions.Timeout:
            return {"error": True, "status_code": None, "detail": f"Timeout tras {self.timeout}s. El comando puede ser demasiado pesado (torch, bandwidth-test) — acótalo con parámetros de duración/cantidad."}
        except requests.exceptions.RequestException as e:
            return {"error": True, "status_code": None, "detail": str(e)}

    def get_system_resource(self):
        """Returns CPU load, uptime, free memory, etc."""
        return self._request("GET", "/system/resource")

    def get_interfaces(self):
        """List all interfaces and their traffic."""
        return self._request("GET", "/interface")

    def get_dhcp_leases(self):
        """List connected devices via DHCP."""
        return self._request("GET", "/ip/dhcp-server/lease")

    @staticmethod
    def is_destructive(path: str) -> bool:
        """Determina si un path de la REST API muta estado (requiere confirmación)."""
        p = path.lower().rstrip("/")
        if any(p.endswith(suf) for suf in DESTRUCTIVE_SUFFIXES):
            return True
        if any(kw in p for kw in DESTRUCTIVE_KEYWORDS):
            return True
        return False

    def execute_raw(self, path: str, params: dict = None):
        """
        Ejecuta cualquier path de la REST API de MikroTik.
        - Si el path es de solo lectura (no termina en /add,/set,/remove,/enable,/disable,/move
          y no contiene comandos de sistema destructivos), se ejecuta como GET y los `params`
          se envían como filtros de query string.
        - Si el path es destructivo, se ejecuta como POST con `params` como body — el llamador
          (mikrotik_tools.py) es responsable de exigir confirmación antes de invocar esto.
        """
        # "All API features are available via POST. Encode the command word in the URL"
        # Since this method receives RouterOS commands (e.g. /ping, /ip/address/print), 
        # it must use POST. GET is only for pure resource paths (e.g. /ip/address).
        return self._request("POST", path, data=params)
