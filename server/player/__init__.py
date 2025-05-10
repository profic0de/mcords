from server.vars import Var
import socket

class Player:
    from server.player.packet import send_packet, recv_packet
    from server.player.login import login
    from server.player.config import config

    def __init__(self, conn: socket.socket, protocol):
        self.protocol_version = protocol
        self.conn = conn

    def is_connected(self):
        try:
            data = self.conn.recv(1, socket.MSG_PEEK)
            if not data:
                return False  # Disconnected
            return True
        except BlockingIOError:
            return True  # Still alive, just no data
        except socket.error:
            return False  # Probably disconnected

