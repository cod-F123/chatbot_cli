from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


engine = create_engine("sqlite:///database.db")
SessionLocal = sessionmaker(bind=engine, )
Base = declarative_base()


def get_session():
    # try:
    #     session = SessionLocal()
    # finally:
    #     yield session

    return SessionLocal()


def create_tabels():
    Base.metadata.create_all(engine)
