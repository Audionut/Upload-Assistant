FROM python:3.12

# Define user and group variables
ARG USERNAME=UploadAssistant
ARG USERGROUP=UploadAssistant
ARG UID=1000
ARG GID=1000

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

# Download and install mediainfo 23.04-1
RUN wget https://mediaarea.net/download/binary/mediainfo/23.04/mediainfo_23.04-1_amd64.Debian_9.0.deb && \
    wget https://mediaarea.net/download/binary/libmediainfo0/23.04/libmediainfo0v5_23.04-1_amd64.Debian_9.0.deb && \
    wget https://mediaarea.net/download/binary/libzen0/0.4.41/libzen0v5_0.4.41-1_amd64.Debian_9.0.deb && \
    apt-get update && \
    apt-get install -y ./libzen0v5_0.4.41-1_amd64.Debian_9.0.deb ./libmediainfo0v5_23.04-1_amd64.Debian_9.0.deb ./mediainfo_23.04-1_amd64.Debian_9.0.deb && \
    rm mediainfo_23.04-1_amd64.Debian_9.0.deb libmediainfo0v5_23.04-1_amd64.Debian_9.0.deb libzen0v5_0.4.41-1_amd64.Debian_9.0.deb

# Create working directory and tmp directory first
RUN mkdir -p /Upload-Assistant/tmp && \
    chmod 755 /Upload-Assistant && \
    chmod 777 /Upload-Assistant/tmp

# Create a custom user with UID 1000 and GID 1000
RUN groupadd -g ${GID} ${USERGROUP} && \
    useradd -m -u ${UID} -g ${USERGROUP} ${USERNAME}

# Set up a virtual environment in user's home directory
RUN python -m venv /home/${USERNAME}/venv && \
    chown -R ${USERNAME}:${USERGROUP} /home/${USERNAME}/venv && \
    chown -R ${USERNAME}:${USERGROUP} /Upload-Assistant

# Switch to the custom user
USER ${USERNAME}

# Set up environment
ENV PATH="/home/${USERNAME}/venv/bin:$PATH"
ENV TMPDIR=/Upload-Assistant/tmp

# Install wheel and other Python dependencies
RUN pip install --upgrade --no-cache-dir pip wheel

# Set the working directory in the container
WORKDIR /Upload-Assistant

# Copy the Python requirements file and install Python dependencies
COPY --chown=${USERNAME}:${USERGROUP} requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the download script
COPY --chown=${USERNAME}:${USERGROUP} bin/download_mkbrr_for_docker.py bin/
RUN chmod +x bin/download_mkbrr_for_docker.py

# Download only the required mkbrr binary
RUN python bin/download_mkbrr_for_docker.py

# Copy the rest of the application
COPY --chown=${USERNAME}:${USERGROUP} . .

# Ensure mkbrr is executable
RUN find bin/mkbrr -type f -name "mkbrr" -exec chmod +x {} \;

# Set the entry point for the container
ENTRYPOINT ["python", "/Upload-Assistant/upload.py"]