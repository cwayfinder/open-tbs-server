import re

from otbs.db.models import Cell, Battle
from otbs.logic.map_config import map_config


class VisitedPoint:
    cell: Cell
    mov: int

    def __init__(self, cell, mov):
        self.cell = cell
        self.mov = mov


def get_cell_resistance(cell_type: str, move_type: str = None):
    terrain_type = re.sub('-\d+$', '', cell_type)
    terrain_config = map_config[terrain_type]

    if move_type == 'fly':
        return 1
    elif move_type == 'flow':
        if cell_type == 'water':
            return terrain_config['flowPathResistance']
        else:
            return terrain_config['pathResistance']
    else:
        return terrain_config['pathResistance']


def get_available_path(cell: Cell, range: int, max_x: int, max_y: int, *,
                       resistances: dict = None,
                       obstacles: set = set()):
    available_path = []
    visited_points = []

    def run(start: Cell, mov: int):
        if not any(point for point in visited_points if point.cell == start and point.mov >= mov):
            visited_points.append(VisitedPoint(start, mov))

            if start not in available_path:
                available_path.append(start)

            for further_cell in get_further_cells(start):
                resistance = resistances[further_cell] if resistances else 1
                if mov >= resistance:
                    run(further_cell, mov - resistance)

    def get_further_cells(origin: Cell):
        x = origin.x
        y = origin.y
        further_cells = [Cell(x - 1, y), Cell(x + 1, y), Cell(x, y - 1), Cell(x, y + 1)]
        further_cells = list(filter(lambda c: 0 <= c.x <= max_x and 0 <= c.y <= max_y, further_cells))
        further_cells = list(filter(lambda c: c not in obstacles, further_cells))

        return further_cells

    run(cell, range)

    available_path.pop(0)
    return available_path
