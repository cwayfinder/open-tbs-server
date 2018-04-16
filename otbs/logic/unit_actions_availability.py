from sqlalchemy import or_

from otbs.db.models import Cell, Unit, Building, Player
from otbs.logic.path_finder import get_cell_resistance, get_available_path
from otbs.logic.unit_master import prototypes


def get_available_actions(unit):
    actions = {cell: 'move' for cell in get_unit_possible_moves(unit)}

    if can_unit_fix(unit):
        actions[unit.cell] = 'fix-building'

    if can_unit_occupy(unit):
        actions[unit.cell] = 'occupy-building'

    return actions


def get_unit_possible_moves(unit):
    if unit.did_move:
        return {}

    battle = unit.battle

    max_x = battle.map_width - 1
    max_y = battle.map_height - 1

    move_type = prototypes[unit.type].get('moveType', None)
    resistances = {Cell(t.x, t.y): get_cell_resistance(t.type, move_type) for t in battle.terrain.all()}
    enemy_units = Unit.query.filter_by(id=unit.id).one().owner.enemy_units
    obstacles = {Cell(unit.x, unit.y) for unit in enemy_units}

    return get_available_path(Cell(unit.x, unit.y), prototypes[unit.type]['mov'] - 1, max_x, max_y,
                              resistances=resistances,
                              obstacles=obstacles)


def can_unit_fix(unit):
    can_fix = prototypes[unit.type].get('canFixBuilding', None)

    if can_fix:
        building = Building.query \
            .filter_by(battle_id=unit.battle_id, x=unit.x, y=unit.y) \
            .filter_by(state='destroyed') \
            .one_or_none()

        if building:
            return True

    return False


def can_unit_occupy(unit):
    can_occupy = prototypes[unit.type].get('canOccupyBuilding', None)

    if can_occupy:
        building = Building.query \
            .filter_by(battle_id=unit.battle_id, x=unit.x, y=unit.y) \
            .filter_by(state='normal') \
            .filter(Building.type.in_(can_occupy)) \
            .outerjoin(Player) \
            .filter(or_(Player.id == None, Player.team != unit.owner.team)) \
            .one_or_none()

        if building:
            return True

    return False
