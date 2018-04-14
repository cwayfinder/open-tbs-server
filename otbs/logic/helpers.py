import re

from otbs.db.models import Unit, Building, Terrain
from otbs.logic import map_config


def get_cell_defence(unit_id):
    unit = Unit.query.filter_by(id=unit_id).one()

    building = Building.query.filter_by(x=unit.x, y=unit.y, battle_id=unit.battle_id).one_or_none()
    if building:
        return 15

    terrain = Terrain.query.filter_by(x=unit.x, y=unit.y, battle_id=unit.battle_id).one_or_none()
    if terrain:
        terrain_type = re.sub('-\d+$', '', terrain.type)
        return map_config[terrain_type]['defence']

    return 0
