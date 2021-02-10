![](logo.png)

&nbsp;

A real time web based (instant) private messaging application written in Python and Javascript, utilizing SocketIO and Flask.

&nbsp;

## Features
* Instant messages between user accounts.
* Realtime multi-tab sync with no page reload required. If multiple tabs are open, or the application is signed in to across multiple devices, all data such as message notifications, read/unread notifiers, and deleted messages/threads stay up to date and sync instantly. 
* Correct datetimes displayed per user local across every timezone using MomentJS and Flask-Moment.


&nbsp;


## Application Integration

&nbsp;

#### Integration Prerequisites
To integrate Flask-Messaging into an existing application some requirements must be met.

* The built in Flask development server must not be in use since it only supports one connection at a time, concurrency is not supported which is required for websockets. [Gunicorn](https://gunicorn.org/), or a similar WSGI server must be used in combination with a concurrent network library such as [Eventlet](http://eventlet.net/).

* Flask-Login must be integrated into the application. Flask-Messaging uses the current_user proxy often.

* SQLAlchemy ORM must be integrated into the application.

* [Flask-Moment](https://github.com/miguelgrinberg/Flask-Moment) must be integrated into the application. 

* The application database must contain a User table with a "username" column, though the migrate script and Flask-Messaging may be adjusted easily to use another user identifier such as an email.

* The application database User table and the User model must have a "websocket_id" column and should be set upon user registration. This ID can be any random string, or the backend may be modified to just emit websocket notifications to something like the users username, and the frontend may be modified as well to listen on the same identifier. A working "websocket_id" generator example can be seen in the standalone application registration view which uses Python's built in UUID4 generator.

* For ease of use Flask-Messaging's HTML templates are designed to use [Fomantic-UI](https://fomantic-ui.com/) (a fork of the popular Semantic-UI which is currently unmaintained). These HTML elements may be modified easily to reference different framework class names, or vanilla HTML/CSS. A quick way to get up and running if another framework is in use you'd like to port to later is to just [include](https://fomantic-ui.com/introduction/getting-started.html#using-a-cdn-provider) Fomantic-UI in the Messaging page headers via a CDN.

* jQuery must be included in the application, though all jQuery commands could be rewritten in vanilla Javascript if desired. Please keep in mind that much of Fomantic-UI depends on jQuery.

&nbsp;

#### Post prerequisites integration steps


1. ```$ git clone https://github.com/blueskyzes/Flask-Messaging.git ```
2. ```$ cd ~/Flask-Messaging```
3. ```$ pip3 install -r requirements.txt```
4. Configure your app to launch with a Flask-SocketIO wrapper. The [Flask-SocketIO](https://flask-socketio.readthedocs.io/en/latest/#initialization) documentation contains additional initialization guidance for advanced initialization methods such as the init_app() method.
5. Merge the Flask-Messaging app database models, views, and templates with your own application
6. Execute the Flask-Migrate script to create the Message database table. The migrate script is designed to be executed from your base application folder and references a SQLite database which may be changed to your database type or file name.
7. Launch your application with your preferred WSGI server.

&nbsp;

## Standalone Application Example
If you do not wish to integrate Flask-Messaging into an existing application and would like to test the application, or plan to build on top of it with no existing codebase, a standalone example is given and may be easily launched. Please note that all integration prerequisites continue to apply to the standalone app as well.

**DO NOT** use the standalone application in a production enviroment until you build additional endpoints, logic, and security into the application for things like password resets, email support, CSRF protection, data/form validation, etc. The standalone application provides the bare minimum in regards to user registration, authentication, and security and is given **only** as an example to build on and to see how things work in **strict** regards to the chat application in a functioning enviroment. Correct Flask application structure should be taken into account as well.


1. ``` $ git clone https://github.com/blueskyzes/Flask-Messaging.git ```
2. ``` $ cd ~/Flask-Messaging ```
3. ``` $ pip3 install -r requirements.txt```
4. ``` $ python3 ./create_db.py```
4. ``` $ gunicorn --worker-class eventlet -w 1 app:app ```
5. Launch your favorite web browser and navigate to [http://127.0.0.1:8000](http://127.0.0.1:8000)
6. Register a new user and login.


&nbsp;


## Security Considerations

#### ⚫ Authentication

Websockets perform no authentication by default. If authentication to the socket is sought after it must be accomplished via cookies or tokens in the header or passed as an argument during connection.

Even if this authentication is accomplished an individual could still potentially perform a sort of MITM attack by simply modifying the client side javascript in attempt to listen in on an event channel they should not have access to. Since these channels are not protected, if someone were to obtain the event channel ID, eavesdropping would be trivial.

This is where I chose to implement a mixture of security by obscurity in combination with regular application authentication. The application will listen for specific events emitted to the random string ID for the messaging thread, and once the socket detects the emitted event it understands that a new message has arrived for that thread, from there a regular Ajax request is sent to get the new message data, by using Ajax we can perform in depth server side authentication of the client to verify identity before sending the data back.
This way if an individual were to somehow obtain the randomly generated ID and attempt to listen on the specific event channel, in this case messaging threads, all they would see would be notifications of new messages arriving, no sensitive information would be exposed.

#### ⚫ Cross Origin Resource Sharing
The library Flask-SocketIO which is utilized has built in CORS support. This prevents external websites from accessing the websocket and potentially using server resources.

&nbsp;

## To Do
* Standardize all javascript DOM modifications to jQuery.
* Clean up HTML/CSS styling and methods.
* Remove inline Javascript calls to functions on button click and instead use event listeners.
* Add Flask message flashing support for template notifications.
* Create proper app structure.
* Add "infinite scroll" type to message thread home and for older message fetch within thread so no button click is necessary. 

&nbsp;

## References
[The Websocket Protocol](https://tools.ietf.org/html/rfc6455)