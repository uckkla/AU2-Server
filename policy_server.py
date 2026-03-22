import asyncio

async def handle_policy(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        # Flash sends this exact string requesting the policy file
        await reader.readuntil(b"\x00")
        print("Policy request received on port 843")
        policy = '<?xml version="1.0"?><cross-domain-policy><allow-access-from domain="*" to-ports="*"/></cross-domain-policy>'
        writer.write((policy + "\x00").encode("utf-8"))
        await writer.drain()
    except Exception as e:
        print(f"Policy server error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()