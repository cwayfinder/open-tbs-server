import bisect

from sqlalchemy import inspect

from otbs.db.db_constants import db_session
from otbs.db.models import Unit, Grave, Building
from otbs.db.pusher import pusher
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

    push_command(unit.battle.id, 'update-selected-unit', {
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
    })


def clear_selected_unit(battle):
    battle.selected_unit = None
    db_session.commit()

    push_command(battle.id, 'clear-selected-unit', {})


def move_unit(unit, cell):
    update_unit(unit, {
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

    update_unit(unit, {
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

    update_building(building, {
        'state': 'normal',
    })

    sync_selected_unit(unit)


def occupy_building(unit):
    building = Building.query.filter_by(battle=unit.battle, x=unit.x, y=unit.y).one()

    building.owner = unit.owner
    unit.did_occupy = True
    db_session.commit()

    update_building(building, {
        'color': building.owner.color,
    })

    sync_selected_unit(unit)


def attack_unit(attacker: Unit, defender: Unit):
    update_unit(attacker, {
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

    update_unit(attacker, {
        'state': 'waiting',
        'stateParams': {},
    })

    attacker.did_attack = True
    db_session.commit()

    if not inspect(attacker).detached:
        sync_selected_unit(attacker)
    else:
        clear_selected_unit(defender.battle)


def decrease_unit_hp(unit, delta_hp):
    health = max(unit.health - delta_hp, 0)
    update_unit(unit, {
        'state': 'bleeding',
        'stateParams': {
            'deltaHp': delta_hp,
        }
    })

    if health == 0:
        kill_unit(unit)
    else:
        unit.health = health
        update_unit(unit, {
            'state': 'waiting',
            'stateParams': {},
            'health': unit.health,
        })

    db_session.commit()


def kill_unit(unit: Unit):
    commander = unit.owner.commander
    if commander.unit == unit:
        commander.unit = None
        commander.death_count += 1
        db_session.commit()

        Unit.query.filter_by(id=unit.id).delete()
        delete_unit(unit)

        db_session.commit()
    else:
        if unit.battle.selected_unit == unit:
            unit.battle.selected_unit = None
            db_session.commit()

        Unit.query.filter_by(id=unit.id).delete()
        delete_unit(unit)

        grave = Grave(x=unit.x, y=unit.y, ttl=2, battle=unit.battle)
        db_session.add(grave)
        db_session.commit()
        add_grave(grave)


def increase_unit_xp(unit: Unit, delta_xp: int):
    xp = unit.xp + delta_xp
    level = bisect.bisect_left(levelList, xp) - 1

    unit.xp = xp
    unit.level = level

    if level > unit.level:
        update_unit(unit, {
            'state': 'gaining-level',
            'stateParams': {
                'level': level
            },
        })
        update_unit(unit, {
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
    update_unit(defender, {
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

    update_unit(defender, {
        'state': 'waiting',
        'stateParams': {},
    })


def push_command(battle_id, type_, payload):
    pusher.trigger(['battle-{0}'.format(battle_id)], 'server-command', {
        'type': type_,
        'payload': payload
    })


def update_building(building: Building, changes):
    push_command(building.battle_id, 'update-building', {
        'building': {
            'id': building.id,
            'changes': changes
        }
    })


def update_unit(unit: Unit, changes):
    push_command(unit.battle_id, 'update-unit', {
        'unit': {
            'id': unit.id,
            'changes': changes
        }
    })


def delete_unit(unit: Unit):
    push_command(unit.battle_id, 'delete-unit', {'id': unit.id})


def add_grave(grave: Grave):
    push_command(grave.battle_id, 'add-grave', {
        'grave': {
            'x': grave.x,
            'y': grave.y,
        }
    })
