import socket
import json
import struct
from typing import Tuple, Optional
from server.vars import Var
from server.logger import logger

# HOST = "127.0.0.1"
HOST = "0.0.0.0"
PORT = 25565

# Custom MOTD Data
MOTD_DATA = {
    "version": {
        "name": "1.21.4",  # Server brand helps compatibility
        "protocol": -1  # Must exactly match client version
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
        "text": "§aPython MOTD Server\n§7Running on Protocol 770"
    },
    "favicon": "data:image/png;base64,<base64>",  # Optional
    "enforcesSecureChat": False,  # Important for 1.19+ clients
    "previewsChat": False  # Important for 1.19+ clients
}

class Packet():
    def __init__(self):
        from Crypto.PublicKey import RSA
        self.private_key = RSA.generate(1024)  # private key (and container for public key info)
        self.public_key = self.private_key.publickey()  # public key derived from the private key

    def recv_exactly(self, conn: socket.socket, length: int) -> Optional[bytes]:
        """Reads exactly length bytes with timeout handling"""
        data = b""
        while len(data) < length:
            try:
                chunk = conn.recv(length - len(data))
            except socket.timeout:
                return None
            if not chunk:
                return None
            data += chunk
        return data

    def recv_packet(self, conn: socket.socket) -> Tuple[Optional[int], bytes]:
        """Receives a full Minecraft packet (properly handles packet length)"""
        # Read packet length
        packet_length, _ = Var.read_varint(conn)
        if packet_length is None or packet_length < 0:
            return None, b""
        
        # Read full packet data
        packet_data = self.recv_exactly(conn, packet_length)
        if not packet_data:
            return None, b""
        
        # Extract packet ID
        packet_id, bytes_read = Var.read_varint_from_bytes(packet_data)
        if packet_id is None:
            return None, b""
        
        # Remaining data is payload
        logger.debug(f"📥 Packet ID: {packet_id}, Length: {packet_length}, Data: {packet_data}")
        return packet_id, packet_data[bytes_read:]

    def send_packet(self, conn: socket.socket, packet_id: int, payload: bytes = b"") -> None:
        """Sends a properly formatted Minecraft packet."""
        packet = Var.write_varint(packet_id) + payload
        logger.debug(f"📤 Packet ID: {packet_id}, Length: {len(packet)}, Data: {packet}")

        conn.sendall(Var.write_varint(len(packet)) + packet)
    
    def enable_encryption(self, secret: bytes):
        from Crypto.Cipher import AES
        """
        Enables AES encryption for all subsequent packets.
        
        This function sets up an AES cipher in CFB mode with an 8-bit segment size (CFB8),
        which is the mode used by Minecraft, using the provided secret (16 bytes) as both key and IV.
        
        After calling this, your send_packet method should check for encryption and encrypt accordingly.
        """
        # Initialize AES ciphers for both encryption and decryption.
        self.encrypt_cipher = AES.new(secret, AES.MODE_CFB, iv=secret, segment_size=8)
        self.decrypt_cipher = AES.new(secret, AES.MODE_CFB, iv=secret, segment_size=8)
        self.encryption_enabled = True
        print("🔐 Encryption enabled")

    def handle_handshake(self, conn: socket.socket) -> int:
        """Handles the initial handshake packet."""
        packet_id, data = self.recv_packet(conn)
        if packet_id != 0x00:
            logger.warn(f"⚠️ Expected handshake (0x00), got {packet_id}")
            return False
        
        # Parse handshake data directly from the bytes
        offset = 0
        
        # Read protocol version
        protocol_version, bytes_read = Var.read_varint_from_bytes(data[offset:])
        offset += bytes_read
        
        # Read server address length
        addr_len, bytes_read = Var.read_varint_from_bytes(data[offset:])
        offset += bytes_read
        
        # Read server address
        server_addr = data[offset:offset+addr_len].decode('utf-8')
        offset += addr_len
        
        # Read server port
        server_port = struct.unpack('>H', data[offset:offset+2])[0]
        offset += 2
        
        # Read next state
        next_state, _ = Var.read_varint_from_bytes(data[offset:])
        
        logger.debug(f"🔍 Handshake: version={protocol_version}, addr={server_addr}:{server_port}, next={next_state}")
        return next_state, protocol_version, f"{server_addr}:{server_port}"

    def handle_status_request(self, conn, protocol_version):
        try:
            # Wait for status request with timeout
            packet_id, _ = self.recv_packet(conn)
            if packet_id is None:
                logger.warn("ℹ️ No status request received (client might have disconnected)")
                return
            if packet_id != 0x00:
                logger.warn(f"⚠️ Expected status request (0x00), got {packet_id}")
                return

            # Send response
            if (MOTD_DATA["version"]["protocol"] == -1):
                response = MOTD_DATA.copy()
                response["version"]["protocol"] = protocol_version
                response = json.dumps(response)
            else:
                response = json.dumps(MOTD_DATA)
            response_data = Var.write_varint(len(response)) + response.encode('utf-8')
            self.send_packet(conn, 0x00, response_data)
            logger.debug("✅ Sent status response")
        except socket.timeout:
            logger.warn("ℹ️ Timed out waiting for status request")

    def handle_ping(self, conn):
        try:
            # Wait for ping with shorter timeout
            conn.settimeout(2.0)  # Shorter timeout just for ping
            packet_id, payload = self.recv_packet(conn)
            if packet_id is None:
                logger.warn("ℹ️ No ping received (normal for some clients)")
                return
            if packet_id != 0x01:
                logger.warn(f"⚠️ Expected ping (0x01), got {packet_id}")
                return
                
            self.send_packet(conn, 0x01, payload)
            logger.debug("✅ Responded to ping")
        except socket.timeout:
            logger.warn("ℹ️ Timed out waiting for ping (normal)")

    def playerId(self):
        # Make sure playerIds exists
        if not hasattr(self, 'playerIds'):
            self.playerIds = set()

        # Find the smallest unused ID starting from 0
        i = 0
        while i in self.playerIds:
            i += 1

        self.playerIds.add(i)
        return i

    def handle_ingame_login(self, player):
        player.Id = self.playerId()
        payload = (
            Var.write_int(player.Id) + #Player's id
            Var.write_bool(False) + #Show hardcore hearts
            Var.write_identifiers(["minecraft:overworld"]) + #All Dimension Names
            Var.write_varint(20) + #Max players (ignored)
            Var.write_varint(10) + #View distance
            Var.write_varint(10) + #Simulation distance
            Var.write_bool(False) + #Reduced Debug Info (F3)
            Var.write_bool(False) + #Enable respawn screen
            Var.write_bool(False) + #Do limited Crafting (ignored)
            Var.write_varint(0) + #Dimension Type
            Var.write_string("minecraft:overworld") + #Dimension Name
            Var.write_long(4172702371561058553) + #Hashed seed
            Var.write_u8(1) + #Gamemode: 0=Survival 1=Creative 2=Adventure 3=Spectator
            Var.write_byte(-1) + #Previous Game mode
            Var.write_bool(False) + #Is debug world type
            Var.write_bool(True) + #Is flat
            Var.write_bool(False) + #Has death location
            Var.write_varint(0) + #Portal cooldown
            Var.write_varint(0) + #Sea level
            Var.write_bool(False) #Enforces Secure Chat
        )
        player.send_packet(0x2b, payload)