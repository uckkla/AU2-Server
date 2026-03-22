import asyncio
import threading
import xml.etree.ElementTree as ET
import html

clients = {} # "name": username, "id": user_id
rooms = {0: {"name": "Party Room", "max": 1000, "pwd": "", "users": {}, "inGame": False}} 
# rooms structure: room_id: {"name": str, "max": int, "pwd": str, "users": {}}
# users structure: user_id: {"name": str, "writer": StreamWriter, "pid": int}
next_user_id = 1

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
def make_message(action: str, room_id: int, inner_xml: str = "") -> str:
    return f'<msg t="sys"><body action="{action}" r="{room_id}">{inner_xml}</body></msg>'

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global next_user_id, rooms
    addr = writer.get_extra_info("peername")
    print(f"New Connection from {addr}")
    try:
        while True:
            data = await reader.readuntil(b"\x00")
            message = data[:-1].decode("utf-8")
            print(f"Received: {html.unescape(message)}")

            root = ET.fromstring(message)
            body = root.find("body")
            action = body.get("action")

            if action == "verChk":
                await send_message(writer, make_message("apiOK", 0))
                print("Sent apiOK")
            
            # Received: <msg t='sys'><body action='login' r='0'><login z='AU2'><nick><![CDATA[ExampleUserName]]></nick><pword><![CDATA[]]></pword></login></body></msg>
            elif action == "login":
                login = body.find("login")
                username = login.find("nick").text
                user_id = next_user_id
                next_user_id += 1

                clients[writer] = {"name": username, "id": user_id}
                print(f"Player logged in: {username} id={user_id}")

                await send_message(writer, make_message("logOK", 0, f'<login id="{user_id}" mod="0" n="{username}" />'))
                print(f"Sent logOK to {username}")
            
            # Received: <msg t='sys'><body action='getRmList' r='0'></body></msg>
            elif action == "getRmList":
                room_list_xml = '<rmList>'
                for r_id, r_data in rooms.items():
                    is_temp = "0" if r_id == 0 else "1"
                    is_game = "0" if r_id == 0 else "1"
                    room_list_xml += f'<rm id="{r_id}" maxu="{r_data.get("max")}" maxs="0" temp="{is_temp}" game="{is_game}" priv="{int(bool(r_data.get("pwd")))}" lmb="0" ucnt="{len(r_data.get("users"))}" scnt="0">'
                    room_list_xml += f'<n><![CDATA[{r_data.get("name")}]]></n>'
                    room_list_xml += f'<vars></vars>'
                    room_list_xml += f'</rm>'
                room_list_xml += '</rmList>'
                await send_message(writer, make_message("rmList", 0, room_list_xml))
            
            # Received: <msg t='sys'><body action='joinRoom' r='-1'><room id='0' pwd='' spec='0' leave='0' old='-1' /></body></msg>
            elif action == "joinRoom":
                room_id = int(body.find("room").get("id"))
                username = clients[writer]["name"]
                user_id = clients[writer]["id"]
                
                # Party Room
                if room_id == 0:
                    rooms[0]["users"][user_id] = {"name": username, "writer": writer}
                    join_ok_xml = f'<pid id="-1"/>'
                    join_ok_xml += f'<vars></vars>'
                    join_ok_xml += f'<uLs>'
                    join_ok_xml += f'<u i="{user_id}" m="0" s="0" p="-1">'
                    join_ok_xml += f'<n><![CDATA[{username}]]></n>'
                    join_ok_xml += f'</u>'
                    join_ok_xml += f'</uLs>'

                    await send_message(writer, make_message("joinOK", room_id, join_ok_xml))
                
                else:
                    pwd = body.find("room").get("pwd")

                    if room_id not in rooms:
                        room_doesnt_exist_xml = f'<error msg="Room does not exist."/>'
                        await send_message(writer, make_message("joinKO", 0, room_doesnt_exist_xml))
                    else:
                        num_players = len(rooms[room_id]["users"])
                        pid = num_players + 1
                        if rooms[room_id]["pwd"] != pwd:
                            wrong_pwd_xml = f'<error msg="Incorrect Password."/>'
                            await send_message(writer, make_message("joinKO", 0, wrong_pwd_xml))
                        elif num_players == rooms[room_id]["max"]:
                            lobby_full_xml = f'<error msg="Lobby is full."/>'
                            await send_message(writer, make_message("joinKO", 0, lobby_full_xml))
                        elif rooms[room_id]["inGame"] == True:
                            game_started_xml = f'<error msg="Game already in progress. Guess your friends started without you!"/>'
                            await send_message(writer, make_message("joinKO", 0, game_started_xml))
                        else:
                            userList = ""
                            uER_xml = f'<u i="{user_id}" m="0" s="0" p="{pid}">'
                            uER_xml += f'<n><![CDATA[{username}]]></n>'
                            uER_xml += f'<vars></vars>'
                            uER_xml += f'</u>'

                            for existing_user_id, existing_user in rooms[room_id]["users"].items():
                                await send_message(existing_user["writer"], make_message("uER", room_id, uER_xml))

                                existing_user_xml = f'<u i="{existing_user_id}" m="0" s="0" p="{existing_user["pid"]}">'
                                existing_user_xml += f'<n><![CDATA[{existing_user["name"]}]]></n>'
                                existing_user_xml += f'<vars></vars>'
                                existing_user_xml += f'</u>'

                                userList += existing_user_xml
                            
                            rooms[room_id]["users"][user_id] = {"name": username, "writer": writer, "pid": pid}
                            join_ok_xml = f'<pid id="{pid}"/>'
                            join_ok_xml += f'<vars></vars>'
                            join_ok_xml += f'<uLs>'
                            join_ok_xml += userList
                            join_ok_xml += uER_xml
                            join_ok_xml += f'</uLs>'

                            if user_id in rooms[0]["users"]:
                                del rooms[0]["users"][user_id]
                            await send_message(writer, make_message("joinOK", room_id, join_ok_xml))

                print(f"Sent joinOK for room {room_id} to {username}")
            
            # Received: <msg t='sys'><body action='createRoom' r='0'><room tmp='1' gam='1' spec='0' exit='1' jas='0'><name><![CDATA[4512-9044-4437-5231]]></name><pwd><![CDATA[]]></pwd><max>4</max><vars></vars></room></body></msg>
            elif action == "createRoom":
                data = body.find("room")
                room_name = data.find("name").text
                max_players = data.find("max").text
                pwd = data.find("pwd").text or ""

                new_room_id = max(rooms.keys()) + 1
                rooms[new_room_id] = {
                    "name": room_name,
                    "max": max_players,
                    "pwd": pwd,
                    "users": {},
                    "inGame": False
                }

                username = clients[writer]["name"]
                user_id = clients[writer]["id"]

                create_room_xml = f'<rm id="{new_room_id}" max="{max_players}" spec="{data.get("spec")}" '
                create_room_xml += f'tmp="{data.get("tmp")}" gam="{data.get("gam")}" priv="{int(bool(pwd))}" limbo="0">'
                create_room_xml += f'<name><![CDATA[{room_name}]]></name>'
                create_room_xml += f'<vars></vars>'
                create_room_xml += f'</rm>'

                await send_message(writer, make_message("roomAdd", new_room_id, create_room_xml))

                # Auto-join the creator into their new room as player 1
                rooms[new_room_id]["users"][user_id] = {"name": username, "writer": writer, "pid": 1}

                join_ok_xml = f'<pid id="1"/>'
                join_ok_xml += f'<vars></vars>'
                join_ok_xml += f'<uLs>'
                join_ok_xml += f'<u i="{user_id}" m="0" s="0" p="1">'
                join_ok_xml += f'<n><![CDATA[{username}]]></n>'
                join_ok_xml += f'<vars></vars>'
                join_ok_xml += f'</u>'
                join_ok_xml += f'</uLs>'

                if user_id in rooms[0]["users"]:
                    del rooms[0]["users"][user_id]

                await send_message(writer, make_message("joinOK", new_room_id, join_ok_xml))
                print(f"Room '{room_name}' created (id={new_room_id}), {username} auto-joined as pid=1")

            elif action == "pubMsg":
                user_id = clients[writer]["id"]
                room_id = int(body.get("r"))
                msg = html.unescape(body.find("txt").text or "")

                msg_xml = f'<user id="{user_id}"></user>'
                msg_xml += f'<txt><![CDATA[{msg}]]></txt>'

                for existing_user_id, existing_user in rooms[room_id]["users"].items():
                    if msg[:2] == "!!":
                        print(f"Sending !! to user {existing_user_id}")
                        await send_message(existing_user["writer"], make_message("pubMsg", room_id, msg_xml))
                    elif msg[:2] == ">>" and existing_user_id != user_id:
                        await send_message(existing_user["writer"], make_message("pubMsg", room_id, msg_xml))
                if msg[:2] == ">>" and '"iG":true' in msg:
                    rooms[room_id]["inGame"] = True
                    
    except asyncio.IncompleteReadError:
        leaver_user_id = clients[writer]["id"]
        username = clients[writer]["name"]
        room_id, room_data = findUserRoom(writer)
        user_left_xml = f'<user id="{leaver_user_id}"></user>'
        print(f"Player {username} left")
        if room_data is not None:
            for user_id, user in room_data["users"].items():
                if user_id != leaver_user_id:
                    print(f'The make_message would be:{make_message("userGone", room_id, user_left_xml)}')
                    await send_message(user["writer"], make_message("userGone", room_id, user_left_xml))
            del room_data["users"][leaver_user_id]

            if len(room_data["users"]) == 0 and room_id != 0:
                del rooms[room_id]
                print(f"Room {room_id} deleted (empty)")

        del clients[writer]
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        writer.close()
        await writer.wait_closed()

def findUserRoom(writer):
    for room_id, room_data in rooms.items():
        for user_id, user in room_data["users"].items():
            if user["writer"] == writer:
                return room_id, room_data
    return None, None

async def debug_state():
    while True:
        await asyncio.sleep(5)
        print(f"\n--- Server State ---")
        for room_id, room_data in rooms.items():
            print(f"Room {room_id} '{room_data['name']}': {list(room_data['users'].keys())}")
        print(f"Clients: {[client['name'] for client in clients.values()]}")
        print(f"-------------------\n")
