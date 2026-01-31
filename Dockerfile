FROM python:3.12

# Update the package list and install system dependencies including mono
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    g++ \
    cargo \
    ffmpeg \
    mediainfo \
    rustc \
    nano \
    ca-certificates \
    curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    update-ca-certificates

# Set up a virtual environment to isolate our Python dependencies
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Install wheel, requests (for DVD MediaInfo download), and other Python dependencies
RUN pip install --upgrade pip==25.3 wheel==0.45.1 requests==2.32.5

# Set the working directory in the container
WORKDIR /Upload-Assistant

# Copy DVD MediaInfo download script and run it
# This downloads specialized MediaInfo binaries for DVD processing with language support
COPY bin/get_dvd_mediainfo_docker.py bin/
RUN python3 bin/get_dvd_mediainfo_docker.py

# Copy the Python requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Download only the required mkbrr binary (requires full repo for src imports)
RUN python3 -c "from bin.get_mkbrr import MkbrrBinaryManager; MkbrrBinaryManager.download_mkbrr_for_docker()"

# Ensure binaries are executable
RUN find bin/mkbrr -name "mkbrr" -print0 | xargs -0 chmod +x

# Download bdinfo binary for the container architecture using the docker helper
RUN python3 bin/get_bdinfo_docker.py

# Ensure bdinfo binaries are executable
RUN find bin/bdinfo -name "bdinfo" -print0 | xargs -0 chmod +x

# Enable non-root access while still letting Upload-Assistant tighten permissions at runtime
RUN chown -R 1000:1000 /Upload-Assistant/bin/mkbrr
RUN chown -R 1000:1000 /Upload-Assistant/bin/MI
RUN chown -R 1000:1000 /Upload-Assistant/bin/bdinfo

# Create tmp directory with appropriate permissions
RUN mkdir -p /Upload-Assistant/tmp && chmod 777 /Upload-Assistant/tmp
ENV TMPDIR=/Upload-Assistant/tmp

# Set the entry point for the container
ENTRYPOINT ["python", "/Upload-Assistant/upload.py"]
