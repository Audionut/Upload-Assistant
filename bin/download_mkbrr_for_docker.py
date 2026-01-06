#!/usr/bin/env python3
# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import platform
import requests
import tarfile
import os
import sys
from pathlib import Path


def download_mkbrr_for_docker(base_dir=".", version="v1.18.0"):
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

        with tarfile.open(temp_archive, 'r:gz') as tar_ref:
            def secure_extract(tar, extract_path="."):
                """Securely extract tar members with comprehensive security checks"""
                base_path = Path(extract_path).resolve()

                for member in tar.getmembers():
                    # Skip symbolic links and hard links entirely for security
                    if member.issym():
                        print(f"Warning: Skipping symbolic link: {member.name}")
                        continue
                    if member.islnk():
                        print(f"Warning: Skipping hard link: {member.name}")
                        continue

                    # Reject absolute paths
                    if os.path.isabs(member.name):
                        print(f"Warning: Skipping absolute path: {member.name}")
                        continue

                    # Reject paths with directory traversal patterns
                    if ".." in member.name.split(os.sep):
                        print(f"Warning: Skipping path with '..': {member.name}")
                        continue

                    # Compute and validate final extraction path
                    try:
                        final_path = (base_path / member.name).resolve()

                        # Ensure final path is within base directory
                        try:
                            os.path.commonpath([base_path, final_path])
                            if not str(final_path).startswith(str(base_path) + os.sep) and final_path != base_path:
                                print(f"Warning: Path outside base directory: {member.name}")
                                continue
                        except ValueError:
                            # Paths are on different drives or commonpath failed
                            print(f"Warning: Invalid path resolution: {member.name}")
                            continue

                    except (OSError, ValueError) as e:
                        print(f"Warning: Path resolution failed for {member.name}: {e}")
                        continue

                    # Only extract regular files and directories
                    if not (member.isfile() or member.isdir()):
                        print(f"Warning: Skipping non-regular file: {member.name}")
                        continue

                    # Check for reasonable file sizes (prevent zip bombs)
                    if member.isfile() and member.size > 100 * 1024 * 1024:  # 100MB limit
                        print(f"Warning: Skipping oversized file: {member.name} ({member.size} bytes)")
                        continue

                    # Secure extraction: create parent directories if needed
                    if member.isfile():
                        final_path.parent.mkdir(parents=True, exist_ok=True)

                        # Extract file without preserving ownership
                        with tar.extractfile(member) as source:
                            with open(final_path, 'wb') as target:
                                if source:
                                    target.write(source.read())

                        # Set secure permissions (no owner/group from archive)
                        final_path.chmod(0o600)  # rw------- for files

                    elif member.isdir():
                        # Create directory with secure permissions
                        final_path.mkdir(parents=True, exist_ok=True)
                        final_path.chmod(0o700)  # rwx------ for directories

                    print(f"Extracted: {member.name}")

            secure_extract(tar_ref, str(bin_dir))

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
