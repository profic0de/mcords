from server.player import Player
from server.vars import Var
from server.tools import Tool
from server.logger import Logger
from server.build import Build
from server.proxy import proxy
# from server.nbt import NBT

def on_packet_received(packet_id: int, data: bytes, player: Player, logger: Logger):
    if packet_id == 0x05:  # Chat command packet
        command, _ = Var.read_string(data)

        args = command.split(" ")
        if len(args) >= 4 and args[0] == "proxy":
            # logger.info(f"{args[2]} + {args[3]}")
            if len(args) <= 5: args.append("")

            args[4] = ":"+args[4]
            cookie = Var.write_string(args[2])+Var.write_string(f"{args[3]}{args[4]}")
            player.send_packet(0x71, Var.write_string("mcords:transfer") +Var.write_varint(len(cookie))+cookie)
            player.send_packet(0x7A, Var.write_string(player.addr.split(":")[0])+Var.write_varint(int(player.addr.split(":")[1])))
        else:
            player.send_packet(0x72, Var.write_TagString(f'Command error: /{command}'))

        # logger.info(f"📦 Player typed command: /{command}")
    elif packet_id == 0x0D:
        transaction, offset = Var.read_varint_from(data)
        command, _ = Var.read_string(data, offset)
        args = command.split(" ")

        # logger.info(f"📦 Player asked suggestions for command: {command}, {len(command)}, {len(args)}, {args}")
        # if len(args) >= 5: return
        if args[0] == "/proxy":
            if args[1] == "join":
                if len(args) == 3: player.send_packet(0x0F, Build.generate_command_suggestions(transaction,12,12,[(player.username, None)]))
                elif len(args) == 4: player.send_packet(0x0F, Build.generate_command_suggestions(transaction,13+len(args[2]),len(args[3]),[("127.0.0.1", None)]))
                elif len(args) == 5: player.send_packet(0x0F, Build.generate_command_suggestions(transaction,14+len(args[2])+len(args[3]),len(args[4]),[("25567", None)]))
