import aiohttp
import requests
import os
import json
import time
from data.config import config
from src.console import console
from src.trackermeta import update_metadata_from_tracker
from src.btnid import get_btn_torrents
from src.clients import Clients
from src.trackersetup import tracker_class_map

client = Clients(config=config)


async def get_tracker_timestamps(base_dir=None):
    """Get tracker timestamps from the log file"""
    timestamp_file = os.path.join(f"{base_dir}", "data", "banned", "tracker_timestamps.json")
    try:
        if os.path.exists(timestamp_file):
            with open(timestamp_file, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        console.print(f"[yellow]Warning: Could not load tracker timestamps: {e}[/yellow]")
        return {}


async def save_tracker_timestamp(tracker_name, base_dir=None, debug=False):
    """Save timestamp for when tracker was processed"""
    timestamp_file = os.path.join(f"{base_dir}", "data", "banned", "tracker_timestamps.json")
    try:
        os.makedirs(f"{base_dir}/data/banned", exist_ok=True)

        timestamps = await get_tracker_timestamps(base_dir)
        timestamps[tracker_name] = time.time()

        with open(timestamp_file, 'w') as f:
            json.dump(timestamps, f, indent=2)

        if debug:
            console.print(f"[yellow]Saved timestamp for {tracker_name} - will be available again in 60 seconds[/yellow]")

    except Exception as e:
        console.print(f"[red]Error saving tracker timestamp: {e}[/red]")


async def get_available_trackers(specific_trackers, base_dir=None, debug=False):
    """Get trackers that are available (60+ seconds since last processed)"""
    timestamps = await get_tracker_timestamps(base_dir)
    current_time = time.time()
    cooldown_seconds = 60

    available = []
    waiting = []

    for tracker in specific_trackers:
        last_processed = timestamps.get(tracker, 0)
        time_since_last = current_time - last_processed

        if time_since_last >= cooldown_seconds:
            available.append(tracker)
        else:
            wait_time = cooldown_seconds - time_since_last
            waiting.append((tracker, wait_time))

    return available, waiting


async def get_tracker_data(video, meta, search_term=None, search_file_folder=None, cat=None, only_id=False):
    found_match = False
    base_dir = meta['base_dir']
    if search_term:
        # Check if a specific tracker is already set in meta
        if not meta.get('emby', False):
            tracker_keys = {
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
                'btn': 'BTN',
                'oe': 'OE',
                'ulcx': 'ULCX',
                'huno': 'HUNO',
                'lst': 'LST',
                'ant': 'ANT',
                'hdb': 'HDB',
                'bhd': 'BHD',
                'blu': 'BLU',
                'aither': 'AITHER',
                'ptp': 'PTP',
            }

        specific_tracker = [tracker_keys[key] for key in tracker_keys if meta.get(key) is not None]

        if specific_tracker:
            if meta.get('is_disc', False) and "ANT" in specific_tracker:
                specific_tracker.remove("ANT")
            if meta.get('category') == "MOVIE" and "BTN" in specific_tracker:
                specific_tracker.remove("BTN")

            async def process_tracker(tracker_name, meta, only_id):
                nonlocal found_match
                if tracker_class_map is None:
                    print(f"Tracker class for {tracker_name} not found.")
                    return meta

                tracker_instance = tracker_class_map[tracker_name](config=config)
                try:
                    updated_meta, match = await update_metadata_from_tracker(
                        tracker_name, tracker_instance, meta, search_term, search_file_folder, only_id
                    )
                    if match:
                        found_match = True
                        if meta.get('debug'):
                            console.print(f"[green]Match found on tracker: {tracker_name}[/green]")
                        meta['matched_tracker'] = tracker_name
                    await save_tracker_timestamp(tracker_name, base_dir=base_dir)
                    return updated_meta
                except aiohttp.ClientSSLError:
                    await save_tracker_timestamp(tracker_name, base_dir=base_dir)
                    print(f"{tracker_name} tracker request failed due to SSL error.")
                except requests.exceptions.ConnectionError as conn_err:
                    await save_tracker_timestamp(tracker_name, base_dir=base_dir)
                    print(f"{tracker_name} tracker request failed due to connection error: {conn_err}")
                return meta

            while not found_match and specific_tracker:
                available_trackers, waiting_trackers = await get_available_trackers(specific_tracker, base_dir, debug=meta['debug'])

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
                            msg = (f"[yellow]All specific trackers in cooldown. "
                                   f"Waiting {remaining:.1f} seconds for {tracker_to_process}. "
                                   f"Cooldowns: {cooldown_info}[/yellow]")
                            console.print(msg, end='\r')
                            time.sleep(1)
                        console.print()

                    else:
                        if meta['debug']:
                            console.print("[red]No specific trackers available[/red]")
                        break

                # Process the selected tracker
                if tracker_to_process == "BTN":
                    btn_id = meta.get('btn')
                    btn_api = config['DEFAULT'].get('btn_api')
                    await get_btn_torrents(btn_api, btn_id, meta)
                    if meta.get('imdb_id') != 0:
                        found_match = True
                        meta['matched_tracker'] = "BTN"
                    await save_tracker_timestamp("BTN", base_dir=base_dir)
                elif tracker_to_process == "ANT":
                    imdb_tmdb_list = await tracker_class_map['ANT'](config=config).get_data_from_files(meta)
                    console.print(f"[green]ANT tracker data found: {imdb_tmdb_list}[/green]")
                    if imdb_tmdb_list:
                        for d in imdb_tmdb_list:
                            meta.update(d)
                        found_match = True
                        meta['matched_tracker'] = "ANT"
                    await save_tracker_timestamp("ANT", base_dir=base_dir)
                else:
                    meta = await process_tracker(tracker_to_process, meta, only_id)

                if not found_match:
                    if tracker_to_process in specific_tracker:
                        specific_tracker.remove(tracker_to_process)
                    remaining_available, remaining_waiting = await get_available_trackers(specific_tracker, base_dir, debug=meta['debug'])

                    if remaining_available or remaining_waiting:
                        if meta['debug'] or meta.get('emby', False):
                            console.print(f"[yellow]No match found with {tracker_to_process}. Checking remaining trackers...[/yellow]")
                    else:
                        if meta['debug']:
                            console.print(f"[yellow]No match found with {tracker_to_process}. No more trackers available to check.[/yellow]")
                        break

            if found_match:
                if meta.get('debug'):
                    console.print(f"[green]Successfully found match using tracker: {meta.get('matched_tracker', 'Unknown')}[/green]")
            else:
                console.print("[yellow]No matches found on any available specific trackers.[/yellow]")

        else:
            # Process all trackers with API = true if no specific tracker is set in meta
            tracker_order = ["PTP", "HDB", "BHD", "BLU", "AITHER", "HUNO", "LST", "OE", "ULCX"]

            if cat == "TV" or meta.get('category') == "TV":
                if meta['debug']:
                    console.print("[yellow]Detected TV content, skipping PTP tracker check")
                tracker_order = [tracker for tracker in tracker_order if tracker != "PTP"]

            async def process_tracker(tracker_name, meta, only_id):
                nonlocal found_match
                if tracker_class_map is None:
                    print(f"Tracker class for {tracker_name} not found.")
                    return meta

                tracker_instance = tracker_class_map[tracker_name](config=config)
                try:
                    updated_meta, match = await update_metadata_from_tracker(
                        tracker_name, tracker_instance, meta, search_term, search_file_folder, only_id
                    )
                    if match:
                        found_match = True
                        if meta.get('debug'):
                            console.print(f"[green]Match found on tracker: {tracker_name}[/green]")
                        meta['matched_tracker'] = tracker_name
                    return updated_meta
                except aiohttp.ClientSSLError:
                    print(f"{tracker_name} tracker request failed due to SSL error.")
                except requests.exceptions.ConnectionError as conn_err:
                    print(f"{tracker_name} tracker request failed due to connection error: {conn_err}")
                return meta

            for tracker_name in tracker_order:
                if not found_match:  # Stop checking once a match is found
                    tracker_config = config['TRACKERS'].get(tracker_name, {})
                    if str(tracker_config.get('useAPI', 'false')).lower() == "true":
                        meta = await process_tracker(tracker_name, meta, only_id)

            if not found_match:
                console.print("[yellow]No matches found on any trackers.[/yellow]")

    else:
        console.print("[yellow]Warning: No valid search term available, skipping tracker updates.[/yellow]")

    return meta


async def ping_unit3d(meta):
    from src.trackers.COMMON import COMMON
    common = COMMON(config)
    import re

    # Prioritize trackers in this order
    tracker_order = ["BLU", "AITHER", "ULCX", "LST", "OE"]

    # Check if we have stored torrent comments
    if meta.get('torrent_comments'):
        # Try to extract tracker IDs from stored comments
        for tracker_name in tracker_order:
            # Skip if we already have region and distributor
            if meta.get('region') and meta.get('distributor'):
                if meta.get('debug', False):
                    console.print(f"[green]Both region ({meta['region']}) and distributor ({meta['distributor']}) found - no need to check more trackers[/green]")
                break

            tracker_id = None
            tracker_key = tracker_name.lower()
            # Check each stored comment for matching tracker URL
            for comment_data in meta.get('torrent_comments', []):
                comment = comment_data.get('comment', '')

                if "blutopia.cc" in comment and tracker_name == "BLU":
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        tracker_id = match.group(1)
                        meta[tracker_key] = tracker_id
                        break
                elif "aither.cc" in comment and tracker_name == "AITHER":
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        tracker_id = match.group(1)
                        meta[tracker_key] = tracker_id
                        break
                elif "lst.gg" in comment and tracker_name == "LST":
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        tracker_id = match.group(1)
                        meta[tracker_key] = tracker_id
                        break
                elif "onlyencodes.cc" in comment and tracker_name == "OE":
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        tracker_id = match.group(1)
                        meta[tracker_key] = tracker_id
                        break
                elif "https://upload.cx" in comment and tracker_name == "ULCX":
                    match = re.search(r'/(\d+)$', comment)
                    if match:
                        tracker_id = match.group(1)
                        meta[tracker_key] = tracker_id
                        break

            # If we found a tracker ID, try to get region/distributor data
            if tracker_id:
                missing_info = []
                if not meta.get('region'):
                    missing_info.append("region")
                if not meta.get('distributor'):
                    missing_info.append("distributor")

                if meta.get('debug', False):
                    console.print(f"[cyan]Using {tracker_name} ID {tracker_id} to get {'/'.join(missing_info)} info[/cyan]")

                tracker_instance = tracker_class_map[tracker_name](config=config)

                # Store initial state to detect changes
                had_region = bool(meta.get('region'))
                had_distributor = bool(meta.get('distributor'))
                await common.unit3d_region_distributor(meta, tracker_name, tracker_instance.torrent_url, tracker_id)

                if meta.get('region') and not had_region:
                    if meta.get('debug', False):
                        console.print(f"[green]Found region '{meta['region']}' from {tracker_name}[/green]")

                if meta.get('distributor') and not had_distributor:
                    if meta.get('debug', False):
                        console.print(f"[green]Found distributor '{meta['distributor']}' from {tracker_name}[/green]")
