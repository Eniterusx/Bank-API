import pytest
import tempfile
import os

from bank_api.models import Country, PrimaryBank, BranchBank, Base
from bank_api.main import app
from tests.testdb import get_engine, get_sessionmaker
from data_parser.parser import load_data

@pytest.fixture(scope="function")
def empty_db_session():
    """A fresh DB with no rows."""
    engine = get_engine()
    sessionmaker = get_sessionmaker(engine)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker()
    yield session
    session.rollback()
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def populated_db_session(empty_db_session):
    """Same clean DB but pre‐populated by creating ORM objects directly."""
    session = empty_db_session

    country_pl = Country(countryISO2="PL", country_name="Poland")
    country_de = Country(countryISO2="DE", country_name="Germany")
    country_us = Country(countryISO2="US", country_name="United States")
    session.add_all([country_pl, country_de, country_us])

    primary_a = PrimaryBank(
        swiftCode="AAAABBCC",
        address="Address A",
        bank_name="Primary A",
        countryISO2="PL"
    )
    primary_b = PrimaryBank(
        swiftCode="DDDDEEFF",
        address="Address B",
        bank_name="Primary B",
        countryISO2="DE"
    )
    primary_c = PrimaryBank(
        swiftCode="AABBCCDD",
        address="Address C",
        bank_name="Primary C",
        countryISO2="PL"
    )
    session.add_all([primary_a, primary_b, primary_c])

    branch_a = BranchBank(
        swiftCode="AAAABBCC",
        swiftCodeBranch="123",
        address="Address C",
        bank_name="Branch A",
        countryISO2="PL"
    )
    branch_b = BranchBank(
        swiftCode="DDDDEEFF",
        swiftCodeBranch="456",
        address="Address D",
        bank_name="Branch B",
        countryISO2="DE"
    )
    session.add_all([branch_a, branch_b])

    session.commit()
    return session

def test_parser_creates_entities(empty_db_session):
    # Test the parser with a temporary CSV file
    csv_content = """SWIFT CODE,NAME,ADDRESS,COUNTRY ISO2 CODE,COUNTRY NAME
        AAAABBCCXXX,Primary A,Address A,PL,Poland
        DDDDEEFFXXX,Primary B,Address B,DE,Germany
        AAAABBCC123,Branch A,Address C,PL,Poland
        DDDDEEFF456,Branch B,Address D,DE,Germany
        """
    
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, newline='') as tmp:
        tmp.write(csv_content)
        tmp.flush()

        load_data(tmp.name, session=empty_db_session)

        os.unlink(tmp.name)

    empty_db_session.flush()

    assert empty_db_session.query(Country).count() == 2
    assert empty_db_session.query(PrimaryBank).count() == 2
    assert empty_db_session.query(BranchBank).count() == 2

def test_load_data_creates_entities(populated_db_session):
    # Check that the data was loaded correctly
    assert populated_db_session.query(Country).count() == 3
    assert populated_db_session.query(PrimaryBank).count() == 3
    assert populated_db_session.query(BranchBank).count() == 2

    primary_bank = populated_db_session.query(PrimaryBank).filter_by(swiftCode="AAAABBCC").first()
    assert primary_bank is not None
    assert primary_bank.bank_name == "Primary A"
    assert primary_bank.address == "Address A"
    assert primary_bank.countryISO2 == "PL"

    branch_bank = populated_db_session.query(BranchBank).filter_by(swiftCode="AAAABBCC").first()
    assert branch_bank is not None
    assert branch_bank.bank_name == "Branch A"
    assert branch_bank.address == "Address C"
    assert branch_bank.countryISO2 == "PL"

    country_pl = populated_db_session.query(Country).filter_by(countryISO2="PL").first()
    assert country_pl is not None
    assert country_pl.country_name == "Poland"

def test_get_existing_primary_bank_no_children(client, populated_db_session):
    resp = client.get("/v1/swift-codes/AABBCCDDXXX")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["address"] == "Address C"
    assert data["bankName"] == "Primary C"
    assert data["countryISO2"] == "PL"
    assert data["countryName"] == "Poland"
    assert data["isHeadquarter"] == True
    assert data["swiftCode"] == "AABBCCDDXXX"
    # check if data has attribute branches
    assert data["branches"] == []

def test_get_existing_primary_bank_with_children(client, populated_db_session):
    resp = client.get("/v1/swift-codes/AAAABBCCXXX")
    assert resp.status_code == 200
    data = resp.get_json()
    
    assert data["address"] == "Address A"
    assert data["bankName"] == "Primary A"
    assert data["countryISO2"] == "PL"
    assert data["countryName"] == "Poland"
    assert data["isHeadquarter"] == True
    assert data["swiftCode"] == "AAAABBCCXXX"

    assert len(data["branches"]) == 1
    assert data["branches"][0]["address"] == "Address C"
    assert data["branches"][0]["bankName"] == "Branch A"
    assert data["branches"][0]["countryISO2"] == "PL"
    assert data["branches"][0]["isHeadquarter"] == False
    assert data["branches"][0]["swiftCode"] == "AAAABBCC123"
 
def test_get_existing_branch_bank(client, populated_db_session):
    resp = client.get("/v1/swift-codes/AAAABBCC123")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["address"] == "Address C"
    assert data["bankName"] == "Branch A"
    assert data["countryISO2"] == "PL"
    assert data["countryName"] == "Poland"
    assert data["isHeadquarter"] == False
    assert data["swiftCode"] == "AAAABBCC123"
    assert "branches" not in data

def test_get_non_existing_bank(client, populated_db_session):
    resp = client.get("/v1/swift-codes/00000000000")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "Bank not found"

def test_get_bank_wrong_length_swift_code(client, populated_db_session):
    resp = client.get("/v1/swift-codes/123")
    assert resp.status_code == 400

    resp = client.get("/v1/swift-codes/12345678901234567890")
    assert resp.status_code == 400

def test_get_bank_no_swift_code(client, populated_db_session):
    resp = client.get("/v1/swift-codes/")
    assert resp.status_code == 400

def test_country_with_banks(client, populated_db_session):
    resp = client.get("/v1/swift-codes/country/PL")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["countryISO2"] == "PL"
    assert data["countryName"] == "Poland"
    assert len(data["swiftCodes"]) == 3
    assert data["swiftCodes"][0]["address"] == "Address A"
    assert data["swiftCodes"][0]["bankName"] == "Primary A"
    assert data["swiftCodes"][0]["countryISO2"] == "PL"
    assert data["swiftCodes"][0]["isHeadquarter"] == True
    assert data["swiftCodes"][0]["swiftCode"] == "AAAABBCCXXX"

def test_country_without_banks(client, populated_db_session):
    resp = client.get("/v1/swift-codes/country/US")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "No banks found in this country"

def test_invalid_country_code(client, populated_db_session):
    resp = client.get("/v1/swift-codes/country/ZZ")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "Country not found"

    resp = client.get("/v1/swift-codes/country/PLL")
    assert resp.status_code == 400

    resp = client.get("/v1/swift-codes/country/P")
    assert resp.status_code == 400

    resp = client.get("/v1/swift-codes/country/$$")
    assert resp.status_code == 400

def test_add_new_bank(client, empty_db_session):
    new_bank = {
        "address": "New Address",
        "bankName": "New Bank",
        "countryISO2": "PL",
        "countryName": "Poland",
        "isHeadquarter": True,
        "swiftCode": "ZZZZZZZZXXX",
    }
    resp = client.post("/v1/swift-codes", json=new_bank)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["message"] == "Bank added successfully"

    # Check if the bank was added to the database
    bank = empty_db_session.query(PrimaryBank).filter_by(swiftCode="ZZZZZZZZ").first()
    assert bank is not None
    assert bank.address == "New Address"
    assert bank.bank_name == "New Bank"
    assert bank.countryISO2 == "PL"
    assert bank.swiftCode == "ZZZZZZZZ"

def test_add_existing_bank(client, populated_db_session):
    existing_bank = {
        "address": "Existing Address",
        "bankName": "Existing Bank",
        "countryISO2": "PL",
        "countryName": "Poland",
        "isHeadquarter": True,
        "swiftCode": "AAAABBCCXXX",
    }
    resp = client.post("/v1/swift-codes", json=existing_bank)
    assert resp.status_code == 409
    data = resp.get_json()
    assert data["error"] == "Bank already exists"

def test_add_bank_missing_data(client, empty_db_session):
    invalid_bank = {
        "address": "Invalid Address",
        "bankName": "Invalid Bank",
        "countryISO2": "PL",
        "countryName": "Poland",
        "isHeadquarter": True,
        # Missing swiftCode
    }
    resp = client.post("/v1/swift-codes", json=invalid_bank)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Missing fields: swiftCode"

    invalid_bank = {
        "address": "Invalid Address",
        "bankName": "Invalid Bank",
        "countryISO2": "PL",
        "countryName": "Poland",
        # Missing isHeadquarter
        "swiftCode": "ZZZZZZZZXXX",
    }

    resp = client.post("/v1/swift-codes", json=invalid_bank)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Missing fields: isHeadquarter"
    
    # Check if the bank was not added to the database
    bank = empty_db_session.query(PrimaryBank).filter_by(swiftCode="ZZZZZZZZ").first()
    assert bank is None

def test_add_bank_empty_address(client, empty_db_session):
    invalid_bank = {
        "address": "",
        "bankName": "Invalid Bank",
        "countryISO2": "PL",
        "countryName": "Poland",
        "isHeadquarter": True,
        "swiftCode": "ZZZZZZZZXXX",
    }
    resp = client.post("/v1/swift-codes", json=invalid_bank)
    assert resp.status_code == 201
    bank = empty_db_session.query(PrimaryBank).filter_by(swiftCode="ZZZZZZZZ").first()
    assert bank is not None
    assert bank.address == ""

def test_add_bank_empty_name(client, empty_db_session):
    invalid_bank = {
        "address": "Invalid Address",
        "bankName": "",
        "countryISO2": "PL",
        "countryName": "Poland",
        "isHeadquarter": True,
        "swiftCode": "ZZZZZZZZXXX",
    }
    resp = client.post("/v1/swift-codes", json=invalid_bank)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Invalid value for bankName"

def test_add_bank_invalid_country_code(client, empty_db_session):
    invalid_bank = {
        "address": "Invalid Address",
        "bankName": "Invalid Bank",
        "countryISO2": "ZZZ",  # Invalid country code
        "countryName": "Invalid Country",
        "isHeadquarter": True,
        "swiftCode": "ZZZZZZZZXXX",
    }
    resp = client.post("/v1/swift-codes", json=invalid_bank)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Invalid value for countryISO2"

def test_add_bank_invalid_swift_code(client, empty_db_session):
    invalid_bank = {
        "address": "Invalid Address",
        "bankName": "Invalid Bank",
        "countryISO2": "PL",
        "countryName": "Invalid Country",
        "isHeadquarter": True,
        "swiftCode": "ZZZZZZZZZXXX", # Invalid length
    }
    resp = client.post("/v1/swift-codes", json=invalid_bank)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Invalid value for swiftCode"

    invalid_bank = {
        "address": "Invalid Address",
        "bankName": "Invalid Bank",
        "countryISO2": "PL",
        "countryName": "Invalid Country",
        "isHeadquarter": True,
        "swiftCode": "ZZZZZZZZ", # Missing branch code
    }
    resp = client.post("/v1/swift-codes", json=invalid_bank)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Invalid value for swiftCode"

def test_add_bank_invalid_name(client, empty_db_session):
    invalid_bank = {
        "address": "",
        "bankName": "", # Empty name
        "countryISO2": "PL",
        "countryName": "Invalid Country",
        "isHeadquarter": True,
        "swiftCode": "ZZZZZZZZXXX", 
    }
    resp = client.post("/v1/swift-codes", json=invalid_bank)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Invalid value for bankName"

def test_add_bank_invalid_headquarter_status(client, empty_db_session):
    invalid_bank = {
        "address": "Invalid Address",
        "bankName": "Invalid Bank",
        "countryISO2": "PL",
        "countryName": "Invalid Country",
        "isHeadquarter": False, # Invalid value (should be True)
        "swiftCode": "ZZZZZZZZXXX", 
    }
    resp = client.post("/v1/swift-codes", json=invalid_bank)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Branch SWIFT code must not end with 'XXX'"

    invalid_bank = {
        "address": "Invalid Address",
        "bankName": "Invalid Bank",
        "countryISO2": "PL",
        "countryName": "Invalid Country",
        "isHeadquarter": True, # Invalid value (should be False)
        "swiftCode": "ZZZZZZZZAAA",
    }
    resp = client.post("/v1/swift-codes", json=invalid_bank)
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "Headquarters SWIFT code must end with 'XXX'"

    # Check if the bank was not added to the database
    bank = empty_db_session.query(PrimaryBank).filter_by(swiftCode="ZZZZZZZZ").first()
    assert bank is None

def test_delete_existing_bank(client, populated_db_session):
    resp = client.delete("/v1/swift-codes/AAAABBCCXXX")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["message"] == "Bank deleted successfully"

    # Check if the bank was deleted from the database
    bank = populated_db_session.query(PrimaryBank).filter_by(swiftCode="AAAABBCC").first()
    assert bank is None

def test_delete_non_existing_bank(client, populated_db_session):
    resp = client.delete("/v1/swift-codes/00000000000")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "Bank not found"