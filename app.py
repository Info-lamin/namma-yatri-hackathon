
import os
import pymongo
import dotenv
import requests
import datetime
from flask import abort
from flask import Flask
from flask import request
from bson import json_util
from functools import wraps
from flask.wrappers import Response
from werkzeug.datastructures import ImmutableMultiDict

dotenv.load_dotenv()
app = Flask(__name__)
VERIFY_TOKEN = 'cashwha'
MONGO_CLIENT = pymongo.MongoClient(os.getenv('MONGO_SRV'))
WHATSAPP_MESSAGES_COL = MONGO_CLIENT["namma yatri"]["whatsapp_messages"]
WHATSAPP_CONTACTS_COL = MONGO_CLIENT["namma yatri"]["whatsapp_contacts"]
whatsapp_account = {
    'ACCESS_TOKEN': os.getenv('WHATSAPP_ACCESS_TOKEN'),
    'FROM_PHONE_NUMBER_ID': os.getenv('WHATSAPP_FROM_PHONE_NUMBER_ID'),
    'WABA_ID': os.getenv('WHATSAPP_WABA_ID'),
    'FROM_PHONE_NUMBER': os.getenv('WHATSAPP_FROM_PHONE_NUMBER'),
    'VERIFY_TOKEN': os.getenv('WHATSAPP_VERIFY_TOKEN')
}

def timestamp(): return str(int(datetime.datetime.now().timestamp()))
def detimestamp(stamp): return datetime.datetime.fromtimestamp(float(stamp))
def jsonify(func):
    @wraps(func)
    def decorator(*args, **kwargs):
        obj = func(*args, **kwargs)
        if type(obj) != list:
            obj = [obj]
        obj = Response(json_util.dumps(obj))
        obj.headers.add('Content-Type', 'application/json')
        return obj
    return decorator
def requirement(*args, **kwargs):
    def decorator(func):
        @wraps(func)
        def inner_func(*_args, **_kwargs):
            message = []
            received_data = _args[0]
            for data in args+tuple(kwargs.keys()):
                if data not in received_data.keys():
                    message.append(f"Missing required argument '{data}' is required.")
                if data in kwargs.keys():
                    if received_data.get(data) not in list(kwargs.get(data)):
                        message.append(f"Invalid Argument '{received_data.get(data)}' is passed for '{data}'. Valid Arguments are {str(list(kwargs.get(data)))}")
            if message != []:
                return message
            returned_value = func(*_args, **_kwargs)
            return returned_value
        return inner_func
    return decorator
def set_creds(func):
    @wraps(func)
    def decorator(received_data=None):
        # request context will not work outside http
        if not received_data:
            received_data = dict(request.args)
        obj = func(received_data)
        return obj
    return decorator


class Message:
    def __init__(self, account) -> None:
        self.payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'text': {
                'preview_url': True
            }
        }
        self.to = None
        self.reply = None
        self.preview_url = True
        self.message = False
        self.account = account
        pass

    def set_reply(self, msg_id):
        self.payload['context'] = {
            'message_id': str(msg_id)
        }

    def send(self):
        if self.to and self.message:
            self.payload['to'] = str(self.to)
            response = requests.post(
                url=f"https://graph.facebook.com/v15.0/{self.account['FROM_PHONE_NUMBER_ID']}/messages",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f"Bearer {self.account['ACCESS_TOKEN']}"
                },
                json=self.payload
            )
            return response.json()

    def set_message(self, message):
        self.message = True
        self.payload['type'] = 'text'
        self.payload['text'] = {
            'preview_url': self.preview_url,
            'body': message
        }

    def set_template(self, to, template_name, language='en', header_parameter=None, body_parameters=None, url_suffix=None, reply_payloads=None):
        to = str(to)
        if len(to) == 10:
            to = f"91{to}"
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language
                },
                "components": []
            }
        }

        if header_parameter:
            if str(header_parameter).startswith('http'):
                payload['template']['components'].append(
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "image",
                                "image": {
                                    "link": str(header_parameter)
                                }
                            }
                        ]
                    }
                )
            else:
                payload['template']['components'].append(
                    {
                        "type": "header",
                        "parameters": [
                            {
                                "type": "text",
                                "text": str(header_parameter)
                            }
                        ]
                    }
                )

        if body_parameters:
            body_payload = {
                "type": "body",
                "parameters": []
            }
            for parameter in body_parameters:
                body_payload['parameters'].append(
                    {
                        "type": "text",
                        "text": str(parameter)
                    }
                )
            payload['template']['components'].append(body_payload)

        if url_suffix:
            payload['template']['components'].append(
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": 0,
                    "parameters": [
                        {
                            "type": "text",
                            "text": str(url_suffix)
                        }
                    ]
                }
            )

        if reply_payloads:
            for index, reply_payload in enumerate(reply_payloads):
                payload['template']['components'].append(
                    {
                        "type": "button",
                        "sub_type": "quick_reply",
                        "index": index,
                        "parameters": [
                            {
                                "type": "payload",
                                "payload": reply_payload
                            }
                        ]
                    }
                )

        self.payload = payload
        self.message = True
        self.to = to

    def set_list(self, message, display_text, list_items, header=None, footer=None):
        '''
        [
            {
                'section_title': '<title>',
                'body': [
                    {
                        'id': '<id>',
                        'title': '<title>',
                        'description': '<description>'
                    }
                ]
            }
        ]
        '''
        self.message = True
        self.payload['type'] = 'interactive'
        data = dict()
        data['type'] = 'list'
        if header:
            data['header'] = {
                'type': 'text',
                'text': str(header)
            }
        if message:
            data['body'] = {
                'text': str(message)
            }
        if footer:
            data['footer'] = {
                'text': str(footer)
            }
        sections = []
        for list_item in list_items:
            sections.append(
                {
                    'title': list_item['section_title'],
                    'rows': list_item['body']
                }
            )
        data['action'] = {
            'button': str(display_text),
            'sections': sections
        }
        self.payload['interactive'] = data

    def get_templates(self):
        templates = []
        url = f"https://graph.facebook.com/v16.0/{self.account['WABA_ID']}/message_templates"
        while True:
            response = requests.get(
                url=url,
                headers={
                    'Authorization': f"Bearer {self.account['ACCESS_TOKEN']}"
                },
            ).json()
            templates.extend(response['data'])
            if 'next' in dict(response['paging']).keys():
                url = response['paging']['next']
            else:
                break
            if 'error' in response.keys():
                return response
        return templates

    def mark_message_read(self, msg_id):
        response = requests.post(
            url=f"https://graph.facebook.com/v15.0/{self.account['FROM_PHONE_NUMBER_ID']}/messages",
            headers={
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {self.account['ACCESS_TOKEN']}"
            },
            json={
                'messaging_product': 'whatsapp',
                'status': 'read',
                'message_id': msg_id
            }
        )
        return response.json()


@app.route('/')
def index():
    return 'Welcome to cashwha module.'


@app.route('/send_message', methods=['POST'])
@jsonify
@set_creds
@requirement('to', 'message')
def send_message(received_data:dict):
    '''
    {
        'to',
        'message',
        'context'
    }
    '''
    msg = Message(received_data['account'])
    msg.to = received_data['to']
    msg.set_message(received_data['message'])
    if received_data.get('context'):
        msg.set_reply(received_data['context'])
    response = dict(msg.send())
    if 'error' in response.keys():
        return jsonify(response)
    stamp = timestamp()
    document = {
        'messaging_product': response['messaging_product'],
        'to_number': response['contacts'][0]['wa_id'],
        'from_number': received_data['account']['FROM_PHONE_NUMBER'],
        'from_id': received_data['account']['FROM_PHONE_NUMBER_ID'],
        'content_type': 'text',
        'body': {
            'body': received_data['message']
        },
        'message_id': response['messages'][0]['id'],
        'timestamp': stamp,
        'message_flow': 'sent',
        'status': 'initiated'
    }
    if received_data.get('context'):
        document['context'] = received_data['context']
    WHATSAPP_MESSAGES_COL.insert_one(document)
    # Contacts
    old_contact = WHATSAPP_CONTACTS_COL.find_one({
        'from_number': received_data['account']['FROM_PHONE_NUMBER'],
        'number': document['to_number']
    })
    if old_contact:
        if int(stamp) > int(old_contact['update_timestamp']):
            WHATSAPP_CONTACTS_COL.update_one(
                {
                    'from_number': received_data['account']['FROM_PHONE_NUMBER'],
                    'number': document['to_number']
                },
                {
                    '$set': {
                        'update_timestamp': stamp
                    }
                }
            )
    else:
        contact = {
            'from_number': received_data['account']['FROM_PHONE_NUMBER'],
            'number': document['to_number'],
            'display': document['to_number'],
            'expiration_timestamp': '1000000000',
            'update_timestamp': stamp,
            'last_incoming_msg_id': '',
            'status': 'read'
        }
        WHATSAPP_CONTACTS_COL.insert_one(contact)
    return 'ok'


@app.route('/get_templates', methods=['POST'])
@jsonify
@set_creds
def get_templates(received_data:dict):
    msg = Message(received_data['account'])
    return msg.get_templates()


@app.route('/send_template', methods=['POST'])
@jsonify
@set_creds
@requirement('to', 'template_name', 'language')
def send_template(received_data:dict):
    '''
    {
        'to',
        'template_name',
        'language'='en',
        'header_parameter',
        'body_parameters',
        'url_suffix'
        'reply_payloads'
    }
    '''
    account = received_data.pop('account')
    msg = Message(account)
    msg.set_template(**received_data)
    response = dict(msg.send())
    if 'error' in response.keys():
        return response
    # Message
    stamp = timestamp()
    for template in msg.get_templates():
        if template['name'] == received_data.get('template_name'):
            body = {}
            for component in template['components']:
                if component['type'] == 'HEADER':
                    header = {}
                    if received_data.get('header_parameter'):
                        if component['format'] == 'TEXT':
                            header['type'] = 'text'
                            header['body'] = str(component['text']).replace('{{1}}', received_data['header_parameter'])
                        if component['format'] == 'MEDIA':
                            pass
                    else:
                        header['type'] = str(component['format']).lower()
                        header['body'] = component[str(component['format']).lower()]
                    body['header'] = header
                if component['type'] == 'BODY':
                    content = str(component['text'])
                    for index, variable in enumerate(received_data.get('body_parameters', [])):
                        content.replace('{{'+str(index)+'}}', variable)
                    body['body'] = content
                if component['type'] == 'FOOTER':
                    body['footer'] = component['text']
                if component['type'] == 'BUTTONS':
                    buttons = []
                    for button in component['buttons']:
                        new_button = {}
                        if button['type'] == 'URL':
                            new_button['type'] = 'url'
                            content = str(button['url'])
                            if received_data.get('url_suffix'):
                                content.replace('{{1}}', received_data['url_suffix'])
                            new_button['body'] = content
                            new_button['value'] = button['url']
                        if button['type'] == 'PHONE_NUMBER':
                            new_button['type'] = 'phone_number'
                            new_button['body'] = button['text']
                            new_button['value'] = button['phone_number']
                        # quick reply
                        buttons.append(new_button)
                    body['buttons'] = buttons
            document = {
                'messaging_product': response['messaging_product'],
                'to_number': response['contacts'][0]['wa_id'],
                'from_number': account['FROM_PHONE_NUMBER'],
                'from_id': account['FROM_PHONE_NUMBER_ID'],
                'content_type': 'template',
                'body': body,
                'message_id': response['messages'][0]['id'],
                'timestamp': stamp,
                'message_flow': 'sent',
                'status': 'initiated'
            }
            WHATSAPP_MESSAGES_COL.insert_one(document)
            break
    # Contact
    old_contact = WHATSAPP_CONTACTS_COL.find_one({
        'from_number': account['FROM_PHONE_NUMBER'],
        'number': document['to_number']
    })
    if old_contact:
        if int(stamp) > int(old_contact['update_timestamp']):
            WHATSAPP_CONTACTS_COL.update_one(
                {
                    'from_number': account['FROM_PHONE_NUMBER'],
                    'number': document['to_number']
                },
                {
                    '$set': {
                        'update_timestamp': stamp
                    }
                }
            )
    else:
        contact = {
            'from_number': account['FROM_PHONE_NUMBER'],
            'number': document['to_number'],
            'display': document['to_number'],
            'expiration_timestamp': '1000000000',
            'update_timestamp': stamp,
            'last_incoming_msg_id': '',
            'status': 'read'
        }
        WHATSAPP_CONTACTS_COL.insert_one(contact)
    return 'ok'


@app.route('/get_chat_contacts', methods=['POST'])
@jsonify
@set_creds
@requirement('number', 'increment')
def get_chat_contacts(received_data:dict):
    '''
        {
            'number',
            'increment
        }
    '''
    number = received_data.get('number')
    increment = int(received_data.get('increment'))
    collection = list(WHATSAPP_CONTACTS_COL.find({
        'from_number': received_data['account']['FROM_PHONE_NUMBER']
    }).sort('update_timestamp', -1))
    if number == 'initial':
        documents = collection[0: increment]
    else:
        for index, document in enumerate(collection):
            if number == document['number']:
                documents = collection[index+1: index + increment + 1]
                break
    return documents


@app.route('/get_chat_messages', methods=['POST'])
@jsonify
@set_creds
@requirement('to_number', 'message_id', 'increment')
def get_chat_messages(received_data:dict):
    '''
        {
            'to_number',
            'message_id',
            'increment'
        }
    '''
    to_number = received_data.get('to_number')
    message_id = received_data.get('message_id')
    increment = int(received_data.get('increment'))
    collection = list(WHATSAPP_MESSAGES_COL.find({
        'from_number': received_data['account']['FROM_PHONE_NUMBER'],
        'to_number': to_number
    }).sort('timestamp', -1))
    if message_id == 'initial':
        documents = collection[0: increment]
    else:
        documents = []
        for index, document in enumerate(collection):
            if message_id == document['message_id']:
                documents = collection[index+1: index + increment + 1]
                break
    return documents


@app.route('/send_reaction', methods=['POST'])
@jsonify
@set_creds
def send_reaction():
    return ''


@app.route('/send_media', methods=['POST'])
@jsonify
@set_creds
def send_media():
    return ''


@app.route('/get_media', methods=['POST'])
@set_creds
@requirement('media_id')
def get_media(received_data:dict):
    response = requests.get(
        url=f"https://graph.facebook.com/v15.0/{received_data['media_id']}?phone_number_id={received_data['account']['FROM_PHONE_NUMBER_ID']}",
        headers={
            'Authorization': f"Bearer {received_data['account']['ACCESS_TOKEN']}"
        }
    ).json()
    mime_type = response['mime_type']
    response = requests.get(
        url=response['url'],
        headers={
            'Authorization': f"Bearer {received_data['account']['ACCESS_TOKEN']}"
        }
    )
    return Response(
        response.content, 
        headers={
            'Content-Disposition': f"attachment; filename=\"{received_data['account']['FROM_PHONE_NUMBER']}_{received_data['media_id']}.{str(mime_type).split('/')[1]}\"",
            'file-name': f"{received_data['account']['FROM_PHONE_NUMBER']}_{received_data['media_id']}.{str(mime_type).split('/')[1]}"
        }, 
        mimetype=mime_type
    )


@app.route('/set_status', methods=['POST'])
@jsonify
@set_creds
@requirement('to', status=['read', 'unread'])
def mark_read(received_data:dict):
    '''{
        'to'
        'status'  # <read, unread>
    }'''
    document = WHATSAPP_CONTACTS_COL.find_one({
        'from_number': received_data['account']['FROM_PHONE_NUMBER'],
        'number': received_data['to']
    })
    WHATSAPP_CONTACTS_COL.update_one(
        {
            'from_number': received_data['account']['FROM_PHONE_NUMBER'],
            'number': received_data['to']
        },
        {
            '$set': {
                'status': received_data['status']
            }
        }
    )
    if received_data['status'] == 'read' and document['status'] != 'read' and document['last_incoming_msg_id'] != '':
        msg = Message(received_data['account'])
        response = msg.mark_message_read(document['last_incoming_msg_id'])
        if 'error' in dict(response).keys():
            return response
    return 'ok'


@app.route('/send_button_message', methods=['POST'])
@jsonify
@set_creds
def send_button_message():
    return ''


@app.route('/send_list_message', methods=['POST'])
@jsonify
@set_creds
def send_list_message():
    return ''


@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode and token:
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                return challenge
        abort(403)
    try:
        received_data = request.get_json()
        from_id = received_data['entry'][0]['changes'][0]['value']['metadata']['phone_number_id']
        from_number = received_data['entry'][0]['changes'][0]['value']['metadata']['display_phone_number']
        if 'statuses' in dict(received_data['entry'][0]['changes'][0]['value']).keys():
            to_number = received_data['entry'][0]['changes'][0]['value']['statuses'][0]['recipient_id']
            status = received_data['entry'][0]['changes'][0]['value']['statuses'][0]['status']
            message_id = received_data['entry'][0]['changes'][0]['value']['statuses'][0]['id']
            stamp = received_data['entry'][0]['changes'][0]['value']['statuses'][0]['timestamp']
            document = WHATSAPP_MESSAGES_COL.find_one({
                'to_number': to_number,
                'from_number': from_number,
                'message_id': message_id
            })
            levels = {
                'initiated': 0,
                'sent': 1,
                'delivered': 2,
                'read': 3,
                'failed': 4,
                'deleted': 5
            }
            if not document:
                return ''
            if levels[status] > levels[document['status']]:
                update = {
                    'status': status
                }
                if status == 'failed':
                    # make a append
                    update['errors'] = received_data['entry'][0]['changes'][0]['value']['statuses'][0]['errors']
                WHATSAPP_MESSAGES_COL.update_one(
                    {
                        'to_number': to_number,
                        'from_number': from_number,
                        'message_id': message_id
                    },
                    {
                        '$set': update
                    }
                )
        if 'messages' in dict(received_data['entry'][0]['changes'][0]['value']).keys():
            message = dict(received_data['entry'][0]['changes'][0]['value']['messages'][0])
            to_number = message['from']
            message_id = message['id']
            stamp = message['timestamp']
            content_type = message.get('type')
            document = {
                'messaging_product': received_data['entry'][0]['changes'][0]['value']['messaging_product'],
                'to_number': to_number,
                'from_id': from_id,
                'from_number': from_number,
                'message_id': message_id,
                'timestamp': stamp,
                'message_flow': 'received',
                'status': 'received'
            }
            if message.get('context'):
                document['context'] = message['context']
            if content_type == 'text':
                document['content_type'] = 'text'
                document['body'] = message['text']
            elif content_type == 'image':
                document['content_type'] = 'image'
                document['body'] = message['image']
            elif content_type == 'interactive':
                document['content_type'] = message['type']
                document['body'] = message[message['type']]
            elif content_type == 'document':
                document['content_type'] = 'document'
                document['body'] = message['document']
            elif content_type == 'audio':
                document['content_type'] = 'audio'
                document['body'] = message['audio']
            elif content_type == 'sticker':
                document['content_type'] = 'sticker'
                document['body'] = message['sticker']
            elif content_type == 'order':
                document['content_type'] = 'order'
                document['body'] = message['order']
            elif content_type == 'video':
                document['content_type'] = 'video'
                document['body'] = message['video']
            elif content_type == 'button':
                document['content_type'] = 'text'
                document['body'] = message['text']
                document['payload'] = message['payload']
            elif content_type == 'contacts':
                document['content_type'] = 'contacts'
                document['body'] = message['contacts']
            elif content_type == 'location':
                document['content_type'] = 'location'
                document['body'] = message['location']
            elif content_type == 'unsupported':
                document['content_type'] = 'unsupported'
                document['body'] = message['errors']
            elif content_type == 'system':
                document['content_type'] = 'system'
                document['body'] = message['system']
            elif content_type == 'reaction':
                reactions = list(dict(WHATSAPP_MESSAGES_COL.find_one(
                    {
                        'from_number': from_number,
                        'message_id': message['reaction']['message_id']
                    }
                )).get('reactions', []))
                reactions.append({
                    'type': 'received',
                    'emoji': message['reaction']['emoji']
                })
                WHATSAPP_MESSAGES_COL.update_one(
                    {
                        'from_number': from_number,
                        'message_id': message['reaction']['message_id']
                    },
                    {
                        '$set': {
                            'reactions': reactions
                        }
                    }
                )
            else:
                pass # mail the payload
            if document.get('body'):
                WHATSAPP_MESSAGES_COL.insert_one(document)
                # Contact
                old_contact = WHATSAPP_CONTACTS_COL.find_one({
                    'from_number': from_number,
                    'number': document['to_number']
                })
                if old_contact:
                    if int(stamp) > int(old_contact['update_timestamp']):
                        WHATSAPP_CONTACTS_COL.update_one(
                            {
                                'from_number': from_number,
                                'number': document['to_number']
                            },
                            {
                                '$set': {
                                    'expiration_timestamp': str(int(stamp) + 86400),
                                    'update_timestamp': stamp,
                                    'last_incoming_msg_id': document['message_id'],
                                    'status': 'unread'
                                }
                            }
                        )
                else:
                    contact = {
                        'from_number': from_number,
                        'number': document['to_number'],
                        'display': document['to_number'],
                        'expiration_timestamp': str(int(stamp) + 86400),
                        'update_timestamp': stamp,
                        'last_incoming_msg_id': document['message_id'],
                        'status': 'unread'
                    }
                    WHATSAPP_CONTACTS_COL.insert_one(contact)
        return ''
    except:
        return '' # mail payload


@app.before_request
def before_request_func():
    if request.path not in ['/', '/cashwha/webhook']:
        if request.headers.get('X-Api-Key') != whatsapp_account['VERIFY_TOKEN']:
            return 'Authentication Failed'
        http_args = request.get_json()
        http_args['account'] = whatsapp_account
        request.args = ImmutableMultiDict(http_args)


# To remove CORS error on the client side
@app.after_request
def after_request_func(response: Response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Credentials', True)
    response.headers.add(
        'Access-Control-Allow-Headers',
        'Origin,Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,locale')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response


'''
Contacts
--------------------------------------------------
| from_number          | 919876543210            |
| number               | 9198765432210           |
| display              | <919876543210 | 'Name'> |
| expiration_timestamp | 234567890               |
| update_timestamp     | 1234567890              |
| last_incoming_msg_id | 'wamid.random'          |
| status               | <'read', 'unread'>      |
--------------------------------------------------

Whatsapp Fields
--------------------------------------------------------------------------------
| messaging_product | 'whatsapp'                                               |
| to_number         | 919876542310                                             |
| from_number       | 919876542310                                             |
| from_id           | 0123456789                                               |
| context           | {'id', 'from', 'forwarded', 'frequently_forwarded'}      |
| content_type      | <'text' | 'image' .....>                                 |
| body              | --->>> Message Content  ------------------------->>>------------------------
| message_id        | 'wamid.random_text'                                      |                 |
| timestamp         | 1234567890                                               |                 |
| message_flow      | <'sent' | 'received'>                                    |                 |
| status            | <'initiated' | 'sent' | 'delivered' | 'read' | 'failed'> |                 |
--------------------------------------------------------------------------------                 |
&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&             v
Message Content Types                                                                            v
------------------------------------------------------------------------------------------       |
| text         | {'body'}                                                                |       |
| image        | {'id', 'caption', 'mime_type', 'sha256'}                                |       |
| button_reply | {'id', 'title'}                                                         |       |
| list_reply   | {'id', 'title', 'description'}                                          |       |
| document     | {'id', 'caption', 'mime_type'}                                          |       |
| audio        | {'id'}                                                                  |       |
| sticker      | {'id', 'animated', 'mime_type', 'sha256'}                               |       |
| order        | {'catalog_id', 'text', 'product_items'}                                 |       |
| video        | {'id'}                                                                  |       |
| contacts     | [{'addresses', 'birthdays', 'emails', 'name', 'org', 'phones', 'urls'}] | <<-----
| location     | {'latitude', 'longitude', 'name', 'address'}                            |
| unsupported  | [{'code', 'details', 'title'}]                                          |
| system       | {'body', 'identity', 'new_wa_id'}                                       |
| template     | {'header', 'body', 'footer', 'buttons'<type, body, value>}              |
------------------------------------------------------------------------------------------
'''
