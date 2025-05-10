# mcords Proxy

> [!WARNING]
> This project is in **beta** and may contain bugs or unstable features.


**mcords proxy** is a custom Minecraft proxy server written in Python designed for flexibility, extensibility, and full control over client-server interaction. Built to support modern Minecraft versions, `mcords` enables advanced packet manipulation, dimension-specific datapack loading, authentication passthrough, and other core networking features for Minecraft modders and server developers.

---

## ✨ Features

- ⚙️ **Custom Packet Handling:** Full control over Minecraft packets with your own implementation.
- 🌐 **Proxy Architecture:** Forward Minecraft clients to backend servers with real-time packet inspection or modification.
- 🔐 **Authentication Support:** Mojang-style authentication passthrough support.
- 📦 **Mod Integration:** Work in progress.
- 🧪 **Modular Structure:** Clean and expandable architecture for plugins, tools, and debugging features.

## ✅ Supports

| Feature                     | Supported | Notes                                                                 |
|----------------------------|-----------|-----------------------------------------------------------------------|
| Minecraft Version          | ✅ 1.21.5  | Tested with Fabric Mods and vanilla                                   |
| Java Edition               | ✅ Yes     | Java-only (no Bedrock support planned)                                |
| Online Mode (Auth)         | ✅ Yes     | Mojang-style authentication passthrough                               |
| Offline Mode               | ✅ Yes     | UUID fallback mode supported                                          |
| Encryption                 | ✅ Yes     | Uses RSA with `cryptography` and `PyNaCl`                             |
| Mod Integration            | ⚠️ No      | (Work in progress)                                                    |
| Bedrock Support            | ❌ No      | Java-only focus                                                       |
| GUI                        | ❌ No      | CLI only; GUI planned for later                                       |


<!--
---

## 📦 Installation

### Requirements

- Python 3.10+
- `aiohttp`
- `cryptography`
- `PyNaCl`
- (Optional) Fabric 1.21.4 mod loader for enhanced mod integration

### Clone the Repository

```bash
git clone https://github.com/yourusername/mcords-proxy.git
cd mcords-proxy
pip install -r requirements.txt
-->
