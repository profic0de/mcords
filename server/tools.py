import zlib
import socket
import dns.resolver
import time
import threading
from server.vars import Var

class Tool:
    @staticmethod
    def resolve_minecraft_srv(domain: str, port: int = 25565) -> tuple[str, int]:
        """
        Returns ip with port from a minecraft SRV record.\n
        Example:
        ```python
        ip, port = Tool.resolve_minecraft_srv("mc.hypixel.net")
        print(f"Hypixel resolved to: {ip}:{port}")
        """
        if port != 25565:
            return socket.gethostbyname(domain), port
        try:
            answers = dns.resolver.resolve(f"_minecraft._tcp.{domain}", "SRV")
            for rdata in answers:
                target = str(rdata.target).rstrip('.')
                return socket.gethostbyname(target), rdata.port
        except Exception:
            return socket.gethostbyname(domain), port

    @staticmethod
    def start_fake_lan_server(motd: str, port: int, interval: float = 1.5):
        """
        Example usage
        ```python
        Tool.start_fake_lan_server("Python LAN Server", 25567)
        """
        def broadcast():
            MCAST_GRP = '224.0.2.60'
            MCAST_PORT = 4445
            msg = f"[MOTD]{motd}[/MOTD][AD]{port}[/AD]".encode('utf-8')
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            
            while True:
                try:
                    sock.sendto(msg, (MCAST_GRP, MCAST_PORT))
                except:
                    time.sleep(interval)
                time.sleep(interval)

        threading.Thread(target=broadcast, daemon=True).start()

    @staticmethod
    def parse_packet(data: bytes, return_len: bool = False):
        # print(f"🔵 [P] {data}")# bytes - {data}")

        # Step 1: Read packet length VarInt
        packet_length, len_len = Var.read_varint_from_bytes(data)

        # Step 2: Read packet ID VarInt from the remaining data
        packet_id, id_len = Var.read_varint_from_bytes(data[len_len:])

        # Step 3: Slice payload (starts after both VarInts)
        payload = data[len_len + id_len:]
        # if return_len:
        #     return packet_id, payload, len_len + id_len

        return packet_id, payload

    @staticmethod
    def compress_packet(data: bytes, threshold: int) -> bytes:
        if len(data) >= threshold:
            data_length = Var.write_varint(len(data))
            packet_id, offset = Var.read_varint_from(data)
            packet_id = Var.write_varint(packet_id)
            packet = zlib.compress(packet_id) + zlib.compress(data[offset:])
            return Var.write_varint(len(data_length)+len(packet)) + data_length + packet
        else:
            data_length = Var.write_varint(0)
            packet = data
            return Var.write_varint(len(data_length)+len(packet)) + data_length + packet

    @staticmethod
    def decompress_packet(data: bytes) -> bytes:
        packet_lenght, offset = Var.read_varint_from(data)
        data_length, delta = Var.read_varint_from(data, offset); offset += delta

        if data_length > 0:
            decompressed_data = zlib.decompress(data[offset:])
        else:    
            decompressed_data = data[offset:]

        return Var.write_varint(len(decompressed_data)) + decompressed_data


# ip, port = Tool.resolve_minecraft_srv("mc.hypixel.net")
# print(f"Hypixel resolved to: {ip}:{port}")
