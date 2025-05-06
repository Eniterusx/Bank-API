# Bank-API
Project created for Remitly Internship

## How to run
### Prerequisites
- Docker
- Docker Compose
- uv (for unit tests)

### Steps
1. Clone the repository
```
git clone https://github.com/Eniterusx/Bank-API
cd bank-api
```

2. Create a `db/password.txt` file in the root directory of the project with the password for the Postgres database. In the example below, the password is set to `postgres_password`. You can change it to whatever you want, but make sure to use the same password in the next step.

```
echo "postgres_password" > db/password.txt
```

3. Create a `.env` file in the `src/bank_api` directory of the project with the following content:
```
DATABASE_URL="postgresql://postgres:postgres_password@db/bank_db"
```
Replace `postgres_password` with password you want to use for the Postgres database. Make sure to use the same password as in the previous step.

4. Populate the database with the initial data
```
docker compose -f docker-compose.yaml -f docker-compose-parser.yaml up --build parser
```

5. Run the application
```
docker compose build
docker compose up
```

### Unit tests
To run the unit tests, you need to launch the dummy database:
```
docker compose -f docker-compose-unit-test.yaml up --build
```
Then, you can run the tests using the following commands:
```
cd backend
uv venv
source .venv/bin/activate
uv pip install -r pyproject.toml .[unit_tests]
pytest
```
