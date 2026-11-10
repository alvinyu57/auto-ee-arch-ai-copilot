FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    VECTOR_DB_PATH=/var/lib/ee-arch

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable \
    && useradd --uid 10001 --create-home appuser \
    && mkdir -p /var/lib/ee-arch \
    && chown appuser:appuser /var/lib/ee-arch

USER appuser
VOLUME ["/var/lib/ee-arch"]
EXPOSE 8000
CMD ["uvicorn", "ee_arch_copilot.main:app", "--host", "0.0.0.0", "--port", "8000"]
