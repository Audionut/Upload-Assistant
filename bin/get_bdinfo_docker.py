#!/usr/bin/env python3
# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
"""
Docker-specific script to download bdinfo binaries for Linux containers.
"""
import os
import platform
import shutil
import tarfile
from pathlib import Path

import requests

try:
    from src.console import console
except ImportError:
    class SimpleConsole:
        def print(self, message: str, markup: bool = False) -> None:  # noqa: ARG002
            print(message)

    console = SimpleConsole()


BDINFO_VERSION = "v1.0.7"
BASE_RELEASE_URL = "https://github.com/Audionut/BDInfoCLI-ng/releases/download"


def download_file(url: str, output_path: Path) -> None:
    console.print(f"Downloading: {url}", markup=False)
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    console.print(f"Downloaded: {output_path.name}", markup=False)


def secure_extract_tar(tar_path: Path, extract_to: Path) -> None:
    with tarfile.open(tar_path, "r:gz") as tar_ref:
        base_path = extract_to.resolve()
        for member in tar_ref.getmembers():
            if member.issym() or member.islnk():
                console.print(f"Warning: Skipping link: {member.name}", markup=False)
                continue
            if os.path.isabs(member.name) or ".." in member.name.split(os.sep):
                console.print(f"Warning: Skipping dangerous path: {member.name}", markup=False)
                continue
            try:
                final_path = (base_path / member.name).resolve()
                try:
                    os.path.commonpath([str(base_path), str(final_path)])
                    if not str(final_path).startswith(str(base_path) + os.sep) and final_path != base_path:
                        console.print(f"Warning: Path outside base directory: {member.name}", markup=False)
                        continue
                except ValueError:
                    console.print(f"Warning: Invalid path resolution: {member.name}", markup=False)
                    continue
            except (OSError, ValueError) as e:
                console.print(f"Warning: Path resolution failed for {member.name}: {e}", markup=False)
                continue

            if not (member.isfile() or member.isdir()):
                console.print(f"Warning: Skipping non-regular file: {member.name}", markup=False)
                continue

            if member.isfile() and member.size > 100 * 1024 * 1024:
                console.print(f"Warning: Skipping oversized file: {member.name} ({member.size} bytes)", markup=False)
                continue

            if member.isdir():
                target_dir = base_path / member.name
                target_dir.mkdir(parents=True, exist_ok=True)
                target_dir.chmod(0o700)
            elif member.isfile():
                target_file = base_path / member.name
                target_file.parent.mkdir(parents=True, exist_ok=True)
                source = tar_ref.extractfile(member)
                if source is not None:
                    with source, open(target_file, "wb") as out_f:
                        out_f.write(source.read())
                    target_file.chmod(0o600)


def download_bdinfo_for_docker(base_dir: Path = Path("/Upload-Assistant"), version: str = BDINFO_VERSION) -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    console.print(f"System: {system}, Architecture: {machine}", markup=False)

    if system != "linux":
        raise Exception(f"This script is only for Linux containers, got: {system}")

    if machine in ("amd64", "x86_64"):
        file_pattern = "bdinfo-linux-x64.tar.gz"
        folder = "linux/amd64"
    elif machine in ("arm64", "aarch64"):
        file_pattern = "bdinfo-linux-arm64.tar.gz"
        folder = "linux/arm64"
    elif machine.startswith("arm"):
        file_pattern = "bdinfo-linux-arm.tar.gz"
        folder = "linux/arm"
    else:
        raise Exception(f"Unsupported architecture: {machine}")

    bin_dir = base_dir / "bin" / "bdinfo" / folder
    bin_dir.mkdir(parents=True, exist_ok=True)
    binary_path = bin_dir / "bdinfo"
    version_path = bin_dir / version

    if version_path.exists() and binary_path.exists() and os.access(binary_path, os.X_OK):
        console.print(f"bdinfo {version} already installed", markup=False)
        return str(binary_path)

    download_url = f"{BASE_RELEASE_URL}/{version}/{file_pattern}"
    console.print(f"Downloading bdinfo from: {download_url}", markup=False)

    temp_archive = bin_dir / f"temp_{file_pattern}"
    download_file(download_url, temp_archive)

    console.print(f"Extracting {temp_archive} to {bin_dir}", markup=False)
    secure_extract_tar(temp_archive, bin_dir)
    temp_archive.unlink()

    # Search for extracted bdinfo executable and move it into place if necessary
    if not binary_path.exists():
        found = None
        for p in bin_dir.rglob("bdinfo"):
            if p.is_file():
                found = p
                break
        if found:
            shutil.move(str(found), str(binary_path))

    if not binary_path.exists():
        raise Exception(f"Failed to extract bdinfo binary to {binary_path}")

    os.chmod(binary_path, 0o700)

    with open(version_path, "w", encoding="utf-8") as vf:
        vf.write(f"BDInfoCLI-ng version {version} installed successfully.")

    console.print(f"Installed bdinfo: {binary_path}", markup=False)
    return str(binary_path)


if __name__ == "__main__":
    try:
        download_bdinfo_for_docker()
        console.print("bdinfo installation completed successfully!", markup=False)
    except Exception as exc:
        console.print(f"ERROR: Failed to install bdinfo: {exc}", markup=False)
        raise SystemExit(1) from exc
