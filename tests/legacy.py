#!/usr/bin/env python3
import socket
import threading
import os
import struct
import uuid
import hashlib
import requests
from typing import Tuple, Optional

from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_v1_5

# --- Helper for Offline UUID Generation ---
def generate_offline_uuid(username: str) -> str:
    """Generates an offline-mode UUID using UUID v3."""
    return str(uuid.uuid3(uuid.NAMESPACE_DNS, "OfflinePlayer:" + username))

# --- Packet Class Definition ---
class Packet:
    def __init__(self):
        # Generate ephemeral RSA key pair for this connection.
        self.private_key = RSA.generate(1024)  # (For production, consider 2048-bit keys.)
        self.public_key = self.private_key.publickey()
        print("Ephemeral RSA keys generated for this connection.")
        
        # Encryption and login state
        self.encryption_enabled = False
        self.shared_secret = None  # Will be set if encryption handshake occurs.
        self.verify_token = None   # Will be generated in encryption request.
        self.username = None       # Set during handshake/login.
        self.encrypt_cipher = None

    # --- Helpers for VarInt and Strings ---
    def write_varint(self, value: int) -> bytes:
        """Encodes an integer into Minecraft’s VarInt format."""
        data = bytearray()
        while True:
            temp = value & 0x7F
            value >>= 7
            if value != 0:
                temp |= 0x80
            data.append(temp)
            if value == 0:
                break
        return bytes(data)

    def write_string(self, s: str) -> bytes:
        """Encodes a string preceded by its VarInt length."""
        encoded = s.encode('utf-8')
        return self.write_varint(len(encoded)) + encoded

    # --- Functions for Receiving from Socket ---
    def read_varint(self, conn: socket.socket) -> Tuple[Optional[int], int]:
        """Reads a VarInt from the connection (one byte at a time)."""
        num = 0
        num_bytes = 0
        for i in range(5):
            chunk = conn.recv(1)
            if not chunk:
                return None, num_bytes
            num |= (chunk[0] & 0x7F) << (7 * i)
            num_bytes += 1
            if not (chunk[0] & 0x80):
                return num, num_bytes
        return None, num_bytes

    def recv_exactly(self, conn: socket.socket, length: int) -> bytes:
        """Receives exactly 'length' bytes from the connection."""
        data = b""
        while len(data) < length:
            chunk = conn.recv(length - len(data))
            if not chunk:
                break
            data += chunk
        return data

    def read_varint_from_bytes(self, data: bytes, offset: int = 0) -> Tuple[Optional[int], int]:
        """Reads a VarInt from data starting at offset."""
        num = 0
        num_bytes = 0
        for i in range(5):
            if offset + i >= len(data):
                return None, num_bytes
            b = data[offset + i]
            num |= (b & 0x7F) << (7 * i)
            num_bytes += 1
            if not (b & 0x80):
                break
        return num, num_bytes

    # --- recv_packet and send_packet ---
    def recv_packet(self, conn: socket.socket) -> Tuple[Optional[int], bytes]:
        """
        Receives a full Minecraft packet:
        • Reads the packet length (VarInt) and then exactly that many bytes.
        • Extracts the packet ID (a VarInt at the start) and returns (packet_id, payload).
        """
        packet_length, _ = self.read_varint(conn)
        if packet_length is None or packet_length < 0:
            return None, b""
        packet_data = self.recv_exactly(conn, packet_length)
        if not packet_data:
            return None, b""
        packet_id, bytes_read = self.read_varint_from_bytes(packet_data)
        if packet_id is None:
            return None, b""
        print(f"📥 Packet ID: {packet_id}, Length: {packet_length}, Data: {packet_data}")
        return packet_id, packet_data[bytes_read:]

    def send_packet(self, conn: socket.socket, packet_id: int, payload: bytes = b"") -> None:
        """
        Constructs and sends a properly formatted Minecraft packet.
        The packet = VarInt(packet_id) + payload, 
        then prefixed with its length (VarInt). If encryption is enabled, encrypts the packet.
        """
        packet = self.write_varint(packet_id) + payload
        print(f"📤 Packet ID: {packet_id}, Length (plaintext): {len(packet)}, Data: {packet}")
        if self.encryption_enabled:
            packet = self.encrypt_cipher.encrypt(packet)
            print(f"🔒 Packet ID: {packet_id}, Encrypted Length: {len(packet)}, Data: {packet}")
        full_packet = self.write_varint(len(packet)) + packet
        conn.sendall(full_packet)

    # --- Dummy Handshake and Login Methods ---
    def handle_handshake(self, conn: socket.socket):
        """
        Dummy handshake: sets the username to 'Proficode' and returns 2 (login state).
        (A real implementation would parse the client's handshake packet.)
        """
        print("Simulated handshake: setting username to 'Proficode' and entering login state.")
        self.username = "Proficode"
        return 2

    def handle_status_request(self, conn: socket.socket):
        print("Handling status request (dummy).")

    def handle_ping(self, conn: socket.socket):
        print("Handling ping (dummy).")

    def handle_login_start(self, conn: socket.socket):
        print(f"🔓 Login Start received for username: {self.username}")
        return True

    def handle_play_state(self, conn: socket.socket):
        print("Entered play state. (Simulation ends here.)")

    # --- Encryption Handshake Methods ---
    def send_encryption_request(self, conn: socket.socket):
        """
        Sends an Encryption Request (packet ID 0x01) containing:
          - Server ID (empty string),
          - Ephemeral public key in DER format (length-prefixed),
          - A random verify token (length-prefixed).
        """
        self.verify_token = os.urandom(4)
        server_id = ""
        public_key_bytes = self.public_key.exportKey('DER')
        payload = self.write_string(server_id)
        payload += self.write_varint(len(public_key_bytes)) + public_key_bytes
        payload += self.write_varint(len(self.verify_token)) + self.verify_token
        payload += b"\x01" #Should authentificate true: \x01 false: \x00
        self.send_packet(conn, 0x01, payload)
        print("Sent encryption request.")

    def handle_encryption_response(self, conn: socket.socket, data: bytes):
        """
        Dummy encryption response handling.
        In a real server, you'd:
          • Decrypt the shared secret and verify token using the private key.
          • Check the token.
          • Enable AES encryption with the shared secret.
        For this demo, if the client initiated encryption (packet id == expected),
        we simulate it by setting a dummy 16-byte shared secret.
        """
        dummy_shared_secret = b'sixteen byte key'  # Exactly 16 bytes.
        self.shared_secret = dummy_shared_secret
        self.enable_encryption(dummy_shared_secret)
        print("Handled encryption response. AES encryption enabled.")

    def enable_encryption(self, secret: bytes):
        """Enables AES encryption (CFB8 mode) for subsequent packets using 'secret'."""
        self.encrypt_cipher = AES.new(secret, AES.MODE_CFB, iv=secret, segment_size=8)
        self.encryption_enabled = True

    def compute_server_hash(self, server_id: str, shared_secret: bytes, public_key_bytes: bytes) -> str:
        """Computes the SHA-1 server hash as expected by Mojang's session server."""
        h = hashlib.sha1()
        h.update(server_id.encode('utf-8'))
        h.update(shared_secret)
        h.update(public_key_bytes)
        digest = h.digest()
        num = int.from_bytes(digest, byteorder='big', signed=True)
        return format(num, 'x')

    def send_login_success(self, conn: socket.socket, uuid_str: str, username: str, properties: list):
        """
        Sends a Login Success packet (packet ID 0x02) including:
          - UUID as a string,
          - Username,
          - A VarInt count of properties followed by each property's name, value, and signature.
        """
        payload = b""
        payload += self.write_string(uuid_str)
        payload += self.write_string(username)
        payload += self.write_varint(len(properties))
        for prop in properties:
            payload += self.write_string(prop.get("name", ""))
            payload += self.write_string(prop.get("value", ""))
            payload += self.write_string(prop.get("signature", ""))
        self.send_packet(conn, 0x02, payload)
        print(f"Sent Login Success for {username} (UUID: {uuid_str}).")

# --- Client Connection Handler ---
def handle_client(conn: socket.socket, addr):
    try:
        print(f"🔗 New connection from {addr}")
        packet = Packet()  # New per-connection Packet instance.
        
        # Simulate handshake.
        next_state = packet.handle_handshake(conn)
        if next_state is None:
            return

        if next_state == 1:
            packet.handle_status_request(conn)
            packet.handle_ping(conn)

        elif next_state == 2:
            if packet.handle_login_start(conn):
                # --- Begin Encryption Handshake (only in state 2) ---
                packet.send_encryption_request(conn)
                response_packet_id, response_payload = packet.recv_packet(conn)
                # If the client did not initiate encryption (packet id == 0), proceed offline.
                EXPECTED_ENCRYPTION_RESPONSE_ID = 0x02  # Expected when client encrypts.
                if response_packet_id == 0:
                    print("Client did not initiate encryption handshake; proceeding in offline mode (no encryption).")
                    # Set a dummy known shared secret (here, empty bytes)
                    packet.shared_secret = b""
                elif response_packet_id == EXPECTED_ENCRYPTION_RESPONSE_ID:
                    packet.handle_encryption_response(conn, response_payload)
                else:
                    raise Exception("Unexpected packet received during encryption handshake.")
                # --- End Encryption Handshake ---
                
                # Compute the server hash. (If in offline mode, shared_secret is set to b"".)
                server_hash = packet.compute_server_hash("", packet.shared_secret, packet.public_key.exportKey("DER"))
                print(f"Computed server hash: {server_hash}")
                session_url = (
                    f"https://sessionserver.mojang.com/session/minecraft/hasJoined"
                    f"?username={packet.username}&serverId={server_hash}"
                )
                try:
                    response = requests.get(session_url, timeout=10)
                    if response.status_code == 200:
                        online_uuid = response.json().get("id")
                        print("✅ Online mode: session verified by Mojang.")
                        uuid_to_use = online_uuid
                    else:
                        print("⚠️ Online mode failed: falling back to offline mode.")
                        uuid_to_use = generate_offline_uuid(packet.username)
                except Exception as e:
                    print("⚠️ Online session verification error; using offline mode.", e)
                    uuid_to_use = generate_offline_uuid(packet.username)
                
                properties = [{
                    "name": "textures",
                    "value": "base64EncodedData",  # Replace with actual texture data if available.
                    "signature": ""
                }]
                packet.send_login_success(conn, uuid_to_use, packet.username, properties)
                packet.handle_play_state(conn)
            else:
                print("❌ Login start failed.")
        else:
            print(f"⚠️ Unknown state received: {next_state}")
    except Exception as e:
        print(f"❌ Error handling client {addr}: {e}")
    finally:
        conn.close()
        print(f"🔌 Connection from {addr} closed.")

# --- Main Server Loop ---
def main():
    HOST = "0.0.0.0"
    PORT = 25565
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"🌐 Server listening on {HOST}:{PORT}")

    while True:
        conn, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
