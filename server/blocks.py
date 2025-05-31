from palette import palette

import os
import psutil

def memory_usage():
    process = psutil.Process(os.getpid())
    mem_bytes = process.memory_info().rss  # Resident Set Size
    mem_mb = mem_bytes / 1024 / 1024
    return mem_mb
    
if __name__ == "__main__" and False:
    import json

    def compress_blocks(blocks_data: dict) -> dict:
        compressed = {}
        for block_name, block_info in blocks_data.items():
            state_ids = [state["id"] for state in block_info.get("states", [])]
            if state_ids:
                compressed[block_name] = min(state_ids)
        return compressed

    # === USAGE EXAMPLE ===

    # Load blocks.json
    with open("blocks.json", "r", encoding="utf-8") as f:
        blocks = json.load(f)

    # Compress
    compressed_palette = compress_blocks(blocks)

    # Save result
    with open("palette.json", "w", encoding="utf-8") as f:
        json.dump(compressed_palette, f, indent=2)
