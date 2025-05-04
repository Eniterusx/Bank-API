# Base stage (shared deps) ------------
    FROM python:3.12.0-alpine AS base

    WORKDIR /app
    
    # Copy pyproject & install packages with uv
    RUN apk update \
        && apk add --no-cache curl ca-certificates \
        && curl -fsSL https://astral.sh/uv/install.sh | sh \
        && rm -rf /var/cache/apk/*

    # Add uv to PATH
    ENV PATH="/root/.local/bin/:$PATH"

    # Copy requirements
    COPY pyproject.toml .

    # Install dependencies with uv
    RUN uv venv && uv pip install -r pyproject.toml
    
    # Backend build -------------------
    FROM base AS backend
    
    WORKDIR /app
    
    COPY src/bank_api/ src/bank_api/

    WORKDIR /app/src
    
    CMD ["uv", "run", "-m", "bank_api.main"]
    
    # Parser build --------------------
    FROM base AS parser
    
    WORKDIR /app
    
    COPY src/bank_api/ src/bank_api/
    COPY src/data_parser/ src/data_parser/

    WORKDIR /app/src
    
    CMD ["uv", "run", "-m", "data_parser.parser"]

    # Unit tests build ----------------
    FROM base AS tests

    WORKDIR /app

    COPY src/bank_api/ src/bank_api/
    COPY src/tests/ src/tests/

    RUN uv pip install ".[unit_tests]"

    WORKDIR /app/src

    # CMD ["uv", "run", "-m", "tests.test_api"]
    CMD ["pytest", "-v", "--tb=short", "--disable-warnings", "--maxfail=1", "--cov=bank_api", "--cov-report=term-missing:skip-covered", "tests/test_api.py"]