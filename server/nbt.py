import struct
import json

class NBT:
    """
    Example of usage:
    ```python
    nbt_data = {
        "name": (NBT.TAG_String, "Proficode"),
        "health": (NBT.TAG_Int, 20),
        "is_admin": (NBT.TAG_Byte, 1),
        "stats": (NBT.TAG_Compound, {
            "kills": (NBT.TAG_Int, 3),
            "deaths": (NBT.TAG_Int, 1)
        }),
    }

    nbt_bytes = NBT.write_tag(NBT.TAG_Compound, "", NBT.write_tag_compound(nbt_data))

    """
    TAG_End = 0
    TAG_Byte = 1
    TAG_Short = 2
    TAG_Int = 3
    TAG_Long = 4
    TAG_Float = 5
    TAG_Double = 6
    TAG_Byte_Array = 7
    TAG_String = 8
    TAG_List = 9
    TAG_Compound = 10
    TAG_Int_Array = 11
    TAG_Long_Array = 12


    def write_nbt_string(s: str) -> bytes:
        encoded = s.encode("utf-8")
        return struct.pack(">H", len(encoded)) + encoded


    def write_tag(tag_type: int, name: str, payload: bytes) -> bytes:
        return struct.pack("B", tag_type) + NBT.write_nbt_string(name) + payload


    def write_tag_end() -> bytes:
        return struct.pack("B", NBT.TAG_End)


    def write_tag_byte(value: int) -> bytes:
        return struct.pack("b", value)


    def write_tag_int(value: int) -> bytes:
        return struct.pack(">i", value)


    def write_tag_string(value: str) -> bytes:
        return NBT.write_nbt_string(value)


    def write_tag_compound(data: dict) -> bytes:
        result = bytearray()
        for key, (tag_type, value) in data.items():
            if tag_type == NBT.TAG_Byte:
                result += NBT.write_tag(tag_type, key, NBT.write_tag_byte(value))
            elif tag_type == NBT.TAG_Int:
                result += NBT.write_tag(tag_type, key, NBT.write_tag_int(value))
            elif tag_type == NBT.TAG_String:
                result += NBT.write_tag(tag_type, key, NBT.write_tag_string(value))
            elif tag_type == NBT.TAG_Compound:
                result += NBT.write_tag(tag_type, key, NBT.write_tag_compound(value))
            else:
                raise ValueError(f"Unsupported tag type: {tag_type} for key: {key}")
        result += NBT.write_tag_end()  # TAG_End
        return bytes(result)

    def encode_chat_component(component: dict) -> bytes:
        json_str = json.dumps(component, separators=(',', ':'))
        return NBT.write_nbt_string(json_str)  # assuming Minecraft expects it as string
