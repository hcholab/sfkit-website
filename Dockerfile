# hadolint global ignore=DL3059

# Install dependencies, lint and test
FROM cgr.dev/chainguard/python:latest-dev AS builder

WORKDIR /app

# Install dependencies
COPY requirements*.txt .

RUN pip install --no-cache-dir --user \
      -r requirements.txt \
      -r requirements-dev.txt

# Copy sources
COPY . .

# stop the build if there are Python syntax errors or undefined names
RUN python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
RUN python -m flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

# Test
RUN python -m pytest

# Clean up
RUN pip uninstall -yr requirements-dev.txt


# Copy everything into the minimal runtime image
FROM us.gcr.io/broad-dsp-gcr-public/base/python:distroless

WORKDIR /app

COPY --from=builder /home/nonroot/.local/bin/hypercorn /bin/
COPY --from=builder /home/nonroot/.local/lib /usr/lib/
COPY --from=builder /app/*.py /app/*.toml ./
COPY --from=builder /app/src ./src/

# TODO: Remove for production
COPY --from=cgr.dev/chainguard/curl /usr/bin/curl /bin/
COPY --from=cgr.dev/chainguard/curl \
  /usr/lib/libcurl.so.4 \
  /usr/lib/libnghttp2.so.* \
  /usr/lib/libbrotlidec.so.1 \
  /usr/lib/libbrotlicommon.so.1 /lib/

ARG APP_VERSION=latest
ARG BUILD_VERSION=latest

ENV APP_VERSION=${APP_VERSION} \
    BUILD_VERSION=${BUILD_VERSION}

ENTRYPOINT ["hypercorn", "app:app", "--bind", "0.0.0.0:8080", "--config", "hypercorn_config.toml"]
