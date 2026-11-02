# The estimate site (estimate.sustenaut.eu): the models in estimate/ as marimo
# notebooks exported to WebAssembly. They run in the reader's browser; every
# file a page loads (Pyodide, the wheels, MathJax, icons) is served from here.
# Build from the repo root, after ./fetch-publication.sh has put the pinned
# publication's objects in objects/:
#   podman build --build-arg GIT_COMMIT=$(git rev-parse HEAD) -t estimate-site .
# Nothing runs from this image: .github/workflows/deploy.yml takes /site out of it
# for Cloudflare Pages.

# pub writes publication 0's reading data, which the pages take inputs from.
# Pinned by commit, as in Sustenaut/pub-site's Dockerfile; move both together.
FROM docker.io/library/rust:1-slim AS pub
ARG PUBLET_REV=07157653fcde075722b6bcb084c6213452abfc7d
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/Sustenaut/publet.git /publet \
    && git -C /publet checkout --quiet "${PUBLET_REV}"
WORKDIR /publet
RUN cargo build --release --locked -p publet-cli

FROM docker.io/library/python:3.14-slim AS site
# marimo, numpy and uv at the versions in requirements.lock; build.py refuses a
# marimo other than the one vendor-lock.json is for. marimo's export looks for
# notebook-local modules with ruff, which it runs (pinned) through uv.
COPY requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir $(grep -E '^(marimo|numpy|uv)==' /tmp/requirements.lock)
COPY --from=pub /publet/target/release/pub /usr/local/bin/pub
WORKDIR /repo
COPY estimate estimate
COPY build.py vendor-lock.json headers.json ./
COPY bundle bundle
COPY notebooks notebooks
COPY objects objects
ARG GIT_COMMIT=unknown
# Downloads Pyodide and the wheels and checks each against vendor-lock.json.
RUN python build.py site --out /site --pub /usr/local/bin/pub --commit "${GIT_COMMIT}" --cache /tmp/cache

FROM scratch
COPY --from=site /site /site
USER 65532
