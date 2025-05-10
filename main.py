from socket import socket, timeout, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR
from server.packet import HOST, PORT
from server import Handle
from server.logger import logger
from server.world import world
from server.proxy import proxy
from threading import Thread
from server.tools import Tool
import sys

if __name__ == "__main__":
    with socket(AF_INET, SOCK_STREAM) as server:
        server.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(5)
        server.settimeout(1.0)  # Helps with keyboard interrupts
        logger.info(f"🟢 Minecraft server running on {HOST}:{PORT}")

        try:
            world.start()
            proxy.start()
            Tool.start_fake_lan_server("Python LAN Server", PORT)
            # command_thread = Thread(target=command_handler, daemon=True)
            # command_thread.start()

            while True:
                try:
                    client, addr = server.accept()
                    client.settimeout(None)  # Timeout for client operations
                    thread = Thread(target=Handle.client, args=(client,), daemon=True)
                    thread.start()
                except timeout:
                    continue
        except KeyboardInterrupt:
            logger.info("🛑 Server shutting down...")
