import sys; import os; sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))); del sys, os
from server.packet.build import Build
import asyncio

a = b'\x72\x0a\x08\x00\x05\x63\x6f\x6c\x6f\x72\x00\x03\x72\x65\x64\x09\x00\x05\x65\x78\x74\x72\x61\x0a\x00\x00\x00\x03\x08\x00\x05\x63\x6f\x6c\x6f\x72\x00\x04\x61\x71\x75\x61\x08\x00\x04\x74\x65\x78\x74\x00\x05\x30\x78\x30\x37\x20\x00\x08\x00\x05\x63\x6f\x6c\x6f\x72\x00\x03\x72\x65\x64\x08\x00\x04\x74\x65\x78\x74\x00\x05\x67\x6f\x74\x3a\x20\x00\x08\x00\x05\x63\x6f\x6c\x6f\x72\x00\x04\x61\x71\x75\x61\x08\x00\x04\x74\x65\x78\x74\x00\x04\x30\x78\x30\x36\x00\x08\x00\x04\x74\x65\x78\x74\x00\x10\x45\x78\x70\x65\x63\x74\x65\x64\x20\x70\x61\x63\x6b\x65\x74\x20\x00\x00'

def diff_bytes(a: bytes, b: bytes, mode=0):
    def lcs_matrix(X, Y):
        m, n = len(X), len(Y)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(m):
            for j in range(n):
                if X[i] == Y[j]:
                    dp[i + 1][j + 1] = dp[i][j] + 1
                else:
                    dp[i + 1][j + 1] = max(dp[i][j + 1], dp[i + 1][j])
        return dp

    def backtrack_lcs(dp, X, Y):
        i, j = len(X), len(Y)
        result = []
        while i > 0 and j > 0:
            if X[i - 1] == Y[j - 1]:
                result.append(('MATCH', i - 1, j - 1))
                i -= 1
                j -= 1
            elif dp[i - 1][j] >= dp[i][j - 1]:
                result.append(('REMOVE', i - 1, None))
                i -= 1
            else:
                result.append(('INSERT', None, j - 1))
                j -= 1
        while i > 0:
            result.append(('REMOVE', i - 1, None))
            i -= 1
        while j > 0:
            result.append(('INSERT', None, j - 1))
            j -= 1
        return result[::-1]

    max_len = max(len(a), len(b))

    if mode == 0:
        print(f"{'Offset':<8} | {'a':<5} | {'b':<5} | Match")
        print("-" * 32)
        for i in range(max_len):
            byte_a = a[i] if i < len(a) else None
            byte_b = b[i] if i < len(b) else None
            hex_a = f"{byte_a:02x}" if byte_a is not None else "--"
            hex_b = f"{byte_b:02x}" if byte_b is not None else "--"
            match = "✓" if byte_a == byte_b else "✗"
            print(f"{i:<8} | {hex_a:<5} | {hex_b:<5} | {match}")

    elif mode == 1:
        print(f"{'Offset':<8} | {'Action':<10} | {'From':<5} | {'To':<5}")
        print("-" * 40)
        if len(a) < len(b):
            for i in range(len(a)):
                print(f"{i:<8} | MATCH      | {a[i]:02x} | {b[i]:02x}")
            for i in range(len(a), len(b)):
                print(f"{i:<8} | ADD        | --    | {b[i]:02x}")
        elif len(b) < len(a):
            for i in range(len(b)):
                print(f"{i:<8} | MATCH      | {a[i]:02x} | {b[i]:02x}")
            for i in range(len(b), len(a)):
                print(f"{i:<8} | ADD        | {a[i]:02x} | --")
        else:
            for i in range(len(a)):
                print(f"{i:<8} | MATCH      | {a[i]:02x} | {b[i]:02x}")

    elif mode == 2:
        print(f"{'Offset':<8} | {'Action':<10} | {'From':<5} | {'To':<5}")
        print("-" * 40)
        for i in range(max_len):
            byte_a = a[i] if i < len(a) else None
            byte_b = b[i] if i < len(b) else None
            if byte_a is None:
                print(f"{i:<8} | ADD        | --    | {byte_b:02x}")
            elif byte_b is None:
                print(f"{i:<8} | REMOVE     | {byte_a:02x} | --")
            elif byte_a != byte_b:
                print(f"{i:<8} | REPLACE    | {byte_a:02x} | {byte_b:02x}")
            else:
                print(f"{i:<8} | MATCH      | {byte_a:02x} | {byte_b:02x}")

    elif mode == 3:
        print(f"{'Offset':<8} | {'Action':<10} | {'From':<5} | {'To':<5}")
        print("-" * 40)
        dp = lcs_matrix(a, b)
        edits = backtrack_lcs(dp, a, b)
        ai = bi = 0
        for action, i, j in edits:
            hex_a = f"{a[i]:02x}" if i is not None else "--"
            hex_b = f"{b[j]:02x}" if j is not None else "--"
            idx = i if i is not None else j
            print(f"{idx:<8} | {action:<10} | {hex_a:<5} | {hex_b:<5}")

    else:
        raise ValueError("Unsupported mode. Use 0, 1, 2, or 3.")


async def main():
    async with Build(packet_id=114,send=False) as build:
        build.text([{"text":"Expected packet ","color":"red"},{"text":"0x07 ","color":"aqua"},{"text":"got: ","color":"red"},{"text":"0x06","color":"aqua"}])
        if a[1:] == build.get()[1:]:
            print("hi")
        else:
            diff_bytes(a[1:], build.get()[1:], 2)
asyncio.run(main())