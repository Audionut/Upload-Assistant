#!/usr/bin/env python3
# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import platform
import shutil
import stat
import tarfile
import zipfile
from pathlib import Path
from typing import Union

import aiofiles
import httpx

try:
    from src.console import console
except ImportError:
    class SimpleConsole:
        def print(self, message: str, markup: bool = False) -> None:  # noqa: ARG002
            print(message)

    console = SimpleConsole()


class BDInfoBinaryManager:
    """Download BDInfoCLI-ng binaries for the host architecture.

    Default version pinned to v1.0.1 (see https://github.com/Audionut/BDInfoCLI-ng/releases/tag/v1.0.1)
    """

    @staticmethod
    async def ensure_bdinfo_binary(base_dir: Union[str, Path], debug: bool, version: str = "v1.0.1") -> str:
        system = platform.system().lower()
        machine = platform.machine().lower()
        if debug:
            console.print(f"[blue]Detected system: {system}, architecture: {machine}[/blue]")

        platform_map: dict[str, dict[str, dict[str, str]]] = {
            "windows": {
                "x86_64": {"file": "bdinfo-win-x64.zip", "folder": "windows/x86_64"},
                "amd64": {"file": "bdinfo-win-x64.zip", "folder": "windows/x86_64"},
            },
            "darwin": {
                "arm64": {"file": "bdinfo-osx-arm64.tar.gz", "folder": "macos/arm64"},
                "x86_64": {"file": "bdinfo-osx-x64.tar.gz", "folder": "macos/x86_64"},
                "amd64": {"file": "bdinfo-osx-x64.tar.gz", "folder": "macos/x86_64"},
            },
            "linux": {
                "x86_64": {"file": "bdinfo-linux-x64.tar.gz", "folder": "linux/amd64"},
                "amd64": {"file": "bdinfo-linux-x64.tar.gz", "folder": "linux/amd64"},
                "arm64": {"file": "bdinfo-linux-arm64.tar.gz", "folder": "linux/arm64"},
                "aarch64": {"file": "bdinfo-linux-arm64.tar.gz", "folder": "linux/arm64"},
                "armv7l": {"file": "bdinfo-linux-arm.tar.gz", "folder": "linux/arm"},
                "armv6l": {"file": "bdinfo-linux-arm.tar.gz", "folder": "linux/armv6"},
                "arm": {"file": "bdinfo-linux-arm.tar.gz", "folder": "linux/arm"},
            },
        }

        if system not in platform_map or machine not in platform_map[system]:
            raise Exception(f"Unsupported platform: {system} {machine}")

        platform_info = platform_map[system][machine]
        file_pattern = platform_info["file"]
        folder_path = platform_info["folder"]
        if debug:
            console.print(f"[blue]Using file pattern: {file_pattern}[/blue]")
            console.print(f"[blue]Target folder: {folder_path}[/blue]")

        bin_dir = Path(base_dir) / "bin" / "bdinfo" / folder_path
        bin_dir.mkdir(parents=True, exist_ok=True)
        if debug:
            console.print(f"[blue]Binary directory: {bin_dir}[/blue]")

        binary_name = "bdinfo.exe" if system == "windows" else "bdinfo"
        binary_path = bin_dir / binary_name
        if debug:
            console.print(f"[blue]Binary path: {binary_path}[/blue]")

        version_path = bin_dir / version
        binary_exists = binary_path.exists() and binary_path.is_file()
        binary_executable = system == "windows" or os.access(binary_path, os.X_OK)
        binary_valid = binary_exists and binary_executable
        if version_path.exists() and version_path.is_file() and binary_valid:
            if debug:
                console.print("[blue]bdinfo version is up to date[/blue]")
            return str(binary_path)

        # Remove any old binary/version markers
        if binary_path.exists() and binary_path.is_file():
            if system != "windows":
                os.chmod(binary_path, 0o600)
            os.remove(binary_path)
            if debug:
                console.print(f"[blue]Removed existing binary at: {binary_path}[/blue]")

        if version_path.exists():
            if system != "windows":
                os.chmod(version_path, 0o644)
            os.remove(version_path)
            if debug:
                console.print(f"[blue]Removed existing version file at: {version_path}[/blue]")

        # Construct download URL using release asset filename observed in v1.0.1
        download_url = f"https://github.com/Audionut/BDInfoCLI-ng/releases/download/{version}/{file_pattern}"
        if debug:
            console.print(f"[blue]Download URL: {download_url}[/blue]")

        try:
            async with (
                httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client,
                client.stream("GET", download_url, timeout=60.0) as response,
            ):
                response.raise_for_status()
                temp_archive = bin_dir / f"temp_{file_pattern}"
                async with aiofiles.open(temp_archive, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        await f.write(chunk)
            if debug:
                console.print(f"[green]Downloaded {file_pattern}[/green]")

            # Extract archive safely
            if file_pattern.endswith(".zip"):
                with zipfile.ZipFile(temp_archive, "r") as zip_ref:
                    def safe_extract_zip(zip_file: zipfile.ZipFile, path: str = ".") -> None:
                        for member in zip_file.namelist():
                            info = zip_file.getinfo(member)
                            perm = info.external_attr >> 16
                            if stat.S_ISLNK(perm):
                                if debug:
                                    console.print(f"[yellow]Warning: Skipping symlink: {member}[/yellow]")
                                continue
                            if os.path.isabs(member) or ".." in member or member.startswith("/"):
                                if debug:
                                    console.print(f"[yellow]Warning: Skipping dangerous path: {member}[/yellow]")
                                continue
                            full_path = os.path.realpath(os.path.join(path, member))
                            base_path = os.path.realpath(path)
                            if not full_path.startswith(base_path + os.sep) and full_path != base_path:
                                if debug:
                                    console.print(f"[yellow]Warning: Skipping path outside target directory: {member}[/yellow]")
                                continue
                            zip_file.extract(member, path)
                            if debug:
                                console.print(f"[cyan]Extracted: {member}[/cyan]")

                    safe_extract_zip(zip_ref, str(bin_dir))

            elif file_pattern.endswith(".tar.gz"):
                with tarfile.open(temp_archive, "r:gz") as tar_ref:
                    def safe_extract_tar(tar_file: tarfile.TarFile, path: str = ".") -> None:
                        for member in tar_file.getmembers():
                            if member.islnk() or member.issym():
                                if debug:
                                    console.print(f"[yellow]Warning: Skipping link entry: {member.name}[/yellow]")
                                continue
                            if os.path.isabs(member.name) or ".." in member.name or member.name.startswith("/"):
                                if debug:
                                    console.print(f"[yellow]Warning: Skipping dangerous path: {member.name}[/yellow]")
                                continue
                            full_path = os.path.realpath(os.path.join(path, member.name))
                            base_path = os.path.realpath(path)
                            if not full_path.startswith(base_path + os.sep) and full_path != base_path:
                                if debug:
                                    console.print(f"[yellow]Warning: Skipping path outside target directory: {member.name}[/yellow]")
                                continue
                            if member.size > 100 * 1024 * 1024:
                                if debug:
                                    console.print(f"[yellow]Warning: Skipping oversized file: {member.name} ({member.size} bytes)[/yellow]")
                                continue
                            tar_file.extract(member, path)
                            if debug:
                                console.print(f"[cyan]Extracted: {member.name}[/cyan]")

                    safe_extract_tar(tar_ref, str(bin_dir))

            temp_archive.unlink()

            # If extraction created a nested directory (common for GitHub release zips),
            # search for the bdinfo executable and move it to the expected binary path.
            if not binary_path.exists():
                binary_basename = binary_name
                found = None
                for p in bin_dir.rglob(binary_basename):
                    if p.is_file():
                        found = p
                        break

                if found:
                    # Move to target location
                    shutil.move(str(found), str(binary_path))
                else:
                    raise Exception(f"Failed to extract bdinfo binary to {binary_path}")

            if system != "windows" and binary_path.exists():
                binary_path.chmod(binary_path.stat().st_mode | stat.S_IEXEC)

            async with aiofiles.open(version_path, "w", encoding="utf-8") as version_file:
                await version_file.write(f"BDInfoCLI-ng version {version} installed successfully.")
            return str(binary_path)

        except httpx.RequestError as e:
            raise Exception(f"Failed to download bdinfo binary: {e}") from e
        except (zipfile.BadZipFile, tarfile.TarError) as e:
            raise Exception(f"Failed to extract bdinfo binary: {e}") from e

    @staticmethod
    def download_bdinfo_for_docker(base_dir: Union[str, Path] = ".", version: str = "v1.0.1") -> str:
        """Synchronous downloader for Linux/Docker usage."""
        system = platform.system().lower()
        machine = platform.machine().lower()
        console.print(f"Detected system: {system}, architecture: {machine}", markup=False)

        if system != "linux":
            raise Exception(f"This script is for Docker/Linux only, detected: {system}")

        platform_map = {
            "x86_64": {"file": "bdinfo-linux-x64.tar.gz", "folder": "linux/amd64"},
            "amd64": {"file": "bdinfo-linux-x64.tar.gz", "folder": "linux/amd64"},
            "arm64": {"file": "bdinfo-linux-arm64.tar.gz", "folder": "linux/arm64"},
            "aarch64": {"file": "bdinfo-linux-arm64.tar.gz", "folder": "linux/arm64"},
            "armv7l": {"file": "bdinfo-linux-arm.tar.gz", "folder": "linux/arm"},
            "arm": {"file": "bdinfo-linux-arm.tar.gz", "folder": "linux/arm"},
        }

        if machine not in platform_map:
            raise Exception(f"Unsupported architecture: {machine}")

        platform_info = platform_map[machine]
        file_pattern = platform_info["file"]
        folder_path = platform_info["folder"]

        console.print(f"Using file pattern: {file_pattern}", markup=False)
        console.print(f"Target folder: {folder_path}", markup=False)

        bin_dir = Path(base_dir) / "bin" / "bdinfo" / folder_path
        bin_dir.mkdir(parents=True, exist_ok=True)
        binary_path = bin_dir / "bdinfo"
        version_path = bin_dir / version

        binary_exists = binary_path.exists() and binary_path.is_file()
        binary_executable = os.access(binary_path, os.X_OK)
        binary_valid = binary_exists and binary_executable
        if version_path.exists() and version_path.is_file() and binary_valid:
            console.print(f"bdinfo {version} already exists, skipping download", markup=False)
            return str(binary_path)

        if binary_path.exists():
            binary_path.unlink()

        download_url = f"https://github.com/Audionut/BDInfoCLI-ng/releases/download/{version}/{file_pattern}"
        console.print(f"Downloading from: {download_url}", markup=False)

        try:
            with (
                httpx.Client(timeout=60.0, follow_redirects=True) as client,
                client.stream("GET", download_url) as response,
            ):
                response.raise_for_status()
                temp_archive = bin_dir / f"temp_{file_pattern}"
                with open(temp_archive, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

            console.print(f"Downloaded {file_pattern}", markup=False)

            with tarfile.open(temp_archive, "r:gz") as tar_ref:
                def secure_extract(tar: tarfile.TarFile, extract_path: str = ".") -> None:
                    base_path = Path(extract_path).resolve()

                    for member in tar.getmembers():
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

                        if member.isfile():
                            final_path.parent.mkdir(parents=True, exist_ok=True)
                            source = tar.extractfile(member)
                            if source is not None:
                                with source, open(final_path, "wb") as target:
                                    target.write(source.read())
                            final_path.chmod(0o600)
                        elif member.isdir():
                            final_path.mkdir(parents=True, exist_ok=True)
                            final_path.chmod(0o700)

                        console.print(f"Extracted: {member.name}", markup=False)

                secure_extract(tar_ref, str(bin_dir))

            temp_archive.unlink()

            # Handle nested extraction directories: search for the executable and move it
            if not binary_path.exists():
                binary_basename = "bdinfo"
                if system == "windows":
                    binary_basename = "bdinfo.exe"
                found = None
                for p in bin_dir.rglob(binary_basename):
                    if p.is_file():
                        found = p
                        break

                if found:
                    shutil.move(str(found), str(binary_path))

            if binary_path.exists():
                os.chmod(binary_path, 0o700)
                console.print(f"bdinfo binary ready at: {binary_path}", markup=False)

                with open(version_path, "w", encoding="utf-8") as version_file:
                    version_file.write(f"BDInfoCLI-ng version {version} installed successfully.")

                return str(binary_path)

            raise Exception(f"Failed to extract bdinfo binary to {binary_path}")

        except Exception as e:
            raise Exception(f"Error downloading bdinfo: {e}") from e
