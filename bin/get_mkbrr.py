import platform
import requests
import tarfile
import zipfile
import stat
import os
from pathlib import Path
from src.console import console


async def ensure_mkbrr_binary(base_dir, debug, version=None):
    system = platform.system().lower()
    machine = platform.machine().lower()
    if debug:
        console.print(f"[blue]Detected system: {system}, architecture: {machine}[/blue]")

    platform_map = {
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
        }
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
    if version_path.exists() and version_path.is_file():
        if debug:
            console.print("[blue]mkbrr version is up to date[/blue]")
        return str(binary_path)
    else:
        wrong_version = True

    if binary_path.exists() and binary_path.is_file():
        if not system == "windows":
            os.chmod(binary_path, 0o755)
        os.remove(binary_path)
        if debug:
            console.print(f"[blue]Removed existing binary at: {binary_path}[/blue]")

    if wrong_version and version_path.exists():
        if not system == "windows":
            os.chmod(version_path, 0o644)
        os.remove(version_path)
        if debug:
            console.print(f"[blue]Removed existing version file at: {version_path}[/blue]")

    download_url = f"https://github.com/autobrr/mkbrr/releases/download/{version}/mkbrr_{version[1:]}_{file_pattern}"
    if debug:
        console.print(f"[blue]Download URL: {download_url}[/blue]")

    try:
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        temp_archive = bin_dir / f"temp_{file_pattern}"
        with open(temp_archive, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        if debug:
            console.print(f"[green]Downloaded {file_pattern}[/green]")

        if file_pattern.endswith('.zip'):
            with zipfile.ZipFile(temp_archive, 'r') as zip_ref:
                zip_ref.extractall(bin_dir)
        elif file_pattern.endswith('.tar.gz'):
            with tarfile.open(temp_archive, 'r:gz') as tar_ref:
                tar_ref.extractall(bin_dir)

        temp_archive.unlink()

        if system != "windows" and binary_path.exists():
            binary_path.chmod(binary_path.stat().st_mode | stat.S_IEXEC)

        if not binary_path.exists():
            raise Exception(f"Failed to extract mkbrr binary to {binary_path}")

        with open(version_path, 'w') as f:
            f.write(f"mkbrr version {version} installed successfully.")
        return str(binary_path)

    except requests.RequestException as e:
        raise Exception(f"Failed to download mkbrr binary: {e}")
    except (zipfile.BadZipFile, tarfile.TarError) as e:
        raise Exception(f"Failed to extract mkbrr binary: {e}")
