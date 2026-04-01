FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

LABEL maintainer="ASF Mission Data Team"

WORKDIR /app

# Keep Python output visible in ECS logs and avoid .pyc clutter
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/usr/local \
    UV_NO_DEV=1

# Minimal OS setup plus non-root user
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --create-home --home-dir /home/app app

COPY pyproject.toml uv.lock README.md ./
COPY asf_mission_data ./asf_mission_data
COPY pipelines.yaml ./pipelines.yaml

RUN uv sync --locked

USER app

ENTRYPOINT ["python", "-m", "asf_mission_data.run"]
CMD ["--help"]
