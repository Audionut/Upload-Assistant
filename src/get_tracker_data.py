import aiohttp
import requests
from data.config import config
from src.console import console
from src.trackermeta import update_metadata_from_tracker
from src.btnid import get_btn_torrents
from src.clients import Clients
from src.trackersetup import tracker_class_map

client = Clients(config=config)


async def get_tracker_data(video, meta, search_term=None, search_file_folder=None, cat=None):
    only_id = config['DEFAULT'].get('only_id', False) if meta.get('onlyID') is None else meta.get('onlyID')
    meta['only_id'] = only_id
    meta['keep_images'] = config['DEFAULT'].get('keep_images', True) if not meta.get('keep_images') else True
    found_match = False

    if search_term:
        # Check if a specific tracker is already set in meta
        tracker_keys = {
            'aither': 'AITHER',
            'blu': 'BLU',
            'lst': 'LST',
            'ulcx': 'ULCX',
            'oe': 'OE',
            'huno': 'HUNO',
            'btn': 'BTN',
            'bhd': 'BHD',
            'hdb': 'HDB',
            'ptp': 'PTP',
        }

        specific_tracker = [tracker_keys[key] for key in tracker_keys if meta.get(key) is not None]

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

        # If a specific tracker is found, process only that tracker
        for tracker in specific_tracker:
            if tracker == "BTN":
                btn_id = meta.get('btn')
                btn_api = config['DEFAULT'].get('btn_api')
                await get_btn_torrents(btn_api, btn_id, meta)
                if meta.get('imdb_id') != 0:
                    found_match = True
                    break
            else:
                meta = await process_tracker(tracker, meta, only_id)
                if found_match:
                    break
        else:
            # Process all trackers with API = true if no specific tracker is set in meta
            tracker_order = ["PTP", "BHD", "BLU", "AITHER", "LST", "OE", "HDB", "HUNO", "ULCX"]

            if cat == "TV" or meta.get('category') == "TV":
                if meta['debug']:
                    console.print("[yellow]Detected TV content, skipping PTP tracker check")
                tracker_order = [tracker for tracker in tracker_order if tracker != "PTP"]

            for tracker_name in tracker_order:
                if not found_match:  # Stop checking once a match is found
                    tracker_config = config['TRACKERS'].get(tracker_name, {})
                    if str(tracker_config.get('useAPI', 'false')).lower() == "true":
                        meta = await process_tracker(tracker_name, meta, only_id)

        if not found_match:
            console.print("[yellow]No matches found on any trackers.[/yellow]")

    else:
        console.print("[yellow]Warning: No valid search term available, skipping tracker updates.[/yellow]")


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
