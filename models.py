from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, select, func
from sqlalchemy.orm import object_session, composite, relationship, column_property
from sqlalchemy.orm.collections import attribute_mapped_collection

from db_constants import Base


class Cell(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __composite_values__(self):
        return self.x, self.y

    def __repr__(self):
        return "Cell(x=%r, y=%r)" % (self.x, self.y)

    def __eq__(self, other):
        return isinstance(other, Cell) and \
               other.x == self.x and \
               other.y == self.y

    def __ne__(self, other):
        return not self.__eq__(other)


# class MapObject(AbstractConcreteBase, Base):
# x = Column(Integer, nullable=False)
# y = Column(Integer, nullable=False)

# cell = composite(Cell, x, y)


class Player(Base):
    __tablename__ = 'players'

    id = Column(Integer, primary_key=True)
    battle_id = Column(ForeignKey('battles.id', name='fk_player_battle'), nullable=False)
    color = Column(String, nullable=False)
    team = Column(Integer, nullable=False)
    money = Column(Integer, nullable=False)
    unit_limit = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    defeated = Column(Boolean)

    commander = relationship("Commander", uselist=False)
    buildings = relationship("Building", back_populates="owner", lazy="dynamic")
    units = relationship("Unit", back_populates="owner", lazy="dynamic")
    wisp_aura_cells = relationship("WispAuraCell", lazy="dynamic")

    # unit_count = column_property(
    #     select([func.count(Unit.id)]).where(Unit.owner_id == id).correlate_except(Unit)
    # )

    @property
    def unit_count(self):
        return object_session(self).scalar(
            select([func.count(Unit.id)]).where(Unit.owner_id == self.id)
        )


class Battle(Base):
    __tablename__ = 'battles'

    id = Column(Integer, primary_key=True)
    turn_count = Column(Integer)
    circle_count = Column(Integer)
    map_width = Column(Integer, nullable=False)
    map_height = Column(Integer, nullable=False)
    active_player_id = Column(Integer, ForeignKey('players.id', name='fk_active_player', use_alter=True))
    winner_team = Column(Integer)

    # collection_class=attribute_mapped_collection('cell')
    terrain = relationship("Terrain", lazy="dynamic", cascade="all, delete-orphan")
    players = relationship("Player", primaryjoin="Player.battle_id==Battle.id", lazy="dynamic", cascade="all, delete-orphan")
    buildings = relationship("Building", lazy="dynamic", cascade="all, delete-orphan")
    graves = relationship("Grave", lazy="dynamic", cascade="all, delete-orphan")
    units = relationship("Unit", lazy="dynamic", cascade="all, delete-orphan")
    active_player = relationship("Player", uselist=False, foreign_keys=[active_player_id], post_update=True)

    # def __init__(self, map_width, map_height):
    #     pass
    # self.map_width = map_width
    # self.map_height = map_height
    # self.turn_count = 0
    # self.circle_count = 0


class Terrain(Base):
    __tablename__ = 'terrain'

    battle_id = Column(ForeignKey('battles.id'), primary_key=True)
    x = Column(Integer, primary_key=True)
    y = Column(Integer, primary_key=True)
    type = Column(String)

    cell = composite(Cell, x, y)


class Unit(Base):
    __tablename__ = 'units'

    id = Column(Integer, primary_key=True)
    battle_id = Column(ForeignKey('battles.id'), nullable=False)
    owner_id = Column(ForeignKey('players.id'), nullable=False)
    type = Column(String, nullable=False)
    xp = Column(Integer, nullable=False)
    level = Column(Integer, nullable=False)
    health = Column(Integer, nullable=False)
    poison_count = Column(Integer)
    did_move = Column(Boolean)
    did_attack = Column(Boolean)
    did_fix = Column(Boolean)
    did_occupy = Column(Boolean)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)

    cell = composite(Cell, x, y)

    owner = relationship("Player", back_populates="units")

    # @hybrid_property
    # def cell(self):
    #     return '{0},{1}'.format(self.x, self.y)

    def __repr__(self):
        return 'id={0},x={1},x={2},type={3},owner_id={4}'.format(self.id, self.x, self.y, self.type, self.owner_id)


class Commander(Base):
    __tablename__ = 'commanders'

    id = Column(Integer, primary_key=True)
    player_id = Column(ForeignKey('players.id'), nullable=False)
    unit_id = Column(ForeignKey('units.id'))
    death_count = Column(Integer)
    xp = Column(Integer, nullable=False)
    level = Column(Integer, nullable=False)
    character = Column(String, nullable=False)

    unit = relationship("Unit", uselist=False)


class WispAuraCell(Base):
    __tablename__ = 'wisp_aura_cells'

    id = Column(Integer, primary_key=True)
    player_id = Column(ForeignKey('players.id'), nullable=False)


class Building(Base):
    __tablename__ = 'buildings'

    id = Column(Integer, primary_key=True)
    battle_id = Column(ForeignKey('battles.id'), nullable=False)
    owner_id = Column(ForeignKey('players.id'))
    type = Column(String, nullable=False)
    state = Column(String, nullable=False)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)

    cell = composite(Cell, x, y)

    owner = relationship("Player", back_populates="buildings")


class Grave(Base):
    __tablename__ = 'graves'

    id = Column(Integer, primary_key=True)
    battle_id = Column(ForeignKey('battles.id'), nullable=False)
    ttl = Column(Integer, nullable=False)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)

    cell = composite(Cell, x, y)
