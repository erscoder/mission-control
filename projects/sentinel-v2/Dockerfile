FROM python:3.12-slim

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY dashboard/ ./dashboard/
COPY run_dashboard.py ./

ENV PATH="/app/.venv/bin:$PATH"
# /app/src → sentinel_v2 package; /app → dashboard package (run_dashboard.py imports dashboard.app)
ENV PYTHONPATH="/app/src:/app"
