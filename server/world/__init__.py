from server.player import Player
from server.build import Build
from server.vars import Var
from server.logger import logger
from server.world.on_packet import on_packet_received
import selectors

logger = logger.create_sub_logger(thread_name="world", output_levels=("INFO", "WARN", "ERROR", "DEBUG"))

class World:
    def __init__(self):
        self.players = {}  # uuid: Player
        self.sockets = []   # List of sockets to poll with select.select()
        self.selector = selectors.DefaultSelector()

    def join(self, player: Player):
        if player.conn.fileno() == -1:
            logger.error(f"❗ Invalid socket for {player.username}")
            return

        # Add player to the players dictionary
        self.players[player.uuid] = player
        self.selector.register(player.conn, selectors.EVENT_READ, data=player)

        player.send_packet(0x22, Var.write_u8(13)+Var.write_float(0.0))

        player.send_packet(0x57, Var.write_varint(0)+Var.write_varint(0))

        player.send_packet(0x0c)
        from server.world.send_chunk import packet
        chunk = lambda x, z: Var.write_int(x) + Var.write_int(z) + packet[8:]
        chunks = 0
        cords = lambda r: [(x, z) for x in range(-r, r + 1) for z in range(-r, r + 1)]
        for cord in cords(2):
            chunks += 1
            player.send_packet(0x27, chunk(cord[0],cord[1]))

        player.send_packet(0x0b, Var.write_varint(chunks))
        player.send_packet(0x41, Var.write_varint(0)
                           +Var.write_double(0.5)+Var.write_double(2.0)+Var.write_double(0.5)
                           +Var.write_double(0.0)+Var.write_double(0.0)+Var.write_double(0.0)
                           +Var.write_float(0.0)+Var.write_float(0.0)
                           +Var.write_int(0))

        player.send_packet(0x10, Build.generate_command_nodes())

        logger.info(f"👋 {getattr(player, 'username', 'Unknown')} joined the world.")

    def leave(self, player: Player):
        # Remove player from the world and close the connection
        if player.uuid in self.players:
            try:
                self.selector.unregister(player.conn)
            except Exception as e:
                logger.warn(f"⚠️ Couldn't unregister {player.username}: {e}")

            del self.players[player.uuid]
            # try:
            #     player.conn.close()
            #     logger.debug(f"✅ Closed socket for {player.username}")
            # except Exception as e:
            #     logger.error(f"❌ Error closing socket for {player.username}: {e}")

    def get_player(self, uuid):
        return self.players.get(uuid)

    def tick(self):
        from time import time
        delay = 0.0
        while True:
            if time()-delay >= 1:
                delay = time()
                for player in self.players.values():
                    player.send_packet(0x26, Var.write_long(0))

            # Only select if there are players connected
            if self.players:
                try:
                    # Use selector's select method
                    events = self.selector.select(timeout=0.05)
                except Exception as e:
                    continue

                disconnected = []

                for key, _ in events:
                    player = key.data  # Retrieve player from key.data
                    try:
                        if not player.is_connected() or player.conn.fileno() == -1:
                            disconnected.append(player)
                            continue

                        result = player.recv_packet()  # Using Player's recv_packet function
                        if result is None or result[0] is None:
                            continue  # No complete packet received yet

                        on_packet_received(result[0],result[1],player,logger)

                    except Exception as e:
                        import traceback
                        logger.error(f"❌ Error reading packet from {getattr(player, 'username', 'Unknown')}: {traceback.format_exc()}")
                        disconnected.append(player)

                for player in disconnected:
                    self.leave(player)
                    logger.info(f"👋 {getattr(player, 'username', 'Unknown')} left the world.")


    def list_players(self, mode="name"):
        if mode == "name":
            return [player.username for player in self.players.values()]
        else:
            return list(self.players.values())

    def start(self):
        """Start the main game loop."""
        from threading import Thread
        Thread(target=self.tick, daemon=True).start()

# Create the world and start the server
world = World()
