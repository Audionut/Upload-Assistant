FROM python:3.12

# Update the package list and install system dependencies including mono
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    g++ \
    cargo \
    mktorrent \
    mediainfo \
    rustc \
    mono-complete \
    nano \
    ca-certificates \
    curl && \
    # Clean up package cache to reduce image size and attack surface
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    # Update CA certificates for secure connections
    update-ca-certificates

# Set up a virtual environment to isolate our Python dependencies
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Install wheel, requests (for DVD MediaInfo download), and other Python dependencies
RUN pip install --upgrade pip==25.3 wheel==0.45.1 requests==2.32.5

# Install Web UI dependencies (in venv)
RUN pip install --no-cache-dir flask==3.1.2 flask-cors==6.0.2

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
# And enable non-root access while still letting Upload-Assistant tighten mkbrr permissions at runtime
RUN chown -R 1000:1000 /Upload-Assistant/bin/mkbrr

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
