from server.vars import Var

class Build:
    @staticmethod
    def generate_command_nodes():
        nodes = []

        def flags(node_type: int = 0, is_executable: bool = False, has_redirect: bool = False, has_suggestions_type: bool = False):
            f = 0
            f |= (node_type & 0x03)
            if is_executable: f |= 0x04
            if has_redirect: f |= 0x08
            if has_suggestions_type: f |= 0x10
            return f.to_bytes(1, byteorder='big')

        nodes += [flags() + Var.write_varint_array([1])]  # root node
        nodes += [flags(1, True) + Var.write_varint_array([2, 3]) + Var.write_string("proxy")]  # proxy

        nodes += [flags(1) + Var.write_varint_array([4]) + Var.write_string("join")]  # proxy join
        nodes += [flags(1) + Var.write_varint_array() + Var.write_string("leave")]  # proxy leave

        # proxy join/leave <username> <ip>
        nodes += [flags(2, True, False, True) + Var.write_varint_array([5]) + Var.write_string("username") +
                Var.write_varint(5) + Var.write_varint(0) + Var.write_string("minecraft:ask_server")]

        nodes += [flags(2, True, False, True) + Var.write_varint_array([6]) + Var.write_string("ip") +
                Var.write_varint(5) + Var.write_varint(0) + Var.write_string("minecraft:ask_server")]

        # Updated port node (brigadier:integer with min=0 and max=65535)
        port_min = 0
        port_max = 65535
        int_flags = 0x01 | 0x02  # both min and max
        properties = bytes([int_flags]) + Var.write_int(port_min) + Var.write_int(port_max)

        nodes += [flags(2, True, False, True) + Var.write_varint_array() + Var.write_string("port") +
                Var.write_varint(3) + properties + Var.write_string("minecraft:ask_server")]

        return Var.write_varint(len(nodes)) + b''.join(nodes) + Var.write_varint(0)

    
    @staticmethod
    def generate_command_suggestions(transaction_id:int,start:int,length:int, matches):
        """
        Example:

        ```python
        matches = [
            ("Steve", None),
            ("Alex", None),
        ]
        """

        packet = Var.write_varint(transaction_id) + Var.write_varint(start) + Var.write_varint(length)

        packet += Var.write_varint(len(matches))

        for match_text, tooltip in matches:
            packet += Var.write_string(match_text)  # Match text
            if tooltip is None:
                packet += b'\x00'  # No tooltip
            else:
                packet += b'\x01\x08' + Var.write_short(len(tooltip)) + tooltip  # Tooltip (if needed)
        
        return packet