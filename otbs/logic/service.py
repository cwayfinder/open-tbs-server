import bisect
from typing import List

from sqlalchemy import inspect

from otbs.db.db_constants import db_session
from otbs.db.models import Terrain, Building, Unit, Commander, Player, Battle, Cell, Grave
from otbs.db.pusher import Command, pusher
from otbs.logic.building_master import building_prototypes
from otbs.logic.helpers import get_cell_defence_bonus, calculate_damage
from otbs.logic.unit_actions_availability import get_available_actions, can_strike_back
from otbs.logic.unit_master import prototypes, commanderList, commanderAddedCost, levelList


class Service:
    battle: Battle
    commands: List[Command]
    shared_commands: List[Command]

    def __init__(self, battle_id: int):
        self.battle = Battle.query.filter_by(id=battle_id).one()
        self.commands = []
        self.shared_commands = []

    def push(self):
        for command in self.shared_commands:
            channel = 'battle-{0}'.format(self.battle.id)
            pusher.trigger([channel], 'server-command', {
                'type': command.type_,
                'payload': command.payload
            })

        return self

    @staticmethod
    def start_battle(battle_map, preferences):
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
            commander = Commander(character=pref['commanderCharacter'], death_count=0, xp=0, level=0,
                                  unit=commander_unit)
            player = Player(color=pref['color'],
                            team=pref['team'],
                            money=preferences['money'],
                            unit_limit=preferences['unitLimit'],
                            type=pref['type'],
                            commander=commander,
                            defeated=False)
            players[map_data['id']] = player

        for b in battle_map['buildings'].values():
            if 'ownerId' in b:
                buildings[b['id']].owner = players[b['ownerId']]

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

    def collect_battle_data(self):
        buildings = self.battle.buildings.outerjoin(Building.owner)

        self.commands.append(Command('update-map', {
            'width': self.battle.map_width,
            'height': self.battle.map_height,
            'terrain': {'{0},{1}'.format(str(t.x), str(t.y)): t.type for t in self.battle.terrain},
            'buildings': [{'x': b.x, 'y': b.y, 'type': b.type} for b in buildings]
        }))

        self.commands.append(Command('update-status', {
            'color': self.battle.active_player.color,
            'unitCount': self.battle.active_player.unit_count,
            'unitLimit': self.battle.active_player.unit_limit,
            'money': self.battle.active_player.money,
            'winnerTeam': self.battle.winner_team,
        }))

        self.commands.append(Command('add-buildings', {
            'buildings': [{
                'id': b.id,
                'x': b.x,
                'y': b.y,
                'type': b.type,
                'state': b.state,
                'color': b.owner.color if b.owner else None,
            } for b in buildings]
        }))

        graves = self.battle.graves
        self.commands.append(Command('add-graves', {
            'graves': [{'id': b.id, 'x': b.x, 'y': b.y} for b in graves]
        }))

        units = self.battle.units.outerjoin(Unit.owner)
        self.commands.append(Command('add-units', {
            'units': [{
                'id': b.id,
                'x': b.x,
                'y': b.y,
                'type': b.type,
                'color': b.owner.color if b.owner else None,
                'level': b.level,
                'health': b.health,
                'state': 'waiting',
                'active': len(get_available_actions(b))
            } for b in units]
        }))

        return self

    def get_commands(self):
        return [c.to_dict() for c in self.commands]

    def handle_click_on_cell(self, x: int, y: int):
        cell = Cell(x, y)

        if self.battle.selected_unit:
            actions = get_available_actions(self.battle.selected_unit)
        else:
            actions = {}

        if cell in actions.keys():
            action = actions[cell]
            print(action)
            self.clear_selected_unit_actions()
            if action == 'move':
                self.move_unit(self.battle.selected_unit, cell)
            elif action == 'fix-building':
                self.fix_building(self.battle.selected_unit)
            elif action == 'occupy-building':
                self.occupy_building(self.battle.selected_unit)
            elif action == 'attack-unit':
                unit = Unit.query.filter_by(battle_id=self.battle.id, x=x, y=y).one()
                self.attack_unit(self.battle.selected_unit, unit)

            self.sync_units_active()

            return self

        unit = Unit.query.filter_by(battle_id=self.battle.id, x=x, y=y, owner=self.battle.active_player).one_or_none()
        if unit:
            self.select_unit(unit)
            return self

        store = Building.query.filter_by(battle_id=self.battle.id, x=x, y=y, type='castle',
                                         owner=self.battle.active_player).one_or_none()
        if store:
            self.commands.append(Command('open-store', {
                'storeCell': {'x': store.x, 'y': store.y},
                'items': get_units_to_buy(self.battle)
            }))
            return self

        self.clear_selected_unit()
        return self

    def sync_units_active(self):
        units = self.battle.active_player.units.all()
        self.shared_commands.append(Command('update-units', {
            'units': [{
                'id': unit.id,
                'changes': {
                    'active': len(get_available_actions(unit))
                }
            } for unit in units]
        }))

    def select_unit(self, unit):
        self.battle.selected_unit = unit
        db_session.commit()

        self.sync_selected_unit()

    def sync_selected_unit(self):
        unit = self.battle.selected_unit
        actions = get_available_actions(unit)
        action_list = [{'x': cell.x, 'y': cell.y, 'type': action_type} for cell, action_type in actions.items()]

        self.shared_commands.append(Command('update-selected-unit', {
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
        }))

    def clear_selected_unit_actions(self):
        self.shared_commands.append(Command('update-selected-unit', {
            'actions': [],
        }))

    def clear_selected_unit(self):
        self.battle.selected_unit = None
        db_session.commit()

        self.shared_commands.append(Command('clear-selected-unit', {}))

    def move_unit(self, unit, cell):
        self.shared_commands.append(Command.update_unit(unit, {
            'state': 'moving',
            'stateParams': {
                'x': cell.x,
                'y': cell.y,
            }
        }))

        unit.x = cell.x
        unit.y = cell.y
        unit.did_move = True
        db_session.commit()

        self.shared_commands.append(Command.update_unit(unit, {
            'state': 'waiting',
            'stateParams': {},
            'x': cell.x,
            'y': cell.y,
        }))

        self.sync_selected_unit()

        # TODO: update wisp aura

    def fix_building(self, unit):
        building = Building.query.filter_by(battle=unit.battle, x=unit.x, y=unit.y).one()

        building.owner = unit.owner
        unit.did_fix = True
        db_session.commit()

        self.shared_commands.append(Command.update_building(building, {
            'state': 'normal',
        }))

        self.sync_selected_unit()

    def occupy_building(self, unit):
        building = Building.query.filter_by(battle=unit.battle, x=unit.x, y=unit.y).one()

        prev_owner = building.owner
        building.owner = unit.owner
        unit.did_occupy = True
        db_session.commit()

        self.shared_commands.append(Command.update_building(building, {
            'color': building.owner.color,
        }))

        self.sync_selected_unit()

        if prev_owner:
            self.check_players_defeat(prev_owner)

    def attack_unit(self, attacker: Unit, defender: Unit):
        defending_player = defender.owner

        self.shared_commands.append(Command.update_unit(attacker, {
            'state': 'attacking',
            'stateParams': {
                'x': defender.x,
                'y': defender.y,
                'targetType': 'unit',
            }
        }))

        dmg = calculate_damage(attacker, defender)

        health = max(defender.health - dmg, 0)
        self.decrease_unit_hp(defender, dmg)
        self.increase_unit_xp(attacker, dmg)

        if health > 0 and can_strike_back(defender, attacker.cell):
            self.strike_back(defender, attacker)

        self.shared_commands.append(Command.update_unit(attacker, {
            'state': 'waiting',
            'stateParams': {},
        }))

        attacker.did_attack = True
        db_session.commit()

        if not inspect(attacker).detached:
            self.sync_selected_unit()
        else:
            self.clear_selected_unit()

        if health == 0:
            self.check_players_defeat(defending_player)

    def decrease_unit_hp(self, unit, delta_hp):
        health = max(unit.health - delta_hp, 0)
        self.shared_commands.append(Command.update_unit(unit, {
            'state': 'bleeding',
            'stateParams': {
                'deltaHp': delta_hp,
            }
        }))

        if health == 0:
            self.kill_unit(unit)
        else:
            unit.health = health
            self.shared_commands.append(Command.update_unit(unit, {
                'state': 'waiting',
                'stateParams': {},
                'health': unit.health,
            }))

        db_session.commit()

    def kill_unit(self, unit: Unit):
        commander = unit.owner.commander
        if commander.unit == unit:
            commander.unit = None
            commander.death_count += 1
            db_session.commit()

            Unit.query.filter_by(id=unit.id).delete()
            self.shared_commands.append(Command.delete_unit(unit))

            db_session.commit()
        else:
            if unit.battle.selected_unit == unit:
                unit.battle.selected_unit = None
                db_session.commit()

            Unit.query.filter_by(id=unit.id).delete()
            self.shared_commands.append(Command.delete_unit(unit))

            grave = Grave(x=unit.x, y=unit.y, ttl=2, battle=unit.battle)
            db_session.add(grave)
            db_session.commit()
            self.shared_commands.append(Command.add_grave(grave))

    def increase_unit_xp(self, unit: Unit, delta_xp: int):
        xp = unit.xp + delta_xp
        level = bisect.bisect_left(levelList, xp) - 1

        unit.xp = xp
        unit.level = level

        if level > unit.level:
            self.shared_commands.append(Command.update_unit(unit, {
                'state': 'gaining-level',
                'stateParams': {
                    'level': level
                },
            }))
            self.shared_commands.append(Command.update_unit(unit, {
                'state': 'waiting',
                'stateParams': {},
                'level': 'level'
            }))

        commander = unit.owner.commander
        if commander.unit_id == unit.id:
            commander.xp = xp
            commander.level = level

        db_session.commit()

    def strike_back(self, defender, attacker):
        self.shared_commands.append(Command.update_unit(defender, {
            'state': 'attacking',
            'stateParams': {
                'x': attacker.x,
                'y': attacker.y,
                'targetType': 'unit',
            }
        }))

        dmg = calculate_damage(defender, attacker)

        self.decrease_unit_hp(attacker, dmg)
        self.increase_unit_xp(defender, dmg)

        self.shared_commands.append(Command.update_unit(defender, {
            'state': 'waiting',
            'stateParams': {},
        }))

    def buy_unit(self, unit_type: str, store_cell: Cell):
        store = Building.query.filter_by(battle_id=self.battle.id, x=store_cell.x, y=store_cell.y).one_or_none()

        if store is None:
            raise Exception('No player\'s store in that cell')

        player = self.battle.active_player
        unit = Unit(type=unit_type, x=store_cell.x, y=store_cell.y, xp=0, level=0, health=100,
                    owner=player, battle=self.battle)
        db_session.add(unit)
        player.money -= get_unit_cost(unit.type, player)
        db_session.commit()

        self.shared_commands.append(Command.add_unit(unit))
        self.shared_commands.append(Command('update-status', {
            'unitCount': self.battle.active_player.unit_count,
            'money': self.battle.active_player.money,
        }))

        self.select_unit(unit)

        return self

    def end_turn(self):
        self.clear_selected_unit()
        self.reset_units()
        self.activate_next_player()

        income = self.collect_gold()
        self.battle.active_player.money += income
        db_session.commit()

        self.shared_commands.append(Command('update-status', {
            'color': self.battle.active_player.color,
            'unitCount': self.battle.active_player.unit_count,
            'unitLimit': self.battle.active_player.unit_limit,
            'money': self.battle.active_player.money,
            'income': income,
        }))

        self.heal_units()

        return self

    def reset_units(self):
        units = Unit.query.filter_by(battle_id=self.battle.id, owner=self.battle.active_player).all()
        for unit in units:
            unit.did_move = False
            unit.did_fix = False
            unit.did_occupy = False
            unit.did_attack = False
        db_session.commit()

        self.shared_commands.append(Command('update-units', {
            'units': [{
                'id': unit.id,
                'changes': {
                    'active': True
                }
            } for unit in units]
        }))

    def activate_next_player(self):
        players = Player.query.filter_by(battle=self.battle, defeated=False).all()
        prev_player = next(p for p in players if p.id == self.battle.active_player.id)
        prev_player_index = players.index(prev_player)
        next_player = players[(prev_player_index + 1) % len(players)]
        self.battle.active_player = next_player
        db_session.commit()

    def collect_gold(self):
        buildings = self.battle.active_player.buildings.all()
        income = 0
        for building in buildings:
            proto = building_prototypes[building.type]
            if 'earn' in proto:
                income += proto['earn']

        return income

    def heal_units(self):
        neutral_buildings_q = self.battle.buildings.filter(Building.type.in_(('well', 'temple')))
        buildings = self.battle.active_player.buildings.union_all(neutral_buildings_q).all()

        injured_units = self.battle.active_player.units.filter(Unit.health < 100).all()
        deltas = {}
        for unit in injured_units:
            b = [b for b in buildings if b.x == unit.x and b.y == unit.y]
            building = b[0] if b else None
            if building:
                up = building_prototypes[building.type]['healthUp']
                delta_hp = min(100 - unit.health, up)
                deltas[unit.id] = delta_hp
                unit.health += delta_hp
        db_session.commit()

        if [u for u in injured_units if u.id in deltas]:
            self.shared_commands.append(Command('update-units', {
                'units': [{
                    'id': unit.id, 'changes': {
                        'state': 'healing',
                        'stateParams': {
                            'deltaHp': deltas[unit.id],
                        }
                    }
                } for unit in injured_units]
            }))
            self.shared_commands.append(Command('update-units', {
                'units': [{
                    'id': unit.id,
                    'changes': {
                        'health': unit.health,
                        'state': 'waiting',
                        'stateParams': {},
                    }
                } for unit in injured_units]
            }))

    def check_players_defeat(self, player: Player):
        has_no_commander = player.commander.unit is None
        has_no_castle = len(player.buildings.filter_by(type='castle').all()) == 0
        if has_no_commander and has_no_castle:
            player.defeated = True
            db_session.commit()

            team_players = self.battle.players.filter_by(team=player.team, defeated=False).all()
            if team_players:
                for team_player in team_players:
                    team_player.money += player.money // len(team_players)
            else:
                alive_players = self.battle.players.filter_by(defeated=False).all()
                teams_left = len({p.team for p in alive_players})
                if teams_left == 1:
                    self.battle.winner_team = alive_players[0].team

                    self.shared_commands.append(Command('update-status', {
                        'winnerTeam': self.battle.winner_team,
                    }))

        db_session.commit()


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


def get_unit_cost(unit_type, player: Player):
    cost = prototypes[unit_type]['cost']

    if unit_type in commanderList:
        return cost + player.commander.death_count * commanderAddedCost
    else:
        return cost
