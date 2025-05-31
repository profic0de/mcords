# MCords

**MCords proxy** is a custom Minecraft proxy server written in Python designed for flexibility, extensibility, and full control over client-server interaction. Built to support modern Minecraft versions, `mcords` enables advanced packet manipulation, authentication passthrough, and other core networking features for Minecraft modders and server developers.

---

> [!WARNING]
> This project is under heavy development.

---

## ✨ Features

- ⚙️ **Custom Packet Handling:** Full control over Minecraft packets with your own implementation.
- 🌐 **Proxy Architecture:** Forward Minecraft clients to servers with real-time packet inspection or modification.
- 🔐 **Authentication Support:** Mojang-style authentication passthrough support.

## ✅ Supports

| Feature                     | Supported | Notes                                                                 |
|----------------------------|-------------|----------------------------------------------------------------------|
| Minecraft Version          | ✅ 1.21.5  | Tested with Fabric Mods and vanilla                                   |
| Java Edition               | ✅ Yes     | Java-only (no Bedrock support planned)                                |
| Online Mode (Auth)         | ✅ Yes     | Mojang-style authentication passthrough                               |
| Offline Mode               | ✅ Yes     | UUID fallback mode supported                                          |
| Encryption                 | ✅ Yes     | Uses RSA with `cryptography` and `PyNaCl`                             |
| Bedrock Support            | ❌ No      | Java-only focus                                                       |
| GUI                        | ⚠️ Sort of |                                                                       |

## 🖥️ OS Compatibility

| Operating System | Supported | Notes                                  |
|------------------|-----------|----------------------------------------|
| 💻 Windows        | ✅ Yes      | Working; Fully tested              |
| 🐧 Linux          | ✅ Yes      | Working; Fully tested              |
| 🍎 macOS          | ⚠️ Not sure | Should work, but not tested        |


---

-->
## 📦 Installation

<!--
### Requirements

- Python 3.10+
- `aiohttp`
- `cryptography`
- `PyNaCl`
-->

### Clone the Repository

```bash
git clone https://github.com/profic0de/mcords.git
cd mcords
```
### Run the server

```bash
pip install -r requirements.txt
python main.py
```
