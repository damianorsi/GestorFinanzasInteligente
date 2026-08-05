# =============================================================================
# Backend — build multi-stage.
#   builder : instala dependencias en un venv aislado
#   dev     : venv + dependencias de desarrollo (tests, lint). Usado por compose.
#   runtime : imagen final, sin toolchain de build, usuario no-root.
# =============================================================================

# --- builder ---------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

# --- dev -------------------------------------------------------------------
FROM builder AS dev

RUN pip install ".[dev]"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /srv
COPY . /srv
RUN chmod +x /srv/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/srv/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --- runtime ---------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv \
    PATH="/opt/venv/bin:$PATH"

# El cliente de MySQL sirve para diagnóstico; curl no se instala a propósito
# (el healthcheck usa urllib de la stdlib).
RUN groupadd --system appuser && useradd --system --gid appuser --home /srv appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /srv
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser entrypoint.sh ./
RUN chmod +x /srv/entrypoint.sh

USER appuser

EXPOSE 8000
ENTRYPOINT ["/srv/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
