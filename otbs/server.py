import json
import uuid

from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy.exc import SQLAlchemyError

from otbs.db.database import init_db
from otbs.db.db_constants import db_session
from otbs.db.models import Cell
from otbs.db.pusher import pusher
from otbs.logic.service import do_start_battle, handle_click_on_cell, get_battle_data, do_buy_unit

app = Flask(__name__)
CORS(app)


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


@app.route("/", methods=["GET", "POST"])
def home():
    return 'Api Home'


@app.route("/api/battle/start", methods=["POST"])
def start_battle():
    data = json.loads(request.data)
    do_start_battle(data['map'], data['preferences'])
    return jsonify({'status': 'ok'})


@app.route("/api/battle/<int:battle_id>", methods=["GET"])
def get_battle(battle_id):
    try:
        commands = get_battle_data(battle_id)
        response_data = {'status': 'ok', 'commands': commands if commands else []}
        return jsonify(response_data)
    except SQLAlchemyError as e:
        response = jsonify({'error': str(e)})
        response.status_code = 400
        return response


@app.route("/api/battle/<int:battle_id>/handle-click-on-cell", methods=["POST"])
def handle_click(battle_id):
    data = json.loads(request.data)
    commands = handle_click_on_cell(data['x'], data['y'], battle_id)
    response_data = {'status': 'ok', 'commands': commands if commands else []}
    return jsonify(response_data)


@app.route("/api/battle/<int:battle_id>/buy-unit", methods=["POST"])
def buy_unit(battle_id):
    data = json.loads(request.data)
    # commands = handle_click_on_cell(data['x'], data['y'], battle_id)
    do_buy_unit(battle_id, data['type'], Cell(data['x'], data['y']))
    response_data = {'status': 'ok'}
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


if __name__ == '__main__':
    init_db()
    app.run()
