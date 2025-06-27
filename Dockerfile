FROM python:3.12

# Update the package list and install system dependencies including mono
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    mediainfo=23.04-1 \
    git \
    g++ \
    cargo \
    mktorrent \
    rustc \
    mono-complete \
    nano && \
    rm -rf /var/lib/apt/lists/*

# Set up a virtual environment to isolate our Python dependencies
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Install wheel and other Python dependencies
RUN pip install --upgrade pip wheel

# Set the working directory in the container
WORKDIR /Upload-Assistant

# Copy the Python requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the application's code
COPY . .

# Detect architecture and keep only the relevant binary
RUN arch=$(uname -m) && \
    if [ "$arch" = "x86_64" ]; then \
      echo "Detected amd64 architecture" && \
      mkdir -p /tmp/mkbrr-save && \
      cp -a bin/mkbrr/linux/amd64 /tmp/mkbrr-save/ && \
      rm -rf bin/mkbrr/* && \
      mkdir -p bin/mkbrr/linux && \
      mv /tmp/mkbrr-save/amd64 bin/mkbrr/linux/ && \
      rm -rf /tmp/mkbrr-save; \
    elif [ "$arch" = "aarch64" ]; then \
      echo "Detected arm64 architecture" && \
      mkdir -p /tmp/mkbrr-save && \
      cp -a bin/mkbrr/linux/arm64 /tmp/mkbrr-save/ && \
      rm -rf bin/mkbrr/* && \
      mkdir -p bin/mkbrr/linux && \
      mv /tmp/mkbrr-save/arm64 bin/mkbrr/linux/ && \
      rm -rf /tmp/mkbrr-save; \
    else \
      echo "Warning: Unrecognized architecture $arch, keeping all binaries"; \
    fi && \
    find bin/mkbrr -type f -name "mkbrr" -exec chmod +x {} \;

# Create tmp directory with appropriate permissions
RUN mkdir -p /Upload-Assistant/tmp && chmod 777 /Upload-Assistant/tmp
ENV TMPDIR=/Upload-Assistant/tmp

# Set the entry point for the container
ENTRYPOINT ["python", "/Upload-Assistant/upload.py"]