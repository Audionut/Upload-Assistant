# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import contextlib
import os
import platform
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Union

import httpx

from src.console import console


class FfmpegBinaryManager:
    AMD_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-01-24-12-54/ffmpeg-n8.0.1-48-g0592be14ff-linux64-lgpl-8.0.tar.xz"
    ARM_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-01-24-12-54/ffmpeg-n8.0.1-48-g0592be14ff-linuxarm64-lgpl-8.0.tar.xz"

    @staticmethod
    def download_ffmpeg_for_docker(base_dir: Union[str, Path] = ".") -> str:
        """Download ffmpeg amd and arm builds and install into bin/ffmpeg/<arch>/ffmpeg.

        This is a synchronous helper intended for use in Dockerfile build steps.
        """
        # Use platform.system() for a well-typed string
        system = platform.system().lower()
        console.print(f"[blue]Detected system: {system}[/blue]")

        if 'linux' not in system:
            raise Exception(f"This script is for Docker/Linux only, detected: {system}")

        base = Path(base_dir)
        ff_root = base / 'bin' / 'ffmpeg'
        ff_root.mkdir(parents=True, exist_ok=True)

        results: dict[str, bool] = {}

        for arch, url in (('amd', FfmpegBinaryManager.AMD_URL), ('arm', FfmpegBinaryManager.ARM_URL)):
            try:
                arch_dir = ff_root / arch
                arch_dir.mkdir(parents=True, exist_ok=True)
                console.print(f"[blue]Downloading ffmpeg for arch {arch} from {url}[/blue]")

                temp_archive = arch_dir / f"ffmpeg_{arch}.tar.xz"
                with httpx.Client(timeout=60.0, follow_redirects=True) as client, client.stream('GET', url, timeout=60.0) as response:
                    response.raise_for_status()
                    with open(temp_archive, 'wb') as f:
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)

                console.print(f"[green]Downloaded {temp_archive.name}[/green]")

                # Extract into a temporary directory to avoid polluting target
                with tempfile.TemporaryDirectory(dir=str(arch_dir)) as extract_dir:
                    try:
                        with tarfile.open(temp_archive, 'r:xz') as tar_ref:
                            # Secure extract: only extract regular files and dirs
                            members = [m for m in tar_ref.getmembers() if (m.isreg() or m.isdir())]
                            for member in members:
                                # Prevent absolute paths and traversal
                                if os.path.isabs(member.name) or '..' in Path(member.name).parts:
                                    console.print(f"[yellow]Skipping unsafe member: {member.name}[/yellow]")
                                    continue
                                tar_ref.extract(member, path=extract_dir)

                        # Search for the ffmpeg binary in the extracted tree
                        found = None
                        for root, _dirs, files in os.walk(extract_dir):
                            for fname in files:
                                if fname == 'ffmpeg':
                                    found = os.path.join(root, fname)
                                    break
                            if found:
                                break

                        if not found:
                            console.print(f"[red]ffmpeg binary not found inside archive for {arch}[/red]")
                            results[arch] = False
                        else:
                            target_path = arch_dir / 'ffmpeg'
                            shutil.move(found, target_path)
                            # Ensure executable
                            target_path.chmod(target_path.stat().st_mode | 0o111)
                            console.print(f"[green]Installed ffmpeg for {arch} at: {target_path}[/green]")
                            results[arch] = True

                    except tarfile.TarError as e:
                        console.print(f"[red]Failed to extract archive for {arch}: {e}[/red]")
                        results[arch] = False

                # Clean up archive file
                with contextlib.suppress(Exception):
                    temp_archive.unlink()

            except httpx.RequestError as e:
                console.print(f"[red]Failed to download ffmpeg for {arch}: {e}[/red]")
                results[arch] = False

        # Summarize
        for a, ok in results.items():
            if ok:
                console.print(f"[green]ffmpeg {a} ready[/green]")
            else:
                console.print(f"[yellow]ffmpeg {a} missing or failed to install[/yellow]")

        return str(ff_root)


if __name__ == '__main__':
    print(FfmpegBinaryManager.download_ffmpeg_for_docker())
