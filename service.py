from db_constants import db_session
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
        commander = Commander(character=pref['commanderCharacter'], death_count=0, xp=0, level=0,
                              unit=units[map_data['commander']['unitId']])
        player = Player(color=pref['color'],
                        team=pref['team'],
                        money=preferences['money'],
                        unit_limit=preferences['unitLimit'],
                        type=pref['type'],
                        commander=commander)
        players[map_data['id']] = player

    for u in battle_map['units'].values():
        print(u['ownerId'], type(u['ownerId']), players.keys(), u['ownerId'] in players)
        units[u['id']].owner = players[u['ownerId']]

    db_session.add_all(players.values())
    db_session.add_all(units.values())

    accuracy = Battle(map_width=battle_map['size']['width'],
                      map_height=battle_map['size']['height'],
                      turn_count=0,
                      circle_count=0,
                      terrain=terrain,
                      buildings=buildings.values(),
                      players=players.values(),
                      units=units.values())

    db_session.add(accuracy)
    db_session.commit()
