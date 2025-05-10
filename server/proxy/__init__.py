import selectors
import socket
from server.player import Player
from server.vars import Var
from server.logger import logger
from server.tools import Tool
from server.parse import Parse
from server.proxy.process_packet import process_packet
from json import dumps
from time import sleep
from traceback import print_exc

class Proxy:
    def __init__(self):
        self.players = {}  # id: Player
        self.sockets = []
        self.selector = selectors.DefaultSelector()
        self.logger = logger.create_sub_logger(thread_name="proxy", output_levels=("INFO", "WARN", "ERROR", "DEBUG"))
        self.playerIds = set()  # Track used player IDs

    def playerId(self):
        """Return the next available player ID (smallest unused integer)."""
        i = 0
        while i in self.playerIds:
            i += 1
        self.playerIds.add(i)
        return i

    def connect_to_server(self, host, port, player: Player):
        try:
            server_socket = socket.create_connection((host, port))
            server_socket.setblocking(False)
            return server_socket
        except Exception as e:
            self.logger.error(f"❌ Failed to connect to target server: {e}")
            player.send_packet(0x00, Var.write_string(dumps([{"text":"❌ Failed to connect to the target server: ","color":"red"},{"text":f"{e}","color":"white"}], separators=(",", ":"))))
            return None

    def join(self, player: Player):
        if player.conn.fileno() == -1:
            self.logger.error(f"❗ Invalid socket for the Player")
            return

        # Assign ID to player
        player.id = self.playerId()
        
        player.recv_packet()
        player.send_packet(0x05, Var.write_string("mcords:transfer"))

        data = Parse.packet(0x04, player.recv_packet()[1], "login")[1][2:]
        username, offset = Var.read_string(data)
        ip, offset = Var.read_string(data, offset); ip = ip.split(":")
        if ip[1] == '':
            from server.tools import Tool
            ip = Tool.resolve_minecraft_srv(ip[0])
        else:
            ip[1] = int(ip[1])

        # if ip[0] == "0.0.0.0": ip[0] = "127.0.0.1"
        self.logger.debug(f"Username: {username}, Ip: {ip}")
        player.remote = self.connect_to_server(ip[0], ip[1], player)  # Change as needed
        if not player.remote:
            self.playerIds.remove(player.id)
            return

        # Register both sockets
        self.players[player.id] = player
        self.selector.register(player.conn, selectors.EVENT_READ, data=("client", player))
        self.selector.register(player.remote, selectors.EVENT_READ, data=("server", player))

        handshake = (
            b'\x00' +
            Var.write_varint(player.protocol_version) +
            Var.write_string(ip[0]) +
            Var.write_ushort(ip[1]) +
            Var.write_varint(2)
        )
        player.remote.sendall(Var.write_varint(len(handshake))+handshake)

        payload = (
            b'\x00'+
            Var.write_string(username) +
            bytes.fromhex(Var.get_offline_uuid(username).replace('-', ''))
        )
        player.remote.sendall(Var.write_varint(len(payload))+payload)
        
        player.proxy = {"state":"login"}
        player.proxy["compression"] = -1
        player.proxy["once"] = 0

        self.logger.info(f"📡 {getattr(player, 'username', 'Unknown')} (ID {player.id}) joined and connected to server.")

    def leave(self, player: Player):
        if player.id in self.players:
            try:
                self.selector.unregister(player.conn)
                self.selector.unregister(player.remote)
            except Exception as e:
                self.logger.warn(f"⚠️ Couldn't unregister sockets for {player.username}: {e}")

            try:
                player.conn.close()
                player.remote.close()
            except Exception as e:
                self.logger.error(f"❌ Error closing sockets for {player.username}: {e}")

            del self.players[player.id]
            self.playerIds.remove(player.id)

    def tick(self):
        while True:
            if not self.players:
                continue  # avoid unnecessary select calls if no players

            try:
                events = self.selector.select(timeout=0.05)
            except Exception as e:
                self.logger.warn(f"⚠️ Selector failed: {e}")
                continue

            disconnected = set()

            for key, _ in events:
                source, player = key.data
                from_sock = player.conn if source == "client" else player.remote
                to_sock = player.remote if source == "client" else player.conn

                try:
                    data = from_sock.recv(4096)

                    # Connection closed cleanly
                    if not data:
                        self.logger.debug(f"🔌 {source.capitalize()} socket closed for {getattr(player, 'username', 'Unknown')} (ID {player.id})")
                        disconnected.add(player)
                        continue

                    # Intercept packet
                    direction = "server" if source == "client" else "client"

                    if player.proxy["once"] <= 8:
                        player.proxy["once"] = player.proxy["once"]+1
                        self.logger.debug(f"[P] Packet processing ({direction}) - {data}")

                    try:
                        processed_data = data
                        # self.logger.debug(f"🔵 [ -> {direction.capitalize()}bound] {getattr(player, 'username', 'Unknown')} - {data}")# bytes - {data}")

                        if player.proxy["compression"] > 0: processed_data = Tool.decompress_packet(processed_data)
                        # self.logger.error(f"Packet processing ({processed_data}) {data}")
                        processed_data = process_packet(processed_data, direction, player, self.logger)
                        # if player.proxy["compression"] > 0 and player.proxy["state"] != "login": processed_data = Tool.compress_packet(processed_data, player.proxy["compression"])
                        processed_data = data  # fall back to raw
                    except Exception as e:
                        self.logger.error(f"❌ Packet processing error ({direction}) -{data}: {e}")
                        print_exc()
                        processed_data = data  # fall back to raw

                    if processed_data:
                        # if player.proxy["compression"] > 0: packet = ""
                        # else: packet = Tool.decompress_packet(data,256)
                        # self.logger.debug(f"[{direction.capitalize()}bound] {getattr(player, 'username', 'Unknown')} - {data}")# bytes - {data}")
                        # self.logger.debug(f"Compression ({player.proxy["compression"]})")
                        to_sock.sendall(processed_data)

                except (ConnectionResetError, ConnectionAbortedError) as e:
                    # self.logger.warn(f"⚠️  {source.capitalize()} forcibly closed connection: {e}")
                    disconnected.add(player)

                except BlockingIOError:
                    # Ignore, socket has no data
                    continue

                except Exception as e:
                    self.logger.error(f"❌ Unexpected error: {e}")
                    print_exc()
                    disconnected.add(player)

            for player in disconnected:
                self.leave(player)
                self.logger.info(f"📡 {getattr(player, 'username', 'Unknown')} (ID {player.id}) disconnected.")

    def start(self):
        from threading import Thread
        Thread(target=self.tick, daemon=True).start()

proxy = Proxy()
