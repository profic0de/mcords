{
    "content": {
        "content": {
            "color": {
                "content": "red",
                "name": "color",
                "type": "TagString"
            },
            "extra": {
                "content": [
                    {
                        "color": {
                            "content": "blue",
                            "name": "color",
                            "type": "TagString"
                        },
                        "text": {
                            "content": "Umm idk",
                            "name": "text",
                            "type": "TagString"
                        }
                    }
                ],
                "name": "extra",
                "type": "TagList"
            },
            "text": {
                "content": "Kicked because: ",
                "name": "text",
                "type": "TagString"
            }
        },
        "name": "",
        "type": "TagCompound"
    },
    "overlay": False
}

a = [b'\x0a',
        b'\x08',
            b'\x00\x05color',b'\x00\x03red',b'\t',
            b'\x00\x05extra',b'\n\x00\x00\x00\x01',
                b'\x08',
                    b'\x00\x05color',b'\x00\x04blue',
                b'\x08',
                    b'\x00\x04text',b'\x00\x07Umm idk',
        b'\x00',
        b'\x08',
            b'\x00\x04text',b'\x00\x10Kicked because: ',
        b'\x00',
    b'\x00']

{
    "content": {
        "content": {
            "color": {
                "content": "blue",
                "name": "color",
                "type": "TagString"
            },
            "text": {
                "content": "Umm idk",
                "name": "text",
                "type": "TagString"
            }
        },
        "name": "",
        "type": "TagCompound"
    },
    "overlay": False
}

def read_varint_from(data: bytes, offset: int = 0):
    """
    Reads a VarInt from data starting at offset.
    Returns a tuple (value, bytes_consumed).
    """
    num = 0
    for i in range(5):
        byte = data[offset + i]
        num |= (byte & 0x7F) << (7 * i)
        if not (byte & 0x80):
            return num, i + 1 + offset
    raise Exception("VarInt too big")

[b'\x0a', b'\x08', b'\x00\x05color', b'\x00\x04blue', b'\x08', b'\x00\x04text', b'\x00\x07Umm idk', b'\x00']

c = b''.join(a)
print(c.hex())

def generate_chat_bytes(component):
    def encode_string(s: str) -> bytes:
        return len(s).to_bytes(2, 'big') + s.encode('utf-8')

    def encode_field(name: str, value: str) -> bytes:
        return (
            b'\x08' +
            encode_string(name) +
            encode_string(value)
        )

    def encode_component(obj: dict) -> bytes:
        out = bytearray()
        out += b'\x0a'
        if "extra" in obj:
            if "color" in obj:
                out += encode_field("color", obj["color"])
            out += b'\x00\x05extra'
            out += b'\n\x00\x00\x00' + len(obj["extra"]).to_bytes(1, 'big')
            for child in obj["extra"]:
                if isinstance(child, str):
                    child = {"text": child}
                elif not isinstance(child, dict):
                    raise TypeError("Each item in 'extra' must be a dict or str")
                inner = encode_component(child)
                out += inner[1:-1]  # remove compound wrap
        else:
            if "color" in obj:
                out += encode_field("color", obj["color"])
            if "text" in obj:
                out += encode_field("text", obj["text"])
        out += b'\x00'
        return bytes(out)

    if isinstance(component, list):
        # Wrap list with "extra", and normalize strings into {"text": "..."}
        component = [c if isinstance(c, dict) else {"text": c} for c in component]
        return encode_component({
            "color": component[0].get("color", "white"),
            "extra": component
        })
    elif isinstance(component, str):
        component = {"text": component}
        return encode_component(component)
    elif isinstance(component, dict):
        return encode_component(component)
    else:
        raise TypeError("Input must be a dict, list of dicts/strings, or string")

print(generate_chat_bytes(["Ofc ",{"text":"HI","color":"red"}]))
