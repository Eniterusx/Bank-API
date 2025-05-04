from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class AbstractBank(Base):
    __abstract__ = True
    id          = Column(Integer, primary_key=True, autoincrement=True)
    swiftCode   = Column(String(8), nullable=False)
    address     = Column(String(255))
    bank_name   = Column(String(255), nullable=False)
    countryISO2 = Column(String(2), nullable=False)

    def __repr__(self):
        return f"<Bank(swiftCode={self.full_swift_code()}, address={self.address}, bank_name={self.bank_name}, countryISO2={self.countryISO2})>"
    
    def full_swift_code(self) -> str:
        raise NotImplementedError("Subclasses must implement this method")

    def is_primary_bank(self) -> bool:
        return self.full_swift_code().endswith("XXX")

class PrimaryBank(AbstractBank):
    __tablename__ = 'primary_banks'

    def full_swift_code(self) -> str:
        return f"{self.swiftCode}XXX"

class BranchBank(AbstractBank):
    __tablename__ = 'branch_banks'
    swiftCodeBranch = Column(String(3), nullable=False)

    def full_swift_code(self) -> str:
        return f"{self.swiftCode}{self.swiftCodeBranch}"

class Country(Base):
    __tablename__ = 'countries'
    countryISO2  = Column(String(2), primary_key=True)
    country_name = Column(String(255), nullable=False)

    def __repr__(self):
        return f"<Country(countryISO2={self.countryISO2}, country_name={self.country_name})>"