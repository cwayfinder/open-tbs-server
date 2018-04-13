from db_constants import db_session
from firestore import fs
from models import Terrain, Building, Unit, Commander, Player, Battle


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
        units[u['id']] = Unit(type=u['type'], x=u['x'], y=u['y'], xp=0, level=0, health=100, owner_id=u['ownerId'])

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
