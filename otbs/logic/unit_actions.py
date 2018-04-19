import bisect

from otbs.db.db_constants import db_session
from otbs.db.firestore import fs
from otbs.db.models import Unit, Grave, Building
from otbs.logic.helpers import calculate_damage, get_cell_defence_bonus
from otbs.logic.unit_actions_availability import can_strike_back, get_available_actions
from otbs.logic.unit_master import levelList, prototypes


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
