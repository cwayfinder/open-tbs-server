from pusher import Pusher

from otbs.db.models import Unit, Grave, Building

pusher = Pusher(
    app_id='511959',
    key='19716bf12b9a14cb1337',
    secret='b54f2ed95b310e402276',
    cluster='eu'
)


class Command:
    def __init__(self, type_, payload):
        self.payload = payload
        self.type_ = type_

    def to_dict(self):
        return {'type': self.type_, 'payload': self.payload}

    @staticmethod
    def add_unit(unit: Unit):
        return Command('add-unit', {
            'unit': {
                'id': unit.id,
                'x': unit.x,
                'y': unit.y,
                'type': unit.type,
                'color': unit.owner.color if unit.owner else None,
                'level': unit.level,
                'health': unit.health,
                'state': 'waiting',
            }
        })

    @staticmethod
    def update_unit(unit: Unit, changes):
        return Command('update-unit', {
            'unit': {
                'id': unit.id,
                'changes': changes
            }
        })

    @staticmethod
    def delete_unit(unit: Unit):
        return Command('delete-unit', {'id': unit.id})

    @staticmethod
    def add_grave(grave: Grave):
        return Command('add-grave', {
            'grave': {
                'x': grave.x,
                'y': grave.y,
            }
        })

    @staticmethod
    def update_building(building: Building, changes):
        return Command('update-building', {
            'building': {
                'id': building.id,
                'changes': changes
            }
        })
