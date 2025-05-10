import socket
import json
import struct
import time
import threading
from typing import Tuple, Optional

HOST = "0.0.0.0"
PORT = 25565

# Custom MOTD Data (as displayed on server list / status screen)
MOTD_DATA = {
    "version": {
        "name": "Paper 1.21",  # Server brand helps compatibility.
        "protocol": 770       # Must exactly match client version.
    },
    "players": {
        "max": 1,             # Large number creates display space.
        "online": 1,          # Must be ≥1 (zero hides hover in some clients).
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
    "favicon": "data:image/png;base64,<base64>",  # Optional favicon.
    "enforcesSecureChat": False,  # Important for 1.19+ clients.
    "previewsChat": False         # Important for 1.19+ clients.
}


def read_varint(conn: socket.socket) -> Tuple[Optional[int], bytes]:
    """Reads VarInt from socket with timeout handling."""
    data = b""
    num = 0
    for i in range(5):
        try:
            byte = conn.recv(1)
        except socket.timeout:
            return None, data
        if not byte:
            return None, data
        data += byte
        byte_val = byte[0]
        num |= (byte_val & 0x7F) << (7 * i)
        if not (byte_val & 0x80):
            return num, data
    return None, data  # Malformed VarInt


def recv_exactly(conn: socket.socket, length: int) -> Optional[bytes]:
    """Reads exactly length bytes with timeout handling."""
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


def write_varint(value: int) -> bytes:
    """Encodes an integer as a Minecraft VarInt."""
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value != 0:
            byte |= 0x80
        out.append(byte)
        if value == 0:
            break
    return bytes(out)


def read_varint_from_bytes(data: bytes) -> Tuple[int, int]:
    """Reads a VarInt from bytes and returns (value, bytes_consumed)."""
    num = 0
    bytes_read = 0
    for i in range(5):
        if len(data) <= bytes_read:
            raise ValueError("Not enough data for VarInt")
        byte = data[bytes_read]
        bytes_read += 1
        num |= (byte & 0x7F) << (7 * i)
        if not (byte & 0x80):
            break
    return num, bytes_read


def recv_packet(conn: socket.socket) -> Tuple[Optional[int], bytes]:
    """Receives a full Minecraft packet (handles packet length properly)."""
    packet_length, _ = read_varint(conn)
    if packet_length is None or packet_length < 0:
        return None, b""
    
    packet_data = recv_exactly(conn, packet_length)
    if not packet_data:
        return None, b""
    
    packet_id, bytes_read = read_varint_from_bytes(packet_data)
    if packet_id is None:
        return None, b""
    
    return packet_id, packet_data[bytes_read:]


def send_packet(conn: socket.socket, packet_id: int, payload: bytes = b"") -> None:
    """Sends a properly formatted Minecraft packet."""
    packet = write_varint(packet_id) + payload
    conn.sendall(write_varint(len(packet)) + packet)


def handle_handshake(conn: socket.socket) -> Optional[int]:
    """
    Handles the handshake packet.
    Returns the client's requested next state:
      1 for status (MOTD query) and 2 for login.
    """
    packet_id, data = recv_packet(conn)
    if packet_id != 0x00:
        print(f"⚠️ Expected handshake (0x00), got {packet_id}")
        return None
    
    offset = 0
    protocol_version, bytes_read = read_varint_from_bytes(data[offset:])
    offset += bytes_read
    
    addr_len, bytes_read = read_varint_from_bytes(data[offset:])
    offset += bytes_read
    
    server_addr = data[offset:offset+addr_len].decode('utf-8')
    offset += addr_len
    
    server_port = struct.unpack('>H', data[offset:offset+2])[0]
    offset += 2
    
    next_state, _ = read_varint_from_bytes(data[offset:])
    
    print(f"🔍 Handshake: version={protocol_version}, addr={server_addr}:{server_port}, next_state={next_state}")
    return next_state


def handle_status_request(conn: socket.socket):
    """
    Handles a status request, sending back the MOTD and the server metadata.
    This is normally seen in the server list.
    """
    try:
        packet_id, _ = recv_packet(conn)
        if packet_id is None:
            print("ℹ️ No status request received (client might have disconnected)")
            return
        if packet_id != 0x00:
            print(f"⚠️ Expected status request (0x00), got {packet_id}")
            return

        response = json.dumps(MOTD_DATA)
        response_data = write_varint(len(response)) + response.encode('utf-8')
        send_packet(conn, 0x00, response_data)
        print("✅ Sent status response (MOTD)")
    except socket.timeout:
        print("ℹ️ Timed out waiting for status request")


def handle_ping(conn: socket.socket):
    """
    Handles a ping packet.
    Replies with the same payload.
    """
    try:
        conn.settimeout(2.0)
        packet_id, payload = recv_packet(conn)
        if packet_id is None:
            print("ℹ️ No ping received (which can be normal)")
            return
        if packet_id != 0x01:
            print(f"⚠️ Expected ping (0x01), got {packet_id}")
            return
        send_packet(conn, 0x01, payload)
        print("✅ Responded to ping")
    except socket.timeout:
        print("ℹ️ Ping timed out (normal)")


def handle_login(conn: socket.socket):
    """
    Handles the login phase.
    Instead of progressing the login (and sending world data), the connection is held open indefinitely.
    The loop periodically checks if the client disconnects so that the thread can clean up.
    """
    print("💤 Login phase entered—connection will be held without sending further data.")
    conn.settimeout(1.0)
    try:
        while True:
            try:
                # Attempt to read a small amount to detect if the socket is closed.
                data = conn.recv(1024)
                if not data:
                    print("🔻 Client closed the connection during login phase.")
                    break
            except socket.timeout:
                # No data received within timeout—continue waiting.
                pass
            # A brief sleep so that we don't busy-wait (and to allow disconnection detection).
            time.sleep(1)
    except Exception as e:
        print(f"❌ Error during login wait: {e}")
    print("🔚 Exiting login phase; connection will now close.")


def handle_client(conn: socket.socket):
    """
    Handles an individual client connection.
    The handshake determines whether the client is asking for a status/MOTD or trying to join the game.
    The login phase (next state == 2) deliberately holds the client in an unfinished state.
    """
    try:
        print(f"🔗 New connection from {conn.getpeername()}")
        next_state = handle_handshake(conn)
        if next_state is None:
            return
        if next_state == 1:
            handle_status_request(conn)
            handle_ping(conn)
        elif next_state == 2:
            handle_login(conn)
        else:
            print(f"⚠️ Unknown state received: {next_state}")
    except Exception as e:
        print(f"❌ Error handling client: {e}")
    finally:
        conn.close()
        print("🔌 Connection closed")


def start_server() -> None:
    """Starts the server and spawns a new thread for each connection."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(5)
        server.settimeout(1.0)
        print(f"🟢 Minecraft MOTD server running on {HOST}:{PORT}")

        try:
            while True:
                try:
                    client, addr = server.accept()
                    client.settimeout(5.0)  # Set an initial timeout for client operations.
                    # Spawn a new thread to handle each client.
                    thread = threading.Thread(target=handle_client, args=(client,), daemon=True)
                    thread.start()
                except socket.timeout:
                    continue
        except KeyboardInterrupt:
            print("\n🛑 Server shutting down...")


if __name__ == "__main__":
    start_server()
