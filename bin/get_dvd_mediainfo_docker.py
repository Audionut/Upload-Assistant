#!/usr/bin/env python3
# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
"""
Docker-specific script to download DVD-capable MediaInfo binaries for Linux.
This script downloads specialized MediaInfo CLI and library binaries that
support DVD IFO/VOB file parsing with language information.
"""
import os
import platform
import requests
import shutil
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

MEDIAINFO_VERSION = "23.04"
MEDIAINFO_CLI_BASE_URL = "https://mediaarea.net/download/binary/mediainfo"
MEDIAINFO_LIB_BASE_URL = "https://mediaarea.net/download/binary/libmediainfo0"


def get_filename(system: str, arch: str, library_type: str = "cli") -> str:
    """Get the appropriate filename for MediaInfo download based on system and architecture."""
    if system == "linux":
        if library_type == "cli":
            # MediaInfo CLI uses Lambda (pre-compiled) version for better DVD support
            return f"MediaInfo_CLI_{MEDIAINFO_VERSION}_Lambda_{arch}.zip"
        elif library_type == "lib":
            # MediaInfo library uses DLL version for better compatibility
            return f"MediaInfo_DLL_{MEDIAINFO_VERSION}_Lambda_{arch}.zip"
        else:
            raise ValueError(f"Unknown library_type: {library_type}")
    else:
        raise ValueError(f"Unsupported system: {system}")


def get_url(system: str, arch: str, library_type: str = "cli") -> str:
    """Construct download URL for MediaInfo components."""
    filename = get_filename(system, arch, library_type)
    if library_type == "cli":
        return f"{MEDIAINFO_CLI_BASE_URL}/{MEDIAINFO_VERSION}/{filename}"
    elif library_type == "lib":
        return f"{MEDIAINFO_LIB_BASE_URL}/{MEDIAINFO_VERSION}/{filename}"
    else:
        raise ValueError(f"Unknown library_type: {library_type}")


def download_file(url: str, output_path: Path) -> None:
    """Download a file from URL to specified path."""
    print(f"Downloading: {url}")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"Downloaded: {output_path.name}")


def extract_linux_binaries(cli_archive: Path, lib_archive: Path, output_dir: Path) -> None:
    """Extract MediaInfo CLI and library from downloaded archives."""
    print("Extracting MediaInfo binaries...")

    # Extract MediaInfo CLI from zip file
    with zipfile.ZipFile(cli_archive, 'r') as zip_ref:
        file_list = zip_ref.namelist()
        mediainfo_file = output_dir / "mediainfo"

        print(f"CLI archive contents: {file_list}")

        # Look for the mediainfo binary in the archive
        for member in file_list:
            if member.endswith('/mediainfo') or member == 'mediainfo':
                zip_ref.extract(member, output_dir.parent)
                extracted_path = output_dir.parent / member
                shutil.move(str(extracted_path), str(mediainfo_file))
                print(f"Extracted CLI binary: {mediainfo_file}")
                break
        else:
            raise Exception("MediaInfo CLI binary not found in archive")

    # Extract MediaInfo library
    with zipfile.ZipFile(lib_archive, 'r') as zip_ref:
        file_list = zip_ref.namelist()
        lib_file = output_dir / "libmediainfo.so.0"

        print(f"Library archive contents: {file_list}")

        # Look for the library file in the archive
        lib_candidates = [
            "lib/libmediainfo.so.0.0.0",
            "libmediainfo.so.0.0.0",
            "libmediainfo.so.0",
            "MediaInfo/libmediainfo.so.0.0.0",
            "MediaInfo/lib/libmediainfo.so.0.0.0"
        ]

        for candidate in lib_candidates:
            if candidate in file_list:
                zip_ref.extract(candidate, output_dir.parent)
                extracted_path = output_dir.parent / candidate
                # Move to final location
                shutil.move(str(extracted_path), str(lib_file))
                # Set appropriate permissions for library file (readable by all)
                os.chmod(lib_file, 0o644)
                print(f"Extracted library: {lib_file}")
                break
        else:
            raise Exception("MediaInfo library not found in archive")

    # Clean up empty lib directory if it exists
    lib_dir = output_dir.parent / "lib"
    if lib_dir.exists() and not any(lib_dir.iterdir()):
        lib_dir.rmdir()


def download_dvd_mediainfo_docker():
    """Download DVD-specific MediaInfo binaries for Docker container."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    print(f"System: {system}, Architecture: {machine}")

    if system != "linux":
        raise Exception(f"This script is only for Linux containers, got: {system}")

    # Normalize architecture names
    if machine in ["amd64", "x86_64"]:
        arch = "x86_64"
    elif machine in ["arm64", "aarch64"]:
        arch = "arm64"
    else:
        raise Exception(f"Unsupported architecture: {machine}")

    # Set up output directory in the container
    base_dir = Path("/Upload-Assistant")
    output_dir = base_dir / "bin" / "MI" / "linux"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Installing DVD MediaInfo to: {output_dir}")

    cli_file = output_dir / "mediainfo"
    lib_file = output_dir / "libmediainfo.so.0"
    version_file = output_dir / f"version_{MEDIAINFO_VERSION}"

    # Check if already installed
    if cli_file.exists() and lib_file.exists() and version_file.exists():
        print(f"DVD MediaInfo {MEDIAINFO_VERSION} already installed")
        return str(cli_file)

    print(f"Downloading DVD-specific MediaInfo CLI and Library: {MEDIAINFO_VERSION}")

    # Get download URLs
    cli_url = get_url(system, arch, "cli")
    lib_url = get_url(system, arch, "lib")

    cli_filename = get_filename(system, arch, "cli")
    lib_filename = get_filename(system, arch, "lib")

    print(f"CLI URL: {cli_url}")
    print(f"Library URL: {lib_url}")

    # Download and extract in temporary directory
    with TemporaryDirectory() as tmp_dir:
        cli_archive = Path(tmp_dir) / cli_filename
        lib_archive = Path(tmp_dir) / lib_filename

        # Download both archives
        download_file(cli_url, cli_archive)
        download_file(lib_url, lib_archive)

        # Extract binaries
        extract_linux_binaries(cli_archive, lib_archive, output_dir)

        # Create version marker
        with open(version_file, 'w') as f:
            f.write(f"MediaInfo {MEDIAINFO_VERSION} - DVD Support")

        # Make CLI binary executable and verify permissions
        if cli_file.exists():
            # Set full executable permissions (owner: rwx, group: rx, other: rx)
            os.chmod(cli_file, 0o755)
            # Verify permissions were set correctly
            file_stat = cli_file.stat()
            is_executable = bool(file_stat.st_mode & 0o111)  # Check if any execute bit is set
            if is_executable:
                print(f"✓ Set executable permissions on: {cli_file} (mode: {oct(file_stat.st_mode)})")
            else:
                raise Exception(f"Failed to set executable permissions on: {cli_file}")
        else:
            raise Exception(f"CLI binary not found for permission setting: {cli_file}")

    # Verify installation and permissions
    if not cli_file.exists():
        raise Exception(f"Failed to install CLI binary: {cli_file}")
    if not lib_file.exists():
        raise Exception(f"Failed to install library: {lib_file}")

    # Final executable verification
    cli_stat = cli_file.stat()
    if not (cli_stat.st_mode & 0o111):
        raise Exception(f"CLI binary is not executable: {cli_file}")
    else:
        print(f"✓ CLI binary is executable: {oct(cli_stat.st_mode)}")

    print(f"Successfully installed DVD MediaInfo {MEDIAINFO_VERSION}")
    print(f"CLI: {cli_file}")
    print(f"Library: {lib_file}")

    return str(cli_file)


if __name__ == "__main__":
    try:
        download_dvd_mediainfo_docker()
        print("DVD MediaInfo installation completed successfully!")
    except Exception as e:
        print(f"ERROR: Failed to install DVD MediaInfo: {e}")
        exit(1)
