FROM python:3.13-slim

RUN groupadd -r appuser && useradd -r -g appuser -m appuser

WORKDIR /usr/src/app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY *.py ./

RUN chown -R appuser:appuser /usr/src/app

USER appuser

CMD ["uv", "run", "python", "-u", "main.py"]
