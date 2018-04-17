map_config = {
    'allColors': ["blue", "red", "green", "black", "gray"],
    'playerColors': ["blue", "red", "green", "black"],
    'playerTypes': ["player", "cpu", "none"],
    'money': [500, 750, 1e3, 1500, 2e3, 5e3],
    'unitsLimits': [10, 15, 20, 25],
    'terrainTypes': ["bridge-1", "bridge-2", "forest-1", "forest-2", "hill-1", "road-1", "stone-1", "stone-2",
                     "terra-1", "terra-2", "terra-3", "terra-4", "terra-5", "water-1", "water-2", "water-3"],

    'terra': {'pathResistance': 1, 'defence': 5},
    'road': {'pathResistance': 1, 'defence': 0},
    'bridge': {'pathResistance': 1, 'defence': 0},
    'hill': {'pathResistance': 2, 'defence': 10},
    'forest': {'pathResistance': 2, 'defence': 10},
    'stone': {'pathResistance': 3, 'defence': 15},
    'water': {'pathResistance': 3, 'flowPathResistance': 1, 'defence': 0, 'flowDefence': 15},
}
