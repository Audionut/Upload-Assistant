#!/usr/bin/env python3
# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import contextlib
import gc
import json
import os
import platform
import re
import shutil
import sys
import time
import traceback
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Optional, cast

import aiofiles
import cli_ui
import discord
import requests
from packaging import version
from torf import Torrent
from typing_extensions import TypeAlias

from bin.get_mkbrr import MkbrrBinaryManager
from cogs.redaction import Redaction
from discordbot import DiscordNotifier
from src.add_comparison import ComparisonManager
from src.args import Args
from src.cleanup import cleanup_manager
from src.clients import Clients
from src.console import console
from src.disc_menus import process_disc_menus
from src.dupe_checking import DupeChecker
from src.get_desc import gen_desc
from src.get_name import NameManager
from src.get_tracker_data import TrackerDataManager
from src.languages import languages_manager
from src.nfo_link import NfoLinkManager
from src.qbitwait import Wait
from src.queuemanage import QueueManager
from src.takescreens import TakeScreensManager
from src.torrentcreate import TorrentCreator
from src.trackerhandle import process_trackers
from src.trackers.AR import AR
from src.trackers.COMMON import COMMON
from src.trackers.PTP import PTP
from src.trackersetup import TRACKER_SETUP, api_trackers, http_trackers, other_api_trackers, tracker_class_map
from src.trackerstatus import TrackerStatusManager
from src.uphelper import UploadHelper
from src.uploadscreens import UploadScreensManager

cli_ui.setup(color='always', title="Upload Assistant")
base_dir = os.path.abspath(os.path.dirname(__file__))

# Early check for -webui to create config if needed
_config_path = os.path.join(base_dir, "data", "config.py")
_example_config_path = os.path.join(base_dir, "data", "example-config.py")
if "-webui" in sys.argv or "--webui" in sys.argv and not os.path.exists(_config_path) and os.path.exists(_example_config_path):
    console.print("No config.py found. Creating default config from example-config.py...", markup=False)
    try:
        shutil.copy2(_example_config_path, _config_path)
        console.print("Default config created successfully!", markup=False)
    except Exception as e:
        console.print(f"Failed to create default config: {e}", markup=False)
        console.print("Continuing without config file...", markup=False)

Meta: TypeAlias = dict[str, Any]

from src.prep import Prep  # noqa: E402

_base_dir = os.path.abspath(os.path.dirname(__file__))
_config_path = os.path.join(_base_dir, "data", "config.py")

# Enable ANSI colors on Windows
_use_colors = True
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # Enable VIRTUAL_TERMINAL_PROCESSING
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        _use_colors = False

# Color codes (empty strings if colors not supported)
_RED = "\033[91m" if _use_colors else ""
_YELLOW = "\033[93m" if _use_colors else ""
_GREEN = "\033[92m" if _use_colors else ""
_RESET = "\033[0m" if _use_colors else ""


def _print_config_error(error_type: str, message: str, lineno: Optional[int] = None,
                        text: Optional[str] = None, offset: Optional[int] = None,
                        suggestion: Optional[str] = None) -> None:
    """Print a formatted config error message."""
    console.print(f"{_RED}{error_type} in config.py:{_RESET}", markup=False)
    if lineno:
        console.print(f"{_RED}  Line {lineno}: {message}{_RESET}", markup=False)
        if text:
            console.print(f"{_YELLOW}    {text.rstrip()}{_RESET}", markup=False)
            if offset:
                console.print(f"{_YELLOW}    {' ' * (offset - 1)}^{_RESET}", markup=False)
    else:
        console.print(f"{_RED}  {message}{_RESET}", markup=False)
    if suggestion:
        console.print(f"{_GREEN}  Suggestion: {suggestion}{_RESET}", markup=False)
    console.print(f"\n{_RED}Reference: https://github.com/Audionut/Upload-Assistant/blob/master/data/example-config.py{_RESET}", markup=False)


config: dict[str, Any]

if os.path.exists(_config_path):
    try:
        from data.config import config as _imported_config  # pyright: ignore[reportMissingImports,reportUnknownVariableType]
        config = cast(dict[str, Any], _imported_config)
    except SyntaxError as e:
        _print_config_error(
            "Syntax error",
            str(e.msg) if e.msg else "Invalid syntax",
            lineno=e.lineno,
            text=e.text,
            offset=e.offset
        )
        console.print(f"\n{_RED}Common syntax issues:{_RESET}", markup=False)
        console.print(f"{_YELLOW}  - Missing comma between dictionary items{_RESET}", markup=False)
        console.print(f"{_YELLOW}  - Missing closing bracket, brace, quote or comma{_RESET}", markup=False)
        console.print(f"{_YELLOW}  - Unclosed string (missing quote at end){_RESET}", markup=False)
        sys.exit(1)
    except NameError as e:
        # Extract line number from traceback
        import traceback
        tb = traceback.extract_tb(sys.exc_info()[2])
        lineno = tb[-1].lineno if tb else None
        text = tb[-1].line if tb else None

        # Check for common mistakes
        suggestion = None
        error_str = str(e)
        if "'true'" in error_str.lower():
            suggestion = "Use 'True' (capital T) instead of 'true'"
        elif "'false'" in error_str.lower():
            suggestion = "Use 'False' (capital F) instead of 'false'"
        elif "'null'" in error_str.lower() or "'none'" in error_str.lower():
            suggestion = "Use 'None' (capital N) instead of 'null' or 'none'"
        elif "is not defined" in error_str:
            # Extract the undefined name from the error message
            import re as _re
            match = _re.search(r"name '([^']+)' is not defined", error_str)
            if match:
                undefined_name = match.group(1)
                suggestion = f"Did you forget quotes? Try \"{undefined_name}\" instead of '{undefined_name}'"

        _print_config_error(
            "Name error",
            str(e),
            lineno=lineno,
            text=text,
            suggestion=suggestion
        )
        sys.exit(1)
    except TypeError as e:
        import traceback
        tb = traceback.extract_tb(sys.exc_info()[2])
        lineno = tb[-1].lineno if tb else None
        text = tb[-1].line if tb else None

        _print_config_error(
            "Type error",
            str(e),
            lineno=lineno,
            text=text
        )
        console.print(f"\n{_RED}Common type issues:{_RESET}", markup=False)
        console.print(f"{_YELLOW}  - Using unhashable type as dictionary key{_RESET}", markup=False)
        console.print(f"{_YELLOW}  - Incorrect data structure nesting{_RESET}", markup=False)
        sys.exit(1)
    except Exception as e:
        import traceback
        tb = traceback.extract_tb(sys.exc_info()[2])
        lineno = tb[-1].lineno if tb else None
        text = tb[-1].line if tb else None

        _print_config_error(
            "Error",
            str(e),
            lineno=lineno,
            text=text
        )
        sys.exit(1)
else:
    console.print(f"{_RED}Configuration file 'config.py' not found.{_RESET}", markup=False)
    console.print(f"{_RED}Please ensure the file is located at: {_YELLOW}{_config_path}{_RESET}", markup=False)
    console.print(f"{_RED}Follow the setup instructions: https://github.com/Audionut/Upload-Assistant{_RESET}", markup=False)
parser = Args(config)
name_manager = NameManager(config)
tracker_data_manager = TrackerDataManager(config)
nfo_link_manager = NfoLinkManager(config)
takescreens_manager = TakeScreensManager(config)
uploadscreens_manager = UploadScreensManager(config)
use_discord = False
discord_cfg_obj = config.get('DISCORD')
discord_config: Optional[dict[str, Any]] = cast(dict[str, Any], discord_cfg_obj) if isinstance(discord_cfg_obj, dict) else None
if discord_config is not None:
    use_discord = bool(discord_config.get('use_discord', False))


async def merge_meta(meta: Meta, saved_meta: Meta) -> dict[str, Any]:
    """Merges saved metadata with the current meta, respecting overwrite rules."""
    overwrite_list = [
        'trackers', 'dupe', 'debug', 'anon', 'category', 'type', 'screens', 'nohash', 'manual_edition', 'imdb', 'tmdb_manual', 'mal', 'manual',
        'hdb', 'ptp', 'blu', 'no_season', 'no_aka', 'no_year', 'no_dub', 'no_tag', 'no_seed', 'client', 'description_link', 'description_file', 'desc', 'draft',
        'modq', 'region', 'freeleech', 'personalrelease', 'unattended', 'manual_season', 'manual_episode', 'torrent_creation', 'qbit_tag', 'qbit_cat',
        'skip_imghost_upload', 'imghost', 'manual_source', 'webdv', 'hardcoded-subs', 'dual_audio', 'manual_type', 'tvmaze_manual'
    ]
    sanitized_saved_meta: dict[str, Any] = {}
    for key, value in saved_meta.items():
        clean_key = key.strip().strip("'").strip('"')
        if clean_key in overwrite_list:
            if clean_key in meta and meta.get(clean_key) is not None:
                sanitized_saved_meta[clean_key] = meta[clean_key]
                if meta.get('debug', False):
                    console.print(f"Overriding {clean_key} with meta value:", meta[clean_key])
            else:
                sanitized_saved_meta[clean_key] = value
        else:
            sanitized_saved_meta[clean_key] = value
    meta.update(sanitized_saved_meta)
    return sanitized_saved_meta


async def print_progress(message: str, interval: int = 10) -> None:
    """Prints a progress message every `interval` seconds until cancelled."""
    try:
        while True:
            await asyncio.sleep(interval)
            console.print(message)
    except asyncio.CancelledError:
        pass


def update_oeimg_to_onlyimage() -> None:
    """Update all img_host_* values from 'oeimg' to 'onlyimage' in the config file."""
    config_path = f"{base_dir}/data/config.py"
    with open(config_path, encoding="utf-8") as f:
        content = f.read()

    new_content = re.sub(
        r"(['\"]img_host_\d+['\"]\s*:\s*)['\"]oeimg['\"]",
        r"\1'onlyimage'",
        content
    )
    new_content = re.sub(
        r"(['\"])(oeimg_api)(['\"]\s*:)",
        r"\1onlyimage_api\3",
        new_content
    )

    if new_content != content:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        console.print("[green]Updated 'oeimg' to 'onlyimage' and 'oeimg_api' to 'onlyimage_api' in config.py[/green]")
    else:
        console.print("[yellow]No 'oeimg' or 'oeimg_api' found to update in config.py[/yellow]")


async def validate_tracker_logins(meta: Meta, trackers: Optional[list[str]] = None) -> None:
    if 'tracker_status' not in meta:
        meta['tracker_status'] = {}

    if not trackers:
        return

    # Filter trackers that are in both the list and tracker_class_map
    valid_trackers = [tracker for tracker in trackers if tracker in tracker_class_map and tracker in http_trackers]
    # RTF/PTP are not HTTP trackers but need validation
    if "RTF" in trackers:
        valid_trackers.append("RTF")
    if "PTP" in trackers:
        valid_trackers.append("PTP")

    if valid_trackers:

        async def validate_single_tracker(tracker_name: str) -> tuple[str, bool]:
            """Validate credentials for a single tracker."""
            try:
                if tracker_name not in meta['tracker_status']:
                    meta['tracker_status'][tracker_name] = {}

                tracker_class = tracker_class_map[tracker_name](config=config)
                if meta['debug']:
                    console.print(f"[cyan]Validating {tracker_name} credentials...[/cyan]")
                if tracker_name == "RTF":
                    login = await tracker_class.api_test(meta)
                elif tracker_name == "PTP":
                    login = await tracker_class.get_AntiCsrfToken(meta)
                else:
                    login = await tracker_class.validate_credentials(meta)

                if not login:
                    meta['tracker_status'][tracker_name]['skipped'] = True

                return tracker_name, login
            except Exception as e:
                console.print(f"[red]Error validating {tracker_name}: {e}[/red]")
                meta['tracker_status'][tracker_name]['skipped'] = True
                return tracker_name, False

        # Run all tracker validations concurrently
        await asyncio.gather(*[validate_single_tracker(tracker) for tracker in valid_trackers])


async def process_meta(meta: Meta, base_dir: str, bot: Any = None) -> None:
    """Process the metadata for each queued path."""
    if use_discord and bot:
        await DiscordNotifier.send_discord_notification(
            config, bot, f"Starting upload process for: {meta['path']}", debug=meta.get('debug', False), meta=meta
        )

    if meta['imghost'] is None:
        meta['imghost'] = config['DEFAULT']['img_host_1']
        try:
            has_oeimg_config = any(
                config['DEFAULT'].get(key) == "oeimg"
                for key in config['DEFAULT']
                if key.startswith("img_host_")
            )
            if has_oeimg_config:
                console.print("[red]oeimg is now onlyimage, your config is being updated[/red]")
                update_oeimg_to_onlyimage()
        except Exception as e:
            console.print(f"[red]Error checking image hosts: {e}[/red]")
            return

    if not meta['unattended']:
        ua = config['DEFAULT'].get('auto_mode', False)
        if str(ua).lower() == "true":
            meta['unattended'] = True
            console.print("[yellow]Running in Auto Mode")
    prep = Prep(screens=meta['screens'], img_host=meta['imghost'], config=config)
    try:
        meta = await prep.gather_prep(meta=meta, mode='cli')
    except Exception as e:
        console.print(f"Error in gather_prep: {e}")
        console.print(traceback.format_exc())
        return

    meta['emby_debug'] = meta.get('emby_debug') if meta.get('emby_debug', False) else config['DEFAULT'].get('emby_debug', False)
    if meta.get('emby_cat', None) == "movie" and meta.get('category', None) != "MOVIE":
        console.print(f"[red]Wrong category detected! Expected 'MOVIE', but found: {meta.get('category', None)}[/red]")
        meta['we_are_uploading'] = False
        return
    elif meta.get('emby_cat', None) == "tv" and meta.get('category', None) != "TV":
        console.print("[red]TV content is not supported at this time[/red]")
        meta['we_are_uploading'] = False
        return

    # If unattended confirm and we had to get metadata ids from filename searching, skip the quick return so we can prompt about database information
    if meta.get('emby', False) and not meta.get('no_ids', False) and not meta.get('unattended_confirm', False) and meta.get('unattended', False):
        await nfo_link_manager.nfo_link(meta)
        meta['we_are_uploading'] = False
        return

    parser = Args(config)
    helper = UploadHelper(config)

    raw_trackers = meta.get('trackers')
    trackers: list[str]
    if isinstance(raw_trackers, list):
        raw_trackers_list = cast(list[Any], raw_trackers)
        trackers = [t for t in raw_trackers_list if isinstance(t, str)]
    elif isinstance(raw_trackers, str):
        trackers = [t.strip().upper() for t in raw_trackers.split(',') if t.strip()]
        meta['trackers'] = trackers
    else:
        trackers = []

    if not meta.get('emby', False):
        if meta.get('trackers_remove', False):
            remove_list = [t.strip().upper() for t in meta['trackers_remove'].split(',')]
            for tracker in remove_list:
                if tracker in meta['trackers']:
                    meta['trackers'].remove(tracker)

        meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await name_manager.get_name(meta)

        if meta['debug']:
            console.print(f"Trackers list before editing: {meta['trackers']}")
        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w', encoding='utf-8') as f:
            await f.write(json.dumps(meta, indent=4))

    if meta.get('emby_debug', False):
        meta['original_imdb'] = meta.get('imdb_id', None)
        meta['original_tmdb'] = meta.get('tmdb_id', None)
        meta['original_mal'] = meta.get('mal_id', None)
        meta['original_tvmaze'] = meta.get('tvmaze_id', None)
        meta['original_tvdb'] = meta.get('tvdb_id', None)
        meta['original_category'] = meta.get('category', None)
        if 'matched_tracker' not in meta:
            await client.get_pathed_torrents(meta['path'], meta)
            if meta['is_disc']:
                search_term = os.path.basename(meta['path'])
                search_file_folder = 'folder'
            else:
                search_term = os.path.basename(meta['filelist'][0]) if meta['filelist'] else None
                search_file_folder = 'file'
            await tracker_data_manager.get_tracker_data(
                meta['video'], meta, search_term, search_file_folder, meta['category'], only_id=meta['only_id']
            )

    editargs_tracking: tuple[str, ...] = ()
    previous_trackers = meta.get('trackers', [])
    try:
        confirm = await helper.get_confirmation(meta)
    except EOFError:
        console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
        await cleanup_manager.cleanup()
        cleanup_manager.reset_terminal()
        sys.exit(1)
    while confirm is False:
        try:
            editargs_str = cli_ui.ask_string("Input args that need correction e.g. (--tag NTb --category tv --tmdb 12345)")
        except EOFError:
            console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
            await cleanup_manager.cleanup()
            cleanup_manager.reset_terminal()
            sys.exit(1)

        if editargs_str == "continue":
            break

        if not editargs_str or not editargs_str.strip():
            console.print("[yellow]No input provided. Please enter arguments, type `continue` to continue or press Ctrl+C to exit.[/yellow]")
            continue

        try:
            editargs = tuple(editargs_str.split())
        except AttributeError:
            console.print("[red]Bad input detected[/red]")
            confirm = False
            continue
        # Tracks multiple edits
        editargs_tracking = editargs_tracking + editargs
        # Carry original args over, let parse handle duplicates
        meta, _help, _before_args = cast(
            tuple[Meta, Any, Any],
            parser.parse(list(' '.join(sys.argv[1:]).split(' ')) + list(editargs_tracking), meta)
        )
        if not meta.get('trackers'):
            meta['trackers'] = previous_trackers
        if isinstance(meta.get('trackers'), str):
            if "," in meta['trackers']:
                meta['trackers'] = [t.strip().upper() for t in meta['trackers'].split(',')]
            else:
                meta['trackers'] = [meta['trackers'].strip().upper()]
        elif isinstance(meta.get('trackers'), list):
            meta['trackers'] = [t.strip().upper() for t in meta['trackers'] if isinstance(t, str)]
        if meta['debug']:
            console.print(f"Trackers list during edit process: {meta['trackers']}")
        meta['edit'] = True
        meta = await prep.gather_prep(meta=meta, mode='cli')
        meta['name_notag'], meta['name'], meta['clean_name'], meta['potential_missing'] = await name_manager.get_name(meta)
        try:
            confirm = await helper.get_confirmation(meta)
        except EOFError:
            console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
            await cleanup_manager.cleanup()
            cleanup_manager.reset_terminal()
            sys.exit(1)

    if meta.get('emby', False):
        if not meta['debug']:
            await nfo_link_manager.nfo_link(meta)
        meta['we_are_uploading'] = False
        return

    if 'remove_trackers' in meta and meta['remove_trackers']:
        removed: list[str] = []
        remove_trackers_list = (
            [t for t in meta['remove_trackers'] if isinstance(t, str)]
            if isinstance(meta.get('remove_trackers'), list)
            else [str(meta['remove_trackers'])]
        )
        for tracker in remove_trackers_list:
            if tracker in meta['trackers']:
                if meta['debug']:
                    console.print(f"[DEBUG] Would have removed {tracker} found in client")
                else:
                    meta['trackers'].remove(tracker)
                    removed.append(tracker)
        if removed:
            console.print(f"[yellow]Removing trackers already in your client: {', '.join(removed)}[/yellow]")
    if not meta['trackers']:
        console.print("[red]No trackers remain after removal.[/red]")
        successful_trackers = 0
        meta['skip_uploading'] = 10

    else:
        console.print(f"[green]Processing {meta['name']} for upload...[/green]")

        # reset trackers after any removals
        trackers = meta['trackers']

        audio_prompted = False
        for tracker in ["AITHER", "ASC", "BJS", "BT", "CBR", "DP", "FF", "GPW", "HUNO", "IHD", "LDU", "LT", "OE", "PTS", "SAM", "SHRI", "SPD", "TTR", "TVC", "ULCX"]:
            if tracker in trackers:
                if not audio_prompted:
                    await languages_manager.process_desc_language(meta, tracker=tracker)
                    audio_prompted = True
                else:
                    if 'tracker_status' not in meta:
                        meta['tracker_status'] = {}
                    if tracker not in meta['tracker_status']:
                        meta['tracker_status'][tracker] = {}
                    if meta.get('unattended_audio_skip', False) or meta.get('unattended_subtitle_skip', False):
                        meta['tracker_status'][tracker]['skip_upload'] = True
                    else:
                        meta['tracker_status'][tracker]['skip_upload'] = False

        await asyncio.sleep(0.2)
        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w', encoding='utf-8') as f:
            await f.write(json.dumps(meta, indent=4))
        await asyncio.sleep(0.2)

        try:
            await validate_tracker_logins(meta, trackers)
            await asyncio.sleep(0.2)
        except Exception as e:
            console.print(f"[yellow]Warning: Tracker validation encountered an error: {e}[/yellow]")

        successful_trackers = await TrackerStatusManager(config=config).process_all_trackers(meta)

        if meta.get('trackers_pass') is not None:
            meta['skip_uploading'] = meta.get('trackers_pass')
        else:
            tracker_pass_checks = config['DEFAULT'].get('tracker_pass_checks')
            if isinstance(tracker_pass_checks, (int, str)):
                meta['skip_uploading'] = int(tracker_pass_checks)
            else:
                meta['skip_uploading'] = 1

    skip_uploading = meta.get('skip_uploading')
    skip_uploading_int = int(skip_uploading) if isinstance(skip_uploading, (int, str)) else 0

    if successful_trackers < skip_uploading_int and not meta['debug']:
        console.print(f"[red]Not enough successful trackers ({successful_trackers}/{skip_uploading_int}). No uploads being processed.[/red]")

    else:
        meta['we_are_uploading'] = True
        common = COMMON(config)
        if meta.get('site_check', False):
            tracker_status = cast(dict[str, dict[str, Any]], meta.get('tracker_status', {}))
            for tracker in meta['trackers']:
                upload_status = tracker_status.get(tracker, {}).get('upload', False)
                if not upload_status:
                    if tracker == "AITHER" and meta.get('aither_trumpable') and len(meta.get('aither_trumpable', [])) > 0:
                        pass
                    else:
                        continue
                if tracker not in tracker_status:
                    continue

                log_path = f"{base_dir}/tmp/{tracker}_search_results.json"
                if not await common.path_exists(log_path):
                    await common.makedirs(os.path.dirname(log_path))

                search_data: list[dict[str, Any]] = []
                if os.path.exists(log_path):
                    try:
                        async with aiofiles.open(log_path, encoding='utf-8') as f:
                            content = await f.read()
                            loaded: Any = json.loads(content) if content.strip() else []
                            search_data = [e for e in cast(list[Any], loaded) if isinstance(e, dict)] if isinstance(loaded, list) else []
                    except Exception:
                        search_data = []

                existing_uuids = {entry.get('uuid') for entry in search_data}

                if meta['uuid'] not in existing_uuids:
                    search_entry = {
                        'uuid': meta['uuid'],
                        'path': meta.get('path', ''),
                        'imdb_id': meta.get('imdb_id', 0),
                        'tmdb_id': meta.get('tmdb_id', 0),
                        'tvdb_id': meta.get('tvdb_id', 0),
                        'mal_id': meta.get('mal_id', 0),
                        'tvmaze_id': meta.get('tvmaze_id', 0),
                    }
                    if tracker == "AITHER":
                        search_entry['trumpable'] = meta.get('aither_trumpable', '')
                    search_data.append(search_entry)

                    async with aiofiles.open(log_path, 'w', encoding='utf-8') as f:
                        await f.write(json.dumps(search_data, indent=4))
            meta['we_are_uploading'] = False
            return

        filename: str = meta.get('title', '')
        bdmv_filename = meta.get('filename', '')
        bdinfo = meta.get('bdinfo', '')
        file_list = [str(p) for p in cast(list[Any], meta.get('filelist', [])) if str(p)]
        videopath: str = file_list[0] if file_list else ""
        console.print(f"Processing {filename} for upload.....")

        meta['frame_overlay'] = config['DEFAULT'].get('frame_overlay', False)
        tracker_status_map = cast(dict[str, dict[str, Any]], meta.get('tracker_status', {}))
        for tracker in ['AZ', 'CZ', 'PHD']:
            upload_status = tracker_status_map.get(tracker, {}).get('upload', False)
            if tracker in meta['trackers'] and meta['frame_overlay'] and upload_status is True:
                meta['frame_overlay'] = False
                console.print("[yellow]AZ, CZ, and PHD do not allow frame overlays. Frame overlay will be disabled for this upload.[/yellow]")

        bdmv_mi_created = False
        for tracker in ["ANT", "DC", "HUNO", "LCD"]:
            upload_status = tracker_status_map.get(tracker, {}).get('upload', False)
            if tracker in trackers and upload_status is True and not bdmv_mi_created:
                await common.get_bdmv_mediainfo(meta)
                bdmv_mi_created = True

        progress_task = asyncio.create_task(print_progress("[yellow]Still processing, please wait...", interval=10))
        try:
            if 'manual_frames' not in meta:
                meta['manual_frames'] = ""
            manual_frames = meta['manual_frames']

            if meta.get('comparison', False):
                await ComparisonManager(meta, config).add_comparison()

            else:
                image_data_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/image_data.json"
                if os.path.exists(image_data_file) and not meta.get('image_list'):
                    try:
                        async with aiofiles.open(image_data_file, encoding='utf-8') as img_file:
                            content = await img_file.read()
                            image_data = cast(dict[str, Any], json.loads(content)) if content.strip() else {}

                            if 'image_list' in image_data and not meta.get('image_list'):
                                meta['image_list'] = image_data['image_list']
                                if meta.get('debug'):
                                    console.print(f"[cyan]Loaded {len(image_data['image_list'])} previously saved image links")

                            if 'image_sizes' in image_data and not meta.get('image_sizes'):
                                meta['image_sizes'] = image_data['image_sizes']
                                if meta.get('debug'):
                                    console.print("[cyan]Loaded previously saved image sizes")

                            if 'tonemapped' in image_data and not meta.get('tonemapped'):
                                meta['tonemapped'] = image_data['tonemapped']
                                if meta.get('debug'):
                                    console.print("[cyan]Loaded previously saved tonemapped status[/cyan]")

                    except Exception as e:
                        console.print(f"[yellow]Could not load saved image data: {str(e)}")

                if meta.get('is_disc', ""):
                    menus_data_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/menu_images.json"
                    if os.path.exists(menus_data_file):
                        try:
                            async with aiofiles.open(menus_data_file, encoding='utf-8') as menus_file:
                                content = await menus_file.read()
                                menu_image_file = cast(dict[str, Any], json.loads(content)) if content.strip() else {}

                                if 'menu_images' in menu_image_file and not meta.get('menu_images'):
                                    meta['menu_images'] = menu_image_file['menu_images']
                                    if meta.get('debug'):
                                        console.print(f"[cyan]Loaded {len(menu_image_file['menu_images'])} previously saved disc menus")

                        except Exception as e:
                            console.print(f"[yellow]Could not load saved menu image data: {str(e)}")
                    elif meta.get('path_to_menu_screenshots', ""):
                        await process_disc_menus(meta, config)

                # Take Screenshots
                try:
                    if meta['is_disc'] == "BDMV":
                        use_vs = meta.get('vapoursynth', False)
                        try:
                            await takescreens_manager.disc_screenshots(
                                meta, bdmv_filename, bdinfo, meta['uuid'], base_dir, use_vs,
                                meta.get('image_list', []), meta.get('ffdebug', False), 0
                            )
                        except asyncio.CancelledError as e:
                            await cleanup_screenshot_temp_files(meta)
                            await asyncio.sleep(0.1)
                            await cleanup_manager.cleanup()
                            gc.collect()
                            cleanup_manager.reset_terminal()
                            raise Exception("Error during screenshot capture") from e
                        except Exception as e:
                            await cleanup_screenshot_temp_files(meta)
                            await asyncio.sleep(0.1)
                            await cleanup_manager.cleanup()
                            gc.collect()
                            cleanup_manager.reset_terminal()
                            raise Exception(f"Error during screenshot capture: {e}") from e

                    elif meta['is_disc'] == "DVD":
                        try:
                            await takescreens_manager.dvd_screenshots(
                                meta,
                                disc_num=0,
                                num_screens=0,
                                retry_cap=False
                            )
                        except asyncio.CancelledError as e:
                            await cleanup_screenshot_temp_files(meta)
                            await asyncio.sleep(0.1)
                            await cleanup_manager.cleanup()
                            gc.collect()
                            cleanup_manager.reset_terminal()
                            raise Exception("Error during screenshot capture") from e
                        except Exception as e:
                            await cleanup_screenshot_temp_files(meta)
                            await asyncio.sleep(0.1)
                            await cleanup_manager.cleanup()
                            gc.collect()
                            cleanup_manager.reset_terminal()
                            raise Exception(f"Error during screenshot capture: {e}") from e

                    else:
                        try:
                            if meta['debug']:
                                console.print(f"videopath: {videopath}, filename: {filename}, meta: {meta['uuid']}, base_dir: {base_dir}, manual_frames: {manual_frames}")

                            await takescreens_manager.screenshots(
                                videopath, filename, meta['uuid'], base_dir, meta,
                                manual_frames=manual_frames  # Pass additional kwargs directly
                            )
                        except asyncio.CancelledError as e:
                            await cleanup_screenshot_temp_files(meta)
                            await asyncio.sleep(0.1)
                            await cleanup_manager.cleanup()
                            gc.collect()
                            cleanup_manager.reset_terminal()
                            raise Exception("Error during screenshot capture") from e
                        except Exception as e:
                            console.print(traceback.format_exc())
                            await cleanup_screenshot_temp_files(meta)
                            await asyncio.sleep(0.1)
                            await cleanup_manager.cleanup()
                            gc.collect()
                            cleanup_manager.reset_terminal()
                            if "workers" in str(e):
                                console.print("[red]max workers issue, see https://github.com/Audionut/Upload-Assistant/wiki/ffmpeg---max-workers-issues[/red]")
                            raise Exception(f"Error during screenshot capture: {e}") from e

                except asyncio.CancelledError as e:
                    await cleanup_screenshot_temp_files(meta)
                    await asyncio.sleep(0.1)
                    await cleanup_manager.cleanup()
                    gc.collect()
                    cleanup_manager.reset_terminal()
                    raise Exception("Error during screenshot capture") from e
                except Exception as e:
                    await cleanup_screenshot_temp_files(meta)
                    await asyncio.sleep(0.1)
                    await cleanup_manager.cleanup()
                    gc.collect()
                    cleanup_manager.reset_terminal()
                    raise Exception("Error during screenshot capture") from e
                finally:
                    await asyncio.sleep(0.1)
                    await cleanup_manager.cleanup()
                    gc.collect()
                    cleanup_manager.reset_terminal()

                if 'image_list' not in meta:
                    meta['image_list'] = []
                manual_frames_str = meta.get('manual_frames', '')
                if isinstance(manual_frames_str, str):
                    manual_frames_list = [f.strip() for f in manual_frames_str.split(',') if f.strip()]
                    manual_frames_count = len(manual_frames_list)
                    if meta['debug']:
                        console.print(f"Manual frames entered: {manual_frames_count}")
                else:
                    manual_frames_count = 0
                if manual_frames_count > 0:
                    meta['screens'] = manual_frames_count
                cutoff = int(meta.get('cutoff') or 1)
                if len(meta.get('image_list', [])) < cutoff and meta.get('skip_imghost_upload', False) is False:
                    # Validate and (if needed) rehost images to tracker-approved hosts before uploading any new screenshots.
                    trackers_with_image_host_requirements = {'A4K', 'BHD', 'DC', 'GPW', 'HUNO', 'MTV', 'OE', 'PTP', 'STC', 'TVC'}

                    relevant_trackers = [
                        t for t in cast(list[Any], meta.get('trackers', []))
                        if isinstance(t, str) and t in trackers_with_image_host_requirements and t in tracker_class_map
                    ]

                    # If all relevant trackers share exactly one common approved host that the user has configured,
                    # and it's not the initially selected host, switch meta['imghost'] to that common host.
                    # If multiple common hosts exist, pick the first by config priority (img_host_1..img_host_9).
                    allowed_hosts: Optional[list[str]] = None
                    if relevant_trackers:
                        try:
                            tracker_instances = {
                                tracker_name: tracker_class_map[tracker_name](config=config)
                                for tracker_name in relevant_trackers
                            }

                            if meta.get('debug'):
                                console.print(f"[cyan]Image host debug: meta['imghost']={meta.get('imghost')} img_host_1={config['DEFAULT'].get('img_host_1')}[/cyan]")
                                console.print(f"[cyan]Image host debug: relevant_trackers={relevant_trackers}[/cyan]")

                            default_cfg_obj = config.get('DEFAULT', {})
                            default_cfg: dict[str, Any] = cast(dict[str, Any], default_cfg_obj) if isinstance(default_cfg_obj, dict) else {}
                            configured_hosts: list[str] = []
                            for host_index in range(1, 10):
                                host_key = f'img_host_{host_index}'
                                if host_key in default_cfg:
                                    host = default_cfg.get(host_key)
                                    if host and host not in configured_hosts:
                                        configured_hosts.append(str(host))

                            if meta.get('debug'):
                                console.print(f"[cyan]Image host debug: configured_hosts={configured_hosts}[/cyan]")

                            approved_sets: list[set[str]] = []
                            all_known = True
                            for tracker_name in relevant_trackers:
                                tracker_instance = tracker_instances[tracker_name]
                                approved_hosts = getattr(tracker_instance, 'approved_image_hosts', None)
                                if not approved_hosts:
                                    all_known = False
                                    break
                                if isinstance(approved_hosts, (list, set, tuple)):
                                    approved_hosts_list = [
                                        str(host)
                                        for host in cast(Iterable[Any], approved_hosts)
                                    ]
                                    approved_sets.append(set(approved_hosts_list))
                                else:
                                    all_known = False
                                    break

                                if meta.get('debug'):
                                    console.print(
                                        f"[cyan]Image host debug: {tracker_name}.approved_image_hosts={approved_hosts_list}[/cyan]"
                                    )

                            if all_known and approved_sets and configured_hosts:
                                common_hosts: set[str] = set()
                                for host_set in approved_sets:
                                    if not common_hosts:
                                        common_hosts = set(host_set)
                                    else:
                                        common_hosts &= host_set
                                common_configured_hosts = [h for h in configured_hosts if h in common_hosts]

                                if meta.get('debug'):
                                    console.print(f"[cyan]Image host debug: common_hosts={sorted(common_hosts)}[/cyan]")
                                    console.print(f"[cyan]Image host debug: common_configured_hosts={common_configured_hosts}[/cyan]")

                                # If we have any common hosts, use them as allowed_hosts for upload_screens
                                if common_configured_hosts:
                                    allowed_hosts = common_configured_hosts
                                elif common_hosts:
                                    allowed_hosts = sorted(common_hosts)

                                # Prefer the user-selected host if it's valid for all relevant trackers; otherwise
                                # fall back to the first common configured host by config priority (img_host_1..img_host_9).
                                current_img_host = str(meta.get('imghost') or config['DEFAULT'].get('img_host_1') or "")
                                preferred_host: Optional[str] = None

                                if common_configured_hosts and current_img_host not in common_configured_hosts:
                                    preferred_host = common_configured_hosts[0]
                                elif common_hosts and current_img_host not in common_hosts:
                                    preferred_host = sorted(common_hosts)[0]

                                if preferred_host and preferred_host != meta.get('imghost'):
                                    if meta.get('debug'):
                                        console.print(
                                            f"[cyan]Image host debug: current host '{current_img_host}' is not common to all trackers; "
                                            f"switching meta['imghost'] from '{meta.get('imghost')}' to '{preferred_host}'.[/cyan]"
                                        )
                                    meta['imghost'] = preferred_host

                            elif meta.get('debug'):
                                console.print(
                                    f"[cyan]Image host debug: cannot compute common host (all_known={all_known}, approved_sets={len(approved_sets)}, configured_hosts={len(configured_hosts)}).[/cyan]"
                                )

                        except Exception as e:
                            if meta.get('debug'):
                                console.print(f"[yellow]Could not determine a common approved image host: {e}[/yellow]")

                    if meta.get('debug'):
                        image_list_for_debug = cast(list[Any], meta.get('image_list') or [])
                        console.print(
                            f"[cyan]Image host debug: pre-upload_screens meta['imghost']={meta.get('imghost')} image_list={len(image_list_for_debug)} cutoff={meta.get('cutoff')} screens={meta.get('screens')}[/cyan]"  # noqa: E501
                        )

                    return_dict: dict[str, Any] = {}
                    try:
                        default_cfg_obj = config.get('DEFAULT', {})
                        default_cfg = cast(dict[str, Any], default_cfg_obj) if isinstance(default_cfg_obj, dict) else {}
                        min_successful_uploads = int(default_cfg.get('min_successful_image_uploads', 3))
                        host_order: list[str] = []
                        for host_index in range(1, 10):
                            host_key = f'img_host_{host_index}'
                            host = default_cfg.get(host_key)
                            if host and host not in host_order:
                                host_str = str(host)
                                if allowed_hosts is None or host_str in allowed_hosts:
                                    host_order.append(host_str)

                        current_img_host = str(meta.get('imghost') or default_cfg.get('img_host_1') or '')
                        if (
                            current_img_host
                            and current_img_host not in host_order
                            and (allowed_hosts is None or current_img_host in allowed_hosts)
                        ):
                            host_order.insert(0, current_img_host)

                        if not host_order and allowed_hosts:
                            host_order = list(allowed_hosts)

                        start_index = host_order.index(current_img_host) if current_img_host in host_order else 0
                        image_list_count = 0

                        for idx in range(start_index, len(host_order)):
                            meta['imghost'] = host_order[idx]
                            await uploadscreens_manager.upload_screens(
                                meta, meta['screens'], 1, 0, meta['screens'], [], return_dict=return_dict, allowed_hosts=allowed_hosts
                            )
                            image_list_count = len(meta.get('image_list', []) or [])
                            if meta.get('debug'):
                                console.print(
                                    f"[cyan]Image host debug: post-upload_screens image_list={image_list_count}[/cyan]"
                                )

                            if image_list_count >= min_successful_uploads:
                                break

                            if idx + 1 < len(host_order):
                                console.print(
                                    f"[yellow]Only {image_list_count} images uploaded; minimum is {min_successful_uploads}. "
                                    f"Switching to next host: {host_order[idx + 1]}[/yellow]"
                                )

                        if image_list_count < min_successful_uploads:
                            raise Exception(
                                f"Minimum of {min_successful_uploads} successful image uploads required, but only "
                                f"{image_list_count} were uploaded."
                            )

                        # Now that image_list exists, populate tracker-specific keys (and only reupload if required)
                        for tracker_name in relevant_trackers:
                            tracker_instance = tracker_class_map[tracker_name](config=config)
                            if meta.get('debug'):
                                key = f"{tracker_name}_images_key"
                                console.print(
                                    f"[cyan]Image host debug: post-upload before {tracker_name}.check_image_hosts() image_list={len(meta.get('image_list', []) or [])} {key}={len(meta.get(key, []) or [])}[/cyan]"  # noqa: E501
                                )
                            await tracker_instance.check_image_hosts(meta)
                            if meta.get('debug'):
                                key = f"{tracker_name}_images_key"
                                console.print(
                                    f"[cyan]Image host debug: post-upload after  {tracker_name}.check_image_hosts() image_list={len(meta.get('image_list', []) or [])} {key}={len(meta.get(key, []) or [])}[/cyan]"  # noqa: E501
                                )
                    except asyncio.CancelledError:
                        console.print("\n[red]Upload process interrupted! Cancelling tasks...[/red]")
                        return
                    except Exception as e:
                        raise e
                    finally:
                        cleanup_manager.reset_terminal()
                        if meta['debug']:
                            console.print("[yellow]Cleaning up resources...[/yellow]")
                        gc.collect()

                elif meta.get('skip_imghost_upload', False) is True and meta.get('image_list', False) is False:
                    meta['image_list'] = []

                async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(meta, indent=4))

                if 'image_list' in meta and meta['image_list']:
                    try:
                        image_list = cast(list[Any], meta.get('image_list') or [])
                        image_data = {
                            "image_list": image_list,
                            "image_sizes": meta.get('image_sizes', {}),
                            "tonemapped": meta.get('tonemapped', False)
                        }

                        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/image_data.json", 'w', encoding='utf-8') as img_file:
                            await img_file.write(json.dumps(image_data, indent=4))

                        if meta.get('debug'):
                            console.print(f"[cyan]Saved {len(image_list)} images to image_data.json")
                    except Exception as e:
                        console.print(f"[yellow]Failed to save image data: {str(e)}")
        finally:
            progress_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await progress_task

        torrent_path = os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")
        if meta.get('force_recheck', False):
            waiter = Wait(config)
            await waiter.select_and_recheck_best_torrent(meta, meta['path'], check_interval=5)
        if not os.path.exists(torrent_path):
            reuse_torrent = None
            if meta.get('rehash', False) is False and not meta['base_torrent_created'] and not meta['we_checked_them_all']:
                reuse_torrent = await client.find_existing_torrent(meta)
                if reuse_torrent is not None:
                    await TorrentCreator.create_base_from_existing_torrent(reuse_torrent, meta['base_dir'], meta['uuid'])

            if meta['nohash'] is False and reuse_torrent is None:
                await TorrentCreator.create_torrent(meta, Path(meta['path']), "BASE")
            if meta['nohash']:
                meta['client'] = "none"

        elif os.path.exists(torrent_path) and meta.get('rehash', False) is True and meta['nohash'] is False:
            await TorrentCreator.create_torrent(meta, Path(meta['path']), "BASE")

        if os.path.exists(torrent_path):
            raw_trackers = meta.get('trackers')
            if isinstance(raw_trackers, str):
                trackers_list = [raw_trackers]
            elif isinstance(raw_trackers, list):
                trackers_list = [str(t) for t in cast(list[Any], raw_trackers) if str(t).strip()]
            else:
                trackers_list = []
            trackers_upper = [str(t).strip().upper() for t in trackers_list if str(t).strip()]

            base_piece_mb: Optional[int] = cast(Optional[int], meta.get('base_torrent_piece_mb'))
            if base_piece_mb is None and any(t in {"HDB", "MTV", "PTP"} for t in trackers_upper):
                try:
                    torrent = await asyncio.to_thread(Torrent.read, torrent_path)
                    base_piece_mb = int(torrent.piece_size // (1024 * 1024))
                    meta['base_torrent_piece_mb'] = base_piece_mb
                except Exception as e:
                    if meta.get('debug', False):
                        console.print(f"[yellow]Unable to cache BASE.torrent piece size: {e}")
                    base_piece_mb = None

            if "MTV" in trackers_upper:
                mtv_cfg = config.get('TRACKERS', {}).get('MTV', {})
                if str(mtv_cfg.get('skip_if_rehash', 'false')).lower() == 'true' and base_piece_mb and base_piece_mb > 8:
                    meta['trackers'] = [t for t in trackers_list if str(t).strip().upper() != "MTV"]
                    trackers_list = [str(t) for t in cast(list[Any], meta.get('trackers') or []) if str(t).strip()]
                    trackers_upper = [str(t).strip().upper() for t in trackers_list if str(t).strip()]
                    if meta.get('debug', False):
                        console.print("[yellow]Removed MTV from trackers due to skip_if_rehash config and 8 MiB limit.[/yellow]")
                    if not meta['trackers']:
                        console.print("[red]No trackers remain after removing MTV for skip_if_rehash.[/red]")
                        meta['we_are_uploading'] = False
                        return

        if int(meta.get('randomized', 0)) >= 1 and not meta['mkbrr']:
            TorrentCreator.create_random_torrents(meta['base_dir'], meta['uuid'], meta['randomized'], meta['path'])

        meta = await gen_desc(meta, takescreens_manager, uploadscreens_manager)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/meta.json", 'w', encoding='utf-8') as f:
            await f.write(json.dumps(meta, indent=4))


async def cleanup_screenshot_temp_files(meta: Meta) -> None:
    """Cleanup temporary screenshot files to prevent orphaned files in case of failures."""
    tmp_dir = f"{meta['base_dir']}/tmp/{meta['uuid']}"
    if os.path.exists(tmp_dir):
        try:
            for file in os.listdir(tmp_dir):
                file_path = os.path.join(tmp_dir, file)
                if os.path.isfile(file_path) and file.endswith((".png", ".jpg")):
                    os.remove(file_path)
                    if meta['debug']:
                        console.print(f"[yellow]Removed temporary screenshot file: {file_path}[/yellow]")
        except Exception as e:
            console.print(f"[red]Error cleaning up temporary screenshot files: {e}[/red]", highlight=False)


async def save_processed_file(log_file: str, file_path: str) -> None:
    """
    Adds a processed file to the log, deduplicating and always appending to the end.
    """
    if os.path.exists(log_file):
        async with aiofiles.open(log_file, encoding='utf-8') as f:
            try:
                content = await f.read()
                loaded: Any = json.loads(content) if content.strip() else []
                processed_files = cast(list[Any], loaded) if isinstance(loaded, list) else []
            except Exception:
                processed_files = []
    else:
        processed_files = []

    processed_files_clean: list[str] = [str(entry) for entry in processed_files if entry != file_path]
    processed_files_clean.append(file_path)

    async with aiofiles.open(log_file, "w", encoding='utf-8') as f:
        await f.write(json.dumps(processed_files_clean, indent=4))


def get_local_version(version_file: str) -> Optional[str]:
    """Extracts the local version from the version.py file."""
    try:
        with open(version_file, encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)
        else:
            console.print("[red]Version not found in local file.")
            return None
    except FileNotFoundError:
        console.print("[red]Version file not found.")
        return None


def get_remote_version(url: str) -> tuple[Optional[str], Optional[str]]:
    """Fetches the latest version information from the remote repository."""
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            content = response.text
            match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
            if match:
                return match.group(1), content
            else:
                console.print("[red]Version not found in remote file.")
                return None, None
        else:
            console.print(f"[red]Failed to fetch remote version file. Status code: {response.status_code}")
            return None, None
    except requests.RequestException as e:
        console.print(f"[red]An error occurred while fetching the remote version file: {e}")
        return None, None


def extract_changelog(content: str, to_version: str) -> Optional[str]:
    """Extracts the changelog entries between the specified versions."""
    # Try to find the to_version with 'v' prefix first (current format)
    patterns_to_try = [
        rf'__version__\s*=\s*"{re.escape(to_version)}"\s*\n\s*"""\s*(.*?)\s*"""',  # Try with 'v' prefix
        rf'__version__\s*=\s*"{re.escape(to_version.lstrip("v"))}"\s*\n\s*"""\s*(.*?)\s*"""'  # Try without 'v' prefix
    ]

    for pattern in patterns_to_try:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            changelog = match.group(1).strip()
            # Remove the comment markers (# ) that were added by the GitHub Action
            changelog = re.sub(r'^# ', '', changelog, flags=re.MULTILINE)
            return changelog

    return None


async def update_notification(base_dir: str) -> Optional[str]:
    version_file = os.path.join(base_dir, 'data', 'version.py')
    remote_version_url = 'https://raw.githubusercontent.com/Audionut/Upload-Assistant/master/data/version.py'

    notice = config['DEFAULT'].get('update_notification', True)
    verbose = config['DEFAULT'].get('verbose_notification', False)

    local_version = get_local_version(version_file)
    if not local_version:
        return None

    if not notice:
        return local_version

    remote_version, remote_content = get_remote_version(remote_version_url)
    if not remote_version:
        return local_version

    if version.parse(remote_version) > version.parse(local_version):
        console.print(f"[red][NOTICE] [green]Update available: v[/green][yellow]{remote_version}")
        console.print(f"[red][NOTICE] [green]Current version: v[/green][yellow]{local_version}")
        asyncio.create_task(asyncio.sleep(1))
        if verbose and remote_content:
            changelog = extract_changelog(remote_content, remote_version)
            if changelog:
                asyncio.create_task(asyncio.sleep(1))
                console.print(f"{changelog}")
            else:
                console.print("[yellow]Changelog not found between versions.[/yellow]")

    return local_version


async def do_the_thing(base_dir: str) -> None:
    await asyncio.sleep(0.1)  # Ensure it's not racing

    tmp_dir = os.path.join(base_dir, "tmp")
    if not os.path.exists(tmp_dir):
        if os.name != 'nt':
            os.makedirs(tmp_dir, mode=0o700, exist_ok=True)
        else:
            os.makedirs(tmp_dir, exist_ok=True)
    else:
        # Ensure existing directory has secure permissions
        if os.name != 'nt':
            os.chmod(tmp_dir, 0o700)

    def ensure_secure_tmp_subdir(subdir_path: str) -> None:
        """Ensure tmp subdirectories are created with secure permissions (0o700)"""
        if not os.path.exists(subdir_path):
            if os.name != 'nt':
                os.makedirs(subdir_path, mode=0o700, exist_ok=True)
            else:
                os.makedirs(subdir_path, exist_ok=True)
        else:
            if os.name != 'nt':
                os.chmod(subdir_path, 0o700)

    bot: Any = None
    connect_task: Optional[asyncio.Task[None]] = None
    meta: Meta = {}
    paths: list[str] = []
    for each in sys.argv[1:]:
        if os.path.exists(each):
            paths.append(os.path.abspath(each))
        else:
            break

    meta['ua_name'] = 'Upload Assistant'
    meta['current_version'] = await update_notification(base_dir)

    signature = 'Created by Upload Assistant'
    if meta.get('current_version', ''):
        signature += f" {meta['current_version']}"
    meta['ua_signature'] = signature
    meta['base_dir'] = base_dir

    cleanup_only = any(arg in ('--cleanup', '-cleanup') for arg in sys.argv) and len(sys.argv) <= 2
    sanitize_meta = config['DEFAULT'].get('sanitize_meta', True)

    try:
        # If cleanup is the only operation, use a dummy path to satisfy the parser
        if cleanup_only:
            args_list = sys.argv[1:] + ['dummy_path']
            meta, _help, _before_args = cast(tuple[Meta, Any, Any], parser.parse(list(' '.join(args_list).split(' ')), meta))
            meta['path'] = None  # Clear the dummy path after parsing
        else:
            meta, _help, _before_args = cast(tuple[Meta, Any, Any], parser.parse(list(' '.join(sys.argv[1:]).split(' ')), meta))

        # Start web UI if requested (exclusive mode - doesn't continue with uploads)
        if meta.get('webui'):
            webui_addr = meta['webui']
            if ':' not in webui_addr:
                console.print("[red]Invalid web UI address format. Use HOST:PORT[/red]")
                sys.exit(1)

            try:
                host, port_str = webui_addr.split(':', 1)
                port = int(port_str)
            except ValueError:
                console.print("[red]Invalid port number in web UI address[/red]")
                sys.exit(1)

            console.print(f"[green]Starting Web UI server on {host}:{port}...[/green]")

            from waitress import serve

            from web_ui.server import app, set_runtime_browse_roots

            # Set browse roots for web UI
            browse_roots = os.environ.get('UA_BROWSE_ROOTS', '').strip()
            if not browse_roots and meta.get('path'):
                # Use the path from command line as browse roots
                path_value = meta['path']
                browse_roots = ' '.join(str(p) for p in cast(list[Any], path_value)) if isinstance(path_value, list) else str(path_value)
            if not browse_roots:
                browse_roots = '.'  # Fallback to current directory

            set_runtime_browse_roots(browse_roots)

            try:
                serve(app, host=host, port=port)
            except Exception as e:
                console.print(f"[red]Web UI server error: {e}[/red]")
                sys.exit(1)
            return  # Exit early when running web UI only

        # Validate config structure and types (after args parsed so we have trackers list)
        from src.configvalidator import group_warnings, validate_config

        # Get active trackers from meta (parsed from command line) or fall back to config default
        active_trackers: Optional[list[str]] = None
        if meta.get('trackers'):
            if isinstance(meta['trackers'], str):
                active_trackers = [t.strip().upper() for t in meta['trackers'].split(',') if t.strip()]
            elif isinstance(meta['trackers'], list):
                trackers_list = cast(list[Any], meta['trackers'])
                active_trackers = [str(t).strip().upper() for t in trackers_list if str(t).strip()]

        # Get active imghost from meta (parsed from command line)
        active_imghost: Optional[str] = None
        if meta.get('imghost'):
            imghost_val = str(meta.get('imghost', '')).strip()
            if imghost_val:
                active_imghost = imghost_val

        is_valid, config_errors, config_warnings = validate_config(config, active_trackers, active_imghost)

        if not is_valid:
            console.print("[bold red]Configuration validation failed:[/bold red]")
            for error in config_errors:
                console.print(f"[red]  ✗ {error}[/red]")
            console.print("[red]\nPlease fix the above errors in your config.py[/red]")
            console.print("[yellow]Reference: https://github.com/Audionut/Upload-Assistant/blob/master/data/example-config.py[/yellow]")
            raise SystemExit(1)

        if config_warnings:
            suppress_warnings = config.get('DEFAULT', {}).get('suppress_warnings', False)
            if not suppress_warnings:
                grouped = group_warnings(config_warnings)
                console.print(f"[yellow]Config validation passed with {len(grouped)} warning(s):[/yellow]")
                for warning_str in grouped:
                    console.print(f"[yellow]  ⚠ {warning_str}[/yellow]")
                console.print()  # Blank line after warnings

        if meta.get('cleanup'):
            if os.path.exists(f"{base_dir}/tmp"):
                shutil.rmtree(f"{base_dir}/tmp")
                console.print("[yellow]Successfully emptied tmp directory[/yellow]")
                console.print()
            if not meta.get('path') or cleanup_only:
                exit(0)

        if not meta.get('path'):
            exit(0)

        path = cast(str, meta['path'])
        path = os.path.abspath(path)
        if path.endswith('"'):
            path = path[:-1]

        is_binary = await get_mkbrr_path(meta, base_dir)
        if not meta['mkbrr']:
            try:
                meta['mkbrr'] = int(config['DEFAULT'].get('mkbrr', False))
            except ValueError:
                if meta['debug']:
                    console.print("[yellow]Invalid mkbrr config value, defaulting to False[/yellow]")
                meta['mkbrr'] = False
        if meta['mkbrr'] and not is_binary:
            console.print("[bold red]mkbrr binary is not available. Please ensure it is installed correctly.[/bold red]")
            console.print("[bold red]Reverting to Torf[/bold red]")
            console.print()
            meta['mkbrr'] = False

        queue, log_file = await QueueManager.handle_queue(path, meta, paths, base_dir)
        queue_list = cast(list[Any], queue)

        processed_files_count = 0
        skipped_files_count = 0
        base_meta = dict(meta.items())

        for queue_item in queue_list:
            total_files = len(queue_list)
            bot = None
            current_item_path = ""
            tmp_path = ""
            try:
                meta = base_meta.copy()

                if meta.get('site_upload_queue'):
                    # Extract path and metadata from site upload queue item
                    queue_item_mapping = cast(Mapping[str, Any], queue_item)
                    path = await QueueManager.process_site_upload_item(queue_item_mapping, meta)
                    current_item_path = path  # Store for logging
                else:
                    # Regular queue processing
                    path = queue_item if isinstance(queue_item, str) else str(queue_item)
                    current_item_path = path

                meta['path'] = path
                meta['uuid'] = None

                if not path:
                    raise ValueError("The 'path' variable is not defined or is empty.")

                tmp_path = os.path.join(base_dir, "tmp", os.path.basename(path))

                # Ensure tmp subdirectory exists with secure permissions
                ensure_secure_tmp_subdir(tmp_path)

                if meta.get('delete_tmp', False) and os.path.exists(tmp_path):
                    try:
                        shutil.rmtree(tmp_path)
                        if os.name != 'nt':
                            os.makedirs(tmp_path, mode=0o700, exist_ok=True)
                        else:
                            os.makedirs(tmp_path, exist_ok=True)
                        if meta['debug']:
                            console.print(f"[yellow]Successfully cleaned temp directory for {os.path.basename(path)}[/yellow]")
                            console.print()
                    except Exception as e:
                        console.print(f"[bold red]Failed to delete temp directory: {str(e)}")

                meta_file = os.path.join(base_dir, "tmp", os.path.basename(path), "meta.json")

                keep_meta = config['DEFAULT'].get('keep_meta', False)

                if not keep_meta or meta.get('delete_meta', False):
                    if os.path.exists(meta_file):
                        try:
                            os.remove(meta_file)
                            if meta['debug']:
                                console.print(f"[bold yellow]Found and deleted existing metadata file: {meta_file}")
                        except Exception as e:
                            console.print(f"[bold red]Failed to delete metadata file {meta_file}: {str(e)}")
                    else:
                        if meta['debug']:
                            console.print(f"[yellow]No metadata file found at {meta_file}")

                if keep_meta and os.path.exists(meta_file):
                    async with aiofiles.open(meta_file, encoding='utf-8') as f:
                        content = await f.read()
                        saved_meta = cast(dict[str, Any], json.loads(content)) if content.strip() else {}
                        console.print("[yellow]Existing metadata file found, it holds cached values")
                        await merge_meta(meta, saved_meta)

            except Exception as e:
                console.print(f"[red]Exception: '{path}': {e}")
                cleanup_manager.reset_terminal()

            discord_bot_token = discord_config.get('discord_bot_token') if discord_config is not None else None
            only_unattended = bool(discord_config.get('only_unattended', False)) if discord_config is not None else False

            if (
                use_discord
                and discord_config is not None
                and isinstance(discord_bot_token, str)
                and discord_bot_token
                and not meta['debug']
                and ((only_unattended and meta.get('unattended', False)) or not only_unattended)
            ):
                try:
                    console.print("[cyan]Starting Discord bot initialization...")
                    intents = discord.Intents.default()
                    intents.message_content = True
                    bot = discord.Client(intents=intents)
                    token = discord_bot_token
                    await asyncio.wait_for(bot.login(token), timeout=10)
                    connect_task = asyncio.create_task(bot.connect())

                    try:
                        await asyncio.wait_for(bot.wait_until_ready(), timeout=20)
                        console.print("[green]Discord Bot is ready!")
                    except asyncio.TimeoutError:
                        console.print("[bold red]Bot failed to connect within timeout period.")
                        console.print("[yellow]Continuing without Discord integration...")
                        if 'connect_task' in locals():
                            connect_task.cancel()
                except discord.LoginFailure:
                    console.print("[bold red]Discord bot token is invalid. Please check your configuration.")
                except discord.ClientException as e:
                    console.print(f"[bold red]Discord client exception: {e}")
                except Exception as e:
                    console.print(f"[bold red]Unexpected error during Discord bot initialization: {e}")

            start_time = 0.0
            if meta['debug']:
                start_time = time.time()

            console.print(f"[green]Gathering info for {os.path.basename(path)}")

            await process_meta(meta, base_dir, bot=bot)
            tracker_setup = TRACKER_SETUP(config=config)
            if 'we_are_uploading' not in meta or not meta.get('we_are_uploading', False):
                if config['DEFAULT'].get('cross_seeding', True):
                    await process_cross_seeds(meta)
                if not meta.get('site_check', False):
                    if not meta.get('emby', False):
                        console.print("we are not uploading.......")
                    if 'queue' in meta and meta.get('queue') is not None:
                        processed_files_count += 1
                        if not meta.get('emby', False):
                            skipped_files_count += 1
                            console.print(f"[cyan]Processed {processed_files_count}/{total_files} files with {skipped_files_count} skipped uploading.")
                        else:
                            console.print(f"[cyan]Processed {processed_files_count}/{total_files}.")
                        if log_file and (not meta['debug'] or "debug" in os.path.basename(log_file)):
                            if meta.get('site_upload_queue'):
                                await QueueManager.save_processed_path(log_file, current_item_path)
                            else:
                                await save_processed_file(log_file, path)

            else:
                console.print()
                console.print("[yellow]Processing uploads to trackers.....")
                meta['are_we_trump_reporting'] = False
                if meta.get('were_trumping', False):
                    console.print("[yellow]Checking for existing trump reports.....")
                    trump_trackers = [t for t in cast(list[Any], meta.get('trackers', [])) if isinstance(t, str)]
                    is_trumping = await tracker_setup.process_trumpables(meta, trackers=trump_trackers)

                    # Apply any per-tracker skip decisions made during trumpable processing
                    skip_upload_trackers = set(meta.get('skip_upload_trackers', []) or [])
                    tracker_status = cast(dict[str, dict[str, Any]], meta.get('tracker_status') or {})
                    for t, st in tracker_status.items():
                        if st.get('skip_upload') is True:
                            skip_upload_trackers.add(t)

                    if skip_upload_trackers:
                        for t in skip_upload_trackers:
                            per_tracker = tracker_status.setdefault(t, {})
                            per_tracker['upload'] = False
                            per_tracker['skipped'] = True

                        meta['tracker_status'] = tracker_status

                        meta['trackers'] = [t for t in meta.get('trackers', []) if t not in skip_upload_trackers]
                        if meta.get('debug', False):
                            console.print(f"[yellow]Skipping trackers due to trump report selection: {', '.join(sorted(skip_upload_trackers))}[/yellow]")

                        if not meta['trackers']:
                            console.print("[bold red]No trackers left to upload after trump checking.[/bold red]")
                            meta['are_we_trump_reporting'] = False

                    if is_trumping:
                        meta['are_we_trump_reporting'] = True

                # we're uploading. the hardcoded successful_trackers = 10 is to bypass the skip_uploading check if not doing double dupe check
                # allowing the skip uploading feature to only apply when double dupe checking is enabled
                successful_trackers = 10
                if meta.get('dupe_again', False):
                    console.print("[yellow]Performing double dupe check on trackers that passed initial upload checks.....[/yellow]")
                    raw_trackers_list = meta.get('trackers', [])
                    trackers_list: list[str]
                    if isinstance(raw_trackers_list, list):
                        trackers_list = [t for t in cast(list[Any], raw_trackers_list) if isinstance(t, str)]
                    else:
                        trackers_list = []
                        meta['trackers'] = trackers_list

                    for tracker in list(trackers_list):
                        tracker_status = cast(dict[str, Any], meta.get('tracker_status', {})).get(tracker, {})
                        if tracker_status.get('upload') is not True:
                            if meta.get('debug'):
                                console.print(f"[yellow]{tracker} was previously marked to skip upload. Skipping double dupe check.[/yellow]")
                            trackers_list.remove(tracker)
                            tracker_status_map = cast(dict[str, Any], meta.get('tracker_status', {}))
                            tracker_status_map.pop(tracker, None)
                            meta['tracker_status'] = tracker_status_map
                            continue

                    if trackers_list:
                        successful_trackers = await TrackerStatusManager(config=config).process_all_trackers(meta)
                    else:
                        successful_trackers = 0

                skip_uploading = meta.get('skip_uploading')
                skip_uploading_int = int(skip_uploading) if isinstance(skip_uploading, (int, str)) else 0

                if successful_trackers < skip_uploading_int and not meta['debug']:
                    console.print(f"[red]Not enough successful trackers ({successful_trackers}/{skip_uploading_int}). No uploads being processed.[/red]")
                else:
                    await process_trackers(
                        meta,
                        config,
                        client,
                        console,
                        list(api_trackers),
                        tracker_class_map,
                        list(http_trackers),
                        list(other_api_trackers),
                    )
                    if use_discord and bot:
                        await DiscordNotifier.send_upload_status_notification(config, bot, meta)

                    if config['DEFAULT'].get('cross_seeding', True):
                        await process_cross_seeds(meta)

                    if 'queue' in meta and meta.get('queue') is not None:
                        processed_files_count += 1
                        if 'limit_queue' in meta and int(meta['limit_queue']) > 0:
                            console.print(f"[cyan]Successfully uploaded {processed_files_count - skipped_files_count} of {meta['limit_queue']} in limit with {total_files} files.")
                        else:
                            console.print(f"[cyan]Successfully uploaded {processed_files_count - skipped_files_count}/{total_files} files.")
                        if log_file and (not meta['debug'] or "debug" in os.path.basename(log_file)):
                            if meta.get('site_upload_queue'):
                                await QueueManager.save_processed_path(log_file, current_item_path)
                            else:
                                await save_processed_file(log_file, path)

            if meta['debug']:
                finish_time = time.time()
                console.print(f"Uploads processed in {finish_time - start_time:.4f} seconds")

            def build_tracker_status_line(tracker: str, status: Any) -> str:
                try:
                    if not isinstance(status, dict):
                        return f"Error printing {tracker} data: invalid status type\n"

                    status_dict = cast(dict[str, Any], status)
                    status_message = status_dict.get('status_message')

                    if tracker == "MTV" and status_message is not None and "data error" not in str(status_message):
                        return f"{str(status_message)}\n"

                    if 'torrent_id' in status_dict:
                        tracker_class = tracker_class_map[tracker](config=config)
                        torrent_url = tracker_class.torrent_url
                        return f"{tracker}: {torrent_url}{status_dict['torrent_id']}\n"

                    if status_message is not None and "data error" not in str(status_message) and tracker != "MTV":
                        return f"{tracker}: {Redaction.redact_private_info(status_message)}\n"

                    if status_message is not None and "data error" in str(status_message):
                        return f"{tracker}: {str(status_message)}\n"

                    if status_dict.get('skipping') is False:
                        return f"{tracker} gave no useful message.\n"

                    return ""
                except Exception as exc:
                    return f"Error printing {tracker} data: {exc}\n"

            if use_discord and bot:
                send_upload_links = bool(discord_config.get('send_upload_links', False)) if discord_config is not None else False
                if send_upload_links:
                    try:
                        discord_message = ""
                        for tracker, status in cast(dict[str, Any], meta.get('tracker_status', {})).items():
                            discord_message += build_tracker_status_line(tracker, status)
                        discord_message += "All tracker uploads processed.\n"
                        await DiscordNotifier.send_discord_notification(
                            config, bot, discord_message, debug=meta.get('debug', False), meta=meta
                        )
                    except Exception as e:
                        console.print(f"[red]Error in tracker print loop: {e}[/red]")
                else:
                    await DiscordNotifier.send_discord_notification(
                        config, bot, f"Finished uploading: {meta['path']}\n", debug=meta.get('debug', False), meta=meta
                    )

            if meta.get('are_we_trump_reporting', False):
                console.print()
                for tracker in meta.get('trumping_trackers', []):
                    console.print(f"[yellow]Submitting trumpable report to {tracker}.....")
                    await tracker_setup.make_trumpable_report(meta, tracker)

            find_requests = config['DEFAULT'].get('search_requests', False) if meta.get('search_requests') is None else meta.get('search_requests')
            if find_requests and meta['trackers'] not in ([], None, "") and not (meta.get('site_check', False) and not meta['is_disc']):
                console.print("[green]Searching for requests on supported trackers.....")
                if meta.get('site_check', False):
                    trackers = meta['requested_trackers']
                    if meta['debug']:
                        console.print(f"[cyan]Using requested trackers for site check: {trackers}[/cyan]")
                else:
                    trackers = [t for t in cast(list[Any], meta.get('trackers', [])) if isinstance(t, str)]
                    if meta['debug']:
                        console.print(f"[cyan]Using trackers for request search: {trackers}[/cyan]")
                await tracker_setup.tracker_request(meta, trackers)

            if meta.get('site_check', False) and 'queue' in meta and meta.get('queue') is not None:
                processed_files_count += 1
                skipped_files_count += 1
                console.print(f"[cyan]Processed {processed_files_count}/{total_files} files.")
                if log_file and (not meta['debug'] or "debug" in os.path.basename(log_file)):
                    if meta.get('site_upload_queue'):
                        await QueueManager.save_processed_path(log_file, current_item_path)
                    else:
                        await save_processed_file(log_file, path)

            if meta.get('delete_tmp', False) and tmp_path and os.path.exists(tmp_path) and meta.get('emby', False):
                try:
                    shutil.rmtree(tmp_path)
                    console.print(f"[yellow]Successfully deleted temp directory for {os.path.basename(path)}[/yellow]")
                    console.print()
                except Exception as e:
                    console.print(f"[bold red]Failed to delete temp directory: {str(e)}")

            if 'limit_queue' in meta and int(meta['limit_queue']) > 0 and (processed_files_count - skipped_files_count) >= int(meta['limit_queue']):
                if sanitize_meta and not meta.get('emby', False):
                    try:
                        await asyncio.sleep(0.2)  # We can't race the status prints
                        meta = await Redaction.clean_meta_for_export(meta)
                    except Exception as e:
                        console.print(f"[red]Error cleaning meta for export: {e}")
                await cleanup_manager.cleanup()
                gc.collect()
                cleanup_manager.reset_terminal()
                break

            if sanitize_meta and not meta.get('emby', False):
                try:
                    await asyncio.sleep(0.2)
                    meta = await Redaction.clean_meta_for_export(meta)
                except Exception as e:
                    console.print(f"[red]Error cleaning meta for export: {e}")
            await cleanup_manager.cleanup()
            gc.collect()
            cleanup_manager.reset_terminal()

    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}")
        if sanitize_meta:
            meta = await Redaction.clean_meta_for_export(meta)
        console.print(traceback.format_exc())
        cleanup_manager.reset_terminal()

    finally:
        if bot is not None:
            await bot.close()
        if connect_task is not None:
            connect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await connect_task
        if not sys.stdin.closed:
            cleanup_manager.reset_terminal()


async def process_cross_seeds(meta: Meta) -> None:
    all_trackers: set[str] = set(api_trackers) | set(http_trackers) | set(other_api_trackers)

    # Get list of trackers to exclude (already in client)
    remove_list: list[str] = []
    if meta.get('remove_trackers', False):
        if isinstance(meta['remove_trackers'], str):
            remove_list = [t.strip().upper() for t in meta['remove_trackers'].split(',')]
        elif isinstance(meta['remove_trackers'], list):
            remove_list = [t.strip().upper() for t in cast(list[Any], meta['remove_trackers']) if isinstance(t, str)]

    # Check for trackers that haven't been dupe-checked yet
    dupe_checked_trackers = [
        t for t in cast(list[Any], meta.get('dupe_checked_trackers', [])) if isinstance(t, str)
    ]

    # Validate tracker configs and build list of valid unchecked trackers
    valid_unchecked_trackers: list[str] = []
    for tracker in all_trackers:
        if tracker in dupe_checked_trackers or meta.get(f'{tracker}_cross_seed', None) is not None or tracker in remove_list:
            continue

        tracker_config = config.get('TRACKERS', {}).get(tracker, {})
        if not tracker_config:
            if meta.get('debug'):
                console.print(f"[yellow]Tracker {tracker} not found in config, skipping[/yellow]")
            continue

        api_key = tracker_config.get('api_key', '')
        announce_url = tracker_config.get('announce_url', '')

        # Ensure both values are strings and strip whitespace
        api_key = str(api_key).strip() if api_key else ''
        announce_url = str(announce_url).strip() if announce_url else ''

        # Skip if both api_key and announce_url are empty
        if not api_key and not announce_url:
            if meta.get('debug'):
                console.print(f"[yellow]Tracker {tracker} has no api_key or announce_url set, skipping[/yellow]")
            continue

        # Skip trackers with placeholder announce URLs
        placeholder_patterns = ['<PASSKEY>', 'customannounceurl', 'get from upload page', 'Custom_Announce_URL', 'PASS_KEY', 'insertyourpasskeyhere']
        announce_url_lower = announce_url.lower()
        if any(pattern.lower() in announce_url_lower for pattern in placeholder_patterns):
            if meta.get('debug'):
                console.print(f"[yellow]Tracker {tracker} has placeholder announce_url, skipping[/yellow]")
            continue

        valid_unchecked_trackers.append(tracker)

    # Search for cross-seeds on unchecked trackers
    if valid_unchecked_trackers and config['DEFAULT'].get('cross_seed_check_everything', False):
        console.print(f"[cyan]Checking for cross-seeds on unchecked trackers: {valid_unchecked_trackers}[/cyan]")

        try:
            await validate_tracker_logins(meta, valid_unchecked_trackers)
            await asyncio.sleep(0.2)
        except Exception as e:
            console.print(f"[yellow]Warning: Tracker validation encountered an error: {e}[/yellow]")

        # Store original unattended value
        original_unattended = meta.get('unattended', False)
        meta['unattended'] = True

        helper = UploadHelper(config)
        dupe_checker = DupeChecker(config)

        async def check_tracker_for_dupes(tracker: str) -> None:
            try:
                tracker_class = tracker_class_map[tracker](config=config)
                disctype = meta.get('disctype', '')

                # Search for existing torrents
                if tracker != "PTP":
                    dupes = await tracker_class.search_existing(meta, disctype)
                else:
                    ptp = PTP(config=config)
                    group_id = meta.get('ptp_groupID')
                    if not group_id:
                        group_id = await ptp.get_group_by_imdb(meta['imdb'])
                        meta['ptp_groupID'] = group_id
                    if group_id is None:
                        return
                    dupes = await ptp.search_existing(group_id, meta, disctype)

                if dupes:
                    dupes = await dupe_checker.filter_dupes(dupes, meta, tracker)
                    _is_dupe, updated_meta = await helper.dupe_check(cast(list[Any], dupes), meta, tracker)
                    # Persist any updates from dupe_check (defensive in case it returns a copy)
                    if updated_meta is not meta:
                        meta.update(updated_meta)

            except Exception as e:
                if meta.get('debug'):
                    console.print(f"[yellow]Error checking {tracker} for cross-seeds: {e}[/yellow]")

        # Run all dupe checks concurrently
        await asyncio.gather(*[check_tracker_for_dupes(tracker) for tracker in valid_unchecked_trackers], return_exceptions=True)

        # Restore original unattended value
        meta['unattended'] = original_unattended

    # Filter to only trackers with cross-seed data
    valid_trackers = [tracker for tracker in all_trackers if meta.get(f'{tracker}_cross_seed', None) is not None]

    if not valid_trackers:
        if meta.get('debug'):
            console.print("[yellow]No trackers found with cross-seed data[/yellow]")
        return

    console.print(f"[cyan]Valid trackers for cross-seed check: {valid_trackers}[/cyan]")

    common = COMMON(config)
    try:
        concurrency_limit = int(config.get('DEFAULT', {}).get('cross_seed_concurrency', 8))
    except (TypeError, ValueError):
        concurrency_limit = 8
    semaphore = asyncio.Semaphore(max(1, concurrency_limit))
    debug = meta.get('debug', False)

    async def handle_cross_seed(tracker: str) -> None:
        cross_seed_key = f'{tracker}_cross_seed'
        cross_seed_value = meta.get(cross_seed_key, False)

        if debug:
            console.print(f"[cyan]Debug: {tracker} - cross_seed: {Redaction.redact_private_info(cross_seed_value)}")

        if not cross_seed_value:
            return

        if debug:
            console.print(f"[green]Found cross-seed for {tracker}!")

        download_url = ""
        if isinstance(cross_seed_value, str) and cross_seed_value.startswith('http'):
            download_url = cross_seed_value
        else:
            if meta.get('debug'):
                console.print(f"[yellow]Invalid cross-seed URL for {tracker}, skipping[/yellow]")
            return

        headers = None
        if tracker == "RTF":
            headers = {
                'accept': 'application/json',
                'Authorization': config['TRACKERS'][tracker]['api_key'].strip(),
            }

        if tracker == "AR" and download_url:
            try:
                ar = AR(config=config)
                auth_key = await ar.get_auth_key(meta)

                # Extract torrent_pass from announce_url
                announce_url = config['TRACKERS']['AR'].get('announce_url', '')
                # Pattern: http://tracker.alpharatio.cc:2710/PASSKEY/announce
                match = re.search(r':\d+/([^/]+)/announce', announce_url)
                torrent_pass = match.group(1) if match else None

                if auth_key and torrent_pass:
                    # Append auth_key and torrent_pass to download_url
                    separator = '&' if '?' in download_url else '?'
                    download_url += f"{separator}authkey={auth_key}&torrent_pass={torrent_pass}"
                    if debug:
                        console.print("[cyan]Added AR auth_key and torrent_pass to download URL[/cyan]")
            except Exception as e:
                if debug:
                    console.print(f"[yellow]Error getting AR auth credentials: {e}[/yellow]")

        async with semaphore:
            await common.download_tracker_torrent(
                meta,
                tracker,
                headers=headers,
                params=None,
                downurl=download_url,
                hash_is_id=False,
                cross=True
            )
            await client.add_to_client(meta, tracker, cross=True)

    tasks = [(tracker, asyncio.create_task(handle_cross_seed(tracker))) for tracker in valid_trackers]

    results = await asyncio.gather(*(task for _, task in tasks), return_exceptions=True)
    for (tracker, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            console.print(f"[red]Cross-seed handling failed for {tracker}: {result}[/red]")


async def get_mkbrr_path(meta: Meta, base_dir: Optional[str] = None) -> Optional[str]:
    try:
        resolved_base_dir = base_dir or os.path.abspath(os.path.dirname(__file__))
        mkbrr_path = await MkbrrBinaryManager.ensure_mkbrr_binary(
            resolved_base_dir, debug=meta['debug'], version="v1.18.0"
        )
        return str(mkbrr_path) if mkbrr_path else None
    except Exception as e:
        console.print(f"[red]Error setting up mkbrr binary: {e}[/red]")
        return None


def check_python_version() -> None:
    pyver = platform.python_version_tuple()
    if int(pyver[0]) != 3 or int(pyver[1]) < 9:
        console.print("[bold red]Python version is too low. Please use Python 3.9 or higher.")
        sys.exit(1)


async def main() -> None:
    try:
        await do_the_thing(base_dir)
    except asyncio.CancelledError:
        console.print("[red]Tasks were cancelled. Exiting safely.[/red]")
    except KeyboardInterrupt:
        console.print("[bold red]Program interrupted. Exiting safely.[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Unexpected error: {e}[/bold red]")


if __name__ == "__main__":
    check_python_version()

    try:
        # Use ProactorEventLoop for Windows subprocess handling
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        asyncio.run(main())  # Ensures proper loop handling and cleanup
    except (KeyboardInterrupt, SystemExit):
        pass
    except BaseException as e:
        console.print(f"[bold red]Critical error: {e}[/bold red]")
    finally:
        asyncio.run(cleanup_manager.cleanup())
        gc.collect()
        cleanup_manager.reset_terminal()
        sys.exit(0)
