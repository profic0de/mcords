from server.config import config

MOTD_DATA = {
    "version": {
        "name": "1.21.8",  # Server brand helps compatibility
        "protocol": 772  # Must exactly match client version
    },
    "players": {
        "max": 1,  # Large number creates display space
        "online": 1,  # Must be ≥1 (zero hides hover in some clients)
        "sample": [
            {
                "name": "§aMain Text Line", 
                "id": "00000000-0000-0000-0000-000000000001"
            },
            {
                "name": "§7Secondary Text",
                "id": "00000000-0000-0000-0000-000000000002"
            }
        ]
    },
    "description": {
        "text": config.get("motd").replace("\\n", "\n")
    },
    "favicon": config.icon(),  # Optional
    "enforcesSecureChat": False,  # Important for 1.19+ clients
    "previewsChat": False  # Important for 1.19+ clients
}