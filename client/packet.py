import socket
import struct

class Protocol:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self):
        """Establishes a connection to the server."""
        self.socket.connect((self.host, self.port))
        print(f"Connected to {self.host}:{self.port}")

    def receive_exactly(self, num_bytes):
        """Receives an exact number of bytes from the socket."""
        buffer = b""
        while len(buffer) < num_bytes:
            chunk = self.socket.recv(num_bytes - len(buffer))
            if not chunk:
                raise ConnectionError("Connection lost while receiving data.")
            buffer += chunk
        return buffer

    def send_packet(self, packet_id, payload):
        """Sends a packet to the server and logs its content."""
        packet_data = struct.pack('>B', packet_id) + payload
        packet_length = len(packet_data)
        packet = struct.pack('>I', packet_length) + packet_data

        self.socket.sendall(packet)
        print(f"Sent Packet -> Length: {packet_length}, ID: {packet_id}, Payload: {payload.hex()}")

    def receive_packet(self):
        """Receives a packet from the server and logs its content."""
        # Read the packet length
        packet_length_bytes = self.receive_exactly(4)
        packet_length = struct.unpack('>I', packet_length_bytes)[0]

        # Read the packet data
        packet_data = self.receive_exactly(packet_length)
        packet_id = struct.unpack('>B', packet_data[:1])[0]
        payload = packet_data[1:]

        print(f"Received Packet -> Length: {packet_length}, ID: {packet_id}, Payload: {payload.hex()}")
        return packet_id, payload

    def close(self):
        """Closes the connection."""
        self.socket.close()
        print("Connection closed.")
