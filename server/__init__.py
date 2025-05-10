from server.handle.client import client

class Handle:
    @staticmethod
    def client(conn):  # Corrected method definition
        client(conn)  # Calls the function from handle/client.py
