import bisect

from otbs.db.db_constants import db_session
from otbs.db.firestore import fs
from otbs.db.models import Terrain, Building, Unit, Commander, Player, Battle, Cell, Grave
from otbs.logic.helpers import get_cell_defence_bonus, calculate_damage
from otbs.logic.unit_actions_availability import get_available_actions, can_strike_back
from otbs.logic.unit_master import prototypes, levelList


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

    sync_battle(battle)


def sync_battle(battle):
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
    battle = Battle.query.filter_by(id=battle_id).one()
    cell = Cell(x, y)

    if battle.selected_unit:
        actions = get_available_actions(battle.selected_unit)
    else:
        actions = {}

    if cell in actions.keys():
        action = actions[cell]
        print(action)
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

    clear_selected_unit(battle)


def select_unit(unit):
    unit.battle.selected_unit = unit
    db_session.commit()

    sync_selected_unit(unit)


def sync_selected_unit(unit):
    actions = get_available_actions(unit)
    action_list = [{'x': cell.x, 'y': cell.y, 'type': action_type} for cell, action_type in actions.items()]

    battle_ref = fs.collection('battles').document(str(unit.battle.id))
    battle_ref.update({
        'selectedUnit': {
            'actions': action_list,
            'briefInfo': {
                'atkMin': prototypes[unit.type]['atk']['min'],
                'atkMax': prototypes[unit.type]['atk']['max'],
                'def': prototypes[unit.type]['def'],
                'extraDef': get_cell_defence_bonus(unit),
                'level': unit.level,
            },
            'x': unit.x,
            'y': unit.y,
        }
    })


def clear_selected_unit(battle):
    battle.selected_unit = None
    db_session.commit()

    battle_ref = fs.collection('battles').document(str(battle.id))
    battle_ref.update({
        'selectedUnit': {}
    })


def move_unit(unit, cell):
    unit_ref = fs.collection('battles').document(str(unit.battle.id)).collection('units').document(str(unit.id))
    unit_ref.update({
        'state': 'moving',
        'stateParams': {
            'x': cell.x,
            'y': cell.y,
        }
    })

    unit.x = cell.x
    unit.y = cell.y
    unit.did_move = True
    db_session.commit()

    unit_ref.update({
        'state': 'waiting',
        'stateParams': {},
        'x': cell.x,
        'y': cell.y,
    })

    sync_selected_unit(unit)

    # TODO: update wisp aura


def fix_building(unit):
    building = Building.query.filter_by(battle=unit.battle, x=unit.x, y=unit.y).one()

    building.owner = unit.owner
    unit.did_fix = True
    db_session.commit()

    battle_ref = fs.collection('battles').document(str(unit.battle.id))
    building_ref = battle_ref.collection('buildings').document(str(building.id))
    building_ref.update({
        'state': 'normal',
    })

    sync_selected_unit(unit)


def occupy_building(unit):
    building = Building.query.filter_by(battle=unit.battle, x=unit.x, y=unit.y).one()

    building.owner = unit.owner
    unit.did_occupy = True
    db_session.commit()

    battle_ref = fs.collection('battles').document(str(unit.battle.id))
    building_ref = battle_ref.collection('buildings').document(str(building.id))
    building_ref.update({
        'color': building.owner.color,
    })

    sync_selected_unit(unit)


def attack_unit(attacker: Unit, defender: Unit):
    battle_ref = fs.collection('battles').document(str(attacker.battle.id))

    attacker_ref = battle_ref.collection('units').document(str(attacker.id))
    attacker_ref.update({
        'state': 'attacking',
        'stateParams': {
            'x': defender.x,
            'y': defender.y,
            'targetType': 'unit',
        }
    })

    dmg = calculate_damage(attacker, defender)

    health = max(defender.health - dmg, 0)
    decrease_unit_hp(defender, dmg)
    increase_unit_xp(attacker, dmg)

    if health > 0 and can_strike_back(defender, attacker.cell):
        strike_back(defender, attacker)

    attacker_ref.update({
        'state': 'waiting',
        'stateParams': {},
    })

    attacker.did_attack = True
    db_session.commit()

    sync_selected_unit(attacker)


def decrease_unit_hp(unit, delta_hp):
    health = max(unit.health - delta_hp, 0)
    unit_ref = fs.collection('battles').document(str(unit.battle.id)).collection('units').document(str(unit.id))
    unit_ref.update({
        'state': 'bleeding',
        'stateParams': {
            'deltaHp': delta_hp,
        }
    })

    if health == 0:
        kill_unit(unit)
    else:
        unit.health = health
        unit_ref.update({
            'state': 'waiting',
            'stateParams': {},
            'health': unit.health,
        })

    db_session.commit()


def kill_unit(unit: Unit):
    battle_ref = fs.collection('battles').document(str(unit.battle_id))

    commander = unit.owner.commander
    if commander.unit == unit:
        commander.unit = None
        commander.death_count += 1
        db_session.commit()

        Unit.query.filter_by(id=unit.id).delete()
        battle_ref.collection('units').document(str(unit.id)).delete()

        db_session.commit()
    else:
        if unit.battle.selected_unit == unit:
            unit.battle.selected_unit = None
            db_session.commit()

        Unit.query.filter_by(id=unit.id).delete()
        battle_ref.collection('units').document(str(unit.id)).delete()

        grave = Grave(x=unit.x, y=unit.y, ttl=2, battle=unit.battle)
        db_session.add(grave)
        db_session.commit()

        battle_ref.collection('graves').document(str(grave.id)).set({
            'x': grave.x,
            'y': grave.y,
        })


def increase_unit_xp(unit: Unit, delta_xp: int):
    unit_ref = fs.collection('battles').document(str(unit.battle.id)).collection('units').document(str(unit.id))

    xp = unit.xp + delta_xp
    level = bisect.bisect_left(levelList, xp) - 1

    unit.xp = xp
    unit.level = level

    if level > unit.level:
        unit_ref.update({
            'state': 'gaining-level',
            'stateParams': {
                'level': level
            },
        })
        unit_ref.update({
            'state': 'waiting',
            'stateParams': {},
            'level': 'level'
        })

    commander = unit.owner.commander
    if commander.unit_id == unit.id:
        commander.xp = xp
        commander.level = level

    db_session.commit()


def strike_back(defender, attacker):
    battle_ref = fs.collection('battles').document(str(attacker.battle.id))

    defender_ref = battle_ref.collection('units').document(str(defender.id))
    defender_ref.update({
        'state': 'attacking',
        'stateParams': {
            'x': attacker.x,
            'y': attacker.y,
            'targetType': 'unit',
        }
    })

    dmg = calculate_damage(defender, attacker)

    decrease_unit_hp(attacker, dmg)
    increase_unit_xp(defender, dmg)

    defender_ref.update({
        'state': 'waiting',
        'stateParams': {},
    })
