from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, select, func, or_, and_
from sqlalchemy.orm import object_session, composite, relationship

from otbs.db.db_constants import Base


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

    def __hash__(self):
        return hash((self.x, self.y))


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
    battle = relationship("Battle", back_populates="players", foreign_keys=[battle_id])

    # unit_count = column_property(
    #     select([func.count(Unit.id)]).where(Unit.owner_id == id).correlate_except(Unit)
    # )

    @property
    def unit_count(self):
        return object_session(self).scalar(
            select([func.count(Unit.id)]).where(Unit.owner_id == self.id)
        )

    @property
    def enemy_buildings(self):
        return object_session(self) \
            .query(Building) \
            .select_from(Player) \
            .filter(and_(Player.battle == self.battle, Player.team != self.team)) \
            .join(Building, Building.owner_id == Player.id) \
            .all()

    @property
    def enemy_units(self):
        return object_session(self) \
            .query(Unit) \
            .outerjoin(Player, Unit.owner_id == Player.id) \
            .filter(Player.battle == self.battle) \
            .filter(or_(Unit.owner_id == None, Player.team != self.team)) \
            .all()

    @property
    def team_units(self):
        return object_session(self) \
            .query(Unit) \
            .select_from(Player) \
            .filter(Player.battle == self.battle) \
            .filter(Player.team == self.team) \
            .join(Unit, Unit.owner_id == Player.id) \
            .all()


class Battle(Base):
    __tablename__ = 'battles'

    id = Column(Integer, primary_key=True)
    turn_count = Column(Integer)
    circle_count = Column(Integer)
    map_width = Column(Integer, nullable=False)
    map_height = Column(Integer, nullable=False)
    winner_team = Column(Integer)
    active_player_id = Column(Integer, ForeignKey('players.id', name='fk_active_player', use_alter=True))
    selected_unit_id = Column(Integer, ForeignKey('units.id', name='fk_selected_unit', use_alter=True))

    # collection_class=attribute_mapped_collection('cell')
    terrain = relationship("Terrain", lazy="dynamic", cascade="all, delete-orphan")
    players = relationship("Player", back_populates="battle", primaryjoin="Player.battle_id==Battle.id", lazy="dynamic",
                           cascade="all, delete-orphan")
    buildings = relationship("Building", back_populates="battle", lazy="dynamic", cascade="all, delete-orphan")
    graves = relationship("Grave", back_populates="battle", lazy="dynamic", cascade="all, delete-orphan")
    units = relationship("Unit", back_populates="battle", primaryjoin="Unit.battle_id==Battle.id", lazy="dynamic",
                         cascade="all, delete-orphan")
    active_player = relationship("Player", uselist=False, foreign_keys=[active_player_id], post_update=True)
    selected_unit = relationship("Unit", uselist=False, foreign_keys=[selected_unit_id], post_update=True)

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
    battle_id = Column(ForeignKey('battles.id', name='fk_unit_battle'), nullable=False)
    owner_id = Column(ForeignKey('players.id'))
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

    battle = relationship("Battle", back_populates="units", foreign_keys=[battle_id])
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
    battle = relationship("Battle", back_populates="buildings")

    def __repr__(self):
        return 'id={0},x={1},y={2},type={3},owner_id={4}'.format(self.id, self.x, self.y, self.type, self.owner_id)


class Grave(Base):
    __tablename__ = 'graves'

    id = Column(Integer, primary_key=True)
    battle_id = Column(ForeignKey('battles.id'), nullable=False)
    ttl = Column(Integer, nullable=False)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)

    cell = composite(Cell, x, y)

    battle = relationship("Battle", back_populates="graves")

# class UnitPrototype(Base):
#     __tablename__ = 'unit_prototypes'
#
#     id = Column(Integer, primary_key=True)
#     cost = Column(Integer, nullable=False)
#     atk_min = Column(Integer, nullable=False)
#     atk_max = Column(Integer, nullable=False)
#     atk_range = Column(Integer, nullable=False)
#     defence = Column(Integer, nullable=False)
#     raise_range = Column(Integer, nullable=False)
#     move = Column(Integer, nullable=False)
#     move_type = Column(String, nullable=False)
#     bonus_atk_against_flying = Column(Integer, nullable=False)
#     bonus_atk_against_skeleton = Column(Integer, nullable=False)
#     without_grave = Column(Boolean, nullable=False)
#     can_fix_buildings = Column(ARRAY(Integer), nullable=False)
#     can_occupy_buildings = Column(ARRAY(Integer), nullable=False)
#     can_act_after_move = Column(Boolean, nullable=False)
#     can_destroy_building = Column(Boolean, nullable=False)
