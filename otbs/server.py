import json

from flask import Flask, request, jsonify
from flask_cors import CORS

from otbs.db.database import init_db
from otbs.db.db_constants import db_session
from otbs.logic.service import do_start_battle, handle_click_on_cell

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


@app.route("/api/battle/<int:battle_id>/handle-click-on-cell", methods=["POST"])
def handle_click(battle_id):
    data = json.loads(request.data)
    commands = handle_click_on_cell(data['x'], data['y'], battle_id)
    response_data = {'status': 'ok', 'commands': commands if commands else []}
    return jsonify(response_data)


if __name__ == '__main__':
    init_db()
    app.run()
