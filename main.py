import asyncio
import threading
import argparse
import logging
import os
from servers.au2_server import AU2Server
from servers.policy_server import handle_policy
from servers.http_server import start_http_server

HOST = "0.0.0.0"
SFS_PORT = 9339
HTTP_PORT = 8000
POLICY_PORT = 843

parser = argparse.ArgumentParser(description="Achievement Unlocked 2 Multiplayer Server")
parser.add_argument("--policy-server", action="store_true", help="Enable dedicated policy server on port 843")
args = parser.parse_args()

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/server.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def main():
    au2_server_instance = AU2Server()
    au2_server = await asyncio.start_server(au2_server_instance.handle_client, HOST, SFS_PORT)
    logger.info(f"SFS server listening on {HOST}:{SFS_PORT}")

    if args.policy_server:
        policy_server = await asyncio.start_server(handle_policy, HOST, POLICY_PORT)
        logger.info(f"Policy server listening on {HOST}:{POLICY_PORT}")
        async with au2_server, policy_server:
            await asyncio.gather(
                au2_server.serve_forever(),
                policy_server.serve_forever(),
                au2_server_instance.debug_state()
            )
    
    else:
        async with au2_server:
            await asyncio.gather(
                au2_server.serve_forever(),
                au2_server_instance.debug_state()
            )

if __name__ == "__main__":
    http_thread = threading.Thread(target=start_http_server, args=(HOST, HTTP_PORT), daemon=True)
    http_thread.start()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped.")