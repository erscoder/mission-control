FROM python:3.12-slim

# System deps: curl for flyctl installer + git for some npm workflows the agents may run
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates git \
 && rm -rf /var/lib/apt/lists/*

# flyctl — required by fly_tool.py to deploy backends
RUN curl -L https://fly.io/install.sh | sh
ENV PATH="/root/.fly/bin:$PATH"

# osv-scanner — required by osv_scanner_tool.py for dependency vulnerability scanning
RUN curl -fsSL -o /usr/local/bin/osv-scanner \
      https://github.com/google/osv-scanner/releases/latest/download/osv-scanner_linux_amd64 \
 && chmod +x /usr/local/bin/osv-scanner

RUN pip install uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
# --no-install-project: install deps only; the package itself is on PYTHONPATH via src/
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
COPY dashboard/ ./dashboard/
COPY run_dashboard.py ./

ENV PATH="/app/.venv/bin:$PATH"
# /app/src → sentinel_v2 package; /app → dashboard package (run_dashboard.py imports dashboard.app)
ENV PYTHONPATH="/app/src:/app"
