import os
import time
import asyncio
import threading
import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import IoTConfig, MQTTSubscription, MQTTMessageCache

class MQTTDaemon:
    _instance = None
    
    def __init__(self):
        self.clients = {}  # id_usuario -> mqtt.Client
        self.lock = threading.Lock()
        self.running = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        id_usuario = userdata.get('id_usuario')
        print(f"[MQTT Daemon] Usuario {id_usuario} reconectado. Rc: {rc}")
        if rc == 0:
            self._resubscribe(id_usuario, client)

    def _on_message(self, client, userdata, msg):
        id_usuario = userdata.get('id_usuario')
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        print(f"[MQTT Daemon] Msj nuevo | Usuario: {id_usuario} | Topic: {topic} | Body: {payload}")
        
        # Save payload to database cache logic
        db: Session = SessionLocal()
        try:
            cache = db.query(MQTTMessageCache).filter(
                MQTTMessageCache.id_usuario == id_usuario,
                MQTTMessageCache.topic == topic
            ).first()
            
            if cache:
                cache.payload = payload
            else:
                new_cache = MQTTMessageCache(
                    id_usuario=id_usuario,
                    topic=topic,
                    payload=payload
                )
                db.add(new_cache)
            db.commit()
        except Exception as e:
            print(f"[MQTT Daemon] Error guardando cache MQTT: {e}")
        finally:
            db.close()

    def _resubscribe(self, id_usuario, client):
        db: Session = SessionLocal()
        try:
            subs = db.query(MQTTSubscription).filter(MQTTSubscription.id_usuario == id_usuario).all()
            for sub in subs:
                client.subscribe(sub.topic)
                print(f"[MQTT Daemon] Usuario {id_usuario} re-suscrito a {sub.topic}")
        finally:
            db.close()

    def add_or_update_client(self, id_usuario: int):
        with self.lock:
            # Desconectar y limpiar si ya existía
            if id_usuario in self.clients:
                self.clients[id_usuario].loop_stop()
                self.clients[id_usuario].disconnect()
                del self.clients[id_usuario]

            db = SessionLocal()
            try:
                config = db.query(IoTConfig).filter(IoTConfig.id_usuario == id_usuario).first()
                if not (config and config.mqtt_auto_connect and config.mqtt_broker):
                    return
                
                # Intentar crear cliente paho v2
                try:
                    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, userdata={'id_usuario': id_usuario})
                except AttributeError:
                    client = mqtt.Client(userdata={'id_usuario': id_usuario})
                    
                if config.mqtt_user and config.mqtt_password:
                    client.username_pw_set(config.mqtt_user, config.mqtt_password)

                client.on_connect = self._on_connect
                client.on_message = self._on_message

                host = config.mqtt_broker.replace("mqtts://", "").replace("mqtt://", "").strip()
                port = config.mqtt_port if config.mqtt_port else 1883
                
                try:
                    client.connect(host, port, 60)
                    client.loop_start()
                    self.clients[id_usuario] = client
                    self._resubscribe(id_usuario, client)
                    print(f"[MQTT Daemon] Hilo iniciado para Usuario {id_usuario}")
                except Exception as e:
                    print(f"[MQTT Daemon] Fallo al iniciar hilo para Usuario {id_usuario}: {e}")
            finally:
                db.close()

    def kill_client(self, id_usuario: int):
        with self.lock:
            if id_usuario in self.clients:
                self.clients[id_usuario].loop_stop()
                self.clients[id_usuario].disconnect()
                del self.clients[id_usuario]
                print(f"[MQTT Daemon] Hilo terminado para Usuario {id_usuario}")


    def trigger_hot_reload(self, id_usuario: int):
        """Dispara recarga para que el demonio re-lea subs y reconecte el cliente del usuario"""
        self.add_or_update_client(id_usuario)

    def start_daemon(self):
        if self.running:
            return
        self.running = True
        print("[MQTT Daemon] Iniciando Bootstrapping Maestro")
        db = SessionLocal()
        try:
            # Buscar usuarios con mqtt_auto_connect encendido
            configs = db.query(IoTConfig).filter(IoTConfig.mqtt_auto_connect == True).all()
            for config in configs:
                self.add_or_update_client(config.id_usuario)
        finally:
            db.close()
