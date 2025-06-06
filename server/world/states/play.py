from server.packet.build import Build
from server.player import Player
from server.world import logger

async def play(player:Player):
    async with Build(0x2b, player) as build:
        player.Id = 0

        build.int(player.Id) #Player's id
        build.bool(False) #Show hardcore hearts
        build.array(["minecraft:overworld"], build.string) #All Dimension Names
        build.varint(20) #Max players (ignored)
        build.varint(10) #View distance
        build.varint(10) #Simulation distance
        build.bool(False) #Reduced Debug Info (F3)
        build.bool(False) #Enable respawn screen
        build.bool(False) #Do limited Crafting (ignored)
        build.varint(0) #Dimension Type
        build.string("minecraft:overworld") #Dimension Name
        build.long(4172702371561058553) #Hashed seed
        build.byte(2, False) #Gamemode: 0=Survival 1=Creative 2=Adventure 3=Spectator
        build.byte(-1, True) #Previous Game mode
        build.bool(False) #Is debug world type
        build.bool(True) #Is flat
        build.bool(False) #Has death location
        build.varint(0) #Portal cooldown
        build.varint(0) #Sea level
        build.bool(False) #Enforces Secure Chat

    async with Build(0x41, player) as build:
        build.varint(0)
        build.double(8.0); build.double(2.0); build.double(8.0)
        build.double(0.0); build.double(0.0); build.double(0.0)
        build.float(0.0); build.float(0.0)
        build.int(0)

    async with Build(0x57, player) as build: #Chunk area center
        build.varint(0)
        build.varint(0)

    async with Build(0x22, player) as build:
        build.varint(13)
        build.float(0.0)

    await player.packet.send(b'\x0c')
    chunks = 0

    from server.world.chunk import build_chunk
    radius = lambda r: (0-r, r+1)
    radius = radius(2)
    for x in range(radius[0],radius[1]):
        for z in range(radius[0],radius[1]):
            await build_chunk([x,z], player, 2)
            chunks += 1

    async with Build(0x0b, player) as build:
        build.varint(chunks)

    async with Build(0x41, player) as build:
        build.varint(0)
        build.double(8.0); build.double(1.0); build.double(8.0)
        build.double(0.0); build.double(0.0); build.double(0.0)
        build.float(0.0); build.float(0.0)
        build.int(0)

    # player.send_packet(0x10, Build.generate_command_nodes())

    logger.info(f"👋 {getattr(player, 'username', 'Unknown')} joined the world.")