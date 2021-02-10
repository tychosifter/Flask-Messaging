from flask import Flask, render_template, flash, redirect, url_for, session, request, abort
from flask_sqlalchemy import SQLAlchemy
from uuid import uuid4
from flask_socketio import SocketIO, emit, Namespace
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import random, string
from sqlalchemy import exists, case, distinct
from flask_moment import Moment
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'Your_secret_KEY-H3rE'


db = SQLAlchemy(app)
socketio = SocketIO(app)
login_manager = LoginManager(app)
moment = Moment(app)


login_manager.login_view = 'login'
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


#Random string generator used for message and thread ID's
def randstrurl(type, pmthread=None):
	letters = string.ascii_lowercase
	randstr =  ''.join(random.choice(letters) for i in range(8))

	if pmthread:
		if not db.session.query(exists().where(Message.thread_id == randstr)).scalar():
			return randstr
		else:
			randstrurl(type=Message, pmthread=True)

	if not db.session.query(exists().where(type.url == randstr)).scalar():
		return randstr
	else:
		randstrurl(type=type)
############

#Database models
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80))
    password = db.Column(db.String(80))
    websocket_id = db.Column(db.String, unique=True, index=True)


class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer(), primary_key=True)
    url = db.Column(db.String())
    sender_id = db.Column(db.String())
    recipient_id = db.Column(db.String())
    subject = db.Column(db.String())
    body = db.Column(db.String())
    timestamp = db.Column(db.DateTime)
    read = db.Column(db.Boolean(), default=False)
    thread_id = db.Column(db.String())
    sender_del = db.Column(db.Boolean())
    recipient_del = db.Column(db.Boolean())
############

#App view routes
@app.route("/")
def index():
    return render_template("index.html")


@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username').lower()
    password = request.form.get('password')
    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password, password):
        flash('Please check your login details and try again.')
        return redirect(url_for('login'))
    login_user(user)
    return redirect(url_for('messages'))


@app.route('/register')
def register():
    return render_template('register.html')


@app.route('/register', methods=['POST'])
def register_post():

    username = request.form.get('username').lower()
    password = request.form.get('password')

    user = User.query.filter_by(username=username).first()

    if user:
        flash('Email address already exists')
        return redirect(url_for('register'))

    new_user = User(username=username, password=generate_password_hash(password, method='sha256'), websocket_id=uuid4().hex)

    db.session.add(new_user)
    db.session.commit()

    return redirect(url_for('login'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/messages/', methods=['POST', 'GET'])
@login_required
def messages():


	if request.args.get('thread_id'):

		#Thread ownership security check
		if not db.session.query(Message).filter(Message.thread_id == request.args.get('thread_id'), Message.recipient_id == current_user.username) \
		or not db.session.query(Message).filter(Message.thread_id == request.args.get('thread_id'), Message.sender_id == current_user.username):
			abort(404)
		##########

		#Fetches non deleted messages in the thread for the current user.
		message_thread_sender = db.session.query(Message).filter(Message.thread_id == request.args.get('thread_id'), Message.sender_id == current_user.username, Message.sender_del == False)
		message_thread_recipient = db.session.query(Message).filter(Message.thread_id == request.args.get('thread_id'), Message.recipient_id == current_user.username, Message.recipient_del == False)
		message_thread = message_thread_sender.union(message_thread_recipient).order_by(Message.timestamp.asc())
		##########

		if not message_thread.count():
				abort(404)


		#Custom pagination handler. Helps with older message ajax fetch requests and first /messages/ pull request offset.
		thread_count = len(message_thread.all())
		if thread_count <= 5:
			offset = 0
		else:
			offset = thread_count-5
		message_thread_paginated = message_thread.offset(offset).limit(5)

		if request.args.get('fetch'): #Need to see if database check for existence is needed here / how flask handles error when in production.

			fetch_last_query = db.session.query(Message).filter(Message.url == request.args.get('fetch')).one()
			testq = message_thread_sender.union(message_thread_recipient).order_by(Message.timestamp.asc()).filter(Message.id < fetch_last_query.id) #Replace this union alreay occurs above.
			testq_count = testq.count()
			if testq_count-5 < 0:
				offsetcnt = 0
			else:
				offsetcnt = testq_count-5
			testq = testq.offset(offsetcnt)

			fetched_messages = render_template('fetch_new_message.html', message_thread=testq)
			return {'status': 200, 'fetched_messages': fetched_messages, 'offsetcnt':offsetcnt}
		##########


		#This marks all messages within thread that are in the current_user's unread as read upon thread open if current user is recipient.
		for message in message_thread:
			if current_user.username == message.recipient_id:
				if message.read == False:
					message.read = True
					db.session.commit()
		##########

		#This sets the recipient ID on replies so even if a user is sending themself a thread the recipient ID will be correct. Possibly/probably refactor.
		if current_user.username == message_thread[0].sender_id:
			recip = message_thread[0].recipient_id
		else:
			recip = message_thread[0].sender_id
		##########

		#Notifies socket if messages are all read to sync orange mailbox notification.
		if not db.session.query(Message).filter(Message.recipient_id == current_user.username, Message.read == False).all():
			socketio.emit(current_user.websocket_id+'_notify', {'type':'mailbox', 'notify':'false'}, namespace='/messages')
		##########

		#Notifies socket when the thread is read so the messages page may update read/unread.
		socketio.emit(current_user.websocket_id+'_notify', {'type':'thread', 'notify':'false', 'thread_id':request.args.get('thread_id')}, namespace='/messages')
		##########

		return render_template('read_message_thread.html', message_thread=message_thread_paginated, thread_id=request.args.get('thread_id'),\
								recip=recip, thread_count=thread_count)


	else:
		page = request.args.get('page', 1, type=int)

		unread_messages = db.session.query(Message).filter(Message.recipient_id == current_user.username, Message.recipient_del == False).order_by(Message.timestamp.desc())


		#This sorts each message thread properly according to the datetime of the last recieved message in each thread which is then used in the custom sort_order
		unread_ids = {}

		for message in unread_messages:
			if not unread_ids.get(message.thread_id):
				unread_ids[message.thread_id] = len(unread_ids)+1
		if not unread_ids:
			sort_order = None
		else:
			sort_order = case(value=Message.thread_id, whens=unread_ids).asc()
		##########


		#This fixes message threads viewed on /messages/ so duplicates will not be displayed, using sqlalchemy's '.in_' for query on list items
		thread_list = []
		message_thread_list = []
		for message in unread_messages:
			if message.thread_id not in thread_list:
				thread_list.append(message.thread_id)
				message_thread_list.append(message.url)
		##########


		message_threads = unread_messages.filter(Message.url.in_(message_thread_list)).order_by(sort_order)


		#Determines what is highlighted on the private messages screen for new unread messages and threads. List is passed to messages.html where Jinja2 logic executes.
		unread_threads = unread_messages.filter(Message.read == False).order_by(Message.timestamp.desc()).all()
		if unread_threads:
			unread_threads_list = []
			for message in unread_threads:
				unread_threads_list.append(message.thread_id)
		else:
			unread_threads_list = []
		##########


		message_threads = message_threads.paginate(page, 5, False)

		#This returns rendered threads for insert when the "Load additional threads" button is clicked on /Messages/
		if page > 1:
			paged_threads = render_template('fetch_new_thread.html', messages=message_threads.items, unread_threads_list=unread_threads_list)

			if not unread_messages.filter(Message.url.in_(message_thread_list)).order_by(sort_order).paginate(page+1, 5, False).items:
				fetch_button = 'false'
			else:
				fetch_button = 'true'

			return {'status':200, 'threads':paged_threads, 'fetch_button':fetch_button}
        ##########

		#Determines if the fetch additional threads button is shown on the /messages/ page.
		if len(message_thread_list) > 5:
			fetch_button = 'true'
		else:
			fetch_button = 'false'
		##########

		return render_template('messages.html', messages=message_threads.items, unread_threads_list=unread_threads_list, fetch_button=fetch_button)



@app.route('/messages/socket/', methods=['POST', 'GET']) #Add additional db check here for sender/recip del true and return 404 if so.
@login_required
def message_socket():

	message = db.session.query(Message).filter(Message.url == request.args.get('url')).all()

	if not message:
		abort(404)

	if current_user.username == message[0].recipient_id or current_user.username == message[0].sender_id:
		pass
	else:
		return {'status': 401}


	if current_user.username == message[0].recipient_id and request.args.get('read'):
		message[0].read = True #Maybe change this to ajax request when div is scrolled into view.
		db.session.commit()

		if not db.session.query(Message).filter(Message.recipient_id == current_user.username, Message.read == False, Message.recipient_del == False).all():
			socketio.emit(current_user.websocket_id+'_notify', {'type':'mailbox', 'notify':'false'}, namespace='/messages')


	if request.args.get('read'):
		socketio.emit(current_user.websocket_id+'_notify', {'type':'thread', 'notify':'false', 'thread_id':message[0].thread_id}, namespace='/messages')
		render_message = render_template('fetch_new_message.html', message_thread=message)
		return {'status':200, 'message':render_message}
	else:
		render_thread = render_template('fetch_new_thread.html', messages=message, unread_threads_list=[message[0].thread_id])
		return {'status':200, 'thread':render_thread, 'thread_id':message[0].thread_id}





@app.route('/messages/new/', methods=['POST', 'GET'])
@login_required
def sendmessage():

	if request.method == 'GET':
		return render_template('send_message.html')


	if request.method == 'POST':

		#Data security checks
		if request.json.get('body') == '' or request.json.get('body') == None or len(request.json.get('subject')) > 70:
			return {'status':418}

		#Mitigates messaging attacks by ensuring thread_id has not been modified on the end user computer by checking thread ownership.
		if request.json.get('thread_id'):
			if db.session.query(Message).filter(Message.thread_id == request.json.get('thread_id'), Message.sender_id == current_user.username).all() or \
				db.session.query(Message).filter(Message.thread_id == request.json.get('thread_id'), Message.recipient_id == current_user.username).all():
				pass
			else:
				return {'status': 418}
		##########


		#Username exists validator
		if not db.session.query(User).filter(User.username == request.json.get('recipient_id').lower()).first():
			return {'error':'No user exists with that username.'}
		##########


		url = randstrurl(type=Message)
		timestamp=datetime.utcnow()

		if request.json.get('thread_id'):
			thread_id = request.json.get('thread_id')
			thread_query = db.session.query(Message).filter(Message.thread_id == thread_id)
			subject = thread_query.order_by(Message.timestamp.desc()).first().subject

		else:
			thread_id = randstrurl(type=Message, pmthread=True)
			subject = request.json.get('subject')


		new_message = Message(sender_id=current_user.username, recipient_id=request.json.get('recipient_id').lower(), subject=subject, body=request.json.get('body'), url=url, \
						 thread_id=thread_id, timestamp=timestamp, sender_del=False, recipient_del=False)
		db.session.add(new_message)
		db.session.commit()


		recipient_websocket_id = db.session.query(User).filter(User.username == request.json.get('recipient_id').lower()).one().websocket_id

		socketio.emit(recipient_websocket_id+'_newmsg', {'message_url' : url}, namespace='/messages') #Recipient websocket messages home listener
		socketio.emit(current_user.websocket_id+'_newmsg', {'message_url' : url}, namespace='/messages') #Messages home listener/thread fetch for sender (Maybe not needed)
		socketio.emit(thread_id, {'message_url' : url}, namespace='/messages') #In thread listener

		return {'status': 200}



@app.route('/messages/delete/', methods=['POST'])
def message_delete():

	if not current_user.is_authenticated:
		return {'status':401}

	if request.json.get('type') == 'thread':
		thread_messages = db.session.query(Message).filter(Message.thread_id == request.json.get('url')).all()

		for message in thread_messages:
			if message.recipient_id == current_user.username:
				message.recipient_del = True
				db.session.commit()

			if message.sender_id == current_user.username:
				message.sender_del = True
				db.session.commit()

		#Emits thread deletion notification so frontend may update. Also sends total unique threads to determine if fetch additional threads button remains.
		sender_messages = db.session.query(Message).filter(Message.thread_id == message.thread_id, Message.sender_id == current_user.username, Message.sender_del == False)
		recipient_messages = db.session.query(Message).filter(Message.thread_id == message.thread_id, Message.recipient_id == current_user.username, Message.recipient_del == False)
		total_threads = sender_messages.union(recipient_messages).distinct(Message.thread_id).count()

		socketio.emit(current_user.websocket_id+'_notify_deletion', {'type':'thread', 'thread_id':request.json.get('url'), 'total_threads':total_threads}, namespace='/messages')
		##########

		flash('Message thread deleted', 'success')
		return {'status': 200}

	if request.json.get('type') == 'message':
		message = db.session.query(Message).filter(Message.url == request.json.get('url')).first()

		if message.recipient_id == current_user.username:
			message.recipient_del = True
			db.session.commit()

		if message.sender_id == current_user.username:
			message.sender_del = True
			db.session.commit()

		#Emits thread deletion notification so frontend may update. Also passes total messages in thread so if 0 a redirect is instructed.
		sender_messages = db.session.query(Message).filter(Message.thread_id == message.thread_id, Message.sender_id == current_user.username, Message.sender_del == False)
		recipient_messages = db.session.query(Message).filter(Message.thread_id == message.thread_id, Message.recipient_id == current_user.username, Message.recipient_del == False)
		total_messages = sender_messages.union(recipient_messages).count()

		socketio.emit(current_user.websocket_id+'_notify_deletion', {'type':'message', 'message_url':request.json.get('url'), 'thread_id':message.thread_id, 'total_messages':total_messages}, namespace='/messages')
		##########

		return {'status': 200}
############



if __name__ == "__main__":
    socketio.run(app)
