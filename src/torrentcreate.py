from datetime import datetime
import torf
from torf import Torrent
import random
import math
import os
import re
import cli_ui
import fnmatch
import time
import subprocess
import sys
import platform
import glob
from src.console import console


def calculate_piece_size(total_size, min_size, max_size, files, meta):
    # Set max_size
    if 'max_piece_size' in meta and meta['max_piece_size']:
        try:
            max_size = min(int(meta['max_piece_size']) * 1024 * 1024, torf.Torrent.piece_size_max)
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

    # Enforce minimum and maximum limits
    piece_size = max(min_size, min(piece_size, max_size))

    # Calculate number of pieces for debugging
    num_pieces = math.ceil(total_size / piece_size)
    if meta.get('debug'):
        console.print(f"Selected piece size: {piece_size / 1024:.2f} KiB")
        console.print(f"Number of pieces: {num_pieces}")

    return piece_size


class CustomTorrent(torf.Torrent):
    # Default piece size limits
    torf.Torrent.piece_size_min = 32768  # 32 KiB
    torf.Torrent.piece_size_max = 134217728

    def __init__(self, meta, *args, **kwargs):
        self._meta = meta

        # Extract and store the precalculated piece size
        self._precalculated_piece_size = kwargs.pop('piece_size', None)
        super().__init__(*args, **kwargs)

        # Set piece size directly
        if self._precalculated_piece_size is not None:
            self._piece_size = self._precalculated_piece_size
            self.metainfo['info']['piece length'] = self._precalculated_piece_size

    @property
    def piece_size(self):
        return self._piece_size

    @piece_size.setter
    def piece_size(self, value):
        if value is None and self._precalculated_piece_size is not None:
            value = self._precalculated_piece_size

        self._piece_size = value
        self.metainfo['info']['piece length'] = value

    def validate_piece_size(self, meta=None):
        if hasattr(self, '_precalculated_piece_size') and self._precalculated_piece_size is not None:
            self._piece_size = self._precalculated_piece_size
            self.metainfo['info']['piece length'] = self._precalculated_piece_size
            return


def build_mkbrr_exclude_string(root_folder, filelist):
    manual_patterns = ["*.nfo", "*.jpg", "*.png", '*.srt', '*.sub', '*.vtt', '*.ssa', '*.ass', "*.txt", "*.xml"]
    keep_set = set(os.path.abspath(f) for f in filelist)

    exclude_files = set()
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


def create_torrent(meta, path, output_filename, tracker_url=None):
    if meta['isdir']:
        if meta['keep_folder']:
            cli_ui.info('--keep-folder was specified. Using complete folder for torrent creation.')
            if not meta.get('tv_pack', False):
                folder_name = os.path.basename(str(path))
                include = [
                    f"{folder_name}/{os.path.basename(f)}"
                    for f in meta['filelist']
                ]
                exclude = ["*", "*/**"]
        else:
            if meta.get('is_disc', False):
                path = path
                include = []
                exclude = []
            elif not meta.get('tv_pack', False):
                os.chdir(path)
                globs = glob.glob1(path, "*.mkv") + glob.glob1(path, "*.mp4") + glob.glob1(path, "*.ts")
                no_sample_globs = [
                    os.path.abspath(f"{path}{os.sep}{file}") for file in globs
                    if not file.lower().endswith('sample.mkv') or "!sample" in file.lower()
                ]
                if len(no_sample_globs) == 1:
                    path = meta['filelist'][0]
                exclude = ["*.*", "*sample.mkv", "!sample*.*"] if not meta['is_disc'] else ""
                include = ["*.mkv", "*.mp4", "*.ts"] if not meta['is_disc'] else ""
            else:
                folder_name = os.path.basename(str(path))
                include = [
                    f"{folder_name}/{os.path.basename(f)}"
                    for f in meta['filelist']
                ]
                exclude = ["*", "*/**"]
    else:
        exclude = ["*.*", "*sample.mkv", "!sample*.*"] if not meta['is_disc'] else ""
        include = ["*.mkv", "*.mp4", "*.ts"] if not meta['is_disc'] else ""

    if meta.get('tv_pack'):
        completeness = check_season_pack_completeness(meta)

        if not completeness['complete']:
            just_go = False
            missing_list = [f"S{s:02d}E{e:02d}" for s, e in completeness['missing_episodes']]
            console.print("[red]Warning: Season pack appears incomplete!")
            console.print(f"[yellow]Missing episodes: {', '.join(missing_list)}")

            # Show first 15 files from filelist
            filelist = meta['filelist']
            files_shown = 0
            batch_size = 15

            console.print(f"[cyan]Filelist ({len(filelist)} files):")
            for i, file in enumerate(filelist[:batch_size]):
                console.print(f"[cyan]  {i+1:2d}. {os.path.basename(file)}")

            files_shown = min(batch_size, len(filelist))

            # Loop to handle showing more files in batches
            while files_shown < len(filelist) and not meta['unattended'] or (meta['unattended'] and meta.get('unattended-confirm', False)):
                remaining_files = len(filelist) - files_shown
                console.print(f"[yellow]... and {remaining_files} more files")

                if remaining_files > batch_size:
                    response = input(f"Show (n)ext {batch_size} files, (a)ll remaining files, (c)ontinue with incomplete pack, or (q)uit? (n/a/c/Q): ")
                else:
                    response = input(f"Show (a)ll remaining {remaining_files} files, (c)ontinue with incomplete pack, or (q)uit? (a/c/Q): ")

                if response.lower() == 'n' and remaining_files > batch_size:
                    # Show next batch of files
                    next_batch = filelist[files_shown:files_shown + batch_size]
                    for i, file in enumerate(next_batch):
                        console.print(f"[cyan]  {files_shown + i + 1:2d}. {os.path.basename(file)}")
                    files_shown += len(next_batch)
                elif response.lower() == 'a':
                    # Show all remaining files
                    remaining_batch = filelist[files_shown:]
                    for i, file in enumerate(remaining_batch):
                        console.print(f"[cyan]  {files_shown + i + 1:2d}. {os.path.basename(file)}")
                    files_shown = len(filelist)
                elif response.lower() == 'c':
                    just_go = True
                    break  # Continue with incomplete pack
                else:  # 'q' or any other input
                    console.print("[red]Aborting torrent creation due to incomplete season pack")
                    sys.exit(1)

            # Final confirmation if not in unattended mode
            if not meta['unattended'] and not just_go or (meta['unattended'] and meta.get('unattended-confirm', False) and not just_go):
                response = input("Continue with incomplete season pack? (y/N): ")
                if response.lower() != 'y':
                    console.print("[red]Aborting torrent creation due to incomplete season pack")
                    sys.exit(1)
        else:
            if meta['debug']:
                console.print("[green]Season pack completeness verified")

    # If using mkbrr, run the external application
    if meta.get('mkbrr'):
        try:
            mkbrr_binary = get_mkbrr_path(meta)
            output_path = os.path.join(meta['base_dir'], "tmp", meta['uuid'], f"{output_filename}.torrent")

            # Ensure executable permission for non-Windows systems
            if not sys.platform.startswith("win"):
                os.chmod(mkbrr_binary, 0o755)

            cmd = [mkbrr_binary, "create", path]

            if tracker_url is not None:
                cmd.extend(["-t", tracker_url])

            if int(meta.get('randomized', 0)) >= 1:
                cmd.extend(["-e"])

            if meta.get('max_piece_size') and tracker_url is None:
                try:
                    max_size_bytes = int(meta['max_piece_size']) * 1024 * 1024

                    # Calculate the appropriate power of 2 (log2)
                    # We want the largest power of 2 that's less than or equal to max_size_bytes
                    import math
                    power = min(27, max(16, math.floor(math.log2(max_size_bytes))))

                    cmd.extend(["-l", str(power)])
                    console.print(f"[yellow]Setting mkbrr piece length to 2^{power} ({(2**power) / (1024 * 1024):.2f} MiB)")
                except (ValueError, TypeError):
                    console.print("[yellow]Warning: Invalid max_piece_size value, using default piece length")

            if not meta.get('is_disc', False):
                exclude_str = build_mkbrr_exclude_string(str(path), meta['filelist'])
                cmd.extend(["--exclude", exclude_str])

            cmd.extend(["-o", output_path])
            if meta['debug']:
                console.print(f"[cyan]mkbrr cmd: {cmd}")

            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

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
                            eta_seconds = max(0, estimated_total_time - elapsed_time)
                            eta = time.strftime("%M:%S", time.gmtime(eta_seconds))
                        else:
                            eta = "--:--"  # Placeholder if we can't estimate yet

                    cli_ui.info_progress(f"mkbrr hashing... {speed} | ETA: {eta}", pieces_done, total_pieces)

                # Detect final output line
                if "Wrote" in line and ".torrent" in line and meta['debug']:
                    console.print(f"[bold cyan]{line}")  # Print the final torrent file creation message

            # Wait for the process to finish
            result = process.wait()

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
            raise sys.exit(1)

    overall_start_time = time.time()
    initial_size = 0
    if os.path.isfile(path):
        initial_size = os.path.getsize(path)
    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            initial_size += sum(os.path.getsize(os.path.join(root, f)) for f in files if os.path.isfile(os.path.join(root, f)))

    piece_size = calculate_piece_size(initial_size, 32768, 134217728, [], meta)

    # Fallback to CustomTorrent if mkbrr is not used
    torrent = CustomTorrent(
        meta=meta,
        path=path,
        trackers=["https://fake.tracker"],
        source="Audionut UA",
        private=True,
        exclude_globs=exclude or [],
        include_globs=include or [],
        creation_date=datetime.now(),
        comment="Created by Audionut's Upload Assistant",
        created_by="Audionut's Upload Assistant",
        piece_size=piece_size
    )

    torrent.generate(callback=torf_cb, interval=5)
    torrent.write(f"{meta['base_dir']}/tmp/{meta['uuid']}/{output_filename}.torrent", overwrite=True)
    torrent.verify_filesize(path)

    total_elapsed_time = time.time() - overall_start_time
    formatted_time = time.strftime("%H:%M:%S", time.gmtime(total_elapsed_time))

    torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/{output_filename}.torrent"
    torrent_file_size = os.path.getsize(torrent_file_path) / 1024
    if meta['debug']:
        console.print()
        console.print(f"[bold green]torrent created in {formatted_time}")
        console.print(f"[green]Torrent file size: {torrent_file_size:.2f} KB")
    return torrent


torf_start_time = time.time()


def torf_cb(torrent, filepath, pieces_done, pieces_total):
    global torf_start_time

    if pieces_done == 0:
        torf_start_time = time.time()  # Reset start time when hashing starts

    elapsed_time = time.time() - torf_start_time

    # Calculate percentage done
    if pieces_total > 0:
        percentage_done = (pieces_done / pieces_total) * 100
    else:
        percentage_done = 0

    # Estimate ETA (if at least one piece is done)
    if pieces_done > 0:
        estimated_total_time = elapsed_time / (pieces_done / pieces_total)
        eta_seconds = max(0, estimated_total_time - elapsed_time)
        eta = time.strftime("%M:%S", time.gmtime(eta_seconds))
    else:
        eta = "--:--"

    # Calculate hashing speed (MB/s)
    if elapsed_time > 0 and pieces_done > 0:
        piece_size = torrent.piece_size / (1024 * 1024)
        speed = (pieces_done * piece_size) / elapsed_time
        speed_str = f"{speed:.2f} MB/s"
    else:
        speed_str = "-- MB/s"

    # Display progress with percentage, speed, and ETA
    cli_ui.info_progress(f"Hashing... {speed_str} | ETA: {eta}", int(percentage_done), 100)


def create_random_torrents(base_dir, uuid, num, path):
    manual_name = re.sub(r"[^0-9a-zA-Z\[\]\'\-]+", ".", os.path.basename(path))
    base_torrent = Torrent.read(f"{base_dir}/tmp/{uuid}/BASE.torrent")
    for i in range(1, int(num) + 1):
        new_torrent = base_torrent
        new_torrent.metainfo['info']['entropy'] = random.randint(1, 999999)
        Torrent.copy(new_torrent).write(f"{base_dir}/tmp/{uuid}/[RAND-{i}]{manual_name}.torrent", overwrite=True)


async def create_base_from_existing_torrent(torrentpath, base_dir, uuid):
    if os.path.exists(torrentpath):
        base_torrent = Torrent.read(torrentpath)
        base_torrent.trackers = ['https://fake.tracker']
        base_torrent.comment = "Created by Audionut's Upload Assistant"
        base_torrent.created_by = "Created by Audionut's Upload Assistant"
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
                info_dict.pop(each, None)
        for each in list(base_torrent.metainfo):
            if each not in ('announce', 'comment', 'creation date', 'created by', 'encoding', 'info'):
                base_torrent.metainfo.pop(each, None)
        base_torrent.source = 'L4G'
        base_torrent.private = True
        Torrent.copy(base_torrent).write(f"{base_dir}/tmp/{uuid}/BASE.torrent", overwrite=True)


def get_mkbrr_path(meta):
    """Determine the correct mkbrr binary based on OS and architecture."""
    base_dir = os.path.join(meta['base_dir'], "bin", "mkbrr")

    # Detect OS & Architecture
    system = platform.system().lower()
    arch = platform.machine().lower()

    if system == "windows":
        binary_path = os.path.join(base_dir, "windows", "x86_64", "mkbrr.exe")
    elif system == "darwin":
        if "arm" in arch:
            binary_path = os.path.join(base_dir, "macos", "arm64", "mkbrr")
        else:
            binary_path = os.path.join(base_dir, "macos", "x86_64", "mkbrr")
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


def check_season_pack_completeness(meta):
    if not meta.get('tv_pack'):
        return {'complete': True, 'missing_episodes': [], 'found_episodes': []}

    files = meta.get('filelist', [])
    if not files:
        return {'complete': True, 'missing_episodes': [], 'found_episodes': []}

    found_episodes = []
    season_numbers = set()

    # Pattern for standard TV shows: S01E01, S01E01E02
    episode_pattern = r'[Ss](\d{1,2})[Ee](\d{1,3})(?:[Ee](\d{1,3}))?'

    # Pattern for episode-only: E01, E01E02 (without season)
    episode_only_pattern = r'\b[Ee](\d{1,3})(?:[Ee](\d{1,3}))?\b'

    # Pattern for anime: " - 43 (1080p)" or "43 (1080p)" or similar
    anime_pattern = r'(?:\s-\s)?(\d{1,3})\s*\((?:\d+p|480p|480i|576i|576p|720p|1080i|1080p|2160p)\)'

    for file_path in files:
        filename = os.path.basename(file_path)
        matches = re.findall(episode_pattern, filename)

        for match in matches:
            season_str = match[0]
            episode1_str = match[1]
            episode2_str = match[2] if match[2] else None

            season_num = int(season_str)
            episode1_num = int(episode1_str)
            found_episodes.append((season_num, episode1_num))
            season_numbers.add(season_num)

            if episode2_str:
                episode2_num = int(episode2_str)
                found_episodes.append((season_num, episode2_num))

        if not matches:
            episode_only_matches = re.findall(episode_only_pattern, filename)
            for match in episode_only_matches:
                episode1_num = int(match[0])
                episode2_num = int(match[1]) if match[1] else None

                season_num = meta.get('season_int', 1)
                found_episodes.append((season_num, episode1_num))
                season_numbers.add(season_num)

                if episode2_num:
                    found_episodes.append((season_num, episode2_num))

        if not matches and not episode_only_matches:
            anime_matches = re.findall(anime_pattern, filename)
            for match in anime_matches:
                episode_num = int(match)
                season_num = meta.get('season_int', 1)
                found_episodes.append((season_num, episode_num))
                season_numbers.add(season_num)

    if not found_episodes:
        console.print("[red]No episodes found in the season pack files.")
        time.sleep(1)
        # return true to not annoy the user with bad regex
        return {'complete': True, 'missing_episodes': [], 'found_episodes': []}

    # Remove duplicates and sort
    found_episodes = sorted(list(set(found_episodes)))

    missing_episodes = []

    # Check each season for completeness
    for season in season_numbers:
        season_episodes = [ep for s, ep in found_episodes if s == season]
        if not season_episodes:
            continue

        min_ep = min(season_episodes)
        max_ep = max(season_episodes)

        # Check for missing episodes in the range
        for ep_num in range(min_ep, max_ep + 1):
            if ep_num not in season_episodes:
                missing_episodes.append((season, ep_num))

    is_complete = len(missing_episodes) == 0

    result = {
        'complete': is_complete,
        'missing_episodes': missing_episodes,
        'found_episodes': found_episodes,
        'seasons': list(season_numbers)
    }

    if meta.get('debug'):
        console.print("[cyan]Season pack completeness check:")
        console.print(f"[cyan]Found episodes: {found_episodes}")
        if missing_episodes:
            console.print(f"[red]Missing episodes: {missing_episodes}")
        else:
            console.print("[green]Season pack appears complete")

    return result
