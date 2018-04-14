from sqlalchemy import or_

from otbs.db.db_constants import db_session
from otbs.db.firestore import fs
from otbs.db.fs_utls import delete_collection
from otbs.db.models import Terrain, Building, Unit, Commander, Player, Battle, Cell
from otbs.logic.helpers import get_cell_defence
from otbs.logic.path_finder import get_available_path, get_cell_resistance
from otbs.logic.unit_master import prototypes


def do_start_battle(battle_map, preferences):
    terrain = []
    for cell, terrain_type in battle_map['terrain'].items():
        [x, y] = cell.split(',')
        terrain.append(Terrain(x=x, y=y, type=terrain_type))
    db_session.add_all(terrain)

    buildings = {}
    for b in battle_map['buildings'].values():
        building = Building(type=b['type'], x=b['x'], y=b['y'], state=b['state'])
        if 'ownerId' in b:
            building.owner_id = b['ownerId']
        buildings[b['id']] = building
    db_session.add_all(buildings.values())

    units = {}
    for u in battle_map['units'].values():
        unit = Unit(type=u['type'], x=u['x'], y=u['y'], xp=0, level=0, health=100)
        if 'ownerId' in u:
            unit.owner_id = u['ownerId']
        units[u['id']] = unit

    players = {}
    for player_id, map_data in battle_map['players'].items():
        pref = preferences['players'][player_id]
        commander_unit = units[map_data['commander']['unitId']]
        commander_unit.type = pref['commanderCharacter']
        commander = Commander(character=pref['commanderCharacter'], death_count=0, xp=0, level=0, unit=commander_unit)
        player = Player(color=pref['color'],
                        team=pref['team'],
                        money=preferences['money'],
                        unit_limit=preferences['unitLimit'],
                        type=pref['type'],
                        commander=commander)
        players[map_data['id']] = player

    for u in battle_map['units'].values():
        if 'ownerId' in u:
            units[u['id']].owner = players[u['ownerId']]

    db_session.add_all(players.values())
    db_session.add_all(units.values())

    first_player_id = next(iter(dict.values(battle_map['players'])))['id']
    first_player = players[first_player_id]
    battle = Battle(map_width=battle_map['size']['width'],
                    map_height=battle_map['size']['height'],
                    turn_count=0,
                    circle_count=0,
                    active_player=first_player,
                    terrain=terrain,
                    buildings=buildings.values(),
                    players=players.values(),
                    units=units.values())

    db_session.add(battle)
    db_session.commit()


def sync_battle(battle_id):
    battle = Battle.query.filter_by(id=battle_id).join(Battle.active_player).one()

    battle_ref = fs.collection('battles').document(str(battle.id))
    battle_ref.set({
        'width': battle.map_width,
        'height': battle.map_height,
        'terrain': {'{0},{1}'.format(str(t.x), str(t.y)): t.type for t in battle.terrain},
        'status': {
            'color': battle.active_player.color,
            'unitCount': battle.active_player.unit_count,
            'unitLimit': battle.active_player.unit_limit,
            'money': battle.active_player.money,
        },
    })

    buildings_ref = battle_ref.collection('buildings')
    for b in battle.buildings.outerjoin(Building.owner):
        buildings_ref.document(str(b.id)).set({
            'x': b.x,
            'y': b.y,
            'type': b.type,
            'state': b.state,
            'color': b.owner.color if b.owner else None,
        })

    units_ref = battle_ref.collection('units')
    for b in battle.units.outerjoin(Unit.owner):
        units_ref.document(str(b.id)).set({
            'x': b.x,
            'y': b.y,
            'type': b.type,
            'color': b.owner.color if b.owner else None,
            'level': b.level,
            'state': 'waiting',
        })


def handle_click_on_cell(x: int, y: int, battle_id: int):
    unit = Unit.query.filter_by(battle_id=battle_id, x=x, y=y).one()
    actions = get_available_actions(unit.id)
    print(actions)
    sync_selected_unit(battle_id, actions, unit)


def sync_selected_unit(battle_id, actions, unit):
    battle_ref = fs.collection('battles').document(str(battle_id))

    action_list = [{'x': cell.x, 'y': cell.y, 'type': action_type} for cell, action_type in actions.items()]
    battle_ref.update({
        'selectedUnit': {
            'actions': action_list,
            'briefInfo': {
                'atkMin': prototypes[unit.type]['atk']['min'],
                'atkMax': prototypes[unit.type]['atk']['max'],
                'def': prototypes[unit.type]['def'],
                'extraDef': get_cell_defence(unit.id),
                'level': unit.level,
            },
        }
    })


def get_unit_possible_moves(unit_id: int):
    unit = Unit.query.filter_by(id=unit_id).one()
    battle = unit.battle

    max_x = battle.map_width - 1
    max_y = battle.map_height - 1

    move_type = prototypes[unit.type].get('moveType', None)
    resistances = {Cell(t.x, t.y): get_cell_resistance(t.type, move_type) for t in battle.terrain.all()}
    enemy_units = Unit.query.filter_by(id=unit_id).one().owner.enemy_units
    obstacles = {Cell(unit.x, unit.y) for unit in enemy_units}

    return get_available_path(Cell(unit.x, unit.y), prototypes[unit.type]['mov'] - 1, max_x, max_y, resistances=resistances,
                              obstacles=obstacles)


def can_unit_fix(unit_id):
    unit = Unit.query.filter_by(id=unit_id).one()
    can_fix = prototypes[unit.type].get('canFixBuilding', None)

    if can_fix:
        building = Building.query \
            .filter_by(battle_id=unit.battle_id, x=unit.x, y=unit.y) \
            .filter_by(state='destroyed') \
            .one_or_none()

        if building:
            return True

    return False


def can_unit_occupy(unit_id):
    unit = Unit.query.filter_by(id=unit_id).one()
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


def get_available_actions(unit_id: int):
    unit = Unit.query.filter_by(id=unit_id).one()

    actions = {cell: 'move' for cell in get_unit_possible_moves(unit_id)}

    if can_unit_fix(unit_id):
        actions[unit.cell] = 'fix-building'

    if can_unit_occupy(unit_id):
        actions[unit.cell] = 'occupy-building'

    return actions
