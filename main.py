import asyncio
import threading
from main_server import AU2Server
from policy_server import handle_policy
from http_server import start_http_server

HOST = "0.0.0.0"
SFS_PORT = 9339
HTTP_PORT = 8000
POLICY_PORT = 843

async def main():
    au2_server_instance = AU2Server()
    au2_server = await asyncio.start_server(au2_server_instance.handle_client, HOST, SFS_PORT)
    policy_server = await asyncio.start_server(handle_policy, HOST, POLICY_PORT)
    
    print(f"SFS server listening on {HOST}:{SFS_PORT}")
    print(f"Policy server listening on {HOST}:{POLICY_PORT}")
    
    async with au2_server, policy_server:
        await asyncio.gather(
            au2_server.serve_forever(),
            policy_server.serve_forever(),
            au2_server_instance.debug_state()
        )

if __name__ == "__main__":
    http_thread = threading.Thread(target=start_http_server, args=(HOST, HTTP_PORT), daemon=True)
    http_thread.start()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stopped.")