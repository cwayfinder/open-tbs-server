import re
from random import randint

from otbs.db.models import Unit, Building, Terrain
from otbs.logic.map_config import map_config
from otbs.logic.unit_master import prototypes, atkByLevel, reduceAtkPoison, bonusAtkByWater, bonusDefByWater, \
    defByLevel, reduceDefPoison, defaultHealth


def get_cell_defence_bonus(unit):
    building = Building.query.filter_by(x=unit.x, y=unit.y, battle_id=unit.battle_id).one_or_none()
    if building:
        return 15

    terrain_type = get_terrain_type(unit)
    proto = prototypes[unit.type]
    if 'moveType' in proto and proto['moveType'] == 'flow' and terrain_type == 'water':
        return bonusDefByWater

    return map_config[terrain_type]['defence']


def get_cell_attack_bonus(attacker, defender):
    bonus = 0

    terrain_type = get_terrain_type(defender)
    atk_proto = prototypes[attacker.type]
    def_proto = prototypes[defender.type]
    if 'moveType' in atk_proto and atk_proto['moveType'] == 'flow' and terrain_type == 'water':
        bonus += bonusAtkByWater
    if 'moveType' in def_proto and def_proto['moveType'] == 'fly' and atk_proto.get('bonusAtkAgainstFly', 0):
        bonus += atk_proto['bonusAtkAgainstFly']
    if defender.type == 'skeleton' and atk_proto.get('bonusAtkAgainstSkeleton', 0):
        bonus += atk_proto['bonusAtkAgainstSkeleton']

    return bonus


def get_terrain_type(unit):
    terrain = Terrain.query.filter_by(x=unit.x, y=unit.y, battle_id=unit.battle_id).one()
    return re.sub('-\d+$', '', terrain.type)


def calculate_attack(attacker: Unit, defender: Unit):
    atk = randint(prototypes[attacker.type]['atk']['min'], prototypes[attacker.type]['atk']['min'])
    atk_level_bonus = atkByLevel * attacker.level
    aura_bonus = 0  # TODO: attacker.underWispAura ? unitMaster.bonusAtkByWispAura: 0;
    atk_poison_penalty = reduceAtkPoison if attacker.poison_count else 0
    atk_cell_bonus = get_cell_attack_bonus(attacker, defender)
    return atk + atk_level_bonus + atk_cell_bonus - atk_poison_penalty + aura_bonus


def calculate_defence(defender: Unit):
    def_level_bonus = defByLevel * defender.level
    def_poison_penalty = reduceDefPoison if defender.poison_count else 0
    def_cell_bonus = get_cell_defence_bonus(defender)
    return def_level_bonus + def_cell_bonus - def_poison_penalty + prototypes[defender.type]['def']


def calculate_damage(attacker: Unit, defender: Unit):
    attack = calculate_attack(attacker, defender)
    defence = calculate_defence(defender)
    health_ratio = attacker.health / defaultHealth
    damage = max(round((attack - defence) * health_ratio), 1)

    return min(damage, defender.health)
