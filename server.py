import json

from flask import Flask, request, render_template, jsonify
from flask_cors import CORS

from database import init_db
from db_constants import db_session
from models import Battle
from service import do_start_battle

app = Flask(__name__)
CORS(app)

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


@app.route("/", methods=["GET", "POST"])
def home():
    return 'Api Home'


@app.route("/api/start-battle", methods=["GET", "POST"])
def start_battle():
    data = json.loads(request.data)
    do_start_battle(data['map'], data['preferences'])
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    init_db()
    app.run()
