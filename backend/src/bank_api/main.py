from sqlalchemy import select, and_
from bank_api.db import get_engine, get_sessionmaker
from bank_api.models import PrimaryBank, BranchBank, Country

from flask import Flask, jsonify, request
from flask_cors import CORS
from typing import Optional, List

app = Flask(__name__)
CORS(app)

def is_primary_bank(swift_code: str) -> bool:
    return swift_code.endswith("XXX")

def get_primary_bank_swift(session, swift_code: str) -> PrimaryBank:
    """Get primary bank information based on the SWIFT code."""

    return session.execute(
        select(PrimaryBank).where(
            PrimaryBank.swiftCode == swift_code[:8]
        )
    ).scalar_one_or_none()

def get_branch_bank_swift(session, swift_code: str) -> BranchBank:
    """Get branch bank information based on the SWIFT code."""
    
    return session.execute(
        select(BranchBank).where(
            and_(
                BranchBank.swiftCode == swift_code[:8],
                BranchBank.swiftCodeBranch == swift_code[8:11]
            )
        )  
    ).scalar_one_or_none()

def get_branch_banks_swift(session, primary_bank_swift_code: str) -> List[BranchBank]:
    """Get all the branch banks based on the first 8 characters of the SWIFT code."""
    
    banks = session.execute(
        select(BranchBank).where(
            BranchBank.swiftCode == primary_bank_swift_code[:8]
        )
    ).fetchall()
    if not banks:
        return []

    return [bank[0] for bank in banks]

def get_banks_in_country(session, countryISO2code: str) -> List[PrimaryBank | BranchBank]:
    """Get all banks in a specific country based on the ISO2 code."""
    
    banks = session.execute(
        select(PrimaryBank).where(
            PrimaryBank.countryISO2 == countryISO2code
        )
    ).fetchall()
    branch_banks = session.execute(
        select(BranchBank).where(
            BranchBank.countryISO2 == countryISO2code
        )
    ).fetchall()
    banks.extend(branch_banks)

    if not banks:
        return []

    return [bank[0] for bank in banks]

@app.route('/v1/swift-codes/', methods=['GET'])
@app.route('/v1/swift-codes/<swift_code>', methods=['GET'])
def get_bank(swift_code: Optional[str] = None):
    """
    Retrieve details of a single SWIFT code whether for a headquarters or branches.
    """
    if not swift_code:
        return jsonify({"error": "Swift code is required"}), 400
    swift_code = swift_code.strip().upper()
    if len(swift_code) != 11:
        return jsonify({"error": "Swift code must be at least 11 characters"}), 400
    if not swift_code.isalnum():
        return jsonify({"error": "Swift code must be alphanumeric"}), 400
        
    
    with SessionLocal() as session:
        if is_primary_bank(swift_code):
            bank: PrimaryBank = get_primary_bank_swift(session, swift_code)
            if not bank:
                return jsonify({"error": "Bank not found"}), 404

            country_name = session.execute(
                select(Country.country_name).where(
                    Country.countryISO2 == bank.countryISO2
                )
            ).scalar_one_or_none()
            if not country_name:
                return jsonify({"error": "Country not found"}), 404

            branch_banks: List[BranchBank] = get_branch_banks_swift(session, swift_code)

            branches = [{
                "address": b.address,
                "bankName": b.bank_name,
                "countryISO2": b.countryISO2,
                "isHeadquarter": b.is_primary_bank(),
                "swiftCode": b.full_swift_code(),
            } for b in branch_banks]

            return jsonify(
                address=bank.address,
                bankName=bank.bank_name,
                countryISO2=bank.countryISO2,
                countryName=country_name,
                isHeadquarter=bank.is_primary_bank(),
                swiftCode=bank.full_swift_code(),
                branches=branches
            ), 200

        else:
            branch: BranchBank = get_branch_bank_swift(session, swift_code)
            if not branch:
                return jsonify(error="Bank not found"), 404
            
            country_name = session.execute(
                select(Country.country_name).where(
                    Country.countryISO2 == branch.countryISO2
                )
            ).scalar_one_or_none()
            if not country_name:
                return jsonify({"error": "Country not found"}), 404
            
            return jsonify(
                address=branch.address,
                bankName=branch.bank_name,
                countryISO2=branch.countryISO2,
                countryName=country_name,
                isHeadquarter=branch.is_primary_bank(),
                swiftCode=branch.full_swift_code(),
            ), 200

@app.route('/v1/swift-codes/country/', methods=['GET'])
@app.route('/v1/swift-codes/country/<countryISO2code>', methods=['GET'])
def get_banks_country(countryISO2code: Optional[str] = None):
    """
    Return all SWIFT codes with details for a specific
    country (both headquarters and branches).
    """
    if not countryISO2code:
        return jsonify({"error": "Country code is required"}), 400
    countryISO2code = countryISO2code.strip().upper()
    if len(countryISO2code) != 2:
        return jsonify({"error": "Country code must be 2 characters"}), 400
    if not countryISO2code.isalnum():
        return jsonify({"error": "Country code must be alphanumeric"}), 400

    with SessionLocal() as session:
        country: Country = session.execute(
            select(Country).where(
                Country.countryISO2 == countryISO2code
            )
        ).scalar_one_or_none()
        
        if not country:
            return jsonify({"error": "Country not found"}), 404

        banks: List[PrimaryBank] = get_banks_in_country(session, countryISO2code)
        if not banks:
            return jsonify({"error": "No banks found in this country"}), 404

        return jsonify(
            countryISO2=country.countryISO2,
            countryName=country.country_name,
            swiftCodes=[{
                "address": b.address,
                "bankName": b.bank_name,
                "countryISO2": b.countryISO2,
                "isHeadquarter": b.is_primary_bank(),
                "swiftCode": b.full_swift_code(),
            } for b in banks]
        ), 200

@app.route('/v1/swift-codes', methods=['POST'])
def add_new_code():
    """
    Adds new SWIFT code entries to the database for a specific country.
    """
    body = request.get_json() or {}

    validators = {
        "bankName":       (str,  lambda v: 0 < len(v) <= 255),
        "countryISO2":    (str,  lambda v: len(v) == 2 and v.isalnum()),
        "countryName":    (str,  lambda v: len(v) > 0),
        "isHeadquarter": (bool, None),
        "swiftCode":      (str,  lambda v: len(v) == 11 and v.isalnum()),
    }

    missing = [k for k in validators if k not in body]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    for field, (ftype, check) in validators.items():
        val = body[field]
        if not isinstance(val, ftype):
            return jsonify({"error": f"{field} must be a {ftype.__name__}"}), 400
        if check and not check(val):
            return jsonify({"error": f"Invalid value for {field}"}), 400

    address = body.get("address", "").strip()

    bankName       = body["bankName"].strip()
    countryISO2    = body["countryISO2"].strip().upper()
    countryName    = body["countryName"].strip()
    isHeadquarter  = body["isHeadquarter"]
    swiftCode      = body["swiftCode"].strip().upper()

    if isHeadquarter and not swiftCode.endswith("XXX"):
        return jsonify({"error": "Headquarters SWIFT code must end with 'XXX'"}), 400
    if not isHeadquarter and swiftCode.endswith("XXX"):
        return jsonify({"error": "Branch SWIFT code must not end with 'XXX'"}), 400

    with SessionLocal() as session:
        country = session.get(Country, countryISO2)
        if not country:
            country = Country(countryISO2=countryISO2, country_name=countryName)
            session.add(country)
        elif country.country_name != countryName:
            return jsonify({"error": "Country name mismatch"}), 409

        swift_prefix = swiftCode[:8]
        swift_branch = swiftCode[8:11]

        if isHeadquarter:
            existing = session.execute(
                select(PrimaryBank).where(PrimaryBank.swiftCode == swift_prefix)
            ).scalar_one_or_none()
            if existing:
                return jsonify({"error": "Bank already exists"}), 409
            session.add(PrimaryBank(
                swiftCode=swift_prefix,
                address=address,
                bank_name=bankName,
                countryISO2=countryISO2
            ))
        else:
            existing = session.execute(
                select(BranchBank).where(
                    and_(
                        BranchBank.swiftCode == swift_prefix,
                        BranchBank.swiftCodeBranch == swift_branch
                    )
                )
            ).scalar_one_or_none()
            if existing:
                return jsonify({"error": "Bank already exists"}), 409
            session.add(BranchBank(
                swiftCode=swift_prefix,
                swiftCodeBranch=swift_branch,
                address=address,
                bank_name=bankName,
                countryISO2=countryISO2
            ))

        session.commit()

    return jsonify({"message": "Bank added successfully"}), 201

@app.route('/v1/swift-codes/', methods=['DELETE'])
@app.route('/v1/swift-codes/<swift_code>', methods=['DELETE'])
def return_code(swift_code: Optional[str] = None):
    """
    Deletes swift-code data if swiftCode matches the one in the database.
    """
    if not swift_code:
        return jsonify({"error": "Swift code is required"}), 400
    
    with SessionLocal() as session:
        if is_primary_bank(swift_code):
            bank: PrimaryBank = get_primary_bank_swift(session, swift_code)
            if not bank:
                return jsonify({"error": "Bank not found"}), 404

            session.delete(bank)
        else:
            branch: BranchBank = get_branch_bank_swift(session, swift_code)
            if not branch:
                return jsonify({"error": "Bank not found"}), 404

            session.delete(branch)

        session.commit()
        if session.is_modified:
            return jsonify({"message": "Bank deleted successfully"}), 200
        else:
            return jsonify({"error": "Bank not found"}), 404

if __name__ == '__main__':
    SessionLocal = get_sessionmaker()
    app.run(host="0.0.0.0", port=8080)
