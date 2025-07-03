FROM python:3.13

WORKDIR /usr/src/app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY *.py ./

CMD ["uv", "run", "python", "-u", "main.py"]
