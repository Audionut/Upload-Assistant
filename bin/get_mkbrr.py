# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import platform
import stat
import tarfile
import zipfile
from pathlib import Path
from typing import Union

import aiofiles
import httpx

from src.console import console


class MkbrrBinaryManager:
    @staticmethod
    async def ensure_mkbrr_binary(base_dir: Union[str, Path], debug: bool, version: str) -> str:
        system = platform.system().lower()
        machine = platform.machine().lower()
        if debug:
            console.print(f"[blue]Detected system: {system}, architecture: {machine}[/blue]")

        platform_map: dict[str, dict[str, dict[str, str]]] = {
            'windows': {
                'x86_64': {'file': 'windows_x86_64.zip', 'folder': 'windows/x86_64'},
                'amd64': {'file': 'windows_x86_64.zip', 'folder': 'windows/x86_64'},
            },
            'darwin': {
                'arm64': {'file': 'darwin_arm64.tar.gz', 'folder': 'macos/arm64'},
                'x86_64': {'file': 'darwin_x86_64.tar.gz', 'folder': 'macos/x86_64'},
                'amd64': {'file': 'darwin_x86_64.tar.gz', 'folder': 'macos/x86_64'},
            },
            'linux': {
                'x86_64': {'file': 'linux_x86_64.tar.gz', 'folder': 'linux/amd64'},
                'amd64': {'file': 'linux_x86_64.tar.gz', 'folder': 'linux/amd64'},
                'arm64': {'file': 'linux_arm64.tar.gz', 'folder': 'linux/arm64'},
                'aarch64': {'file': 'linux_arm64.tar.gz', 'folder': 'linux/arm64'},
                'armv7l': {'file': 'linux_arm.tar.gz', 'folder': 'linux/arm'},
                'armv6l': {'file': 'linux_arm.tar.gz', 'folder': 'linux/armv6'},
                'arm': {'file': 'linux_arm.tar.gz', 'folder': 'linux/arm'},
            },
            'freebsd': {
                'x86_64': {'file': 'freebsd_x86_64.tar.gz', 'folder': 'freebsd/x86_64'},
                'amd64': {'file': 'freebsd_x86_64.tar.gz', 'folder': 'freebsd/x86_64'},
            },
        }

        if system not in platform_map or machine not in platform_map[system]:
            raise Exception(f"Unsupported platform: {system} {machine}")

        platform_info = platform_map[system][machine]
        file_pattern = platform_info['file']
        folder_path = platform_info['folder']
        if debug:
            console.print(f"[blue]Using file pattern: {file_pattern}[/blue]")
            console.print(f"[blue]Target folder: {folder_path}[/blue]")

        bin_dir = Path(base_dir) / "bin" / "mkbrr" / folder_path
        bin_dir.mkdir(parents=True, exist_ok=True)
        if debug:
            console.print(f"[blue]Binary directory: {bin_dir}[/blue]")

        binary_name = "mkbrr.exe" if system == "windows" else "mkbrr"
        binary_path = bin_dir / binary_name
        if debug:
            console.print(f"[blue]Binary path: {binary_path}[/blue]")

        wrong_version = False
        version_path = bin_dir / version
        binary_exists = binary_path.exists() and binary_path.is_file()
        binary_executable = system == "windows" or os.access(binary_path, os.X_OK)
        binary_valid = binary_exists and binary_executable
        if version_path.exists() and version_path.is_file() and binary_valid:
            if debug:
                console.print("[blue]mkbrr version is up to date[/blue]")
            return str(binary_path)
        else:
            wrong_version = True

        if binary_path.exists() and binary_path.is_file():
            if system != "windows":
                # Set secure permissions before removal
                os.chmod(binary_path, 0o600)
            os.remove(binary_path)
            if debug:
                console.print(f"[blue]Removed existing binary at: {binary_path}[/blue]")

        if wrong_version and version_path.exists():
            if system != "windows":
                os.chmod(version_path, 0o644)
            os.remove(version_path)
            if debug:
                console.print(f"[blue]Removed existing version file at: {version_path}[/blue]")

        download_url = f"https://github.com/autobrr/mkbrr/releases/download/{version}/mkbrr_{version[1:]}_{file_pattern}"
        if debug:
            console.print(f"[blue]Download URL: {download_url}[/blue]")

        try:
            async with (
                httpx.AsyncClient(timeout=60.0) as client,
                client.stream("GET", download_url, timeout=60.0) as response,
            ):
                response.raise_for_status()
                temp_archive = bin_dir / f"temp_{file_pattern}"
                async with aiofiles.open(temp_archive, 'wb') as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        await f.write(chunk)
            if debug:
                console.print(f"[green]Downloaded {file_pattern}[/green]")

            if file_pattern.endswith('.zip'):
                with zipfile.ZipFile(temp_archive, 'r') as zip_ref:
                    # Safely extract zip file with validation to prevent directory traversal attacks
                    def safe_extract_zip(zip_file: zipfile.ZipFile, path: str = ".") -> None:
                        """Safely extract zip members, checking for directory traversal attacks"""
                        for member in zip_file.namelist():
                            # Check for symlinks in ZIP files
                            info = zip_file.getinfo(member)
                            perm = info.external_attr >> 16
                            if stat.S_ISLNK(perm):
                                if debug:
                                    console.print(f"[yellow]Warning: Skipping symlink: {member}[/yellow]")
                                continue

                            # Check for absolute paths
                            if os.path.isabs(member):
                                if debug:
                                    console.print(f"[yellow]Warning: Skipping absolute path: {member}[/yellow]")
                                continue

                            # Check for directory traversal patterns
                            if ".." in member or member.startswith("/"):
                                if debug:
                                    console.print(f"[yellow]Warning: Skipping dangerous path: {member}[/yellow]")
                                continue

                            # Check if the final path would be safe
                            full_path = os.path.realpath(os.path.join(path, member))
                            base_path = os.path.realpath(path)
                            if not full_path.startswith(base_path + os.sep) and full_path != base_path:
                                if debug:
                                    console.print(
                                        f"[yellow]Warning: Skipping path outside target directory: {member}[/yellow]"
                                    )
                                continue

                            # Extract the safe member
                            zip_file.extract(member, path)
                            if debug:
                                console.print(f"[cyan]Extracted: {member}[/cyan]")

                    safe_extract_zip(zip_ref, str(bin_dir))

            elif file_pattern.endswith('.tar.gz'):
                with tarfile.open(temp_archive, 'r:gz') as tar_ref:
                    # Safely extract tar file with validation to prevent directory traversal attacks
                    def safe_extract_tar(tar_file: tarfile.TarFile, path: str = ".") -> None:
                        """Safely extract tar members, checking for directory traversal attacks"""
                        for member in tar_file.getmembers():
                            # Check for symlinks and hardlinks in TAR files
                            if member.islnk() or member.issym():
                                if debug:
                                    console.print(f"[yellow]Warning: Skipping link entry: {member.name}[/yellow]")
                                continue

                            # Check for absolute paths
                            if os.path.isabs(member.name):
                                if debug:
                                    console.print(f"[yellow]Warning: Skipping absolute path: {member.name}[/yellow]")
                                continue

                            # Check for directory traversal patterns
                            if ".." in member.name or member.name.startswith("/"):
                                if debug:
                                    console.print(f"[yellow]Warning: Skipping dangerous path: {member.name}[/yellow]")
                                continue

                            # Check if the final path would be safe
                            full_path = os.path.realpath(os.path.join(path, member.name))
                            base_path = os.path.realpath(path)
                            if not full_path.startswith(base_path + os.sep) and full_path != base_path:
                                if debug:
                                    console.print(
                                        f"[yellow]Warning: Skipping path outside target directory: {member.name}[/yellow]"
                                    )
                                continue

                            # Check for reasonable file sizes (prevent tar bombs)
                            if member.size > 100 * 1024 * 1024:  # 100MB limit
                                if debug:
                                    console.print(
                                        f"[yellow]Warning: Skipping oversized file: {member.name} ({member.size} bytes)[/yellow]"
                                    )
                                continue

                            # Extract the safe member
                            tar_file.extract(member, path)
                            if debug:
                                console.print(f"[cyan]Extracted: {member.name}[/cyan]")

                    safe_extract_tar(tar_ref, str(bin_dir))

            temp_archive.unlink()

            if system != "windows" and binary_path.exists():
                binary_path.chmod(binary_path.stat().st_mode | stat.S_IEXEC)

            if not binary_path.exists():
                raise Exception(f"Failed to extract mkbrr binary to {binary_path}")

            async with aiofiles.open(version_path, 'w', encoding='utf-8') as version_file:
                await version_file.write(f"mkbrr version {version} installed successfully.")
            return str(binary_path)

        except httpx.RequestError as e:
            raise Exception(f"Failed to download mkbrr binary: {e}") from e
        except (zipfile.BadZipFile, tarfile.TarError) as e:
            raise Exception(f"Failed to extract mkbrr binary: {e}") from e

    @staticmethod
    def download_mkbrr_for_docker(base_dir: Union[str, Path] = ".", version: str = "v1.18.0") -> str:
        """Download mkbrr binary for Docker/Linux - synchronous version."""
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

        binary_exists = binary_path.exists() and binary_path.is_file()
        binary_executable = os.access(binary_path, os.X_OK)
        binary_valid = binary_exists and binary_executable
        if version_path.exists() and version_path.is_file() and binary_valid:
            print(f"mkbrr {version} already exists, skipping download")
            return str(binary_path)

        if binary_path.exists():
            binary_path.unlink()

        download_url = f"https://github.com/autobrr/mkbrr/releases/download/{version}/mkbrr_{version[1:]}_{file_pattern}"
        print(f"Downloading from: {download_url}")

        try:
            with (
                httpx.Client(timeout=60.0) as client,
                client.stream("GET", download_url) as response,
            ):
                response.raise_for_status()
                temp_archive = bin_dir / f"temp_{file_pattern}"
                with open(temp_archive, 'wb') as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

            print(f"Downloaded {file_pattern}")

            with tarfile.open(temp_archive, 'r:gz') as tar_ref:
                def secure_extract(tar: tarfile.TarFile, extract_path: str = ".") -> None:
                    """Securely extract tar members with comprehensive security checks."""
                    base_path = Path(extract_path).resolve()

                    for member in tar.getmembers():
                        if member.issym():
                            print(f"Warning: Skipping symbolic link: {member.name}")
                            continue
                        if member.islnk():
                            print(f"Warning: Skipping hard link: {member.name}")
                            continue

                        if os.path.isabs(member.name):
                            print(f"Warning: Skipping absolute path: {member.name}")
                            continue

                        if ".." in member.name.split(os.sep):
                            print(f"Warning: Skipping path with '..': {member.name}")
                            continue

                        try:
                            final_path = (base_path / member.name).resolve()

                            try:
                                os.path.commonpath([base_path, final_path])
                                if not str(final_path).startswith(str(base_path) + os.sep) and final_path != base_path:
                                    print(f"Warning: Path outside base directory: {member.name}")
                                    continue
                            except ValueError:
                                print(f"Warning: Invalid path resolution: {member.name}")
                                continue

                        except (OSError, ValueError) as e:
                            print(f"Warning: Path resolution failed for {member.name}: {e}")
                            continue

                        if not (member.isfile() or member.isdir()):
                            print(f"Warning: Skipping non-regular file: {member.name}")
                            continue

                        if member.isfile() and member.size > 100 * 1024 * 1024:  # 100MB limit
                            print(f"Warning: Skipping oversized file: {member.name} ({member.size} bytes)")
                            continue

                        if member.isfile():
                            final_path.parent.mkdir(parents=True, exist_ok=True)

                            source = tar.extractfile(member)
                            if source is not None:
                                with source, open(final_path, 'wb') as target:
                                    target.write(source.read())

                            final_path.chmod(0o600)

                        elif member.isdir():
                            final_path.mkdir(parents=True, exist_ok=True)
                            final_path.chmod(0o700)

                        print(f"Extracted: {member.name}")

                secure_extract(tar_ref, str(bin_dir))

            temp_archive.unlink()

            if binary_path.exists():
                os.chmod(binary_path, 0o700)
                print(f"mkbrr binary ready at: {binary_path}")

                with open(version_path, 'w', encoding='utf-8') as version_file:
                    version_file.write(f"mkbrr version {version} installed successfully.")

                return str(binary_path)

            raise Exception(f"Failed to extract mkbrr binary to {binary_path}")

        except Exception as e:
            raise Exception(f"Error downloading mkbrr: {e}") from e
