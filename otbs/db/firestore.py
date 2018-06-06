import sys

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore


def init_firebase():
    cred = credentials.Certificate('open-tbs-2e6dea4850c8.json')
    firebase_admin.initialize_app(cred, {
        'apiKey': 'AIzaSyCzwtvdM6zjSko2Et6EpuhDnQrwE-wLPvs',
        'authDomain': 'open-tbs.firebaseapp.com',
        'databaseURL': 'https://open-tbs.firebaseio.com',
        'projectId': 'open-tbs',
        'storageBucket': 'open-tbs.appspot.com',
        'messagingSenderId': '1033179704115',
    })
    fs = firestore.client()
    print(firebase_admin._apps)
    sys.stdout.flush()
