import pytest
from tests.testdb import get_engine, get_sessionmaker
from bank_api.models import Base
import bank_api.main as main_mod

@pytest.fixture(scope="session", autouse=True)
def test_db_and_app():
    # 1) create test‐engine & sessionmaker
    engine = get_engine()
    TestSessionLocal = get_sessionmaker(engine)

    # 2) create schema
    Base.metadata.create_all(bind=engine)

    # 3) patch main.SessionLocal to use test sessions
    main_mod.SessionLocal = TestSessionLocal

    # 4) enable TESTING on the app
    main_mod.app.config["TESTING"] = True

    yield  # tests run here

    # teardown
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    # yield a Flask test client
    from bank_api.main import app
    with app.test_client() as client:
        yield client