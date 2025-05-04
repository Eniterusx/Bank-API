import csv
from sqlalchemy import select

from bank_api.models import Country, PrimaryBank, BranchBank, Base
from bank_api.db import get_sessionmaker


def load_data(filename: str, session):
    
    def is_primary_bank(swift: str) -> bool:
        return swift.endswith("XXX")
    
    try:
        with open(filename, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # check if row is empty
                if not any(row.values()):
                    continue
                if not row['SWIFT CODE'] or not row['NAME'] or not row['ADDRESS'] or not row['COUNTRY ISO2 CODE'] or not row['COUNTRY NAME']:
                    continue
                raw_swift = row['SWIFT CODE'].strip()
                primary_code = raw_swift[:8]
                branch_code  = raw_swift[8:11]

                # 1) country upsert
                country = session.get(Country, row['COUNTRY ISO2 CODE'])
                if not country:
                    country = Country(
                        countryISO2  = row['COUNTRY ISO2 CODE'],
                        country_name = row['COUNTRY NAME']
                    )
                    session.add(country)

                # 2) bank existence check
                if is_primary_bank(raw_swift):
                    exists = session.execute(
                        select(PrimaryBank).where(PrimaryBank.swiftCode == primary_code)
                    ).scalar_one_or_none()
                    if not exists:
                        session.add(PrimaryBank(
                            swiftCode   = primary_code,
                            address     = row['ADDRESS'].strip(),
                            bank_name   = row['NAME'],
                            countryISO2 = row['COUNTRY ISO2 CODE']
                        ))
                else:
                    exists = session.execute(
                        select(BranchBank).where(
                            BranchBank.swiftCode       == primary_code,
                            BranchBank.swiftCodeBranch == branch_code
                        )
                    ).scalar_one_or_none()
                    if not exists:
                        session.add(BranchBank(
                            swiftCode        = primary_code,
                            swiftCodeBranch  = branch_code,
                            address          = row['ADDRESS'].strip(),
                            bank_name        = row['NAME'],
                            countryISO2      = row['COUNTRY ISO2 CODE']
                        ))

        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    SessionLocal = get_sessionmaker()
    session = SessionLocal()

    Base.metadata.create_all(bind=session.get_bind())

    try:
        load_data("data_parser/data.csv", session)
    finally:
        session.close()