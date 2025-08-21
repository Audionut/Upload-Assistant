FROM python:3.12

# No venv required in a docker container
ARG PIP_BREAK_SYSTEM_PACKAGES=1
ARG PIP_ROOT_USER_ACTION=ignore

# Update the package list and install system dependencies including mono
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    g++ \
    cargo \
    mktorrent \
    rustc \
    mono-complete \
    nano && \
    rm -rf /var/lib/apt/lists/*

# Download and install mediainfo 23.04-1 -- must use this version as newer ones break DVD support
RUN wget https://mediaarea.net/download/binary/mediainfo/23.04/mediainfo_23.04-1_amd64.Debian_9.0.deb && \
    wget https://mediaarea.net/download/binary/libmediainfo0/23.04/libmediainfo0v5_23.04-1_amd64.Debian_9.0.deb && \
    wget https://mediaarea.net/download/binary/libzen0/0.4.41/libzen0v5_0.4.41-1_amd64.Debian_9.0.deb && \
    apt-get update && \
    apt-get install -y ./libzen0v5_0.4.41-1_amd64.Debian_9.0.deb ./libmediainfo0v5_23.04-1_amd64.Debian_9.0.deb ./mediainfo_23.04-1_amd64.Debian_9.0.deb && \
    rm mediainfo_23.04-1_amd64.Debian_9.0.deb libmediainfo0v5_23.04-1_amd64.Debian_9.0.deb libzen0v5_0.4.41-1_amd64.Debian_9.0.deb

# Create working directory and tmp directory first
RUN mkdir -p /app/tmp && \
    chmod 755 /app && \
    chmod 777 /app/tmp

ENV TMPDIR=/app/tmp

# Install wheel and other Python dependencies
RUN pip install --upgrade --no-cache-dir pip wheel

# Set the working directory in the container
WORKDIR /app

# Copy the Python requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the download script
COPY bin/download_mkbrr_for_docker.py bin/
RUN chmod +x bin/download_mkbrr_for_docker.py

# Download only the required mkbrr binary
RUN python bin/download_mkbrr_for_docker.py

# Copy the rest of the application
COPY . .

# Ensure mkbrr is executable
RUN find bin/mkbrr -type f -name "mkbrr" -exec chmod +x {} \;

# Don't run as root
USER nobody:nogroup

# Set the entry point for the container
ENTRYPOINT ["python", "/app/upload.py"]