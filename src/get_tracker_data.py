# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import json
import os
import sys
import time
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Optional, cast
from urllib.parse import urlparse

import aiohttp
import cli_ui
import requests

from src.btnid import BtnIdManager
from src.cleanup import cleanup_manager
from src.console import console
from src.trackermeta import TrackerMetaManager
from src.trackersetup import tracker_class_map


class TrackerDataManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        trackers_cfg = cast(Mapping[str, Mapping[str, Any]], config.get('TRACKERS', {}))
        if not isinstance(trackers_cfg, dict):
            raise ValueError("'TRACKERS' config section must be a dict")
        default_cfg = cast(Mapping[str, Any], config.get('DEFAULT', {}))
        if not isinstance(default_cfg, dict):
            raise ValueError("'DEFAULT' config section must be a dict")
        self.trackers_config = trackers_cfg
        self.default_config = default_cfg
        self.tracker_meta_manager = TrackerMetaManager(config)

    def get_tracker_config(self, tracker_name: str) -> Mapping[str, Any]:
        return self.trackers_config.get(tracker_name, MappingProxyType({}))

    async def get_tracker_timestamps(self, base_dir: Optional[str] = None) -> dict[str, float]:
        """Get tracker timestamps from the log file"""
        timestamp_file = os.path.join(f"{base_dir}", "data", "banned", "tracker_timestamps.json")
        try:
            if os.path.exists(timestamp_file):
                with open(timestamp_file) as f:
                    return cast(dict[str, float], json.load(f))
            return {}
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load tracker timestamps: {e}[/yellow]")
            return {}

    async def save_tracker_timestamp(self, tracker_name: str, base_dir: Optional[str] = None, debug: bool = False) -> None:
        """Save timestamp for when tracker was processed"""
        timestamp_file = os.path.join(f"{base_dir}", "data", "banned", "tracker_timestamps.json")
        try:
            os.makedirs(f"{base_dir}/data/banned", exist_ok=True)

            timestamps = await self.get_tracker_timestamps(base_dir)
            timestamps[tracker_name] = time.time()

            with open(timestamp_file, 'w') as f:
                json.dump(timestamps, f, indent=2)

            if debug:
                console.print(f"[yellow]Saved timestamp for {tracker_name} - will be available again in 60 seconds[/yellow]")

        except Exception as e:
            console.print(f"[red]Error saving tracker timestamp: {e}[/red]")

    async def get_available_trackers(
        self,
        specific_trackers: list[str],
        base_dir: Optional[str] = None,
        debug: bool = False,
    ) -> tuple[list[str], list[tuple[str, float]]]:
        """Get trackers that are available (60+ seconds since last processed)"""
        timestamps = await self.get_tracker_timestamps(base_dir)
        current_time = time.time()
        available: list[str] = []
        waiting: list[tuple[str, float]] = []

        for tracker in specific_trackers:
            cooldown_seconds = 60 if tracker == "PTP" else 15
            last_processed = timestamps.get(tracker, 0)
            time_since_last = current_time - last_processed

            if time_since_last >= cooldown_seconds:
                available.append(tracker)
            else:
                wait_time = cooldown_seconds - time_since_last
                waiting.append((tracker, wait_time))

        return available, waiting

    async def get_tracker_data(
        self,
        video: Any,
        meta: dict[str, Any],
        search_term: Optional[str] = None,
        search_file_folder: Optional[str] = None,
        cat: Optional[str] = None,
        only_id: bool = False,
    ) -> dict[str, Any]:
        found_match = False
        base_dir = meta['base_dir']
        search_term_value = search_term or ""
        search_file_folder_value = search_file_folder or ""
        if search_term:
            # Check if a specific tracker is already set in meta
            if not meta.get('emby', False):
                tracker_keys = {
                    # preference some unit3d based trackers first
                    # since they can return tmdb/imdb/tvdb ids
                    'aither': 'AITHER',
                    'blu': 'BLU',
                    'lst': 'LST',
                    'ulcx': 'ULCX',
                    'oe': 'OE',
                    'huno': 'HUNO',
                    'ant': 'ANT',
                    'btn': 'BTN',
                    'bhd': 'BHD',
                    'hdb': 'HDB',
                    'sp': 'SP',
                    'rf': 'RF',
                    'otw': 'OTW',
                    'yus': 'YUS',
                    'dp': 'DP',
                    'ptp': 'PTP',
                }
            else:
                # Preference trackers with lesser overall torrents
                # Leaving the more complete trackers free when really needed
                tracker_keys = {
                    'sp': 'SP',
                    'otw': 'OTW',
                    'dp': 'DP',
                    'yus': 'YUS',
                    'rf': 'RF',
                    'oe': 'OE',
                    'ulcx': 'ULCX',
                    'huno': 'HUNO',
                    'lst': 'LST',
                    'ant': 'ANT',
                    'hdb': 'HDB',
                    'bhd': 'BHD',
                    'blu': 'BLU',
                    'aither': 'AITHER',
                    'btn': 'BTN',
                    'ptp': 'PTP',
                }

            specific_tracker: list[str] = [tracker_keys[key] for key in tracker_keys if meta.get(key) is not None]

            # Filter out trackers that don't have valid config or api_key/announce_url
            if specific_tracker:
                valid_trackers: list[str] = []
                for tracker in specific_tracker:
                    if "BTN" in tracker:
                        valid_trackers.append(tracker)
                        continue
                    tracker_config = self.get_tracker_config(tracker)
                    api_key = tracker_config.get('api_key', '')
                    announce_url = tracker_config.get('announce_url', '')

                    if not tracker_config:
                        if meta.get('debug'):
                            console.print(f"[yellow]Tracker {tracker} not found in config, skipping[/yellow]")
                        continue

                    # Accept tracker if it has either a valid api_key or announce_url
                    has_api_key = api_key and api_key.strip() != ''
                    has_announce_url = announce_url and announce_url.strip() != ''

                    if not has_api_key and not has_announce_url:
                        if meta.get('debug'):
                            console.print(f"[yellow]Tracker {tracker} has no api_key or announce_url set, skipping[/yellow]")
                        continue

                    valid_trackers.append(tracker)

                specific_tracker = valid_trackers

            if meta['debug']:
                console.print(f"[blue]Specific trackers to check: {specific_tracker}[/blue]")

            if specific_tracker:
                if meta.get('is_disc', False) and "ANT" in specific_tracker:
                    specific_tracker.remove("ANT")
                if meta.get('category') == "MOVIE" and "BTN" in specific_tracker:
                    specific_tracker.remove("BTN")

                meta_trackers_raw = meta.get('trackers', [])
                meta_trackers: list[str]
                if isinstance(meta_trackers_raw, str):
                    meta_trackers = [t.strip().upper() for t in meta_trackers_raw.split(',')]
                elif isinstance(meta_trackers_raw, list):
                    meta_trackers_list = cast(list[Any], meta_trackers_raw)
                    meta_trackers = [str(t).upper() for t in meta_trackers_list]
                else:
                    meta_trackers = []

                # for just searching, remove any specific trackers already in meta['trackers']
                # since that tracker was found in client, and remove it from meta['trackers']
                for tracker in list(specific_tracker):
                    if tracker in meta_trackers and meta.get('site_check', False):
                        specific_tracker.remove(tracker)
                        meta_trackers.remove(tracker)

                # Update meta['trackers'] preserving list format
                if meta_trackers:
                    meta['trackers'] = meta_trackers
                else:
                    meta['trackers'] = []

                async def process_tracker(tracker_name: str, meta: dict[str, Any], only_id: bool) -> dict[str, Any]:
                    nonlocal found_match
                    tracker_factory = tracker_class_map.get(tracker_name)
                    if tracker_factory is None:
                        console.print(f"[red]Tracker class for {tracker_name} not found.[/red]")
                        return meta

                    tracker_instance = tracker_factory(config=self.config)
                    try:
                        updated_meta, match = await self.tracker_meta_manager.update_metadata_from_tracker(
                            tracker_name,
                            tracker_instance,
                            meta,
                            search_term_value,
                            search_file_folder_value,
                            only_id,
                        )
                        if match:
                            found_match = True
                            if meta.get('debug'):
                                console.print(f"[green]Match found on tracker: {tracker_name}[/green]")
                            meta['matched_tracker'] = tracker_name
                        await self.save_tracker_timestamp(tracker_name, base_dir=base_dir)
                        return cast(dict[str, Any], updated_meta)
                    except aiohttp.ClientSSLError:
                        await self.save_tracker_timestamp(tracker_name, base_dir=base_dir)
                        print(f"{tracker_name} tracker request failed due to SSL error.")
                    except requests.exceptions.ConnectionError as conn_err:
                        await self.save_tracker_timestamp(tracker_name, base_dir=base_dir)
                        print(f"{tracker_name} tracker request failed due to connection error: {conn_err}")
                    return meta

                while not found_match and specific_tracker:
                    meta_trackers_raw = meta.get('trackers', [])
                    if isinstance(meta_trackers_raw, str):
                        meta_trackers = [t.strip().upper() for t in meta_trackers_raw.split(',')]
                    elif isinstance(meta_trackers_raw, list):
                        meta_trackers_list = cast(list[Any], meta_trackers_raw)
                        meta_trackers = [str(t).upper() for t in meta_trackers_list]
                    else:
                        meta_trackers = []

                    available_trackers, waiting_trackers = await self.get_available_trackers(
                        specific_tracker, base_dir, debug=meta['debug']
                    )

                    if available_trackers:
                        if meta['debug'] or meta.get('emby', False):
                            console.print(f"[green]Available trackers: {', '.join(available_trackers)}[/green]")
                        tracker_to_process = available_trackers[0]
                    else:
                        if waiting_trackers:
                            waiting_trackers.sort(key=lambda x: x[1])
                            tracker_to_process, wait_time = waiting_trackers[0]

                            cooldown_info = ", ".join(
                                f"{tracker} ({wait_time:.1f}s)" for tracker, wait_time in waiting_trackers
                            )
                            for remaining in range(int(wait_time), -1, -1):
                                msg = (
                                    f"[yellow]All specific trackers in cooldown. "
                                    f"Waiting {remaining:.1f} seconds for {tracker_to_process}. "
                                    f"Cooldowns: {cooldown_info}[/yellow]"
                                )
                                console.print(msg, end='\r')
                                await asyncio.sleep(1)
                            console.print()

                        else:
                            if meta['debug']:
                                console.print("[red]No specific trackers available[/red]")
                            break

                    # Process the selected tracker
                    if tracker_to_process == "BTN":
                        btn_id_value = meta.get('btn')
                        btn_id = str(btn_id_value) if btn_id_value is not None else ""
                        btn_api = self.default_config.get('btn_api')
                        if isinstance(btn_api, str) and len(btn_api) > 25:
                            imdb, tvdb = await BtnIdManager.get_btn_torrents(btn_api, btn_id, meta)
                            if imdb != 0 or tvdb != 0:
                                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                                    console.print(f"[green]Found BTN IDs: IMDb={imdb}, TVDb={tvdb}[/green]")
                                    try:
                                        if cli_ui.ask_yes_no("Do you want to use these ids?", default=True):
                                            if imdb != 0:
                                                meta['imdb_id'] = int(imdb)
                                            if tvdb != 0:
                                                meta['tvdb_id'] = int(tvdb)
                                            found_match = True
                                            meta['matched_tracker'] = "BTN"
                                    except EOFError:
                                        console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                                        await cleanup_manager.cleanup()
                                        cleanup_manager.reset_terminal()
                                        sys.exit(1)
                                else:
                                    if imdb != 0:
                                        meta['imdb_id'] = int(imdb)
                                    if tvdb != 0:
                                        meta['tvdb_id'] = int(tvdb)
                                    found_match = True
                                    meta['matched_tracker'] = "BTN"
                            await self.save_tracker_timestamp("BTN", base_dir=base_dir)
                    elif tracker_to_process == "ANT":
                        imdb_tmdb_list = await tracker_class_map['ANT'](config=self.config).get_data_from_files(meta)
                        if imdb_tmdb_list:
                            console.print(f"[green]Found ANT IDs: {imdb_tmdb_list}[/green]")
                            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                                try:
                                    if cli_ui.ask_yes_no("Do you want to use these ids?", default=True):
                                        for d in imdb_tmdb_list:
                                            meta.update(d)
                                        found_match = True
                                        meta['matched_tracker'] = "ANT"
                                except EOFError:
                                    console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                                    await cleanup_manager.cleanup()
                                    cleanup_manager.reset_terminal()
                                    sys.exit(1)
                            else:
                                for d in imdb_tmdb_list:
                                    meta.update(d)
                                found_match = True
                                meta['matched_tracker'] = "ANT"
                        await self.save_tracker_timestamp("ANT", base_dir=base_dir)
                    else:
                        meta = await process_tracker(tracker_to_process, meta, only_id)

                    if not found_match:
                        if tracker_to_process in specific_tracker:
                            specific_tracker.remove(tracker_to_process)
                        remaining_available, remaining_waiting = await self.get_available_trackers(
                            specific_tracker, base_dir, debug=meta['debug']
                        )

                        if remaining_available or remaining_waiting:
                            if meta['debug'] or meta.get('emby', False):
                                console.print(
                                    f"[yellow]No match found with {tracker_to_process}. Checking remaining trackers...[/yellow]"
                                )
                        else:
                            if meta['debug']:
                                console.print(
                                    f"[yellow]No match found with {tracker_to_process}. No more trackers available to check.[/yellow]"
                                )
                            break

                if found_match:
                    if meta.get('debug'):
                        console.print(
                            f"[green]Successfully found match using tracker: {meta.get('matched_tracker', 'Unknown')}[/green]"
                        )
                else:
                    if meta['debug']:
                        console.print("[yellow]No matches found on any available specific trackers.[/yellow]")

            else:
                # Process all trackers with API = true if no specific tracker is set in meta
                tracker_order = ["PTP", "HDB", "BHD", "BLU", "AITHER", "HUNO", "LST", "OE", "ULCX"]

                if cat == "TV" or meta.get('category') == "TV":
                    if meta['debug']:
                        console.print("[yellow]Detected TV content, skipping PTP tracker check")
                    tracker_order = [tracker for tracker in tracker_order if tracker != "PTP"]

                async def process_tracker(tracker_name: str, meta: dict[str, Any], only_id: bool) -> dict[str, Any]:
                    nonlocal found_match
                    tracker_factory = tracker_class_map.get(tracker_name)
                    if tracker_factory is None:
                        console.print(f"[red]Tracker class for {tracker_name} not found.[/red]")
                        return meta

                    tracker_instance = tracker_factory(config=self.config)
                    try:
                        updated_meta, match = await self.tracker_meta_manager.update_metadata_from_tracker(
                            tracker_name,
                            tracker_instance,
                            meta,
                            search_term_value,
                            search_file_folder_value,
                            only_id,
                        )
                        if match:
                            found_match = True
                            if meta.get('debug'):
                                console.print(f"[green]Match found on tracker: {tracker_name}[/green]")
                            meta['matched_tracker'] = tracker_name
                        return cast(dict[str, Any], updated_meta)
                    except aiohttp.ClientSSLError:
                        print(f"{tracker_name} tracker request failed due to SSL error.")
                    except requests.exceptions.ConnectionError as conn_err:
                        print(f"{tracker_name} tracker request failed due to connection error: {conn_err}")
                    return meta

                for tracker_name in tracker_order:
                    if not found_match:  # Stop checking once a match is found
                        tracker_config = self.get_tracker_config(tracker_name)
                        if str(tracker_config.get('useAPI', 'false')).lower() == "true":
                            meta = await process_tracker(tracker_name, meta, only_id)

                if not found_match:
                    meta['no_tracker_match'] = True
                    if meta['debug']:
                        console.print("[yellow]No matches found on any trackers.[/yellow]")

        else:
            console.print("[yellow]Warning: No valid search term available, skipping tracker updates.[/yellow]")

        return meta

    async def ping_unit3d(self, meta: dict[str, Any]) -> None:
        import re

        from src.trackers.COMMON import COMMON

        common = COMMON(self.config)

        # Prioritize trackers in this order
        tracker_order = ["BLU", "AITHER", "ULCX", "LST", "OE"]

        # Check if we have stored torrent comments
        if meta.get('torrent_comments'):
            # Try to extract tracker IDs from stored comments
            for tracker_name in tracker_order:
                # Skip if we already have region and distributor
                if meta.get('region') and meta.get('distributor'):
                    if meta.get('debug', False):
                        console.print(
                            f"[green]Both region ({meta['region']}) and distributor ({meta['distributor']}) found - no need to check more trackers[/green]"
                        )
                    break

                tracker_id: str = ""
                tracker_key = tracker_name.lower()
                # Check each stored comment for matching tracker URL
                for comment_data in meta.get('torrent_comments', []):
                    comment = str(comment_data.get('comment', ''))
                    is_tracker_comment = False
                    tracker_hosts = {
                        "BLU": "blutopia.cc",
                        "AITHER": "aither.cc",
                        "LST": "lst.gg",
                        "OE": "onlyencodes.cc",
                        "ULCX": "upload.cx",
                    }
                    expected_host = tracker_hosts.get(tracker_name)
                    if expected_host and expected_host in comment:
                        candidate_urls: list[str] = re.findall(r"https?://[^\s\"'<>]+", comment)
                        for url in candidate_urls:
                            parsed = urlparse(url)
                            if parsed.scheme in ("http", "https") and parsed.hostname == expected_host:
                                is_tracker_comment = True
                                break

                    if is_tracker_comment:
                        match = re.search(r'/(\d+)$', comment)
                        if match:
                            tracker_id = match.group(1)
                            meta[tracker_key] = tracker_id
                            break

                # If we found a tracker ID, try to get region/distributor data
                if tracker_id:
                    missing_info: list[str] = []
                    if not meta.get('region'):
                        missing_info.append("region")
                    if not meta.get('distributor'):
                        missing_info.append("distributor")

                    if meta.get('debug', False):
                        console.print(f"[cyan]Using {tracker_name} ID {tracker_id} to get {'/'.join(missing_info)} info[/cyan]")

                    tracker_instance = tracker_class_map[tracker_name](config=self.config)

                    # Store initial state to detect changes
                    had_region = bool(meta.get('region'))
                    had_distributor = bool(meta.get('distributor'))
                    await common.unit3d_region_distributor(meta, tracker_name, tracker_instance.torrent_url, str(tracker_id))

                    if meta.get('region') and not had_region and meta.get('debug', False):
                        console.print(f"[green]Found region '{meta['region']}' from {tracker_name}[/green]")

                    if meta.get('distributor') and not had_distributor and meta.get('debug', False):
                        console.print(f"[green]Found distributor '{meta['distributor']}' from {tracker_name}[/green]")


