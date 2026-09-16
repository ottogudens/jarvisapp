import requests
import urllib3

# Suppress SSL warnings since MikroTik often uses self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MikrotikService:
    def __init__(self, ip: str, username: str, password: str, port: int = 80):
        self.ip = ip
        self.username = username
        self.password = password
        self.port = port
        self.base_url = f"http://{self.ip}:{self.port}/rest"

    def _request(self, method: str, path: str, data=None):
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method,
                url,
                auth=(self.username, self.password),
                json=data,
                verify=False,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def get_system_resource(self):
        """Returns CPU load, uptime, free memory, etc."""
        return self._request("GET", "/system/resource")
        
    def get_interfaces(self):
        """List all interfaces and their traffic."""
        return self._request("GET", "/interface")

    def get_dhcp_leases(self):
        """List connected devices via DHCP."""
        return self._request("GET", "/ip/dhcp-server/lease")

    def execute_raw(self, path: str, params: dict = None):
        """Execute any arbitrary MikroTik API path. e.g. /ip/firewall/filter"""
        method = "POST" if params else "GET"
        return self._request(method, path, data=params)
