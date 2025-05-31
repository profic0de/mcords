from server.packet.build import Build
from server.player import Player

def get_block(x, y, z):
    return 'minecraft:stone'

async def section(blocks, section, preset=1):
    async with Build(0x00, send=False) as build:
        build.short(blocks) #Block count

        if preset == 0:
            if section == 0:
                build.byte(0) #Bytes per entry
                build.varint(10)
            else:
                from main import palette as pallete
                from math import ceil, log2

                unique_states = []
                state_to_index = {}

                for y in range(16):
                    for z in range(16):
                        for x in range(16):
                            state = get_block(x, y, z)  #'minecraft:stone'
                            # state = "minecraft:stone"
                            if state not in state_to_index:
                                index = len(unique_states)
                                unique_states.append(state)
                                state_to_index[state] = index

                palette = [pallete[state] for state in unique_states]

                build.varint(len(palette))
                for global_id in palette:
                    build.varint(global_id)

                bpe = max(4, (len(palette) - 1).bit_length())
                build.byte(bpe)

                indexes = []
                for y in range(16):
                    for z in range(16):
                        for x in range(16):
                            state = get_block(x, y, z)
                            # state = 'minecraft:stone'
                            index = state_to_index[state]
                            indexes.append(index)

                build.data_array(indexes, bpe)
        elif preset == 1:
            build.byte(0) #Bytes per entry
            build.varint(10)
        #Biome data
        build.byte(0) #Bytes per entry
        build.varint(1) #Plains
        return build.get()[1:]

async def build_chunk(xz, player:Player, preset):
    x = xz[0]
    z = xz[1]
    async with Build(0x27, player) as build:
        build.int(x)
        build.int(z)

        data = [
            # (1, [111, 222, 333]),
            # (2, [444, 555])
        ]

        # build.array(data, lambda i: (
        #     build.varint(i[0]),
        #     build.array(i[1], build.long)
        # ))

        build.array(data, lambda item: (
            build.varint(item[0]),
            build.varint(item[1]),
            build.long(item[2])
        )) #Heightmaps

        async with Build(0x00, send=False) as data_b:
            for i in range(24):
                data_b.raw(await section(4096, i, preset))

            data = data_b.get()[1:]
        build.varint(len(data))
        build.raw(data)

        build.varint(0) #No Block Entities

        build.varint(0)
        build.varint(0)
        build.varint(0)
        build.varint(0)
        
        build.array([0]*2048, build.byte)
        build.array([0]*2048, build.byte)
        # build.array([0]*2048, build.byte)
        # build.array([0]*2048, build.byte)

