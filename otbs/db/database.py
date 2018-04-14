from otbs.db.db_constants import Base, engine


def init_db():
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
    # you will have to import them first before calling init_db()
    from otbs.db.models import Battle

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
