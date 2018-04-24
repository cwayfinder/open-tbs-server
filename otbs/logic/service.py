from otbs.db.db_constants import db_session
from otbs.db.models import Terrain, Building, Unit, Commander, Player, Battle, Cell, Grave
from otbs.logic.unit_actions import move_unit, fix_building, occupy_building, attack_unit, select_unit, \
    clear_selected_unit, clear_selected_unit_actions, add_unit, push_command
from otbs.logic.unit_actions_availability import get_available_actions
from otbs.logic.unit_master import prototypes, commanderList, commanderAddedCost


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


def get_battle_data(battle_id):
    battle = Battle.query.filter_by(id=battle_id).one()
    commands = []

    buildings = battle.buildings.outerjoin(Building.owner)

    commands.append({
        'type': 'update-map',
        'payload': {
            'width': battle.map_width,
            'height': battle.map_height,
            'terrain': {'{0},{1}'.format(str(t.x), str(t.y)): t.type for t in battle.terrain},
            'buildings': [{
                'x': b.x,
                'y': b.y,
                'type': b.type,
            } for b in buildings]
        }
    })

    commands.append({
        'type': 'update-status',
        'payload': {
            'color': battle.active_player.color,
            'unitCount': battle.active_player.unit_count,
            'unitLimit': battle.active_player.unit_limit,
            'money': battle.active_player.money,
        }
    })

    commands.append({
        'type': 'add-buildings',
        'payload': {
            'buildings': [{
                'id': b.id,
                'x': b.x,
                'y': b.y,
                'type': b.type,
                'state': b.state,
                'color': b.owner.color if b.owner else None,
            } for b in buildings]
        }
    })

    graves = battle.graves
    commands.append({
        'type': 'add-graves',
        'payload': {
            'graves': [{
                'id': b.id,
                'x': b.x,
                'y': b.y,
            } for b in graves]
        }
    })

    units = battle.units.outerjoin(Unit.owner)
    commands.append({
        'type': 'add-units',
        'payload': {
            'units': [{
                'id': b.id,
                'x': b.x,
                'y': b.y,
                'type': b.type,
                'color': b.owner.color if b.owner else None,
                'level': b.level,
                'health': b.health,
                'state': 'waiting',
            } for b in units]
        }
    })

    return commands


def handle_click_on_cell(x: int, y: int, battle_id: int):
    battle = Battle.query.filter_by(id=battle_id).one()
    cell = Cell(x, y)

    if battle.selected_unit:
        actions = get_available_actions(battle.selected_unit)
    else:
        actions = {}

    if cell in actions.keys():
        action = actions[cell]
        print(action)
        clear_selected_unit_actions(battle.selected_unit)
        if action == 'move':
            move_unit(battle.selected_unit, cell)
        elif action == 'fix-building':
            fix_building(battle.selected_unit)
        elif action == 'occupy-building':
            occupy_building(battle.selected_unit)
        elif action == 'attack-unit':
            unit = Unit.query.filter_by(battle_id=battle_id, x=x, y=y).one()
            attack_unit(battle.selected_unit, unit)
        return

    unit = Unit.query.filter_by(battle_id=battle_id, x=x, y=y).one_or_none()
    if unit:
        select_unit(unit)
        return

    store = Building.query.filter_by(battle_id=battle_id, x=x, y=y, type='castle').one_or_none()
    if store:
        return [{
            'type': 'open-store',
            'payload': {
                'storeCell': {
                    'x': store.x,
                    'y': store.y,
                },
                'items': get_units_to_buy(battle)
            },
        }]

    clear_selected_unit(battle)


def get_units_to_buy(battle: Battle):
    to_buy = {t: p for t, p in prototypes.items() if p['cost'] > 0 and t not in commanderList}

    player = battle.active_player
    commander = player.commander
    if commander.unit_id is None:
        to_buy[commander.character] = prototypes[commander.character]

    items_ = [{
        'type': unit_type,
        'name': proto['name'],
        'description': proto['description'],
        'color': player.color,
        'atkMin': proto['atk']['min'],
        'atkMax': proto['atk']['max'],
        'def': proto['def'],
        'mov': proto['mov'],
        'cost': get_unit_cost(unit_type, player),
        'available': proto['cost'] <= player.money,
    } for unit_type, proto in to_buy.items()]

    return sorted(items_, key=lambda x: x['cost'])


def do_buy_unit(battle_id: int, unit_type: str, store_cell: Cell):
    battle = Battle.query.filter_by(id=battle_id).one()

    store = Building.query.filter_by(battle_id=battle_id, x=store_cell.x, y=store_cell.y).one_or_none()

    if store is None:
        raise Exception('No player\'s store in that cell')

    player = battle.active_player
    unit = Unit(type=unit_type, x=store_cell.x, y=store_cell.y, xp=0, level=0, health=100,
                owner=player, battle=battle)
    db_session.add(unit)
    player.money -= get_unit_cost(unit.type, player)
    db_session.commit()

    add_unit(unit)
    push_command(battle_id, 'update-status', {
        'unitCount': battle.active_player.unit_count,
        'money': battle.active_player.money,
    })

    select_unit(unit)


def get_unit_cost(unit_type, player: Player):
    cost = prototypes[unit_type]['cost']

    if unit_type in commanderList:
        return cost + player.commander.death_count * commanderAddedCost
    else:
        return cost
