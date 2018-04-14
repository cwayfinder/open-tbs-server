defByLevel = 2
atkByLevel = 2
reduceMoveByPoison = 1
bonusAtkByWispAura = 10
reduceAtkPoison = 10
reduceDefPoison = 10
bonusAtkByWater = 10
bonusDefByWater = 15
levelList = [0, 84, 172, 265, 362, 464, 571, 684, 802, 926]
commanderList = ['galamar', 'valadorn', 'demon-lord', 'saeth']
commanderAddedCost = 200
prototypes = {
    'galamar': {
        'atk': {'min': 55, 'max': 65},
        'atkRange': 2,
        'def': 20,
        'mov': 5,
        'canFixBuilding': True,
        'withoutGrave': True,
        'canOccupyBuilding': ['farm', 'castle'],
        'cost': 200,
    },
    'valadorn': {
        'atk': {'min': 55, 'max': 65},
        'atkRange': 2,
        'def': 20,
        'mov': 5,
        'canFixBuilding': True,
        'withoutGrave': True,
        'canOccupyBuilding': ['farm', 'castle'],
        'cost': 200,
    },
    'demon-lord': {
        'atk': {'min': 55, 'max': 65},
        'atkRange': 2,
        'def': 20,
        'mov': 5,
        'canFixBuilding': True,
        'withoutGrave': True,
        'canOccupyBuilding': ['farm', 'castle'],
        'cost': 200,
    },
    'saeth': {
        'atk': {'min': 55, 'max': 65},
        'atkRange': 2,
        'def': 20,
        'mov': 5,
        'canFixBuilding': True,
        'withoutGrave': True,
        'canOccupyBuilding': ['farm', 'castle'],
        'cost': 200,
    },
    'saeth-heavens-fury': {
        'atk': {'min': 55, 'max': 65},
        'atkRange': 16,
        'def': 45,
        'mov': 1,
        'canNotBeBuy': True,
    },
    'soldier': {
        'atk': {'min': 50, 'max': 55},
        'atkRange': 2,
        'def': 5,
        'mov': 5,
        'canFixBuilding': True,
        'canOccupyBuilding': ['farm'],
        'cost': 150,
    },
    'archer': {
        'atk': {'min': 50, 'max': 55},
        'atkRange': 3,
        'def': 5,
        'mov': 5,
        'bonusAtkAgainstFly': 30,
        'cost': 250,
    },
    'elemental': {
        'atk': {'min': 50, 'max': 55},
        'atkRange': 2,
        'def': 10,
        'mov': 5,
        'moveType': 'flow',
        'cost': 300,
    },
    'sorceress': {
        'atk': {'min': 40, 'max': 45},
        'atkRange': 2,
        'raiseRange': 2,
        'def': 5,
        'mov': 5,
        'cost': 400,
    },
    'wisp': {
        'atk': {'min': 35, 'max': 40},
        'atkRange': 2,
        'auraRange': 3,
        'def': 10,
        'mov': 5,
        'bonusAtkAgainstSkeleton': 30,
        'cost': 500,
    },
    'dire-wolf': {
        'atk': {'min': 60, 'max': 65},
        'atkRange': 2,
        'def': 15,
        'mov': 6,
        'poisonPeriod': 2,
        'cost': 600,
    },
    'golem': {
        'atk': {'min': 60, 'max': 70},
        'atkRange': 2,
        'def': 30,
        'mov': 5,
        'cost': 600,
    },
    'catapult': {
        'atk': {'min': 50, 'max': 70},
        'atkRange': 5,
        'def': 10,
        'mov': 4,
        'cost': 700,
        'cannotActAfterMove': True,
        'canDestroyBuilding': True,
    },
    'dragon': {
        'atk': {'min': 70, 'max': 80},
        'atkRange': 2,
        'def': 25,
        'mov': 7,
        'moveType': 'fly',
        'cost': 1e3,
    },
    'skeleton': {
        'atk': {'min': 40, 'max': 50},
        'atkRange': 2,
        'def': 2,
        'mov': 5,
        'withoutGrave': True,
        'cost': 0,
    },
    'crystal': {
        'atk': {'min': 0, 'max': 0},
        'atkRange': 1,
        'def': 15,
        'mov': 4,
        'cost': 0,
    },
}
