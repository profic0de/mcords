from base64 import b64encode
import os

class Config:
    def __init__(self):
        self._properties = {}

        self._default_values = {
            "network-compression-threshold": "-1",
            "server-port": "25565",
            "online-mode": "true",
            "server-ip": "0.0.0.0",
            "max-players": "20",
            "version": "1.21.5",
            "motd": "A Minecraft Server"
        }

    def load(self):
        filepath = "server.properties"

        if not os.path.exists(filepath):
            with open(filepath, "w") as f:
                for key, value in self._default_values.items():
                    f.write(f"{key}={value}\n")

        self._properties.clear()
        with open(filepath, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    self._properties[key.strip()] = value.strip()

    def get(self, key, default=None):
        return self._properties.get(key, default)
    
    def icon(self, path="server-icon.png"):
        if not os.path.exists(path):
            return None  # or raise an exception if required

        with open(path, "rb") as img_file:
            encoded = b64encode(img_file.read()).decode("utf-8")
            return f"data:image/png;base64,{encoded}"

config = Config()
config.load()