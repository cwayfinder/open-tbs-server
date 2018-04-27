from typing import Dict

from sqlalchemy import or_

from otbs.db.models import Cell, Unit, Building, Player
from otbs.logic.building_master import building_prototypes
from otbs.logic.path_finder import get_cell_resistance, get_available_path
from otbs.logic.unit_master import prototypes


def get_available_actions(unit: Unit) -> Dict[Cell, str]:
    actions = {}
    actions.update({cell: 'move' for cell in get_unit_possible_moves(unit)})

    if can_fix_building(unit):
        actions[unit.cell] = 'fix-building'

    if can_occupy_building(unit):
        actions[unit.cell] = 'occupy-building'

    actions.update({cell: 'attack-building' for cell in get_buildings_under_attack(unit)})
    actions.update({cell: 'attack-unit' for cell in get_units_under_attack(unit)})
    actions.update({cell: 'raise-skeleton' for cell in get_graves_to_raise(unit)})

    return actions


def get_unit_possible_moves(unit):
    if unit.did_move or unit.did_attack or unit.did_occupy or unit.did_fix:
        return set()

    battle = unit.battle

    max_x = battle.map_width - 1
    max_y = battle.map_height - 1

    move_type = prototypes[unit.type].get('moveType', None)
    resistances = {Cell(t.x, t.y): get_cell_resistance(t.type, move_type) for t in battle.terrain.all()}
    enemy_units = Unit.query.filter_by(id=unit.id).one().owner.enemy_units
    obstacles = {Cell(unit.x, unit.y) for unit in enemy_units}

    path = get_available_path(Cell(unit.x, unit.y), prototypes[unit.type]['mov'], max_x, max_y, resistances=resistances,
                              obstacles=obstacles)
    occupied_cells = {Cell(unit.x, unit.y) for unit in Unit.query.filter_by(battle_id=battle.id).all()}
    return path.difference(occupied_cells)


def can_fix_building(unit):
    if unit.did_attack or unit.did_occupy:
        return False

    can_fix = prototypes[unit.type].get('canFixBuilding', None)

    if can_fix:
        building = Building.query \
            .filter_by(battle_id=unit.battle_id, x=unit.x, y=unit.y) \
            .filter_by(state='destroyed') \
            .one_or_none()

        if building:
            return True

    return False


def can_occupy_building(unit):
    if unit.did_attack or unit.did_fix:
        return False

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


def get_buildings_under_attack(unit):
    if unit.did_attack or unit.did_occupy or unit.did_fix:
        return set()

    can_destroy_building = prototypes[unit.type].get('canDestroyBuilding', False)
    can_act = not prototypes[unit.type].get('cannotActAfterMove', False)
    can_attack = can_destroy_building and can_act

    if can_attack:
        buildings = unit.owner.enemy_buildings
        destroyable = [b for b in buildings if 'destroyed' in building_prototypes[b.type]['availableStates']]
        enemies_cells = {Cell(b.x, b.y) for b in destroyable}
        targets = get_cells_under_attack(unit).intersection(enemies_cells)
        return targets.difference(get_units_under_attack(unit))
    else:
        return set()


def get_units_under_attack(unit):
    if unit.did_attack or unit.did_occupy or unit.did_fix:
        return set()

    units = unit.owner.enemy_units
    enemies_cells = {Cell(b.x, b.y) for b in units}
    targets = get_cells_under_attack(unit).intersection(enemies_cells)
    return targets


def get_cells_under_attack(unit):
    max_x = unit.battle.map_width - 1
    max_y = unit.battle.map_height - 1

    range_ = prototypes[unit.type]['atkRange']
    if isinstance(range_, int):
        min_range = 1
        max_range = range_
    else:
        min_range = range_['min']
        max_range = range_['max']

    cells = get_available_path(Cell(unit.x, unit.y), max_range, max_x, max_y)
    cells = {cell for cell in cells if abs(cell.x - unit.x) >= min_range or abs(cell.y - unit.y) >= min_range}
    return cells


def can_strike_back(unit, target_cell):
    return target_cell in get_units_under_attack(unit)


def get_graves_to_raise(unit):
    graves = {Cell(b.x, b.y) for b in unit.battle.graves}

    max_x = unit.battle.map_width - 1
    max_y = unit.battle.map_height - 1
    range_ = prototypes[unit.type].get('raiseRange', 0)
    cells_in_range = get_available_path(Cell(unit.x, unit.y), range_, max_x, max_y)
    targets = cells_in_range.intersection(graves)
    return targets
