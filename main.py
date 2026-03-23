import asyncio
import threading
import argparse
from main_server import AU2Server
from policy_server import handle_policy
from http_server import start_http_server

HOST = "0.0.0.0"
SFS_PORT = 9339
HTTP_PORT = 8000
POLICY_PORT = 843

parser = argparse.ArgumentParser(description="Achievement Unlocked 2 Multiplayer Server")
parser.add_argument("--policy-server", action="store_true", help="Enable dedicated policy server on port 843")
args = parser.parse_args()

async def main():
    au2_server_instance = AU2Server()
    au2_server = await asyncio.start_server(au2_server_instance.handle_client, HOST, SFS_PORT)
    print(f"SFS server listening on {HOST}:{SFS_PORT}")

    if args.policy_server:
        policy_server = await asyncio.start_server(handle_policy, HOST, POLICY_PORT)
        print(f"Policy server listening on {HOST}:{POLICY_PORT}")
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
        print("Server stopped.")