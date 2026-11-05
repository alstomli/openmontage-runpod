# syntax=docker/dockerfile:1.7
FROM python:3.11.11-slim-bookworm@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5 AS upstream
# Fixed public source archive makes GitHub builds independent of submodule checkout behavior.
ADD --checksum=sha256:27a1a709dfcdf58d98b2918cafe5acb88220cef933b718e2926d23cf7ccd160c https://codeload.github.com/calesthio/OpenMontage/tar.gz/d21f5d4eaa08422b09c7091757a05affcbabb35b /tmp/upstream.tar.gz
RUN python -c "import tarfile; a=tarfile.open('/tmp/upstream.tar.gz'); a.extractall('/src', filter='data')" \
 && mv /src/OpenMontage-d21f5d4eaa08422b09c7091757a05affcbabb35b /src/openmontage
FROM node:22.14.0-bookworm-slim@sha256:1c18d9ab3af4585870b92e4dbc5cac5a0dc77dd13df1a5905cea89fc720eb05b AS node
FROM python:3.11.11-slim-bookworm@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5 AS media-base
ARG UPSTREAM_COMMIT=d21f5d4eaa08422b09c7091757a05affcbabb35b
LABEL org.opencontainers.image.title="OpenMontage Runpod supplied-asset worker" \
      org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.openmontage.upstream.commit=$UPSTREAM_COMMIT
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && apt-get update \
 && apt-get install -y --no-install-recommends chromium ffmpeg fonts-dejavu-core fonts-liberation ca-certificates \
 && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    OPENMONTAGE_ROOT=/opt/openmontage WORK_ROOT=/tmp/openmontage \
    STORAGE_BACKEND=local LOCAL_STORAGE_ROOT=/data/openmontage INPUT_ROOT=/inputs \
    COMPOSER_BROWSER_EXECUTABLE=/usr/bin/chromium REMOTION_CONCURRENCY=1
WORKDIR /opt/openmontage/remotion-composer
COPY --from=upstream /src/openmontage/remotion-composer/package*.json ./
RUN npm ci --no-audit --no-fund
FROM media-base AS runtime
COPY --from=upstream /src/openmontage /opt/openmontage
COPY UPSTREAM.json /opt/upstream.json
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY openmontage_worker ./openmontage_worker
COPY handler.py ./
RUN python -m pip install --no-cache-dir -e . \
 && mkdir -p /data/openmontage /inputs /tmp/openmontage \
 && dpkg-query -W > /opt/system-packages.txt \
 && python -m pip freeze > /opt/python-packages.txt
COPY scripts ./scripts
COPY tests ./tests
CMD ["python", "-u", "scripts/start_worker.py"]
