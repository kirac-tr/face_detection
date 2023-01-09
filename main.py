# -*- coding: utf-8 -*-
import asyncio, logging, requests, json, cv2, os, re
from email import message_from_bytes
from aiosmtpd.controller import Controller
from deepstack_sdk import ServerConfig, Detection
from aiosmtpd.smtp import AuthResult, LoginPassword


bot_token         = os.environ['TELEGRAM_TOKEN']
api_url           = f"https://api.telegram.org/bot{bot_token}/"
chat_id           = os.environ['TELEGRAM_CHAT_ID']
deepstack_ip      = os.environ['DEEPSTACK_IP']
deepstack_port    = os.environ['DEEPSTACK_PORT']
server_ip         = os.environ['SERVER_IP']
server_port       = os.environ['SERVER_PORT']
server_username   = os.environ['SERVER_USERNAME']
server_password   = os.environ['SERVER_PASSWORD']
device_regex      = os.environ['DEVICE_REGEX']
objects           = os.environ['OBJECTS']
confidance        = os.environ['CONFIDANCE']
objects_list      = objects.split(",")
confidance_list   = confidance.split(",")
station_list      = []
list              = []
ip_address        = ""
device_name       = ""
server_auth = {server_username.encode(): server_password.encode(),}

logging.basicConfig(level = logging.INFO,
                    format = '%(asctime)s:%(levelname)s:%(name)s:%(message)s')
detect_dict = {}
for i in range(len(objects_list)):
    detect_dict[objects_list[i]] = confidance_list[i]

async def face_registeration(caption):
    user_image = open(f"/home/face/user/{caption}.jpg","rb").read()
    response = requests.post(f"http://{str(deepstack_ip)}:{str(deepstack_port)}/v1/vision/face/register",
        files={"image":user_image},data={"userid":f"{caption}"}).json()
    await send_Message(chat_id, text =f"Yeni kişi kaydedildi: {caption}")

async def face_recognition(file="image.jpg"):
    image_data = open(file,"rb").read()
    faces = requests.post(f"http://{str(deepstack_ip)}:{str(deepstack_port)}/v1/vision/face/list").json()
    response = requests.post(f"http://{str(deepstack_ip)}:{str(deepstack_port)}/v1/vision/face/recognize",
        files={"image":image_data},data={"min_confidence":confidance}).json()
    for user in response["predictions"]:
        if user['userid'] in faces['faces']:
            text_caption = f"{user['userid']} {device_name} istasyonunda!!!"
            await send_Photo(chat_id, file, text_caption)
    os.remove('image.jpg')

async def faces_listing():
    user_list = []
    faces = requests.post(f"http://{str(deepstack_ip)}:{str(deepstack_port)}/v1/vision/face/list").json()
    f = faces['faces']
    for u in f:
        user_list.append(u)
    result = '\n'.join(user_list)
    await send_Message(chat_id, text=f"Kayıtlı Kişiler:\n{result}")

async def face_deleting(text_list):
    user = text_list[1]+" "+text_list[2]
    response = requests.post(f"http://{str(deepstack_ip)}:{str(deepstack_port)}/v1/vision/face/delete",
        data={"userid":user}).json()
    await send_Message(chat_id, f"{user} adlı kayıt silindi.")

async def send_Message(chat_id, text):
    data={'chat_id': chat_id, 'text': text}
    req = requests.post(f"{api_url}sendMessage",data=data)
    return req.json()

async def send_Photo(chat_id, file, text_caption):
    data = {"chat_id": chat_id, "caption": text_caption}
    api = f"{api_url}sendPhoto"
    with open(file, "rb") as image_file:
        req = requests.post(api, data=data, files={"photo": image_file})
    return req.json()

def get_url(urls):
    response = requests.get(urls)
    content = response.content.decode('utf8')
    return content

def get_json(urls): 
    content = get_url(urls)
    js      = json.loads(content)
    return js

def get_updates(offset=None): 
    urls = f"{api_url}getUpdates?timeout=60"
    if offset:
        urls += f"&offset={offset}"
    js = get_json(urls)
    return js

def get_last_update_id(updates): 
    update_ids = []
    for update in updates['result']:
        update_ids.append(int(update['update_id']))
    return max(update_ids)

async def get_file(file_id, caption):
    api = f"{api_url}getFile"
    r = requests.get(api, params={'file_id': file_id})
    file_info = r.json()['result']
    file_path = file_info['file_path']
    file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
    r = requests.get(file_url)
    with open(f"/home/face/user/{caption}.jpg", "wb") as f:
        f.write(r.content)
        f.close()
    await face_registeration(caption)

async def send_Message(chat_id, text):
    data={'chat_id': chat_id, 'text': text}
    req = requests.post(f"{api_url}sendMessage",data=data)
    return req.json()

async def get_updates(offset):
    url = f"{api_url}getUpdates?offset={offset}"
    r = requests.get(url)
    return r.json()

async def get_message(data):
    if data['result']:
        for message in data['result']:
            try:
                chat_id = message['message']['chat']['id']
                text = message['message']['text']
                text_list = text.split(" ")
                if text == "/list":
                    await faces_listing()
                if text_list[0] == "/remove":
                    await face_deleting(text_list)
                if message['message']['caption']:
                    pass
            except (IndexError, KeyError):
                pass
            try:
                photo   = message['message']['photo'][-1]
                file_id = photo['file_id']
                caption = message['message']['caption']
                await get_file(file_id,caption)
            except KeyError:
                pass

def authenticator(server, session, envelope, mechanism, auth_data):
    assert isinstance(auth_data, LoginPassword)
    username = auth_data.login
    password = auth_data.password
    if server_auth.get(username) == password:
        return AuthResult(success=True)
    else:
        return AuthResult(success=False, handled=False)

class SMTPHandler:
    async def handle_DATA(self, server, session, envelope):
        remote_ip = []
        for ip in session.peer:
            remote_ip.append(ip)
        m = message_from_bytes(envelope.content)
        if m.is_multipart():
            for part in m.walk():
                ctype = part.get_content_type()
                disposition = str(part.get('Content-Disposition'))
                if ctype == 'text/html':
                    body = part.get_payload(decode=True)
                    #print("\n******************************************************* - text/html MAIL CONTENTS - *******************************************************\n")
                    #print(body)
                    device = re.search(device_regex, str(body))
                    #print("\n")
                    #print(device)
                    #print("\n*******************************************************************************************************************************************\n")
                    global ip_address
                    ip_address = remote_ip[0]
                    list.append(ip_address)
                    global device_name
                    device_name = device[0]

                if  ctype == 'text/plain':
                    body = part.get_payload(decode=True)
                    #print("\n******************************************************* - text/plain MAIL CONTENTS - *******************************************************\n")
                    #print(body)
                    device = re.search(device_regex, str(body))
                    #print("\n")
                    #print(device)
                    #print("\n*******************************************************************************************************************************************\n")
                    ip_address = remote_ip[0]
                    list.append(ip_address)
                    device_name = device[0]
                        
                if (ctype == 'application/x-msdownload' or ctype == 'application/octet-stream' or ctype == 'image/jpeg' or ctype == 'image/png' or ctype == 'multipart/mixed' or ctype == 'multipart/alternative' ) and 'attachment;' in disposition:
                    open('latest.jpg', 'wb').write(part.get_payload(decode=True,))
                    image_data  = open('latest.jpg',"rb").read()
                    response    = requests.post(f"http://{str(deepstack_ip)}:{str(deepstack_port)}/v1/vision/detection",files={"image":image_data}).json()
                    coordinates = [] 
                    mlistp      = []
                    for object in response["predictions"]:
                        for key, value in detect_dict.items():
                            if (object['label'] == key and object['confidence']>=float(value)):
                                y1 = int(object["y_max"])
                                y2 = int(object["y_min"])
                                x1 = int(object["x_max"])
                                x2 = int(object["x_min"])
                                z1 = object["label"]
                                coordinates=([x1,y2,x2,y1,z1])
                                mlistp.append(coordinates)
                                img= cv2.imread('latest.jpg')
                        i=0
                        for i in range(len(mlistp)):
                            imgdr = cv2.rectangle(img, (mlistp[i][0], mlistp[i][1]), \
                                    (mlistp[i][2], mlistp[i][3]),(0,255,0), 2)
                            imgdr = cv2.putText(imgdr, mlistp[i][4], (mlistp[i][2], mlistp[i][3]+10), \
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.4,(255,255,255), 1)
                            cv2.imwrite("image.jpg",imgdr)
            try:
                os.remove('latest.jpg')
                await face_recognition('image.jpg')
            except FileNotFoundError:
                pass
        return '250 OK'
async def main():
    server = Controller(SMTPHandler(),
        hostname=server_ip,
        port=server_port,
        authenticator=authenticator,
        auth_required=True,
        auth_require_tls=False,)
    server.start()
    while True:
        try:
            offset = None
            data = await get_updates(offset)
            await get_message(data)
            if len(data) > 0:
                offset = data['result'][0]['update_id'] + 1
                data = await get_updates(offset)
        except (IndexError, KeyboardInterrupt):
            pass
asyncio.run(main(), debug=True)