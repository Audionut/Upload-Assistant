# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import contextlib
import fnmatch
import glob
import math
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Mapping, MutableMapping, Sequence
from datetime import datetime, timezone
from typing import Any, Optional, Union

import cli_ui
import torf
from torf import Torrent
from typing_extensions import TypeAlias

from src.console import console

PIECE_SIZE_MIN = 32 * 1024  # 32 KiB
PIECE_SIZE_MAX = 134_217_728  # 128 MiB

Meta: TypeAlias = MutableMapping[str, Any]


def calculate_piece_size(
    total_size: int,
    min_size: int,
    max_size: int,
    meta: Mapping[str, Any],
    piece_size: Optional[int] = None,
) -> int:
    return TorrentCreator.calculate_piece_size(
        total_size=total_size,
        min_size=min_size,
        max_size=max_size,
        meta=meta,
        piece_size=piece_size,
    )


class CustomTorrent(torf.Torrent):
    def __init__(self, meta: Mapping[str, Any], *args: Any, **kwargs: Any) -> None:
        self._meta = meta

        # Extract and store the precalculated piece size
        self._precalculated_piece_size: Optional[int] = kwargs.pop('piece_size', None)
        super().__init__(*args, **kwargs)

        # Set piece size directly
        if self._precalculated_piece_size is not None:
            self._piece_size = self._precalculated_piece_size
            self.metainfo['info']['piece length'] = self._precalculated_piece_size

    @property
    def piece_size_min(self) -> int:
        return PIECE_SIZE_MIN

    @piece_size_min.setter
    def piece_size_min(self, piece_size_min: Optional[int]) -> None:
        _ = piece_size_min
        return None

    @property
    def piece_size_max(self) -> int:
        return PIECE_SIZE_MAX

    @piece_size_max.setter
    def piece_size_max(self, piece_size_max: Optional[int]) -> None:
        _ = piece_size_max
        return None

    @property
    def piece_size(self) -> int:
        return self._piece_size

    @piece_size.setter
    def piece_size(self, value: Optional[int]) -> None:
        if self._precalculated_piece_size is not None:
            value = self._precalculated_piece_size
        if value is None:
            return

        self._piece_size = value
        self.metainfo['info']['piece length'] = value

    def validate_piece_size(self, _meta: Optional[Mapping[str, Any]] = None) -> None:
        if self._precalculated_piece_size is not None:
            self._piece_size = self._precalculated_piece_size
            self.metainfo['info']['piece length'] = self._precalculated_piece_size
            return


class TorrentCreator:
    # Limit concurrent torrent creation to avoid heavy parallel hashing
    _create_torrent_semaphore = asyncio.Semaphore(1)
    _create_torrent_inflight = 0
    _torf_start_time = time.time()

    @staticmethod
    def calculate_piece_size(
        total_size: int,
        min_size: int,
        max_size: int,
        meta: Mapping[str, Any],
        piece_size: Optional[int] = None,
    ) -> int:
        # Set max_size
        if piece_size:
            try:
                max_size = min(int(piece_size) * 1024 * 1024, PIECE_SIZE_MAX)
            except ValueError:
                max_size = 134217728  # Fallback to default if conversion fails
        else:
            max_size = 134217728  # 128 MiB default maximum

        if meta.get('debug'):
            console.print(f"Content size: {total_size / (1024*1024):.2f} MiB")
            console.print(f"Max size: {max_size}")

        total_size_mib = total_size / (1024*1024)

        if total_size_mib <= 60:  # <= 60 MiB
            piece_size = 32 * 1024  # 32 KiB
        elif total_size_mib <= 120:  # <= 120 MiB
            piece_size = 64 * 1024  # 64 KiB
        elif total_size_mib <= 240:  # <= 240 MiB
            piece_size = 128 * 1024  # 128 KiB
        elif total_size_mib <= 480:  # <= 480 MiB
            piece_size = 256 * 1024  # 256 KiB
        elif total_size_mib <= 960:  # <= 960 MiB
            piece_size = 512 * 1024  # 512 KiB
        elif total_size_mib <= 1920:  # <= 1.875 GiB
            piece_size = 1024 * 1024  # 1 MiB
        elif total_size_mib <= 3840:  # <= 3.75 GiB
            piece_size = 2 * 1024 * 1024  # 2 MiB
        elif total_size_mib <= 7680:  # <= 7.5 GiB
            piece_size = 4 * 1024 * 1024  # 4 MiB
        elif total_size_mib <= 15360:  # <= 15 GiB
            piece_size = 8 * 1024 * 1024  # 8 MiB
        elif total_size_mib <= 46080:  # <= 45 GiB
            piece_size = 16 * 1024 * 1024  # 16 MiB
        elif total_size_mib <= 92160:  # <= 90 GiB
            piece_size = 32 * 1024 * 1024  # 32 MiB
        elif total_size_mib <= 138240:  # <= 135 GiB
            piece_size = 64 * 1024 * 1024
        else:
            piece_size = 128 * 1024 * 1024  # 128 MiB

        if any(tracker in meta.get('trackers', []) for tracker in ['HDB', 'PTP']) and piece_size > 16 * 1024 * 1024:
            piece_size = 16 * 1024 * 1024

        # Enforce minimum and maximum limits
        piece_size = max(min_size, min(piece_size, max_size))

        # Calculate number of pieces for debugging
        num_pieces = math.ceil(total_size / piece_size)
        if meta.get('debug'):
            console.print(f"Selected piece size: {piece_size / 1024:.2f} KiB")
            console.print(f"Number of pieces: {num_pieces}")

        return piece_size

    @staticmethod
    def build_mkbrr_exclude_string(root_folder: str, filelist: Sequence[str]) -> str:
        manual_patterns = ["*.nfo", "*.jpg", "*.png", '*.srt', '*.sub', '*.vtt', '*.ssa', '*.ass', "*.txt", "*.xml"]
        keep_set = {os.path.abspath(f) for f in filelist}

        exclude_files: set[str] = set()
        for dirpath, _, filenames in os.walk(root_folder):
            for fname in filenames:
                full_path = os.path.abspath(os.path.join(dirpath, fname))
                if full_path in keep_set:
                    continue
                if any(fnmatch.fnmatch(fname, pat) for pat in manual_patterns):
                    continue
                exclude_files.add(fname)

        exclude_str = ",".join(sorted(exclude_files) + manual_patterns)
        return exclude_str

    @classmethod
    async def create_torrent(
        cls,
        meta: Meta,
        path: Union[str, os.PathLike[str]],
        output_filename: str,
        tracker_url: Optional[str] = None,
        piece_size: int = 0,
    ) -> Union[str, Torrent]:
        # Ensure only one torrent creation runs at a time
        wait_started: Optional[float] = None
        if cls._create_torrent_semaphore.locked():
            wait_started = time.time()
            if meta.get('debug', False):
                console.print("[yellow]Waiting for create_torrent slot...[/yellow]")

        async with cls._create_torrent_semaphore:
            cls._create_torrent_inflight += 1
            if meta.get('debug', False):
                wait_msg = ""
                if wait_started is not None:
                    waited = time.time() - wait_started
                    wait_msg = f" (waited {waited:.2f}s)"
                console.print(f"[cyan]create_torrent start | in-flight={cls._create_torrent_inflight}{wait_msg}[/cyan]")

            try:
                if not piece_size:
                    piece_size = meta.get('max_piece_size', 0)
                tracker_url = tracker_url or None
                include: list[str] = []
                exclude: list[str] = []

                if meta['keep_folder']:
                    console.print('--keep-folder was specified. Using complete folder for torrent creation.')
                    # specific nfo catch for certain trackers. BASE catch should prevent unintentional inclusion by default
                    if meta.get('keep_nfo', False) and "BASE" not in output_filename:
                        console.print('--keep-nfo was specified. Including NFO files in torrent.')
                        include = ["*.mkv", "*.mp4", "*.ts", "*.nfo"]
                        exclude = ["*.*", "*sample.mkv"]
                        meta['mkbrr'] = False
                    elif not meta.get('tv_pack', False):
                        folder_name = os.path.basename(str(path))
                        include = [
                            f"{folder_name}/{os.path.basename(f)}"
                            for f in meta['filelist']
                        ]
                        exclude = ["*", "*/**"]

                elif meta['isdir']:
                    if meta.get('keep_nfo', False) and not meta.get('is_disc', False) and "BASE" not in output_filename:
                        console.print('--keep-nfo was specified. Including NFO files in torrent.')
                        include = ["*.mkv", "*.mp4", "*.ts", "*.nfo"]
                        exclude = ["*.*", "*sample.mkv"]
                        meta['mkbrr'] = False
                    elif meta.get('is_disc', False):
                        include = []
                        exclude = []
                    elif not meta.get('tv_pack', False):
                        path_dir = os.fspath(path)
                        os.chdir(path_dir)
                        globs = [os.path.basename(f) for f in glob.glob(os.path.join(path_dir, "*.mkv"))] + [
                            os.path.basename(f) for f in glob.glob(os.path.join(path_dir, "*.mp4"))
                        ] + [os.path.basename(f) for f in glob.glob(os.path.join(path_dir, "*.ts"))]
                        no_sample_globs = [
                            os.path.abspath(f"{path_dir}{os.sep}{file}") for file in globs
                            if not file.lower().endswith('sample.mkv') or "!sample" in file.lower()
                        ]
                        if len(no_sample_globs) == 1:
                            path = meta['filelist'][0]
                        exclude = ["*.*", "*sample.mkv", "!sample*.*"] if not meta['is_disc'] else []
                        include = ["*.mkv", "*.mp4", "*.ts"] if not meta['is_disc'] else []
                    else:
                        folder_name = os.path.basename(str(path))
                        include = [
                            f"{folder_name}/{os.path.basename(f)}"
                            for f in meta['filelist']
                        ]
                        exclude = ["*", "*/**"]
                else:
                    exclude = ["*.*", "*sample.mkv", "!sample*.*"] if not meta['is_disc'] else []
                    include = ["*.mkv", "*.mp4", "*.ts"] if not meta['is_disc'] else []

                # If using mkbrr, run the external application
                if meta.get('mkbrr'):
                    try:
                        # Validate input path to prevent potential command injection
                        if not os.path.exists(path):
                            raise ValueError(f"Path does not exist: {path}")
                        mkbrr_binary = cls.get_mkbrr_path(meta)
                        # Validate mkbrr binary exists and is executable
                        if not os.path.exists(mkbrr_binary):
                            raise FileNotFoundError(f"mkbrr binary not found: {mkbrr_binary}")
                        output_path = os.path.join(meta['base_dir'], "tmp", meta['uuid'], f"{output_filename}.torrent")

                        # Ensure executable permission for non-Windows systems
                        if not sys.platform.startswith("win"):
                            with contextlib.suppress(Exception):
                                os.chmod(mkbrr_binary, 0o700)

                        cmd = [mkbrr_binary, "create", os.fspath(path)]

                        if tracker_url:
                            cmd.extend(["-t", tracker_url])

                        if int(meta.get('randomized', 0)) >= 1:
                            cmd.extend(["-e"])

                        if piece_size and not tracker_url:
                            try:
                                max_size_bytes = int(piece_size) * 1024 * 1024

                                # Calculate the appropriate power of 2 (log2)
                                # We want the largest power of 2 that's less than or equal to max_size_bytes
                                power = min(27, max(16, math.floor(math.log2(max_size_bytes))))

                                cmd.extend(["-l", str(power)])
                                console.print(f"[yellow]Setting mkbrr piece length to 2^{power} ({(2**power) / (1024 * 1024):.2f} MiB)")
                            except (ValueError, TypeError):
                                console.print("[yellow]Warning: Invalid max_piece_size value, using default piece length")

                        if not piece_size and not tracker_url and not any(tracker in meta.get('trackers', []) for tracker in ['HDB', 'PTP', 'MTV']):
                            cmd.extend(['-m', '27'])

                        if meta.get('mkbrr_threads') != '0':
                            cmd.extend(["--workers", str(meta['mkbrr_threads'])])

                        if not meta.get('is_disc', False):
                            exclude_str = cls.build_mkbrr_exclude_string(str(path), meta['filelist'])
                            cmd.extend(["--exclude", exclude_str])

                        cmd.extend(["-o", output_path])
                        if meta['debug']:
                            console.print(f"[cyan]mkbrr cmd: {cmd}")

                        # Run mkbrr subprocess in thread to avoid blocking
                        def run_mkbrr() -> int:
                            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

                            if process.stdout is None:
                                return process.wait()

                            total_pieces = 100  # Default to 100% for scaling progress
                            pieces_done = 0
                            mkbrr_start_time = time.time()

                            for line in process.stdout:
                                line = line.strip()

                                # Detect hashing progress, speed, and percentage
                                match = re.search(r"Hashing pieces.*?\[(\d+(?:\.\d+)? (?:G|M)(?:B|iB)/s)\]\s+(\d+)%", line)
                                if match:
                                    speed = match.group(1)  # Extract speed (e.g., "1.7 GiB/s")
                                    pieces_done = int(match.group(2))  # Extract percentage (e.g., "14")

                                    # Try to extract the ETA directly if it's in the format [elapsed:remaining]
                                    eta_match = re.search(r'\[(\d+)s:(\d+)s\]', line)
                                    if eta_match:
                                        eta_seconds = int(eta_match.group(2))
                                        eta = time.strftime("%M:%S", time.gmtime(eta_seconds))
                                    else:
                                        # Fallback to calculating ETA if not directly available
                                        elapsed_time = time.time() - mkbrr_start_time
                                        if pieces_done > 0:
                                            estimated_total_time = elapsed_time / (pieces_done / 100)
                                            eta_seconds = int(max(0.0, estimated_total_time - elapsed_time))
                                            eta = time.strftime("%M:%S", time.gmtime(eta_seconds))
                                        else:
                                            eta = "--:--"  # Placeholder if we can't estimate yet

                                    cli_ui.info_progress(f"mkbrr hashing... {speed} | ETA: {eta}", pieces_done, total_pieces)

                                # Detect final output line
                                if "Wrote" in line and ".torrent" in line and meta['debug']:
                                    console.print(f"[bold cyan]{line}")  # Print the final torrent file creation message

                            # Wait for the process to finish
                            return process.wait()

                        result = await asyncio.to_thread(run_mkbrr)

                        # Verify the torrent was actually created
                        if result != 0:
                            console.print(f"[bold red]mkbrr exited with non-zero status code: {result}")
                            raise RuntimeError(f"mkbrr exited with status code {result}")

                        if not os.path.exists(output_path):
                            console.print("[bold red]mkbrr did not create a torrent file!")
                            raise FileNotFoundError(f"Expected torrent file {output_path} was not created")
                        else:
                            return output_path

                    except subprocess.CalledProcessError as e:
                        console.print(f"[bold red]Error creating torrent with mkbrr: {e}")
                        console.print("[yellow]Falling back to CustomTorrent method")
                        meta['mkbrr'] = False
                    except Exception as e:
                        console.print(f"[bold red]Error using mkbrr: {str(e)}")
                        console.print("[yellow]Falling back to CustomTorrent method")
                        meta['mkbrr'] = False
                overall_start_time = time.time()

                # Calculate initial size
                def calculate_size() -> int:
                    size = 0
                    if os.path.isfile(path):
                        size = os.path.getsize(path)
                    elif os.path.isdir(path):
                        for root, _dirs, files in os.walk(path):
                            size += sum(os.path.getsize(os.path.join(root, f)) for f in files if os.path.isfile(os.path.join(root, f)))
                    return size

                initial_size = await asyncio.to_thread(calculate_size)

                piece_size = cls.calculate_piece_size(initial_size, 32768, 134217728, meta, piece_size=piece_size)

                # Fallback to CustomTorrent if mkbrr is not used
                torrent = CustomTorrent(
                    meta=meta,
                    path=path,
                    trackers=["https://fake.tracker"],
                    source="UA",
                    private=True,
                    exclude_globs=exclude or [],
                    include_globs=include or [],
                    creation_date=datetime.now(timezone.utc),
                    comment="Created by Upload Assistant",
                    created_by="Upload Assistant",
                    piece_size=piece_size
                )

                # Run torrent generation in thread to avoid blocking the event loop
                def generate_torrent() -> None:
                    torrent.generate(callback=cls.torf_cb, interval=5)
                    torrent.write(f"{meta['base_dir']}/tmp/{meta['uuid']}/{output_filename}.torrent", overwrite=True)
                    torrent.verify_filesize(path)

                await asyncio.to_thread(generate_torrent)

                total_elapsed_time = time.time() - overall_start_time
                formatted_time = time.strftime("%H:%M:%S", time.gmtime(total_elapsed_time))

                torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/{output_filename}.torrent"
                torrent_file_size = os.path.getsize(torrent_file_path) / 1024
                if meta['debug']:
                    console.print()
                    console.print(f"[bold green]torrent created in {formatted_time}")
                    console.print(f"[green]Torrent file size: {torrent_file_size:.2f} KB")
                return torrent
            finally:
                cls._create_torrent_inflight -= 1
                if meta.get('debug', False):
                    console.print(f"[cyan]create_torrent end | in-flight={cls._create_torrent_inflight}[/cyan]")

    @staticmethod
    def torf_cb(torrent: Torrent, _filepath: str, pieces_done: int, pieces_total: int) -> None:
        if pieces_done == 0:
            TorrentCreator._torf_start_time = time.time()  # Reset start time when hashing starts

        elapsed_time = time.time() - TorrentCreator._torf_start_time

        # Calculate percentage done
        percentage_done = (pieces_done / pieces_total) * 100 if pieces_total > 0 else 0.0

        # Estimate ETA (if at least one piece is done)
        if pieces_done > 0 and pieces_total > 0:
            estimated_total_time = elapsed_time / (pieces_done / pieces_total)
            eta_seconds = max(0.0, estimated_total_time - elapsed_time)
            eta = time.strftime("%M:%S", time.gmtime(eta_seconds))
        else:
            eta = "--:--"

        # Calculate hashing speed (MB/s)
        if elapsed_time > 0 and pieces_done > 0:
            piece_size_bytes = torrent.piece_size or 0
            piece_size = piece_size_bytes / (1024 * 1024)
            speed = (pieces_done * piece_size) / elapsed_time
            speed_str = f"{speed:.2f} MB/s"
        else:
            speed_str = "-- MB/s"

        # Display progress with percentage, speed, and ETA
        cli_ui.info_progress(f"Hashing... {speed_str} | ETA: {eta}", int(percentage_done), 100)

    @staticmethod
    def create_random_torrents(base_dir: str, uuid: str, num: Union[int, str], path: str) -> None:
        manual_name = re.sub(r"[^0-9a-zA-Z\[\]\'\-]+", ".", os.path.basename(path))
        base_torrent = Torrent.read(f"{base_dir}/tmp/{uuid}/BASE.torrent")
        for i in range(1, int(num) + 1):
            new_torrent = base_torrent
            new_torrent.metainfo['info']['entropy'] = random.randint(1, 999999)  # type: ignore  # nosec B311
            Torrent.copy(new_torrent).write(f"{base_dir}/tmp/{uuid}/[RAND-{i}]{manual_name}.torrent", overwrite=True)

    @staticmethod
    async def create_base_from_existing_torrent(torrentpath: str, base_dir: str, uuid: str) -> None:
        if os.path.exists(torrentpath):
            base_torrent = Torrent.read(torrentpath)
            base_torrent.trackers = ['https://fake.tracker']
            base_torrent.comment = "Created by Upload Assistant"
            base_torrent.created_by = "Created by Upload Assistant"
            info_dict = base_torrent.metainfo['info']
            valid_keys = ['name', 'piece length', 'pieces', 'private', 'source']

            # Add the correct key based on single vs multi file torrent
            if 'files' in info_dict:
                valid_keys.append('files')
            elif 'length' in info_dict:
                valid_keys.append('length')

            # Remove everything not in the whitelist
            for each in list(info_dict):
                if each not in valid_keys:
                    info_dict.pop(each, None)  # type: ignore
            for each in list(base_torrent.metainfo):
                if each not in ('announce', 'comment', 'creation date', 'created by', 'encoding', 'info'):
                    base_torrent.metainfo.pop(each, None)  # type: ignore
            base_torrent.source = 'L4G'
            base_torrent.private = True
            Torrent.copy(base_torrent).write(f"{base_dir}/tmp/{uuid}/BASE.torrent", overwrite=True)

    @staticmethod
    def get_mkbrr_path(meta: Mapping[str, Any]) -> str:
        """Determine the correct mkbrr binary based on OS and architecture."""
        system_mkbrr = shutil.which("mkbrr")
        if system_mkbrr:
            return system_mkbrr

        base_dir = os.path.join(str(meta['base_dir']), "bin", "mkbrr")

        # Detect OS & Architecture
        system = platform.system().lower()
        arch = platform.machine().lower()

        if system == "windows":
            binary_path = os.path.join(base_dir, "windows", "x86_64", "mkbrr.exe")
        elif system == "darwin":
            binary_path = os.path.join(base_dir, "macos", "arm64", "mkbrr") if "arm" in arch else os.path.join(base_dir, "macos", "x86_64", "mkbrr")
        elif system == "linux":
            if "x86_64" in arch:
                binary_path = os.path.join(base_dir, "linux", "amd64", "mkbrr")
            elif "armv6" in arch:
                binary_path = os.path.join(base_dir, "linux", "armv6", "mkbrr")
            elif "arm" in arch:
                binary_path = os.path.join(base_dir, "linux", "arm", "mkbrr")
            elif "aarch64" in arch or "arm64" in arch:
                binary_path = os.path.join(base_dir, "linux", "arm64", "mkbrr")
            else:
                raise Exception("Unsupported Linux architecture")
        else:
            raise Exception("Unsupported OS")

        if not os.path.exists(binary_path):
            raise FileNotFoundError(f"mkbrr binary not found: {binary_path}")

        return binary_path


def build_mkbrr_exclude_string(root_folder: str, filelist: Sequence[str]) -> str:
    return TorrentCreator.build_mkbrr_exclude_string(root_folder, filelist)


async def create_torrent(
    meta: Meta,
    path: Union[str, os.PathLike[str]],
    output_filename: str,
    tracker_url: Optional[str] = None,
    piece_size: int = 0,
) -> Union[str, Torrent]:
    return await TorrentCreator.create_torrent(
        meta=meta,
        path=path,
        output_filename=output_filename,
        tracker_url=tracker_url,
        piece_size=piece_size,
    )


def torf_cb(torrent: Torrent, filepath: str, pieces_done: int, pieces_total: int) -> None:
    TorrentCreator.torf_cb(torrent, filepath, pieces_done, pieces_total)


def create_random_torrents(base_dir: str, uuid: str, num: Union[int, str], path: str) -> None:
    TorrentCreator.create_random_torrents(base_dir, uuid, num, path)


async def create_base_from_existing_torrent(torrentpath: str, base_dir: str, uuid: str) -> None:
    await TorrentCreator.create_base_from_existing_torrent(torrentpath, base_dir, uuid)


def get_mkbrr_path(meta: Mapping[str, Any]) -> str:
    return TorrentCreator.get_mkbrr_path(meta)
