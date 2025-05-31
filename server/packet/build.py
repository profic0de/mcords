from server.packet import Packet
from server.player import Player
from typing import Callable
from struct import pack
from io import BytesIO
import asyncio

class Build:
    def __init__(self, packet_id: int, writer: asyncio.StreamWriter | Player = None, send: bool = True):
        self._writer = writer
        self._send = send
        self._stream = BytesIO()

        self.varint(packet_id)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._send:
            if self._writer is None:
                raise ValueError("Writer wasn't set")
            if isinstance(self._writer, Player):
                packet = self._writer.packet
            else:
                packet = Packet(writer=self._writer)
            await packet.send(self._stream.getvalue())

        self._stream.close()
        del self

    def get(self) -> bytes:
        """Raw payload."""
        return self._stream.getvalue()

    #-----------------------------------------------------------

    def varint(self, value: int):
        while True:
            temp = value & 0x7F
            value >>= 7
            if value != 0:
                self._stream.write(bytes([temp | 0x80]))
            else:
                self._stream.write(bytes([temp]))
                break

    def string(self, text: str):
        encoded = text.encode("utf-8")
        self.varint(len(encoded))
        self._stream.write(encoded)

    def long(self, value: int):
        self._stream.write(value.to_bytes(8, byteorder='big', signed=True))

    def raw(self, value: bytes):
        self._stream.write(value)

    def bool(self, value: bool):
        self._stream.write(b'\x01' if value else b'\x00')

    def text(self, component):
        import io

        def encode_string(s: str) -> bytes:
            return len(s).to_bytes(2, 'big') + s.encode('utf-8')

        def encode_field(name: str, value: str):
            self._stream.write(b'\x08')
            self._stream.write(encode_string(name))
            self._stream.write(encode_string(value))

        class _MiniChatEncoder:
            def __init__(self, stream):
                self._stream = stream

            def encode_string(self, s: str) -> bytes:
                return len(s).to_bytes(2, 'big') + s.encode('utf-8')

            def encode_field(self, name: str, value: str):
                self._stream.write(b'\x08')
                self._stream.write(self.encode_string(name))
                self._stream.write(self.encode_string(value))

            def encode_component(self, obj: dict):
                self._stream.write(b'\x0a')  # Begin compound
                if "color" in obj:
                    self.encode_field("color", obj["color"])
                if "text" in obj:
                    self.encode_field("text", obj["text"])
                self._stream.write(b'\x00')  # End compound

        def encode_component(obj: dict):
            self._stream.write(b'\x0a')  # Begin compound

            if "extra" in obj:
                if "color" in obj:
                    encode_field("color", obj["color"])

                self._stream.write(b'\x00\x05extra')
                self._stream.write(b'\n\x00\x00\x00' + len(obj["extra"]).to_bytes(1, 'big'))

                for child in obj["extra"]:
                    if isinstance(child, str):
                        child = {"text": child}
                    elif not isinstance(child, dict):
                        raise TypeError("Each item in 'extra' must be a dict or str")

                    nested_buf = io.BytesIO()
                    _MiniChatEncoder(nested_buf).encode_component(child)
                    nested_data = nested_buf.getvalue()
                    self._stream.write(nested_data[1:-1])  # Strip outer compound tags
            else:
                if "color" in obj:
                    encode_field("color", obj["color"])
                if "text" in obj:
                    encode_field("text", obj["text"])

            self._stream.write(b'\x00')  # End compound

        # Normalize input and call encoder
        if isinstance(component, list):
            component = [c if isinstance(c, dict) else {"text": c} for c in component]
            encode_component({
                "color": component[0].get("color", "white"),
                "extra": component
            })
        elif isinstance(component, str):
            encode_component({"text": component})
        elif isinstance(component, dict):
            encode_component(component)
        else:
            raise TypeError("Input must be a dict, list of dicts/strings, or string")

    def array(self, array, func:Callable):
        self.varint(len(array))
        for item in array:
            func(item)

    def double(self, value: float):
        from struct import pack
        self._stream.write(pack('>d', value))

    def float(self, value: float):
        from struct import pack
        self._stream.write(pack('>f', value))

    def byte(self, value: int, signed=True):
        self._stream.write(value.to_bytes(1, byteorder='big', signed=signed))

    def short(self, value: int):
        from struct import pack
        self._stream.write(pack('>h', value))

    def int(self, value: int):
        self._stream.write(value.to_bytes(4, byteorder='big', signed=True))

    def fixed_bytes(self, size: int, signed: bool = True) -> Callable[[int], None]:
        def write_fn(value: int):
            self._stream.write(value.to_bytes(size, byteorder='big', signed=signed))
        return write_fn

    def data_array(self, palette_indices: list[int], bits_per_entry: int):
        if bits_per_entry == 0:
            return  # empty

        longs = []
        current_long = 0
        bits_used = 0

        for index in palette_indices:
            if bits_used + bits_per_entry > 64:
                # Pad and store the current long
                longs.append(current_long)
                current_long = 0
                bits_used = 0

            # Insert the index into the current long
            assert index < (1 << bits_per_entry), f"Index {index} out of bounds for {bits_per_entry} bits"
            current_long |= index << bits_used

            bits_used += bits_per_entry

            if bits_used == 64:
                longs.append(current_long)
                current_long = 0
                bits_used = 0

        # Don't forget the last long
        if bits_used > 0:
            longs.append(current_long)

        # Write the longs as big-endian
        self.varint(len(longs))  # write number of longs
        for value in longs:
            self.long(value)

    def position(self, x: int, y: int, z: int):
        # Ensure values are within valid ranges
        if not (-33554432 <= x <= 33554431):
            raise ValueError("x out of range")
        if not (-2048 <= y <= 2047):
            raise ValueError("y out of range")
        if not (-33554432 <= z <= 33554431):
            raise ValueError("z out of range")

        x &= 0x3FFFFFF  # 26 bits
        y &= 0xFFF      # 12 bits
        z &= 0x3FFFFFF  # 26 bits

        self._stream.write(pack(">Q", ((x << 38) | (z << 12) | y)))
