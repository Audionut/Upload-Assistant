#!/usr/bin/env python3
import platform
import requests
import tarfile
import os
import sys
from pathlib import Path


def download_mkbrr_for_docker(base_dir=".", version="v1.14.0"):
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
        response = requests.get(download_url, stream=True, timeout=60)
        response.raise_for_status()

        temp_archive = bin_dir / f"temp_{file_pattern}"
        with open(temp_archive, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"Downloaded {file_pattern}")

        # Safely extract tar file with validation to prevent directory traversal attacks
        with tarfile.open(temp_archive, 'r:gz') as tar_ref:
            def is_safe_path(path, base_path):
                """Check if the extraction path is safe (within base directory)"""
                # Resolve the full path
                full_path = os.path.realpath(os.path.join(base_path, path))
                base_path = os.path.realpath(base_path)
                # Ensure the path is within the base directory
                return full_path.startswith(base_path + os.sep) or full_path == base_path

            def safe_extract(tar, path="."):
                """Safely extract tar members, checking for directory traversal attacks"""
                for member in tar.getmembers():
                    # Check for absolute paths
                    if os.path.isabs(member.name):
                        print(f"Warning: Skipping absolute path: {member.name}")
                        continue

                    # Check for directory traversal patterns
                    if ".." in member.name or member.name.startswith("/"):
                        print(f"Warning: Skipping dangerous path: {member.name}")
                        continue

                    # Check if the final path would be safe
                    if not is_safe_path(member.name, path):
                        print(f"Warning: Skipping path outside target directory: {member.name}")
                        continue

                    # Check for reasonable file sizes (prevent zip bombs)
                    if member.size > 100 * 1024 * 1024:  # 100MB limit
                        print(f"Warning: Skipping oversized file: {member.name} ({member.size} bytes)")
                        continue

                    # Extract the safe member
                    tar.extract(member, path)
                    print(f"Extracted: {member.name}")

            safe_extract(tar_ref, str(bin_dir))

        temp_archive.unlink()

        if binary_path.exists():
            os.chmod(binary_path, 0o700)  # rwx------ (owner only)
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
