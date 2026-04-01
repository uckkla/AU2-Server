import asyncio
import xml.etree.ElementTree as ET
import html
import logging


logger = logging.getLogger(__name__)

class AU2Server:
    # Note: Some of these errors are handled by the SWF itself, but good measure in case it is bypassed.
    JOIN_ERRORS = {
        "wrong_password": "<error msg='Incorrect Password.'/>",
        "room_not_found": "<error msg='Room does not exist.'/>",
        "lobby_full": "<error msg='Lobby is full.'/>",
        "game_in_progress": "<error msg='Game already in progress. Guess your friends started without you!'/>",
        "duplicate_username": "<error msg='Another player already has that username in this lobby. How about be unique?'/>",
        "party_room_reserved": "<error msg='You cannot join the Party Room directly."
    }

    CREATE_ERRORS = {
        "room_exists": "<room e='Room name already exists.'/>",
    }

    def __init__(self):
        self.clients = {}
        self.rooms = {0: {"name": "Party Room", "max": 1000, "pwd": "", "users": {}, "inGame": False}} 
        self.next_user_id = 1
        self.handlers = {"verChk": self.handle_ver_chk,
            "login": self.handle_login,
            "getRmList": self.handle_get_rm_list,
            "joinRoom": self.handle_join_room,
            "createRoom": self.handle_create_room,
            "pubMsg": self.handle_pub_msg
        }

    # Relevant for send_message
    """
        private function writeToSocket(msg:String) : void
        {
            var byteBuff:ByteArray = new ByteArray();
            byteBuff.writeUTFBytes(msg);
            byteBuff.writeByte(0);
            this.socketConnection.writeBytes(byteBuff);
            this.socketConnection.flush();
        }
    """
    @staticmethod
    async def send_message(writer: asyncio.StreamWriter, xml_str: str):
        writer.write((xml_str + "\x00").encode("utf-8"))
        await writer.drain()

    # Relevant for make_message
    """
        private function xmlReceived(msg:String) : void
        {
            var xmlData:XML = new XML(msg);
            var handlerId:String = xmlData.@t;
            var action:String = xmlData.body.@action;
            var roomId:int = int(xmlData.body.@r);
            var handler:IMessageHandler = this.messageHandlers[handlerId];
            if(handler != null)
            {
                handler.handleMessage(xmlData,XTMSG_TYPE_XML);
            }
        }
    """
    @staticmethod
    def make_message(action: str, room_id: int, inner_xml: str = "") -> str:
        return f'<msg t="sys"><body action="{action}" r="{room_id}">{inner_xml}</body></msg>'
    
    async def send_join_ko(self, writer, message):
        await self.send_message(writer, self.make_message("joinKO", 0, self.JOIN_ERRORS[message]))

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        logger.info(f"New Connection from {addr}")

        try:
            while True:
                data = await reader.readuntil(b"\x00")
                message = data[:-1].decode("utf-8")
                logger.debug(f"Received: {html.unescape(message)}")

                if message == "<policy-file-request/>":
                    await self.handle_policy_file(writer)
                    continue

                root = ET.fromstring(message)
                body = root.find("body")
                action = body.get("action")

                if action in self.handlers:
                    await self.handlers[action](writer, body)
        
        # IncompleteReadError - Graceful disconnect (Leaving Lobby/Game) / Bytes no longer sent
        # ConnectionResetError - Forced disconnect (Closing Flash Projector)
        except (asyncio.IncompleteReadError, ConnectionResetError):
            await self.handle_disconnect(writer)
            
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    # Received: <msg t='sys'><body action='verChk' r='0'><ver v='161' /></body></msg>
    async def handle_ver_chk(self, writer, body):
        await self.send_message(writer, self.make_message("apiOK", 0))
        logger.debug("Sent apiOK")

    # Received: <msg t='sys'><body action='login' r='0'><login z='AU2'><nick><![CDATA[ExampleUserName]]></nick><pword><![CDATA[]]></pword></login></body></msg>
    async def handle_login(self, writer, body):
        login = body.find("login")
        username = login.find("nick").text
        user_id = self.next_user_id
        self.next_user_id += 1

        self.clients[writer] = {"name": username, "id": user_id}
        logger.info(f"Player logged in: {username} id={user_id}")

        await self.send_message(writer, self.make_message("logOK", 0, f'<login id="{user_id}" mod="0" n="{username}" />'))
        logger.debug(f"Sent logOK to {username}")

    # Received: <msg t='sys'><body action='getRmList' r='0'></body></msg>
    async def handle_get_rm_list(self, writer, body):
        room_list_xml = '<rmList>'
        for room_id, room_data in self.rooms.items():
            is_temp = "0" if room_id == 0 else "1"
            is_game = "0" if room_id == 0 else "1"
            room_list_xml += f'<rm id="{room_id}" maxu="{room_data.get("max")}" maxs="0" temp="{is_temp}" game="{is_game}" priv="{int(bool(room_data.get("pwd")))}" lmb="0" ucnt="{len(room_data.get("users"))}" scnt="0">'
            room_list_xml += f'<n><![CDATA[{room_data.get("name")}]]></n>'
            room_list_xml += f'<vars></vars>'
            room_list_xml += f'</rm>'
        room_list_xml += '</rmList>'
        await self.send_message(writer, self.make_message("rmList", 0, room_list_xml))

    # Received: <msg t='sys'><body action='joinRoom' r='-1'><room id='0' pwd='' spec='0' leave='0' old='-1' /></body></msg>
    async def handle_join_room(self, writer, body):
        room_id = int(body.find("room").get("id"))
        username = self.clients[writer]["name"]
        user_id = self.clients[writer]["id"]
        
        # Party Room
        if room_id == 0:
            current_room = int(body.get("r"))
            # If player has already joined party room and trying to join it again, means they tried to join "Party Room" name.
            # Messy solution as it doesnt tell the player why they couldnt join, but they are stuck in Party Room otherwise.
            if current_room == 0:
                await self.send_join_ko(writer, "party_room_reserved")
                writer.close()
                return
            
            self.rooms[0]["users"][user_id] = {"name": username, "writer": writer}
            join_ok_xml = f'<pid id="-1"/>'
            join_ok_xml += f'<vars></vars>'
            join_ok_xml += f'<uLs>'
            join_ok_xml += f'<u i="{user_id}" m="0" s="0" p="-1">'
            join_ok_xml += f'<n><![CDATA[{username}]]></n>'
            join_ok_xml += f'</u>'
            join_ok_xml += f'</uLs>'

            await self.send_message(writer, self.make_message("joinOK", room_id, join_ok_xml))
        
        else:
            pwd = body.find("room").get("pwd")

            if room_id not in self.rooms:
                await self.send_join_ko(writer, "room_not_found")
            else:
                num_players = len(self.rooms[room_id]["users"])
                pid = num_players + 1
                if self.rooms[room_id]["pwd"] != pwd:
                    await self.send_join_ko(writer, "wrong_password")
                elif num_players == self.rooms[room_id]["max"]:
                    await self.send_join_ko(writer, "lobby_full")
                elif self.rooms[room_id]["inGame"] == True:
                    await self.send_join_ko(writer, "game_in_progress")
                elif username in [user["name"] for user in self.rooms[room_id]["users"].values()]:
                    await self.send_join_ko(writer, "duplicate_username")

                else:
                    userList = ""
                    uER_xml = f'<u i="{user_id}" m="0" s="0" p="{pid}">'
                    uER_xml += f'<n><![CDATA[{username}]]></n>'
                    uER_xml += f'<vars></vars>'
                    uER_xml += f'</u>'

                    for existing_user_id, existing_user in self.rooms[room_id]["users"].items():
                        await self.send_message(existing_user["writer"], self.make_message("uER", room_id, uER_xml))

                        existing_user_xml = f'<u i="{existing_user_id}" m="0" s="0" p="{existing_user["pid"]}">'
                        existing_user_xml += f'<n><![CDATA[{existing_user["name"]}]]></n>'
                        existing_user_xml += f'<vars></vars>'
                        existing_user_xml += f'</u>'

                        userList += existing_user_xml
                    
                    self.rooms[room_id]["users"][user_id] = {"name": username, "writer": writer, "pid": pid}
                    join_ok_xml = f'<pid id="{pid}"/>'
                    join_ok_xml += f'<vars></vars>'
                    join_ok_xml += f'<uLs>'
                    join_ok_xml += userList
                    join_ok_xml += uER_xml
                    join_ok_xml += f'</uLs>'

                    if user_id in self.rooms[0]["users"]:
                        del self.rooms[0]["users"][user_id]
                    await self.send_message(writer, self.make_message("joinOK", room_id, join_ok_xml))

        logger.debug(f"Sent joinOK for room {room_id} to {username}")

    # Received: <msg t='sys'><body action='createRoom' r='0'><room tmp='1' gam='1' spec='0' exit='1' jas='0'><name><![CDATA[4512-9044-4437-5231]]></name><pwd><![CDATA[]]></pwd><max>4</max><vars></vars></room></body></msg>
    async def handle_create_room(self, writer, body):
        data = body.find("room")
        room_name = data.find("name").text
        max_players = data.find("max").text
        pwd = data.find("pwd").text or ""

        existing_names = [r["name"] for r in self.rooms.values()]
        if room_name in existing_names:
            room_exists_xml = '<room e="Room name already exists."/>'
            await self.send_message(writer, self.make_message("createRmKO", 0, CREATE_ERRORS["room_exists"]))
            return

        new_room_id = max(self.rooms.keys()) + 1
        self.rooms[new_room_id] = {
            "name": room_name,
            "max": int(max_players),
            "pwd": pwd,
            "users": {},
            "inGame": False
        }

        username = self.clients[writer]["name"]
        user_id = self.clients[writer]["id"]

        create_room_xml = f'<rm id="{new_room_id}" max="{max_players}" spec="{data.get("spec")}" '
        create_room_xml += f'tmp="{data.get("tmp")}" gam="{data.get("gam")}" priv="{int(bool(pwd))}" limbo="0">'
        create_room_xml += f'<name><![CDATA[{room_name}]]></name>'
        create_room_xml += f'<vars></vars>'
        create_room_xml += f'</rm>'

        await self.send_message(writer, self.make_message("roomAdd", new_room_id, create_room_xml))

        # Auto-join the creator into their new room as player 1
        self.rooms[new_room_id]["users"][user_id] = {"name": username, "writer": writer, "pid": 1}

        join_ok_xml = f'<pid id="1"/>'
        join_ok_xml += f'<vars></vars>'
        join_ok_xml += f'<uLs>'
        join_ok_xml += f'<u i="{user_id}" m="0" s="0" p="1">'
        join_ok_xml += f'<n><![CDATA[{username}]]></n>'
        join_ok_xml += f'<vars></vars>'
        join_ok_xml += f'</u>'
        join_ok_xml += f'</uLs>'

        if user_id in self.rooms[0]["users"]:
            del self.rooms[0]["users"][user_id]

        await self.send_message(writer, self.make_message("joinOK", new_room_id, join_ok_xml))
        logger.info(f"Room '{room_name}' created (id={new_room_id}), {username} auto-joined as pid=1")

    # Received: <msg t='sys'><body action='pubMsg' r='1'><txt><![CDATA[>>{"ready":false,"iG":false,"cF":1,"done":false,"tint":3184365,"xM":0,"ws":0,"yM":0,"xS":1}]]></txt></body></msg>
    async def handle_pub_msg(self, writer, body):
        user_id = self.clients[writer]["id"]
        room_id = int(body.get("r"))
        msg = html.unescape(body.find("txt").text or "")

        msg_xml = f'<user id="{user_id}"></user>'
        msg_xml += f'<txt><![CDATA[{msg}]]></txt>'

        for existing_user_id, existing_user in self.rooms[room_id]["users"].items():
            if msg[:2] == "!!":
                await self.send_message(existing_user["writer"], self.make_message("pubMsg", room_id, msg_xml))
            elif msg[:2] == ">>" and existing_user_id != user_id:
                await self.send_message(existing_user["writer"], self.make_message("pubMsg", room_id, msg_xml))
        if msg[:2] == ">>" and '"iG":true' in msg:
            self.rooms[room_id]["inGame"] = True

    async def handle_disconnect(self, writer):
        # Policy request as connection is cut short
        if writer not in self.clients:
            return
        leaver_user_id = self.clients[writer]["id"]
        username = self.clients[writer]["name"]
        room_id, room_data = self.find_user_room(writer)
        user_left_xml = f'<user id="{leaver_user_id}"></user>'
        logger.info(f"Player {username} left")
        if room_data is not None:
            for user_id, user in room_data["users"].items():
                if user_id != leaver_user_id:
                    await self.send_message(user["writer"], self.make_message("userGone", room_id, user_left_xml))
            del room_data["users"][leaver_user_id]

            if len(room_data["users"]) == 0 and room_id != 0:
                del self.rooms[room_id]
                logger.info(f"Room {room_id} deleted (empty)")

        del self.clients[writer]

    async def handle_policy_file(self, writer):
        policy_xml = '<?xml version="1.0"?><cross-domain-policy><allow-access-from domain="*" to-ports="9339"/></cross-domain-policy>'
        await self.send_message(writer, policy_xml)

    def find_user_room(self, writer):
        for room_id, room_data in self.rooms.items():
            for user_id, user in room_data["users"].items():
                if user["writer"] == writer:
                    return room_id, room_data
        return None, None

    async def debug_state(self):
        while True:
            await asyncio.sleep(5)

            logger.debug(f"\n--- Server State ---")
            for room_id, room_data in self.rooms.items():
                logger.debug(f"Room {room_id} '{room_data['name']}': {list(room_data['users'].keys())}")
            logger.debug(f"Clients: {[client['name'] for client in self.clients.values()]}")
