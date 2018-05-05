import json
import uuid

from firebase_admin import auth
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy.exc import SQLAlchemyError

from otbs.auth import AuthError, requires_auth, get_token_sub
from otbs.db.database import init_db
from otbs.db.db_constants import db_session
from otbs.db.firestore import init_firebase
from otbs.db.models import Cell
from otbs.db.pusher import pusher
from otbs.logic.service import Service

app = Flask(__name__)
CORS(app)


@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


@app.route("/", methods=["GET", "POST"])
def home():
    return 'Api Home'


@app.route("/api/battle/start", methods=["POST"])
@requires_auth
def start_battle():
    data = json.loads(request.data)
    commands = Service() \
        .start_battle(data['map'], data['preferences']) \
        .get_commands()
    return jsonify({'status': 'ok', 'commands': commands})


@app.route("/api/battle/<int:battle_id>", methods=["GET"])
@requires_auth
def get_battle(battle_id):
    try:
        commands = Service(battle_id).collect_battle_data().get_commands()
        response_data = {'status': 'ok', 'commands': commands}
        return jsonify(response_data)
    except SQLAlchemyError as e:
        response = jsonify({'error': str(e)})
        response.status_code = 400
        return response


@app.route("/api/battle/<int:battle_id>/handle-click-on-cell", methods=["POST"])
def handle_click(battle_id):
    data = json.loads(request.data)
    commands = Service(battle_id) \
        .handle_click_on_cell(data['x'], data['y']) \
        .push(request.headers['x-socket-id']) \
        .get_commands()
    response_data = {'status': 'ok', 'commands': commands}
    return jsonify(response_data)


@app.route("/api/battle/<int:battle_id>/buy-unit", methods=["POST"])
def buy_unit(battle_id):
    data = json.loads(request.data)
    commands = Service(battle_id) \
        .buy_unit(data['type'], Cell(data['x'], data['y'])) \
        .push(request.headers['x-socket-id']) \
        .get_commands()
    response_data = {'status': 'ok', 'commands': commands}
    return jsonify(response_data)


@app.route("/api/battle/<int:battle_id>/end-turn", methods=["POST"])
def end_turn(battle_id):
    commands = Service(battle_id) \
        .end_turn() \
        .push(request.headers['x-socket-id']) \
        .get_commands()
    response_data = {'status': 'ok', 'commands': commands}
    return jsonify(response_data)


@app.route("/pusher/auth", methods=["POST"])
def pusher_auth():
    socket_id = request.form['socket_id']
    channel = request.form['channel_name']
    presence_data = {
        'user_id': uuid.uuid4().hex
    }
    auth = pusher.authenticate(socket_id=socket_id, channel=channel, custom_data=presence_data)
    return jsonify(auth)


@app.route("/firebase/auth", methods=["GET"])
def firebase_auth():
    custom_token = auth.create_custom_token(get_token_sub())
    return jsonify({'firebaseToken': custom_token.decode('utf-8')})


if __name__ == '__main__':
    init_firebase()
    init_db()
    app.run()
