import socket
import threading

class MinecraftProxy:
    def __init__(self, proxy_host, proxy_port, server_host, server_port):
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port
        self.server_host = server_host
        self.server_port = server_port

    @staticmethod
    def read_varint(data):
        value = 0
        shift = 0
        for i in range(len(data)):
            byte = data[i]
            value |= (byte & 0x7F) << shift
            shift += 7
            if not (byte & 0x80):
                return value, i + 1
        raise ValueError("VarInt too big")

    @staticmethod
    def parse_packet(data):
        length, offset = MinecraftProxy.read_varint(data)
        packet_id, id_offset = MinecraftProxy.read_varint(data[offset:])
        total_offset = offset + id_offset
        return length, packet_id, total_offset

    def start(self):
        print(f"🌐 Starting proxy on {self.proxy_host}:{self.proxy_port}")
        proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        proxy_socket.bind((self.proxy_host, self.proxy_port))
        proxy_socket.listen(5)
        print("✅ Proxy is ready to accept connections...")

        while True:
            client_conn, client_addr = proxy_socket.accept()
            print(f"🔗 Connection from {client_addr}")
            threading.Thread(target=self.handle_client, args=(client_conn,)).start()

    def handle_client(self, client_conn):
        try:
            server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_conn.connect((self.server_host, self.server_port))
            print("🔄 Connected to Minecraft server")

            threading.Thread(target=self.relay_data, args=(client_conn, server_conn, "Client -> Server")).start()
            threading.Thread(target=self.relay_data, args=(server_conn, client_conn, "Server -> Client")).start()
        except Exception as e:
            print(f"❌ Error handling client: {e}")
            client_conn.close()

    def relay_data(self, source, destination, direction):
        try:
            while True:
                data = source.recv(10000)
                if not data:
                    break

                try:
                    length, packet_id, offset = self.parse_packet(data)
                    self.process_packet(packet_id, data[offset:], direction)
                except Exception as e:
                    print(f"⚠️ Packet parse error: {e}")

                destination.sendall(data)
        except Exception as e:
            print(f"⚠️ Relay error ({direction}): {e}")
        finally:
            source.close()
            destination.close()
    
    def process_packet(self, packet_id, payload, direction):        
        """Custom packet processing logic."""

        if packet_id == 39:
            print(f"🎮 [{direction}] packet (0x{packet_id:02x}) sent: [{packet_id:02x}{payload.hex()}] [{payload}]")


# Configuration
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 25566
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 25567

proxy = MinecraftProxy(PROXY_HOST, PROXY_PORT, SERVER_HOST, SERVER_PORT)
proxy.start()
