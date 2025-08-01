#!/usr/bin/env python3
import platform
import requests
import tarfile
import os
import sys
from pathlib import Path


def download_mkbrr_for_docker(base_dir=".", version="v1.8.1"):
    """Download mkbrr binary for Docker - synchronous version"""

    system = platform.system().lower()
    machine = platform.machine().lower()
    print(f"Detected system: {system}, architecture: {machine}")

    if system != "linux":
        raise Exception(f"This script is for Docker/Linux only, detected: {system}")

    platform_map = {
        'x86_64': {'file': 'linux_x86_64.tar.gz', 'folder': 'linux/amd64'},
        'amd64': {'file': 'linux_x86_64.tar.gz', 'folder': 'linux/amd64'},
        'arm64': {'file': 'linux_arm64.tar.gz', 'folder': 'linux/arm64'},
        'aarch64': {'file': 'linux_arm64.tar.gz', 'folder': 'linux/arm64'},
        'armv7l': {'file': 'linux_arm.tar.gz', 'folder': 'linux/arm'},
        'arm': {'file': 'linux_arm.tar.gz', 'folder': 'linux/arm'},
    }

    if machine not in platform_map:
        raise Exception(f"Unsupported architecture: {machine}")

    platform_info = platform_map[machine]
    file_pattern = platform_info['file']
    folder_path = platform_info['folder']

    print(f"Using file pattern: {file_pattern}")
    print(f"Target folder: {folder_path}")

    bin_dir = Path(base_dir) / "bin" / "mkbrr" / folder_path
    bin_dir.mkdir(parents=True, exist_ok=True)
    binary_path = bin_dir / "mkbrr"
    version_path = bin_dir / version

    if version_path.exists():
        print(f"mkbrr {version} already exists, skipping download")
        return str(binary_path)

    if binary_path.exists():
        binary_path.unlink()

    # Download URL
    download_url = f"https://github.com/autobrr/mkbrr/releases/download/{version}/mkbrr_{version[1:]}_{file_pattern}"
    print(f"Downloading from: {download_url}")

    try:
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        temp_archive = bin_dir / f"temp_{file_pattern}"
        with open(temp_archive, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"Downloaded {file_pattern}")

        with tarfile.open(temp_archive, 'r:gz') as tar_ref:
            tar_ref.extractall(bin_dir)

        temp_archive.unlink()

        if binary_path.exists():
            os.chmod(binary_path, 0o755)
            print(f"mkbrr binary ready at: {binary_path}")

            with open(version_path, 'w') as f:
                f.write(f"mkbrr version {version} installed successfully.")

            return str(binary_path)
        else:
            raise Exception(f"Failed to extract mkbrr binary to {binary_path}")

    except Exception as e:
        print(f"Error downloading mkbrr: {e}")
        sys.exit(1)


if __name__ == "__main__":
    download_mkbrr_for_docker()
