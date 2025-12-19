#!/usr/bin/env python3
# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import platform
import requests
import shutil
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from src.console import console

MEDIAINFO_VERSION = "23.04"
MEDIAINFO_CLI_BASE_URL = "https://mediaarea.net/download/binary/mediainfo"
MEDIAINFO_LIB_BASE_URL = "https://mediaarea.net/download/binary/libmediainfo0"


def get_filename(system: str, arch: str, library_type: str = "cli") -> str:
    if system == "linux":
        if library_type == "cli":
            # MediaInfo CLI uses Lambda (pre-compiled) version
            return f"MediaInfo_CLI_{MEDIAINFO_VERSION}_Lambda_{arch}.zip"
        elif library_type == "lib":
            # MediaInfo library uses DLL version
            return f"MediaInfo_DLL_{MEDIAINFO_VERSION}_Lambda_{arch}.zip"
        else:
            raise ValueError(f"Unknown library_type: {library_type}")
    else:
        return


def get_url(system: str, arch: str, library_type: str = "cli") -> str:
    filename = get_filename(system, arch, library_type)
    if library_type == "cli":
        return f"{MEDIAINFO_CLI_BASE_URL}/{MEDIAINFO_VERSION}/{filename}"
    elif library_type == "lib":
        return f"{MEDIAINFO_LIB_BASE_URL}/{MEDIAINFO_VERSION}/{filename}"
    else:
        raise ValueError(f"Unknown library_type: {library_type}")


def download_file(url: str, output_path: Path) -> None:
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def extract_linux(cli_archive: Path, lib_archive: Path, output_dir: Path) -> None:
    # Extract MediaInfo CLI from zip file
    with zipfile.ZipFile(cli_archive, 'r') as zip_ref:
        file_list = zip_ref.namelist()
        mediainfo_file = output_dir / "mediainfo"

        # Look for the mediainfo binary in the archive
        for member in file_list:
            if member.endswith('/mediainfo') or member == 'mediainfo':
                zip_ref.extract(member, output_dir.parent)
                extracted_path = output_dir.parent / member
                shutil.move(str(extracted_path), str(mediainfo_file))
                break

    # Extract MediaInfo library
    with zipfile.ZipFile(lib_archive, 'r') as zip_ref:
        file_list = zip_ref.namelist()
        lib_file = output_dir / "libmediainfo.so.0"

        # Look for the library file in the archive
        if "lib/libmediainfo.so.0.0.0" in file_list:
            zip_ref.extract("lib/libmediainfo.so.0.0.0", output_dir.parent)
            extracted_path = output_dir.parent / "lib/libmediainfo.so.0.0.0"
            shutil.move(str(extracted_path), str(lib_file))

    # Clean up empty lib directory if it exists
    lib_dir = output_dir.parent / "lib"
    if lib_dir.exists() and not any(lib_dir.iterdir()):
        lib_dir.rmdir()


def download_dvd_mediainfo(base_dir, debug=False):
    system = platform.system().lower()
    machine = platform.machine().lower()

    if debug:
        console.print(f"[blue]System: {system}, arch: {machine}[/blue]")

    if system not in ["linux"]:
        return

    if system == "linux" and machine not in ["x86_64", "arm64"]:
        return

    if machine == "amd64":
        machine = "x86_64"

    platform_dir = "linux"
    output_dir = Path(base_dir) / "bin" / "MI" / platform_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if debug:
        console.print(f"[blue]Output: {output_dir}[/blue]")

    cli_file = output_dir / "mediainfo"
    lib_file = output_dir / "libmediainfo.so.0"
    version_file = output_dir / f"version_{MEDIAINFO_VERSION}"

    if cli_file.exists() and lib_file.exists() and version_file.exists():
        if debug:
            console.print(f"[blue]MediaInfo CLI and Library {MEDIAINFO_VERSION} exist[/blue]")
        return str(cli_file)
    console.print(f"[yellow]Downloading specific MediaInfo CLI and Library for DVD processing: {MEDIAINFO_VERSION}...[/yellow]")
    # Download MediaInfo CLI
    cli_url = get_url(system, machine, "cli")
    cli_filename = get_filename(system, machine, "cli")

    # Download MediaInfo Library
    lib_url = get_url(system, machine, "lib")
    lib_filename = get_filename(system, machine, "lib")

    if debug:
        console.print(f"[blue]MediaInfo CLI URL: {cli_url}[/blue]")
        console.print(f"[blue]MediaInfo CLI filename: {cli_filename}[/blue]")
        console.print(f"[blue]MediaInfo Library URL: {lib_url}[/blue]")
        console.print(f"[blue]MediaInfo Library filename: {lib_filename}[/blue]")

    with TemporaryDirectory() as tmp_dir:
        cli_archive = Path(tmp_dir) / cli_filename
        lib_archive = Path(tmp_dir) / lib_filename

        # Download both archives
        download_file(cli_url, cli_archive)
        if debug:
            console.print(f"[green]Downloaded {cli_filename}[/green]")

        download_file(lib_url, lib_archive)
        if debug:
            console.print(f"[green]Downloaded {lib_filename}[/green]")

        extract_linux(cli_archive, lib_archive, output_dir)

        if debug:
            console.print("[green]Extracted library[/green]")

        with open(version_file, 'w') as f:
            f.write(f"MediaInfo {MEDIAINFO_VERSION}")

        # Make CLI binary executable
        if cli_file.exists():
            os.chmod(cli_file, 0o755)

    if not cli_file.exists():
        raise Exception(f"Failed to extract CLI binary to {cli_file}")
    if not lib_file.exists():
        raise Exception(f"Failed to extract library to {lib_file}")

    return str(cli_file)
