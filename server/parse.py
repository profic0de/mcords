from server.vars import Var

class Parse:
    @staticmethod
    def packet(packet_id: int, data: bytes, state: str = "play"):
        suffix = {
            "handshake": "_h",
            "status": "_s",
            "login": "_l",
            "config": "_c",
            "play": "_p"
        }.get(state)

        if suffix is None:
            raise ValueError(f"Invalid state: {state}")

        # Format function name like x00_p, x02_l, etc.
        func_name = f"x{packet_id:02X}{suffix}"

        # Look for that function in the class
        func = getattr(Parse, func_name, None)
        if callable(func):
            return func(data)
        else:
            raise Exception(f"No handler found for: {func_name}")

    @staticmethod
    def x00_c(data: bytes):
        parsed = {}
        offset = 0

        # String: Language (VarInt length + UTF-8 string)
        str_len, delta = Var.read_varint_from_bytes(data[offset:])
        offset += delta
        lang = data[offset:offset + str_len].decode("utf-8")
        parsed["locale"] = lang
        offset += str_len

        # VarInt: View Distance
        parsed["viewDistance"], delta = Var.read_varint_from_bytes(data[offset:])
        offset += delta

        # Chat Flags
        parsed["chatFlags"], delta = Var.read_varint_from_bytes(data[offset:])
        offset += delta

        parsed["chatColors"] = bool(data[offset])
        offset += 1

        parsed["skinParts"] = data[offset]
        offset += 1

        parsed["mainHand"], delta = Var.read_varint_from_bytes(data[offset:])
        offset += delta

        parsed["enableTextFiltering"] = bool(data[offset])
        offset += 1

        parsed["enableServerListing"] = bool(data[offset])
        offset += 1

        parsed["particles"], delta = Var.read_varint_from_bytes(data[offset:])
        offset += delta
        
        return parsed
    
    @staticmethod
    def x04_l(data: bytes):
        cookie, offset = Var.read_string(data)
        return cookie, data[offset:]
