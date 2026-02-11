FROM python:3.12

# ── System dependencies ──────────────────────────────────────────────
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

# ── Python environment ──────────────────────────────────────────────
# Ensure Python output is sent straight to the container logs (no buffering)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip==25.3 wheel==0.45.1 requests==2.32.5

# ── Application setup ────────────────────────────────────────────────
WORKDIR /Upload-Assistant

# Copy DVD MediaInfo download script and run it
# This downloads specialized MediaInfo binaries for DVD processing with language support
COPY bin/get_dvd_mediainfo_docker.py bin/
RUN python3 bin/get_dvd_mediainfo_docker.py

# Copy the Python requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Preserve the built-in data/ directory outside the mount-point so that
# volume mounts over /Upload-Assistant/data/ don't hide critical files
# (__init__.py, version.py, example-config.py, templates/).
# At runtime the app restores any missing files from this copy.
RUN cp -a data /Upload-Assistant/defaults/data

# Download only the required mkbrr binary (requires full repo for src imports)
RUN python3 -c "from bin.get_mkbrr import MkbrrBinaryManager; MkbrrBinaryManager.download_mkbrr_for_docker()"

# Download bdinfo binary for the container architecture using the docker helper
RUN python3 bin/get_bdinfo_docker.py

# Ensure downloaded binaries are executable
RUN find bin/mkbrr -name "mkbrr" -print0 | xargs -0 chmod +x && \
    find bin/bdinfo -name "bdinfo" -print0 | xargs -0 chmod +x

# ── Permissions ──────────────────────────────────────────────────────
# Give UID 1000 ownership (runtime binary updates need chmod) and let
# any other UID (e.g. Unraid 99:100) read/execute.
RUN chown -R 1000:1000 /Upload-Assistant/bin/mkbrr \
    && chown -R 1000:1000 /Upload-Assistant/bin/MI \
    && chown -R 1000:1000 /Upload-Assistant/bin/bdinfo \
    && chmod -R o+rX /Upload-Assistant/bin/mkbrr \
    && chmod -R o+rX /Upload-Assistant/bin/MI \
    && chmod -R o+rX /Upload-Assistant/bin/bdinfo

# Create tmp directory; world-writable so any UID can use it
RUN mkdir -p /Upload-Assistant/tmp && chmod 1777 /Upload-Assistant/tmp
ENV TMPDIR=/Upload-Assistant/tmp

# ── Runtime metadata ─────────────────────────────────────────────────
# Document the WebUI port (informational only; does not publish the port)
EXPOSE 5000

# Let Docker send SIGTERM for graceful shutdown (Python handles it in upload.py)
STOPSIGNAL SIGTERM

# Health check for WebUI mode — ignored when running CLI
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:5000/api/health || exit 1

# ── Entrypoint ───────────────────────────────────────────────────────
# The venv is already on PATH, so "python" resolves to /venv/bin/python.
# Pass arguments via CMD or `docker run ... <args>`.
#   WebUI : docker run ... image --webui 0.0.0.0:5000
#   CLI   : docker run ... image /data/content --trackers BHD
ENTRYPOINT ["python", "/Upload-Assistant/upload.py"]

# Default: show help when no arguments are provided
CMD ["-h"]
