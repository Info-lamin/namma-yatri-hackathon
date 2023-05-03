import smtplib
import datetime
import requests
from flask import request
from bson import json_util
from flask import Response
from functools import wraps
from email.message import Message as EmailMessage

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
def mail(from_address, to_address, password, subject, message, priority):   #it sends the mail,  only gmails without two factor authentication are supported
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        m = EmailMessage()
        m['From'] = from_address
        m['To'] = to_address
        m['X-Priority'] = str(priority)
        m['Subject'] = subject
        m.set_payload(message)
        smtp.login(from_address, password)
        smtp.sendmail(from_address, to_address, m.as_string())
    return None

class Message:
    def __init__(self, account) -> None:
        self.payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual'
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
            if self.preview_url:
                if self.payload.get('text'):
                    self.payload['text']['preview_url'] = True
                else:
                    self.payload['text'] = {
                        'preview_url': True
                    }
            self.payload['to'] = str(self.to)
            response = requests.post(
                url=f"https://graph.facebook.com/v16.0/{self.account['FROM_PHONE_NUMBER_ID']}/messages",
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f"Bearer {self.account['ACCESS_TOKEN']}"
                },
                json=self.payload
            )
            mail(
                'mail.orderbywhatsapp@gmail.com', 
                "laminkutty@gmail.com", 
                'svgtkoddwibptyii', 
                "Error from OrderByWhatsapp", 
                f"{response.status_code} {response.text}",
                1
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
        self.preview_url = False
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
    