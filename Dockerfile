FROM python:3.12-slim AS base

ENV PIP_VERSION=25.3
ENV REQUESTS_VERSION=2.32.5

ENV DEBIAN_FRONTEND=noninteractive

# Update the package list and install system dependencies including mono
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    ffmpeg \
    mediainfo \
    mktorrent \
    mono-complete \
    nano && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    update-ca-certificates

# Setup venv
FROM base AS builder-venv

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    cargo \
    git \
    g++ \
    rustc

COPY requirements.txt /tmp/requirements.txt

# Python venv setup
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Install requirements
RUN pip install --no-cache-dir --upgrade pip==${PIP_VERSION} && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Finalize app directory in seperate build stage
FROM base AS builder-app

# Copy virtual environment
COPY --from=builder-venv /venv /venv
ENV PATH="/venv/bin:$PATH"

# Install requests (for DVD MediaInfo download)
RUN pip install --upgrade requests==${REQUESTS_VERSION}

WORKDIR /Upload-Assistant

# Copy app into container
COPY . .

# Run DVD MediaInfo download script
RUN python3 bin/get_dvd_mediainfo_docker.py

# Download only the required mkbrr binary (requires full repo for src imports)
RUN python3 -c "from bin.get_mkbrr import MkbrrBinaryManager; MkbrrBinaryManager.download_mkbrr_for_docker()"

# START BUILDING SLIM IMAGE
FROM base

# Copy venv
COPY --from=builder-venv /venv /venv
ENV PATH="/venv/bin:$PATH"

# Copy application
COPY --from=builder-app /Upload-Assistant /Upload-Assistant

# Set workdir
WORKDIR /Upload-Assistant

# Ensure mkbrr is executable
RUN find bin/mkbrr -type f -name "mkbrr" -exec chmod +x {} \;

# Enable non-root access while still letting Upload-Assistant tighten mkbrr permissions at runtime
RUN chown -R 1000:1000 /Upload-Assistant/bin/mkbrr

# Enable non-root access for DVD MediaInfo binary
RUN chown -R 1000:1000 /Upload-Assistant/bin/MI

# Create tmp directory with appropriate permissions
RUN mkdir -p /Upload-Assistant/tmp && chmod 777 /Upload-Assistant/tmp
ENV TMPDIR=/Upload-Assistant/tmp

# Set the entry point for the container
ENTRYPOINT ["python", "/Upload-Assistant/upload.py"]
