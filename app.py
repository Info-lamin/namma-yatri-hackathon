import os
import dotenv
import pymongo
import requests
import datetime
import threading
from functions import *
from flask import abort
from flask import Flask
from flask import request
from flask import session
from bson import json_util
from flask import redirect
from functools import wraps
from flask import render_template
from flask.wrappers import Response
from werkzeug.datastructures import ImmutableMultiDict

dotenv.load_dotenv()
app = Flask(__name__)
VERIFY_TOKEN = 'cashwha'
MONGO_CLIENT = pymongo.MongoClient(os.getenv('MONGO_SRV'))
WHATSAPP_CONTACTS_COL = MONGO_CLIENT["namma_yatri"]["whatsapp_contacts"]
DRIVERS_COL = MONGO_CLIENT["namma_yatri"]["drivers"]


def make_order():
    # create a new order and return the ride no.
    # put the order in the drivers pool to be picked
    return None


def incoming_message(contact: dict, message: dict):
    booking_status = contact.get('booking_status', {})
    if message.get('content_type') == 'location':
        if booking_status.get('value') == 'awaiting from location':
            # send_message({
            #     'to': contact.get('number'),
            #     'message': 'Thank You sending your current location.\n\nPlease send your destination location to book your ride.',
            #     'context': message.get('message_id')
            # })
            booking_status['value'] = 'awaiting to location'
            booking_status['data'].append(message['body'])
            WHATSAPP_CONTACTS_COL.update_one({
                'number': contact.get('number')
            }, {
                '$set': {
                    'booking_status': booking_status
                }
            })
            return None # The user sends a from location and the server requests to send a to location
        if booking_status.get('value') == 'awaiting to location':
            # initiate order
            # send_message({
            #     'to': contact.get('number'),
            #     'message': 'Your Ride has been initialised',
            #     'context': message.get('message_id')
            # })
            booking_status['value'] = 'awaiting to location'  # change this
            booking_status['data'].append(message['body'])
            WHATSAPP_CONTACTS_COL.update_one({
                'number': contact.get('number')
            }, {
                '$set': {
                    'booking_status': booking_status
                }
            })
            make_order()
            return None # The user sends the to location and the server initiates the order
            # The order is sent back to the customer and sent to the drivers pool
        return None # you have to initialise the order first to send your location
    if message.get('content_type') == 'text':
        message_body = message.get('body', {}).get('body')
        if message_body == 'Book a Ride':
            return None # the server requests for the current location
        return None # The user sent a unknown message so start with a new conversation
    return None

# 1. Driver picks the order and the driver details and OTP is sent to the customer
# 2. Driver enters the OTP from the customer to authenticate
# 3. On successful authentication the to location is sent to the driver

@app.route('/driver', methods=['GET', 'POST'])
def driver():
    mode = request.args.get('mode')
    method = request.method
    if mode == 'login':
        if method == 'GET':
            return render_template('login.html') # login page
        else:
            username = request.form['username']
            password = request.form['password']
            user = DRIVERS_COL.find_one({'username': username, 'password': password})
            if user is None:
                return 'Invalid username or password'
            session['logged_in'] = username
            return redirect('/driver')# authenticate the login credentials
    if mode == 'register':
        if method == 'GET':
            return render_template('register.html') # register page
        else:
            username = request.form['username']
            password = request.form['password']
            if DRIVERS_COL.find_one({'username': username}) is not None:
                return 'Username already exists'
            user = {'username': username, 'password': password}
            DRIVERS_COL.insert_one(user)
            return redirect('/driver?mode=login') # save the driver details
    if mode == 'logout':
        session.pop('logged_in', None)
        return redirect('/driver?mode=login') # logout the user
    if mode == 'rides':
        return None # respond with the list of rides available
    if mode == 'ride':
        request.args.get('ride_no')
        return None # display the ride details
    if mode == 'pick_ride':
        request.args.get('ride_no')
        if method == 'POST':
            return None # allocate the ride to the driver if available else return no
            # send the driver details and otp to customer
    if mode == 'authenticate_ride':
        request.args.get('ride_no')
        if method == 'GET':
            return None # return a page to enter otp
        else:
            request.args.get('otp')
            return None # authenticate otp and redirect
    if mode == 'end_ride':
        request.args.get('ride_no')
        if method == 'POST':
            return None # ends the ride and server requests for the feedback from customer
    return None # return home page


# def send_message(received_data:dict):
#     '''
#     {
#         'to',
#         'message',
#         'context'
#     }
#     '''
#     msg = Message(received_data['account'])
#     msg.to = received_data['to']
#     msg.set_message(received_data['message'])
#     if received_data.get('context'):
#         msg.set_reply(received_data['context'])
#     response = dict(msg.send())
#     if 'error' in response.keys():
#         return jsonify(response)
#     stamp = timestamp()
#     document = {
#         'messaging_product': response['messaging_product'],
#         'to_number': response['contacts'][0]['wa_id'],
#         'from_number': received_data['account']['FROM_PHONE_NUMBER'],
#         'from_id': received_data['account']['FROM_PHONE_NUMBER_ID'],
#         'content_type': 'text',
#         'body': {
#             'body': received_data['message']
#         },
#         'message_id': response['messages'][0]['id'],
#         'timestamp': stamp,
#         'message_flow': 'sent',
#         'status': 'initiated'
#     }
#     if received_data.get('context'):
#         document['context'] = received_data['context']
#     # Contacts
#     old_contact = WHATSAPP_CONTACTS_COL.find_one({
#         'from_number': received_data['account']['FROM_PHONE_NUMBER'],
#         'number': document['to_number']
#     })
#     if old_contact:
#         if int(stamp) > int(old_contact['update_timestamp']):
#             WHATSAPP_CONTACTS_COL.update_one(
#                 {
#                     'from_number': received_data['account']['FROM_PHONE_NUMBER'],
#                     'number': document['to_number']
#                 },
#                 {
#                     '$set': {
#                         'update_timestamp': stamp
#                     }
#                 }
#             )
#     else:
#         contact = {
#             'from_number': received_data['account']['FROM_PHONE_NUMBER'],
#             'number': document['to_number'],
#             'display': document['to_number'],
#             'expiration_timestamp': '1000000000',
#             'update_timestamp': stamp,
#             'last_incoming_msg_id': '',
#             'status': 'read',
#             'booking_status': {
#                 'value': 0,
#                 'data': []
#             }
#         }
#         WHATSAPP_CONTACTS_COL.insert_one(contact)
#     return 'ok'




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
                pass
            else:
                pass # mail the payload
            if document.get('body'):
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
                        'status': 'unread',
                        'booking_status': {
                            'value': 0,
                            'data': []
                        }
                    }
                    WHATSAPP_CONTACTS_COL.insert_one(contact)
                contact = WHATSAPP_CONTACTS_COL.find_one({
                    'from_number': from_number,
                    'number': document['to_number']
                })
                th = threading.Thread(target=incoming_message, args=(contact, message))
                th.start()
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
| booking_status       | {value, data}           |
--------------------------------------------------
'''
