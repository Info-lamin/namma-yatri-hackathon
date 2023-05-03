import os
import dotenv
import random
import string
import pymongo
import threading
from functions import *
from flask import abort
from flask import Flask
from flask import request
from flask import session
from flask import redirect
from flask import render_template
from flask.wrappers import Response
from werkzeug.datastructures import ImmutableMultiDict

dotenv.load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = 'my custom secret key'
MONGO_CLIENT = pymongo.MongoClient(os.getenv('MONGO_SRV'))
WHATSAPP_CONTACTS_COL = MONGO_CLIENT["namma_yatri"]["whatsapp_contacts"]
RIDES_COL = MONGO_CLIENT["namma_yatri"]["rides"]
DRIVERS_COL = MONGO_CLIENT["namma_yatri"]["drivers"]
whatsapp_account = {
    'ACCESS_TOKEN': os.getenv('WHATSAPP_ACCESS_TOKEN'),
    'FROM_PHONE_NUMBER_ID': os.getenv('WHATSAPP_FROM_PHONE_NUMBER_ID'),
    'WABA_ID': os.getenv('WHATSAPP_WABA_ID'),
    'FROM_PHONE_NUMBER': os.getenv('WHATSAPP_FROM_PHONE_NUMBER'),
    'VERIFY_TOKEN': os.getenv('WHATSAPP_VERIFY_TOKEN')
}


@app.route('/')
def index():
    return redirect(f"https://api.whatsapp.com/send?phone={whatsapp_account['FROM_PHONE_NUMBER']}&text=Hi")


def unique_order_id():
    rand_text = ''.join(random.choices(string.digits , k=6))
    document = RIDES_COL.find_one({'order_id': rand_text})
    if document == None:
        return rand_text
    return unique_order_id()


def make_order(booking_status):
    # create a new order and r1eturn the ride no.
    # put the order in the drivers pool to be picked
    order_id = unique_order_id()
    otp = ''.join(random.choices(string.digits , k=5))
    booking_status['order_id'] = order_id
    booking_status['otp'] = otp
    RIDES_COL.insert_one(dict(booking_status))
    return order_id, otp


def incoming_message(contact: dict, message: dict):
    msg = Message(whatsapp_account)
    msg.to = contact.get('number')
    booking_status = contact.get('booking_status', {})
    if message.get('content_type') == 'location':
        if booking_status.get('value') == 'awaiting from location':
            msg.set_message('Thank you please send your to location.')
            msg.send()
            booking_status['value'] = 'awaiting to location'
            booking_status['from'] = message['body']
            WHATSAPP_CONTACTS_COL.update_one(
                {
                    '_id': contact.get('_id')
                },
                {
                    '$set': {
                        'booking_status': booking_status
                    }
                }
            )
            return None # The user sends a from location and the server requests to send a to location
        if booking_status.get('value') == 'awaiting to location':
            booking_status['value'] = 'ride scheduled'
            booking_status['to'] = message['body']
            booking_status['contact'] = contact.get('number')
            ride_no, otp = make_order(booking_status)
            msg.set_message(f"*Ride No. {ride_no}*\nThank you for using Namma Yatri.\nYour ride has been scheduled and you will be notified once the ride is alotted.\n\nYour OTP is *{otp}*")
            msg.send()
            WHATSAPP_CONTACTS_COL.update_one(
                {
                    '_id': contact.get('_id')
                },
                {
                    '$set': {
                        'booking_status': booking_status
                    }
                }
            )
            return None # The user sends the to location and the server initiates the order
            # The order is sent back to the customer and sent to the drivers pool
        msg.set_message('Kindly initiate the ride before sending your location.')
        msg.send()
        return None # you have to initialise the order first to send your location
    if message.get('content_type') == 'interactive':
        message_body = message.get('body', {}).get('list_reply', {}).get('title')
        message_id = message.get('body', {}).get('list_reply', {}).get('id', '')
        if message_body == 'Book a Ride':
            msg.set_message('Please Send Your current Location to Book a Ride')
            msg.send()
            booking_status['value'] = 'awaiting from location'
            WHATSAPP_CONTACTS_COL.update_one(
                {
                    '_id': contact.get('_id')
                },
                {
                    '$set': {
                        'booking_status': booking_status
                    }
                }
            )
            return None # the server requests for the current location
        if message_body == 'Customer Care':
            msg.set_message('You can contact Customer Care on call via +91 94885 60252\n\nThank you for using Namma Yatri. Have a nice day.')
            msg.send()
            return None
        if message_body == 'Reset':
            booking_status = {'value': 0}
            WHATSAPP_CONTACTS_COL.update_one(
                {
                    '_id': contact.get('_id')
                },
                {
                    '$set': {
                        'booking_status': booking_status
                    }
                }
            )
            msg.set_message('Thank You your data has been resetted.')
            msg.send()
            message['content_type'] = 'text'
            msg = Message(whatsapp_account)
            msg.to = contact.get('number')
        if 'rate' in message_id:
            _, rate, ride_no = message_id.split('_')
            RIDES_COL.update_one(
                {
                    'order_id': ride_no
                },
                {
                    '$set': {
                        'rate': rate
                    }
                }
            )
    if message.get('content_type') == 'text':
        msg.set_list(
            'Hello Welcome to Namma Yatri.', 
            'Option', 
            [
                {
                    'section_title': 'Please Select an Option',
                    'body': [
                        {
                            'id': '1',
                            'title': 'Book a Ride'
                        },
                        {
                            'id': '2',
                            'title': 'Customer Care'
                        },
                        {
                            'id': '3',
                            'title': 'Reset'
                        }
                    ]
                }
            ]
        )
        msg.send()
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
        if not session.get('logged_in'):
            return redirect('/driver')
        documents = RIDES_COL.find({'value': 'ride scheduled'})
        return render_template('rides.html', documents=documents) # respond with the list of rides available
    if mode == 'pick_ride':
        if not session.get('logged_in'):
            return redirect('/driver')
        ride_no = request.args.get('ride_no')
        document = RIDES_COL.find_one({'order_id': ride_no})
        if not document:
            return 'Invalid Ride No'
        if request.method == 'GET':
            return render_template('ride.html', document=document)
        otp = request.form.get('otp')
        if document['otp'] == otp:
            RIDES_COL.update_one(
                {
                    'order_id': ride_no
                },
                {
                    '$set': {
                        'value': 'ride ended'
                    }
                }
            )
            msg = Message(whatsapp_account)
            msg.to = document['contact']
            msg.set_list(
                'Thank You for choosing Namma Yatri.\nWe hope you had an great experience riding.\nKindly rate this ride.', 
                'Rate Us', 
                [
                    {
                        'section_title': 'Rate Us',
                        'body': [
                            {
                                'id': f"rate_5_{ride_no}",
                                'title': '⭐⭐⭐⭐⭐'
                            },
                            {
                                'id': f"rate_4_{ride_no}",
                                'title': '⭐⭐⭐⭐'
                            },
                            {
                                'id': f"rate_3_{ride_no}",
                                'title': '⭐⭐⭐'
                            },
                            {
                                'id': f"rate_2_{ride_no}",
                                'title': '⭐⭐'
                            },
                            {
                                'id': f"rate_1_{ride_no}",
                                'title': '⭐'
                            }
                        ]
                    }
                ]
            )
            msg.send()
            return 'Ride Ended Successfully'
        return 'Invalid OTP' # allocate the ride to the driver if available else return no
        # send the driver details and otp to customer
    return render_template('home.html') # return home page


@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode and token:
            if mode == 'subscribe' and token == whatsapp_account['VERIFY_TOKEN']:
                return challenge
        abort(403)
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
                        'value': 0
                    }
                }
                WHATSAPP_CONTACTS_COL.insert_one(contact)
            contact = WHATSAPP_CONTACTS_COL.find_one({
                'from_number': from_number,
                'number': document['to_number']
            })
            incoming_message(contact, document)
            # th = threading.Thread(target=incoming_message, args=(contact, document))
            # th.start()
    return ''


@app.before_request
def before_request_func():
    if request.path not in ['/', '/webhook', '/driver']:
        if request.headers.get('X-Api-Key') != whatsapp_account['VERIFY_TOKEN']:
            return 'Authentication Failed', 401
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
