import os
import json
import httpx
import paho.mqtt.client as mqtt
from typing import Optional, Dict, Any

class IoTService:
    """Servicio para controlar la integracion con Home Assistant y MQTT."""
    
    def __init__(self, db_session, id_usuario: int):
        from backend.models import IoTConfig
        self.db = db_session
        self.config = self.db.query(IoTConfig).filter(IoTConfig.id_usuario == id_usuario).first()

    def get_ha_headers(self) -> dict:
        if not self.config or not self.config.ha_token:
            raise Exception("No hay token de Home Assistant configurado para este usuario.")
        return {
            "Authorization": f"Bearer {self.config.ha_token}",
            "Content-Type": "application/json"
        }

    async def obtener_estado_dispositivo(self, entity_id: str) -> str:
        """Obtiene el estado de un dispositivo en Home Assistant."""
        if not self.config or not self.config.ha_url:
            return "Home Assistant no está configurado."
        
        url = f"{self.config.ha_url.rstrip('/')}/api/states/{entity_id}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.get_ha_headers(), timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    state = data.get("state")
                    attributes = data.get("attributes", {})
                    friendly_name = attributes.get("friendly_name", entity_id)
                    return f"Dispositivo '{friendly_name}' está en estado '{state}'."
                elif response.status_code == 404:
                    return f"No se encontró el dispositivo {entity_id}."
                else:
                    return f"Error {response.status_code} de Home Assistant."
        except Exception as e:
            return f"Excepción conectando a Home Assistant: {str(e)}"

    async def activar_dispositivo(self, entity_id: str, action: str = "turn_on", extra_data: Optional[Dict[str, Any]] = None) -> str:
        """Llama a un servicio de Home Assistant (ej. light.turn_on)."""
        if not self.config or not self.config.ha_url:
            return "Home Assistant no está configurado."
            
        domain = entity_id.split('.')[0]
        url = f"{self.config.ha_url.rstrip('/')}/api/services/{domain}/{action}"
        
        payload = {"entity_id": entity_id}
        if extra_data:
            payload.update(extra_data)
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=self.get_ha_headers(), json=payload, timeout=5.0)
                if response.status_code == 200:
                    return f"Comando '{action}' enviado exitosamente a {entity_id}."
                else:
                    return f"Error {response.status_code} al enviar comando a HA."
        except Exception as e:
            return f"Excepción conectando a Home Assistant: {str(e)}"

    def publicar_mensaje_mqtt(self, topic: str, payload: str) -> str:
        """Publica un mensaje a un broker MQTT remoto configurado por el usuario."""
        if not self.config or not self.config.mqtt_broker:
            return "MQTT Broker no está configurado."
            
        try:
            # Compatibilidad Paho MQTT v2.0+
            import paho.mqtt.client as mqtt
            try:
                client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            except AttributeError:
                client = mqtt.Client() # Fallback para v1.x
                
            if self.config.mqtt_user and self.config.mqtt_password:
                client.username_pw_set(self.config.mqtt_user, self.config.mqtt_password)
                
            port = self.config.mqtt_port if self.config.mqtt_port else 1883
            host = self.config.mqtt_broker.strip()
            
            use_tls = False
            if host.startswith("mqtts://"):
                use_tls = True
                host = host.replace("mqtts://", "")
            elif host.startswith("mqtt://"):
                host = host.replace("mqtt://", "")
                
            # Soporte TLS/SSL si usan servidores Cloud (HiveMQ, AWS, etc)
            if port == 8883 or str(port) == "8883" or use_tls:
                import ssl
                client.tls_set(cert_reqs=ssl.CERT_NONE)
                client.tls_insecure_set(True)
                
            client.connect(host, int(port), keepalive=60)
            client.publish(topic, payload)
            client.disconnect()
            return f"Mensaje publicado exitosamente en el tópico '{topic}'."
        except Exception as e:
            return f"Error publicando en MQTT: {str(e)}"
