FROM python:3.12

ARG FFMPEG_RELEASE=autobuild-2025-08-31-13-00
ARG FFMPEG_FLAVOR=ffmpeg-n7.1.1-57-g1b48158a23-linux64-gpl-7.1
ARG FFMPEG_URL=https://github.com/BtbN/FFmpeg-Builds/releases/download/${FFMPEG_RELEASE}/${FFMPEG_FLAVOR}.tar.xz
ARG FFMPEG_SHA256=7a4dcf07bc7c89a33970c5c0f524fc1662ea4e2f342c9d10a6a9f307cdc03f6c

# Update the package list and install system dependencies including mono
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    xz-utils \
    git \
    g++ \
    cargo \
    mktorrent \
    mediainfo \
    rustc \
    mono-complete \
    nano && \
    rm -rf /var/lib/apt/lists/*

# Install specific ffmpeg build
RUN curl -L "$FFMPEG_URL" -o /tmp/ffmpeg.tar.xz && \
    echo "${FFMPEG_SHA256}  /tmp/ffmpeg.tar.xz" | sha256sum -c - && \
    tar -xJf /tmp/ffmpeg.tar.xz -C /tmp && \
    cp /tmp/${FFMPEG_FLAVOR}/bin/ffmpeg /usr/local/bin/ && \
    cp /tmp/${FFMPEG_FLAVOR}/bin/ffprobe /usr/local/bin/ && \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    rm -rf /tmp/ffmpeg.tar.xz /tmp/${FFMPEG_FLAVOR}

# Set up a virtual environment to isolate our Python dependencies
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Install wheel, requests (for DVD MediaInfo download), and other Python dependencies
RUN pip install --upgrade pip wheel requests

# Install Web UI dependencies (in venv)
RUN pip install --no-cache-dir flask flask-cors

# Set the working directory FIRST
WORKDIR /Upload-Assistant

# Copy DVD MediaInfo download script and run it
COPY bin/get_dvd_mediainfo_docker.py bin/
RUN python3 bin/get_dvd_mediainfo_docker.py

# Copy the Python requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the download script
COPY bin/download_mkbrr_for_docker.py bin/
RUN chmod +x bin/download_mkbrr_for_docker.py

# Download only the required mkbrr binary
RUN python3 bin/download_mkbrr_for_docker.py

# Copy the rest of the application (including web_ui)
COPY . .

# Ensure mkbrr is executable
RUN find bin/mkbrr -type f -name "mkbrr" -exec chmod +x {} \;

# Create tmp directory with appropriate permissions
RUN mkdir -p /Upload-Assistant/tmp && chmod 777 /Upload-Assistant/tmp
ENV TMPDIR=/Upload-Assistant/tmp

# Add environment variable to enable/disable Web UI
ENV ENABLE_WEB_UI=false

# Make entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Set the entry point for the container
ENTRYPOINT ["/Upload-Assistant/docker-entrypoint.sh"]
CMD ["python", "upload.py"]
