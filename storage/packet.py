import socket
import struct
from threading import Thread

class MinecraftServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = {}  # To track connected clients

    def start_server(self):
        """Starts the server to listen for incoming connections."""
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Server started at {self.host}:{self.port}")

        while True:
            client_socket, client_address = self.server_socket.accept()
            print(f"Client connected from {client_address}")
            self.clients[client_socket] = {}  # Track client state
            Thread(target=self.handle_client, args=(client_socket,)).start()

    def handle_client(self, client_socket):
        """Handles communication with a connected client."""
        try:
            while True:
                packet_id, payload = self.receive_packet(client_socket)
                print(f"Received Packet -> ID: {packet_id}, Payload: {payload.hex()}")

                # Process and respond to the packet
                self.process_packet(client_socket, packet_id, payload)
        except ConnectionError:
            print("Client disconnected.")
            self.clients.pop(client_socket, None)
            client_socket.close()

    def receive_exactly(self, sock, num_bytes):
        """Receives an exact number of bytes from the socket."""
        buffer = b""
        while len(buffer) < num_bytes:
            chunk = sock.recv(num_bytes - len(buffer))
            if not chunk:
                raise ConnectionError("Connection lost while receiving data.")
            buffer += chunk
        return buffer

    def receive_packet(self, client_socket):
        """Receives a packet and decodes its content."""
        # Receive the packet length (4 bytes)
        packet_length_bytes = self.receive_exactly(client_socket, 4)
        packet_length = struct.unpack('>I', packet_length_bytes)[0]

        # Receive the packet content
        packet_data = self.receive_exactly(client_socket, packet_length)
        packet_id = struct.unpack('>B', packet_data[:1])[0]
        payload = packet_data[1:]

        return packet_id, payload

    def send_packet(self, client_socket, packet_id, payload):
        """Encodes and sends a packet to the client."""
        packet_data = struct.pack('>B', packet_id) + payload
        packet_length = len(packet_data)
        packet = struct.pack('>I', packet_length) + packet_data

        try:
            client_socket.sendall(packet)
            print(f"Sent Packet -> ID: {packet_id}, Payload: {payload.hex()}")
        except BrokenPipeError:
            print("Failed to send packet. Client may have disconnected.")

    def process_packet(self, client_socket, packet_id, payload):
        """Processes received packets and sends appropriate responses."""
        if packet_id == 0x00:  # Handshake Packet
            print("Processing Handshake Packet...")
            self.handle_handshake(client_socket, payload)
        elif packet_id == 0x01:  # Login Start Packet
            print("Processing Login Start Packet...")
            self.handle_login(client_socket, payload)
        elif packet_id == 0x02:  # Example Play Packet
            print("Processing Play Packet...")
            self.handle_play(client_socket, payload)
        else:
            print(f"Unknown Packet ID: {packet_id}, ignoring...")

    def handle_handshake(self, client_socket, payload):
        """Handles the Handshake phase."""
        print(f"Handshake Payload: {payload.hex()}")
        # Assume the client requests the Login state (state = 2)
        print("Handshake complete. Moving to Login phase...")

    def handle_login(self, client_socket, payload):
        """Handles the Login phase."""
        print(f"Login Payload: {payload.hex()}")
        # Send Login Success packet (fake UUID and username)
        uuid = "00000000-0000-0000-0000-000000000000"  # Example UUID
        username = "Player"
        uuid_bytes = uuid.replace("-", "").encode("utf-8")
        username_bytes = username.encode("utf-8")
        self.send_packet(client_socket, 0x02, uuid_bytes + username_bytes)

    def handle_play(self, client_socket, payload):
        """Handles the Play phase."""
        print(f"Play Payload: {payload.hex()}")
        # Example response: Echo the payload back to the client
        self.send_packet(client_socket, 0x02, payload)

    def stop_server(self):
        """Stops the server and disconnects all clients."""
        for client in self.clients.keys():
            client.close()
        self.server_socket.close()
        print("Server stopped.")
