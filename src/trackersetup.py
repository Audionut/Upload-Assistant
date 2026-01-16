# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta
from typing import Any, Union

import aiofiles
import cli_ui
import httpx

from src.cleanup import cleanup, reset_terminal
from src.console import console
from src.trackers.ACM import ACM
from src.trackers.AITHER import AITHER
from src.trackers.ANT import ANT
from src.trackers.AR import AR
from src.trackers.ASC import ASC
from src.trackers.AZ import AZ
from src.trackers.BHD import BHD
from src.trackers.BHDTV import BHDTV
from src.trackers.BJS import BJS
from src.trackers.BLU import BLU
from src.trackers.BT import BT
from src.trackers.CBR import CBR
from src.trackers.COMMON import COMMON
from src.trackers.CZ import CZ
from src.trackers.DC import DC
from src.trackers.DP import DP
from src.trackers.EMUW import EMUW
from src.trackers.FF import FF
from src.trackers.FL import FL
from src.trackers.FNP import FNP
from src.trackers.FRIKI import FRIKI
from src.trackers.GPW import GPW
from src.trackers.HDB import HDB
from src.trackers.HDS import HDS
from src.trackers.HDT import HDT
from src.trackers.HHD import HHD
from src.trackers.HUNO import HUNO
from src.trackers.IHD import IHD
from src.trackers.IS import IS
from src.trackers.ITT import ITT
from src.trackers.LCD import LCD
from src.trackers.LDU import LDU
from src.trackers.LST import LST
from src.trackers.LT import LT
from src.trackers.MTV import MTV
from src.trackers.NBL import NBL
from src.trackers.OE import OE
from src.trackers.OTW import OTW
from src.trackers.PHD import PHD
from src.trackers.PT import PT
from src.trackers.PTER import PTER
from src.trackers.PTP import PTP
from src.trackers.PTS import PTS
from src.trackers.PTT import PTT
from src.trackers.R4E import R4E
from src.trackers.RAS import RAS
from src.trackers.RF import RF
from src.trackers.RTF import RTF
from src.trackers.SAM import SAM
from src.trackers.SHRI import SHRI
from src.trackers.SN import SN
from src.trackers.SP import SP
from src.trackers.SPD import SPD
from src.trackers.STC import STC
from src.trackers.THR import THR
from src.trackers.TIK import TIK
from src.trackers.TL import TL
from src.trackers.TLZ import TLZ
from src.trackers.TOS import TOS
from src.trackers.TTG import TTG
from src.trackers.TTR import TTR
from src.trackers.TVC import TVC
from src.trackers.ULCX import ULCX
from src.trackers.UTP import UTP
from src.trackers.YOINK import YOINK
from src.trackers.YUS import YUS


class TRACKER_SETUP:
    def __init__(self, config: dict[str, Any]):
        self.config: dict[str, Any] = config

    def _create_tracker_instance(self, tracker: str) -> Union[Any, None]:
        tracker_class = tracker_class_map.get(tracker.upper())
        if tracker_class is None:
            return None
        return tracker_class(self.config)

    def trackers_enabled(self, meta):
        if meta.get('trackers') is not None:
            trackers = meta['trackers']
        else:
            trackers = self.config['TRACKERS']['default_trackers']

        if isinstance(trackers, str):
            trackers = trackers.split(',')

        trackers = [str(s).strip().upper() for s in trackers]

        if meta.get('manual', False):
            trackers.insert(0, "MANUAL")

        valid_trackers = [t for t in trackers if t in tracker_class_map or t == "MANUAL"]
        removed_trackers = set(trackers) - set(valid_trackers)

        for tracker in removed_trackers:
            print(f"Warning: Tracker '{tracker}' is not recognized and will be ignored.")

        return valid_trackers

    async def get_banned_groups(self, meta, tracker):
        file_path = os.path.join(meta['base_dir'], 'data', 'banned', f'{tracker}_banned_groups.json')

        tracker_instance = self._create_tracker_instance(tracker)
        if tracker_instance is None:
            return None
        banned_url = getattr(tracker_instance, 'banned_url', None)
        if not isinstance(banned_url, str):
            return None

        # Check if we need to update
        if not await self.should_update(file_path):
            return file_path

        headers = {
            'Authorization': f"Bearer {self.config['TRACKERS'][tracker]['api_key'].strip()}",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        all_data = []
        next_cursor = None

        async with httpx.AsyncClient() as client:
            while True:
                try:
                    # Add query parameters for pagination
                    params = {'cursor': next_cursor, 'per_page': 100} if next_cursor else {'per_page': 100}
                    response = await client.get(url=banned_url, headers=headers, params=params)

                    if response.status_code == 200:
                        response_json = response.json()

                        if isinstance(response_json, list):
                            # Directly add the list if it's the entire response
                            all_data.extend(response_json)
                            break  # No pagination in this case
                        elif isinstance(response_json, dict):
                            page_data = response_json.get('data', [])
                            if not isinstance(page_data, list):
                                console.print(f"[red]Unexpected 'data' format: {type(page_data)}[/red]")
                                return None

                            all_data.extend(page_data)
                            meta_info = response_json.get('meta', {})
                            if not isinstance(meta_info, dict):
                                console.print(f"[red]Unexpected 'meta' format: {type(meta_info)}[/red]")
                                return None

                            # Check if there is a next page
                            next_cursor = meta_info.get('next_cursor')
                            if not next_cursor:
                                break  # Exit loop if there are no more pages
                        else:
                            console.print(f"[red]Unexpected response format: {type(response_json)}[/red]")
                            return None
                    elif response.status_code == 404:
                        console.print(f"Error: Tracker '{tracker}' returned 404 for the banned groups API.")
                        return None
                    else:
                        console.print(f"Error: Received status code {response.status_code} for tracker '{tracker}'.")
                        return None

                except httpx.RequestError as e:
                    console.print(f"[red]HTTP Request failed for tracker '{tracker}': {e}[/red]")
                    return None
                except Exception as e:
                    console.print(f"[red]An unexpected error occurred: {e}[/red]")
                    return None

        if meta['debug']:
            console.print("Total banned groups retrieved:", len(all_data))

        if not all_data:
            return "empty"

        await self.write_banned_groups_to_file(file_path, all_data, debug=meta['debug'])

        return file_path

    async def write_banned_groups_to_file(self, file_path, json_data, debug=False):
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            if not isinstance(json_data, list):
                console.print("Invalid data format: expected a list of groups.")
                return

            # Extract 'name' values from the list
            names = [item['name'] for item in json_data if isinstance(item, dict) and 'name' in item]
            names_csv = ', '.join(names)
            file_content = {
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "banned_groups": names_csv,
                "raw_data": json_data
            }

            await asyncio.to_thread(self._write_file, file_path, file_content)
            if debug:
                console.print(f"File '{file_path}' updated successfully with {len(names)} groups.")
        except Exception as e:
            console.print(f"An error occurred: {e}")

    def _write_file(self, file_path, data):
        """ Blocking file write operation, runs in a background thread """
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

    async def should_update(self, file_path):
        try:
            content = await asyncio.to_thread(self._read_file, file_path)
            data = json.loads(content)
            last_updated = datetime.strptime(data['last_updated'], "%Y-%m-%d")
            return datetime.now() >= last_updated + timedelta(days=1)
        except FileNotFoundError:
            return True
        except Exception as e:
            console.print(f"Error reading file: {e}")
            return True

    def _read_file(self, file_path):
        """ Helper function to read the file in a blocking thread """
        with open(file_path, encoding="utf-8") as file:
            return file.read()

    async def check_banned_group(self, tracker, banned_group_list, meta):
        result = False
        if not meta['tag']:
            return False

        group_tags = meta['tag'][1:].lower()
        if 'taoe' in group_tags:
            group_tags = 'taoe'

        if tracker.upper() in ("AITHER", "LST", "SPD"):
            file_path = await self.get_banned_groups(meta, tracker)
            if file_path == "empty":
                console.print(f"[bold red]No banned groups found for '{tracker}'.")
                return False
            if not file_path:
                console.print(f"[bold red]Failed to load banned groups for '{tracker}'.")
                return False

            # Load the banned groups from the file
            try:
                content = await asyncio.to_thread(self._read_file, file_path)
                data = json.loads(content)
                banned_groups = data.get("banned_groups", "")
                if banned_groups:
                    banned_group_list = banned_groups.split(", ")

            except FileNotFoundError:
                console.print(f"[bold red]Banned group file for '{tracker}' not found.")
                return False
            except json.JSONDecodeError:
                console.print(f"[bold red]Failed to parse banned group file for '{tracker}'.")
                return False

        for tag in banned_group_list:
            if isinstance(tag, list):
                if group_tags == tag[0].lower():
                    console.print(f"[bold yellow]{meta['tag'][1:]}[/bold yellow][bold red] was found on [bold yellow]{tracker}'s[/bold yellow] list of banned groups.")
                    console.print(f"[bold red]NOTE: [bold yellow]{tag[1]}")
                    result = True
            else:
                if group_tags == tag.lower():
                    console.print(f"[bold yellow]{meta['tag'][1:]}[/bold yellow][bold red] was found on [bold yellow]{tracker}'s[/bold yellow] list of banned groups.")
                    result = True

        if result:
            if not meta['unattended'] or meta.get('unattended_confirm', False):
                try:
                    if cli_ui.ask_yes_no(cli_ui.red, "Do you want to continue anyway?", default=False):
                        return False
                except EOFError:
                    console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                    await cleanup()
                    reset_terminal()
                    sys.exit(1)
                return True

            return True

        return False

    async def write_internal_claims_to_file(self, file_path, data, debug=False):
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            if not isinstance(data, list):
                console.print("Invalid data format: expected a list of claims.")
                return

            extracted_data = []
            for item in data:
                if not isinstance(item, dict) or 'attributes' not in item:
                    console.print(f"Skipping invalid item: {item}")
                    continue

                attributes = item['attributes']
                extracted_data.append({
                    "title": attributes.get('title', 'Unknown'),
                    "season": attributes.get('season', 'Unknown'),
                    "tmdb_id": attributes.get('tmdb_id', 'Unknown'),
                    "resolutions": attributes.get('resolutions', []),
                    "types": attributes.get('types', [])
                })

            if not extracted_data:
                if debug:
                    console.print("No valid claims found to write.")
                return

            titles_csv = ', '.join([data['title'] for data in extracted_data])

            file_content = {
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "titles_csv": titles_csv,
                "extracted_data": extracted_data,
                "raw_data": data
            }

            await asyncio.to_thread(self._write_file, file_path, file_content)
            if debug:
                console.print(f"File '{file_path}' updated successfully with {len(extracted_data)} claims.")
        except Exception as e:
            console.print(f"An error occurred: {e}")

    async def get_torrent_claims(self, meta, tracker):
        file_path = os.path.join(meta['base_dir'], 'data', 'banned', f'{tracker}_claimed_releases.json')
        tracker_instance = self._create_tracker_instance(tracker)
        if tracker_instance is None:
            return None
        claims_url = getattr(tracker_instance, 'claims_url', None)
        if not isinstance(claims_url, str):
            return None

        # Check if we need to update
        if not await self.should_update(file_path):
            return await self.check_tracker_claims(meta, tracker)

        headers = {
            'Authorization': f"Bearer {self.config['TRACKERS'][tracker]['api_key'].strip()}",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        all_data = []
        next_cursor = None

        async with httpx.AsyncClient() as client:
            while True:
                try:
                    # Add query parameters for pagination
                    params = {'cursor': next_cursor, 'per_page': 100} if next_cursor else {'per_page': 100}
                    response = await client.get(url=claims_url, headers=headers, params=params)

                    if response.status_code == 200:
                        response_json = response.json()
                        page_data = response_json.get('data', [])
                        if not isinstance(page_data, list):
                            console.print(f"[red]Unexpected 'data' format: {type(page_data)}[/red]")
                            return False

                        all_data.extend(page_data)
                        meta_info = response_json.get('meta', {})
                        if not isinstance(meta_info, dict):
                            console.print(f"[red]Unexpected 'meta' format: {type(meta_info)}[/red]")
                            return False

                        # Check if there is a next page
                        next_cursor = meta_info.get('next_cursor')
                        if not next_cursor:
                            break  # Exit loop if there are no more pages
                    else:
                        console.print(f"[red]Error: Received status code {response.status_code}[/red]")
                        return False

                except httpx.RequestError as e:
                    console.print(f"[red]HTTP Request failed: {e}[/red]")
                    return False
                except Exception as e:
                    console.print(f"[red]An unexpected error occurred: {e}[/red]")
                    return False

        if meta['debug']:
            console.print("Total claims retrieved:", len(all_data))

        if not all_data:
            return False

        await self.write_internal_claims_to_file(file_path, all_data, debug=meta['debug'])

        return await self.check_tracker_claims(meta, tracker)

    async def check_tracker_claims(self, meta, tracker):
        if isinstance(tracker, str):
            trackers = [tracker.strip().upper()]
        elif isinstance(tracker, list):
            trackers = [s.upper() for s in tracker]
        else:
            console.print("[red]Invalid trackers input format.[/red]")
            return False

        async def process_single_tracker(tracker_name):
            try:
                tracker_instance = self._create_tracker_instance(tracker_name)
                if tracker_instance is None:
                    console.print(f"[red]Tracker {tracker_name} is not registered in tracker_class_map[/red]")
                    return False

                # Get name-to-ID mappings directly
                type_mapping = await tracker_instance.get_type_id(meta, mapping_only=True)
                type_name = meta.get('type', '')
                type_ids = [type_mapping.get(type_name)] if type_name else []
                if None in type_ids:
                    console.print("[yellow]Warning: Type in meta not found in tracker type mapping.[/yellow]")

                resolution_mapping = await tracker_instance.get_resolution_id(meta, mapping_only=True)
                resolution_name = meta.get('resolution', '')
                resolution_ids = [resolution_mapping.get(resolution_name)] if resolution_name else []
                if None in resolution_ids:
                    console.print("[yellow]Warning: Resolution in meta not found in tracker resolution mapping.[/yellow]")

                tmdb_id = meta.get('tmdb', [])
                if isinstance(tmdb_id, int):
                    tmdb_id = [tmdb_id]
                elif isinstance(tmdb_id, str):
                    tmdb_id = [int(tmdb_id)]
                elif isinstance(tmdb_id, list):
                    tmdb_id = [int(id) for id in tmdb_id]
                else:
                    console.print(f"[red]Invalid TMDB ID format in meta: {tmdb_id}[/red]")
                    return False

                metaseason = meta.get('season_int')
                if metaseason:
                    seasonint = int(metaseason)
                file_path = os.path.join(meta['base_dir'], 'data', 'banned', f'{tracker_name}_claimed_releases.json')
                if not os.path.exists(file_path):
                    console.print(f"[red]No claim data file found for {tracker_name}[/red]")
                    return False

                with open(file_path) as file:
                    extracted_data = json.load(file).get('extracted_data', [])

                for item in extracted_data:
                    title = item.get('title')
                    season = item.get('season')
                    api_tmdb_id = item.get('tmdb_id')
                    api_resolutions = item.get('resolutions', [])
                    api_types = item.get('types', [])

                    if (
                        api_tmdb_id in tmdb_id
                        and (meta['category'] == "MOVIE" or season == seasonint)
                        and all(res in api_resolutions for res in resolution_ids)
                        and all(typ in api_types for typ in type_ids)
                    ):
                        console.print(f"[green]Claimed match found at [cyan]{tracker}: [yellow]{title}, Season: {season}, TMDB ID: {api_tmdb_id}[/green]")
                        return True

                return False

            except Exception as e:
                console.print(f"[red]Error processing tracker {tracker_name}: {e}[/red]", highlight=True)
                import traceback
                console.print(traceback.format_exc())
                return False

        results = await asyncio.gather(*[process_single_tracker(tracker) for tracker in trackers])
        match_found = any(results)

        return match_found

    async def get_tracker_requests(self, meta, tracker, url):
        if meta['debug']:
            console.print(f"[bold green]Searching for existing requests on {tracker}[/bold green]")
        requests: list[dict[str, Any]] = []
        headers = {
            'Authorization': f"Bearer {self.config['TRACKERS'][tracker]['api_key'].strip()}",
            'Accept': 'application/json'
        }
        params = {
            'tmdb': meta['tmdb'],
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url=url, headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and isinstance(data['data'], list):
                        results_list = data['data']
                    elif 'results' in data and isinstance(data['results'], list):
                        results_list = data['results']
                    else:
                        console.print(f"[bold red]Unexpected response format: {type(data)}[/bold red]")
                        return requests

                    try:
                        for each in results_list:
                            attributes = each
                            result = {
                                'id': attributes.get('id'),
                                'name': attributes.get('name'),
                                'description': attributes.get('description'),
                                'category': attributes.get('category_id'),
                                'type': attributes.get('type_id'),
                                'resolution': attributes.get('resolution_id'),
                                'bounty': attributes.get('bounty'),
                                'status': attributes.get('status'),
                                'claimed': attributes.get('claimed'),
                                'season': attributes.get('season_number'),
                                'episode': attributes.get('episode_number'),
                            }
                            requests.append(result)
                    except Exception as e:
                        console.print(f"[bold red]Error processing response data: {e}[/bold red]")
                        return requests
                else:
                    console.print(f"[bold red]Failed to search torrents on {tracker}. HTTP Status: {response.status_code}")
        except httpx.TimeoutException:
            console.print("[bold red]Request timed out after 5 seconds")
        except httpx.RequestError as e:
            console.print(f"[bold red]Unable to search for existing torrents: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")

        return requests

    async def bhd_request_check(self, meta, tracker, url):
        if 'BHD' not in self.config['TRACKERS'] or not self.config['TRACKERS']['BHD'].get('api_key'):
            console.print("[red]BHD API key not configured. Skipping BHD request check.[/red]")
            return []
        if meta['debug']:
            console.print(f"[bold green]Searching for existing requests on {tracker}[/bold green]")
        requests: list[dict[str, Any]] = []
        params = {
            'action': 'search',
            'tmdb_id': f"{meta['category'].lower()}/{meta['tmdb_id']}",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url=url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and isinstance(data['data'], list):
                        results_list = data['data']
                    elif 'results' in data and isinstance(data['results'], list):
                        results_list = data['results']
                    else:
                        console.print(f"[bold red]Unexpected response format: {type(data)}[/bold red]")
                        console.print(f"[bold red]Full response: {data}[/bold red]")
                        return requests

                    try:
                        for each in results_list:
                            attributes = each
                            result = {
                                'id': attributes.get('id'),
                                'name': attributes.get('name'),
                                'type': attributes.get('source'),
                                'resolution': attributes.get('type'),
                                'dv': attributes.get('dv'),
                                'hdr': attributes.get('hdr'),
                                'bounty': attributes.get('bounty'),
                                'status': attributes.get('status'),
                                'internal': attributes.get('internal'),
                                'url': attributes.get('url'),
                            }
                            requests.append(result)
                    except Exception as e:
                        console.print(f"[bold red]Error processing response data: {e}[/bold red]")
                        console.print(f"[bold red]Response data: {data}[/bold red]")
                        return requests
                else:
                    console.print(f"[bold red]Failed to search torrents. HTTP Status: {response.status_code}")
        except httpx.TimeoutException:
            console.print("[bold red]Request timed out after 5 seconds")
        except httpx.RequestError as e:
            console.print(f"[bold red]Unable to search for existing torrents: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
        # console.print(f"Debug: BHD requests found: {requests}")
        return requests

    async def tracker_request(self, meta, tracker):
        if isinstance(tracker, str):
            trackers = [tracker.strip().upper()]
        elif isinstance(tracker, list):
            trackers = [s.upper() for s in tracker]
        else:
            console.print("[red]Invalid trackers input format.[/red]")
            return False

        async def process_single_tracker(tracker_name: str):
            tracker_instance = self._create_tracker_instance(tracker_name)
            if tracker_instance is None:
                console.print(f"[red]Tracker {tracker_name} is not registered in tracker_class_map[/red]")
                return False

            requests: list[dict[str, Any]] = []
            url: Union[str, None] = None
            try:
                url = tracker_instance.requests_url
            except AttributeError:
                if tracker_name.upper() not in ('ASC', 'BJS', 'FF', 'HDS', 'AZ', 'CZ', 'PHD'):
                    # tracker without requests url not supported
                    return False

            if tracker_name.upper() == "BHD":
                if not url:
                    return False
                requests = await self.bhd_request_check(meta, tracker_name, url)
            elif tracker_name.upper() in ('ASC', 'BJS', 'FF', 'HDS', 'AZ', 'CZ', 'PHD'):
                # These trackers have custom request handling
                requests = await tracker_instance.get_requests(meta)
                return False
            else:
                if not url:
                    return False
                requests = await self.get_tracker_requests(meta, tracker_name, url)
                type_mapping = await tracker_instance.get_type_id(meta, mapping_only=True)
                type_name = meta.get('type', '')
                type_ids = [type_mapping.get(type_name)] if type_name else []
                if None in type_ids:
                    console.print("[yellow]Warning: Type in meta not found in tracker type mapping.[/yellow]")

                resolution_mapping = await tracker_instance.get_resolution_id(meta, mapping_only=True)
                resolution_name = meta.get('resolution', '')
                resolution_ids = [resolution_mapping.get(resolution_name)] if resolution_name else []
                if None in resolution_ids:
                    console.print("[yellow]Warning: Resolution in meta not found in tracker resolution mapping.[/yellow]")

                category_mapping = await tracker_instance.get_category_id(meta, mapping_only=True)
                category_name = meta.get('category', '')
                category_ids = [category_mapping.get(category_name)] if category_name else []
                if None in category_ids:
                    console.print("[yellow]Warning: Some categories in meta not found in tracker category mapping.[/yellow]")

            tmdb_id = meta.get('tmdb', [])
            if isinstance(tmdb_id, int):
                tmdb_id = [tmdb_id]
            elif isinstance(tmdb_id, str):
                tmdb_id = [int(tmdb_id)]
            elif isinstance(tmdb_id, list):
                tmdb_id = [int(id) for id in tmdb_id]
            else:
                console.print(f"[red]Invalid TMDB ID format in meta: {tmdb_id}[/red]")
                return False

            # Initialize request log for this tracker
            common = COMMON(self.config)
            log_path = f"{meta['base_dir']}/tmp/{tracker_name}_request_results.json"
            if not await common.path_exists(log_path):
                await common.makedirs(os.path.dirname(log_path))

            request_data: list[dict[str, Any]] = []
            try:
                async with aiofiles.open(log_path, encoding='utf-8') as f:
                    content = await f.read()
                    request_data = json.loads(content) if content.strip() else []
            except Exception:
                request_data = []

            existing_uuids = {entry.get('uuid') for entry in request_data if isinstance(entry, dict)}

            for each in requests:
                type_name = False
                resolution = False
                season = False
                episode = False
                double_check = False
                api_id = each.get('id')
                api_category = each.get('category')
                api_name = str(each.get('name') or '')
                api_type = each.get('type')
                api_type_str = str(api_type or '')
                api_bounty = each.get('bounty')
                api_status = each.get('status')
                api_description = str(each.get('description') or '')
                api_resolution = each.get('resolution')
                api_resolution_str = str(api_resolution or '')
                api_resolution_lower = api_resolution_str.lower()
                if "BHD" not in tracker_name:
                    if str(api_type) in [str(tid) for tid in type_ids]:
                        type_name = True
                    elif api_type is None:
                        type_name = True
                        double_check = True
                    if str(api_resolution) in [str(rid) for rid in resolution_ids]:
                        resolution = True
                    elif api_resolution is None:
                        resolution = True
                        double_check = True
                    api_claimed = each.get('claimed')
                    if meta['category'] == "TV":
                        season_value = each.get('season')
                        if season_value is not None:
                            api_season = int(season_value)
                        else:
                            api_season = 0
                        if api_season and meta.get('season_int') and api_season == meta.get('season_int'):
                            season = True
                        episode_value = each.get('episode')
                        if episode_value is not None:
                            api_episode = int(episode_value)
                        else:
                            api_episode = 0
                        if api_episode and meta.get('episode_int') and api_episode == meta.get('episode_int'):
                            episode = True
                    if str(api_category) in [str(cid) for cid in category_ids]:
                        new_url = re.sub(r'/api/requests/filter$', f'/requests/{api_id}', url)
                        if meta.get('category') == "MOVIE" and type_name and resolution and not api_claimed:
                            console.print(f"[bold blue]Found exact request match on [bold yellow]{tracker_name}[/bold yellow] with bounty [bold yellow]{api_bounty}[/bold yellow] and with status [bold yellow]{api_status}[/bold yellow][/bold blue]")
                            console.print(f"[bold blue]Claimed status:[/bold blue] [bold yellow]{api_claimed}[/bold yellow]")
                            console.print(f"[bold green]{api_name}:[/bold green] {new_url}")
                            console.print()
                            if double_check:
                                console.print("[bold red]Type and/or resolution was set to ANY, double check any description requirements:[/bold red]")
                                console.print(f"[bold yellow]Request desc:[/bold yellow] {api_description[:100]}")
                                console.print()

                            if meta.get('uuid') not in existing_uuids:
                                request_entry = {
                                    'uuid': meta.get('uuid'),
                                    'path': meta.get('path', ''),
                                    'url': new_url,
                                    'name': api_name,
                                    'bounty': api_bounty,
                                    'description': api_description,
                                    'claimed': api_claimed
                                }
                                request_data.append(request_entry)
                                existing_uuids.add(meta.get('uuid'))
                        elif meta.get('category') == "TV" and season and episode and type_name and resolution and not api_claimed:
                            console.print(f"[bold blue]Found exact request match on [bold yellow]{tracker_name}[/bold yellow] with bounty [bold yellow]{api_bounty}[/bold yellow] and with status [bold yellow]{api_status}[/bold yellow][/bold blue]")
                            console.print(f"[bold blue]Claimed status:[/bold blue] [bold yellow]{api_claimed}[/bold yellow]")
                            console.print(f"[bold yellow]{api_name}[/bold yellow] - [bold yellow]S{api_season:02d} E{api_episode:02d}:[/bold yellow] {new_url}")
                            console.print()
                            if double_check:
                                console.print("[bold red]Type and/or resolution was set to ANY, double check any description requirements:[/bold red]")
                                console.print(f"[bold yellow]Request desc:[/bold yellow] {api_description[:100]}")
                                console.print()

                            if meta.get('uuid') not in existing_uuids:
                                request_entry = {
                                    'uuid': meta.get('uuid'),
                                    'path': meta.get('path', ''),
                                    'url': new_url,
                                    'name': api_name,
                                    'bounty': api_bounty,
                                    'description': api_description,
                                    'claimed': api_claimed
                                }
                                request_data.append(request_entry)
                                existing_uuids.add(meta.get('uuid'))
                        else:
                            console.print(f"[bold blue]Found request on [bold yellow]{tracker_name}[/bold yellow] with bounty [bold yellow]{api_bounty}[/bold yellow] and with status [bold yellow]{api_status}[/bold yellow][/bold blue]")
                            console.print(f"[bold blue]Claimed status:[/bold blue] [bold yellow]{api_claimed}[/bold yellow]")
                            if meta.get('category') == "MOVIE":
                                console.print(f"[bold yellow]{api_name}:[/bold yellow] {new_url}")
                            else:
                                console.print(f"[bold yellow]{api_name}[/bold yellow] - [bold yellow]S{api_season:02d} E{api_episode:02d}:[/bold yellow] {new_url}")
                            console.print(f"[bold green]Request desc: {api_description[:100]}[/bold green]")
                            console.print()

                            if not api_claimed and meta.get('uuid') not in existing_uuids:
                                request_entry = {
                                    'uuid': meta.get('uuid'),
                                    'path': meta.get('path', ''),
                                    'url': new_url,
                                    'name': api_name,
                                    'bounty': api_bounty,
                                    'description': api_description,
                                    'claimed': api_claimed,
                                    'match_type': 'partial'
                                }
                                request_data.append(request_entry)
                                existing_uuids.add(meta.get('uuid'))
                else:
                    unclaimed = each.get('status') == 1
                    internal = each.get('internal') == 1
                    claimed_status = ""
                    if each.get('status') == 1:
                        claimed_status = "Unfilled"
                    elif each.get('status') == 2:
                        claimed_status = "Claimed"
                    elif each.get('status') == 3:
                        claimed_status = "Pending"
                    dv = False
                    hdr = False
                    season = False
                    meta_hdr = meta.get('HDR', '')
                    is_season = re.search(r'S\d{2}', api_name)
                    if is_season and is_season == meta.get('season'):
                        season = True
                    if each.get('dv') and meta_hdr == "DV":
                        dv = True
                    if each.get('hdr') and meta_hdr in ("HDR10", "HDR10+", "HDR"):
                        hdr = True
                    if not each.get('dv') and "DV" not in meta_hdr:
                        dv = True
                    if not each.get('hdr') and meta_hdr not in ("HDR10", "HDR10+", "HDR"):
                        hdr = True
                    if 'remux' in api_resolution_lower:
                        if 'uhd' in api_resolution_lower and meta.get('resolution') == "2160p" and meta.get('type') == "REMUX" or 'uhd' not in api_resolution_lower and meta.get('resolution') == "1080p" and meta.get('type') == "REMUX":
                            resolution = True
                            type_name = True
                    elif 'remux' not in api_resolution_lower and meta.get('is_disc') == "BDMV":
                        if 'uhd' in api_resolution_lower and meta.get('resolution') == "2160p" or 'uhd' not in api_resolution_lower and meta.get('resolution') == "1080p":
                            resolution = True
                            type_name = True
                    elif api_resolution == meta.get('resolution'):
                        resolution = True
                    meta_type = str(meta.get('type') or '')
                    if 'Blu-ray' in api_type_str and meta_type == "ENCODE" or 'WEB' in api_type_str and 'WEB' in meta_type:
                        type_name = True
                    if meta.get('category') == "MOVIE" and type_name and resolution and unclaimed and not internal and dv and hdr:
                        console.print(f"[bold blue]Found exact request match on [bold yellow]{tracker_name}[/bold yellow] with bounty [bold yellow]{api_bounty}[/bold yellow] and with status [bold yellow]{claimed_status}[/bold yellow][/bold blue]")
                        console.print(f"[bold green]{api_name}:[/bold green] {each.get('url')}")
                        console.print()

                        if meta.get('uuid') not in existing_uuids:
                            request_entry = {
                                'uuid': meta.get('uuid'),
                                'path': meta.get('path', ''),
                                'url': each.get('url', ''),
                                'name': api_name,
                                'bounty': api_bounty,
                                'claimed': claimed_status
                            }
                            request_data.append(request_entry)
                            existing_uuids.add(meta.get('uuid'))
                    if meta.get('category') == "MOVIE" and type_name and resolution and unclaimed and not internal and not dv and not hdr and 'uhd' in api_resolution_lower:
                        console.print(f"[bold blue]Found request match on [bold yellow]{tracker_name}[/bold yellow] with bounty [bold yellow]{api_bounty}[/bold yellow] with mismatched HDR or DV[/bold blue]")
                        console.print(f"[bold green]{api_name}:[/bold green] {each.get('url')}")
                        console.print()

                        if meta.get('uuid') not in existing_uuids:
                            request_entry = {
                                'uuid': meta.get('uuid'),
                                'path': meta.get('path', ''),
                                'url': each.get('url', ''),
                                'name': api_name,
                                'bounty': api_bounty,
                                'claimed': claimed_status
                            }
                            request_data.append(request_entry)
                            existing_uuids.add(meta.get('uuid'))
                    if meta.get('category') == "TV" and season and type_name and resolution and unclaimed and not internal and dv and hdr:
                        console.print(f"[bold blue]Found exact request match on [bold yellow]{tracker_name}[/bold yellow] with bounty [bold yellow]{api_bounty}[/bold yellow] and with status [bold yellow]{claimed_status}[/bold yellow][/bold blue]")
                        console.print(f"[bold yellow]{api_name}[/bold yellow] - [bold yellow]{meta.get('season')}:[/bold yellow] {each.get('url')}")
                        console.print()

                        if meta.get('uuid') not in existing_uuids:
                            request_entry = {
                                'uuid': meta.get('uuid'),
                                'path': meta.get('path', ''),
                                'url': each.get('url', ''),
                                'name': api_name,
                                'bounty': api_bounty,
                                'claimed': claimed_status
                            }
                            request_data.append(request_entry)
                            existing_uuids.add(meta.get('uuid'))
                    if meta.get('category') == "TV" and season and type_name and resolution and unclaimed and not internal and not dv and not hdr:
                        console.print(f"[bold blue]Found request match on [bold yellow]{tracker_name}[/bold yellow] with bounty [bold yellow]{api_bounty}[/bold yellow] with mismatched HDR or DV[/bold blue]")
                        console.print(f"[bold yellow]{api_name}[/bold yellow] - [bold yellow]{meta.get('season')}:[/bold yellow] {each.get('url')}")
                        console.print()

                        if meta.get('uuid') not in existing_uuids:
                            request_entry = {
                                'uuid': meta.get('uuid'),
                                'path': meta.get('path', ''),
                                'url': each.get('url', ''),
                                'name': api_name,
                                'bounty': api_bounty,
                                'claimed': claimed_status
                            }
                            request_data.append(request_entry)
                            existing_uuids.add(meta.get('uuid'))
                    else:
                        console.print(f"[bold blue]Found request on [bold yellow]{tracker_name}[/bold yellow] with bounty [bold yellow]{api_bounty}[/bold yellow] and with status [bold yellow]{claimed_status}[/bold yellow][/bold blue]")
                        if internal:
                            console.print("[bold red]Request is internal only[/bold red]")
                        console.print(f"[bold yellow]{api_name}[/bold yellow] - {each.get('url')}")
                        console.print()

            # Save all logged requests to file
            if request_data:
                async with aiofiles.open(log_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(request_data, indent=4))

            return requests

        results = await asyncio.gather(*[process_single_tracker(tracker) for tracker in trackers])
        match_found = any(results)

        return match_found

    async def process_trumpables(self, meta, trackers):
        if isinstance(trackers, str):
            trackers = [trackers.strip().upper()]
        elif isinstance(trackers, list):
            trackers = [s.upper() for s in trackers]
        else:
            console.print("[red]Invalid trackers input format.[/red]")
            return False

        # Track which trackers support trumping for later use
        trumping_trackers: list[str] = []

        for tracker in trackers:
            tracker_instance = self._create_tracker_instance(tracker)
            if tracker_instance is None:
                console.print(f"[red]Tracker {tracker} is not registered in tracker_class_map[/red]")
                continue

            if not isinstance(getattr(tracker_instance, 'trumping_url', None), str):
                continue  # Skip trackers without trumping url support

            trumping_trackers.append(tracker)
        if not trumping_trackers:
            if meta['debug']:
                console.print("[yellow]No trackers with trumping support found.[/yellow]")
            return False

        # Track trackers to skip without mutating meta['trackers'] in-place
        # NOTE: meta['skip_trackers'] is used elsewhere as a boolean, so use a distinct key here.
        meta.setdefault('skip_upload_trackers', [])

        # Store which trackers we're trump reporting on (may be filtered later)
        meta['trumping_trackers'] = trumping_trackers

        for tracker in trumping_trackers:
            tracker_instance = self._create_tracker_instance(tracker)
            if tracker_instance is None:
                console.print(f"[red]Tracker {tracker} is not registered in tracker_class_map[/red]")
                continue
            url = getattr(tracker_instance, 'trumping_url', None)
            if not isinstance(url, str):
                continue

            reported_torrent_id = f"{meta.get('trumpable_id', '')}"
            if not reported_torrent_id:
                # Try tracker-specific matched ID
                reported_torrent_id = f"{meta.get(f'{tracker}_matched_id', '')}"
            if not reported_torrent_id and meta.get('matched_episode_ids', []):
                reported_torrent_id = f"{meta['matched_episode_ids'][0].get('id', '')}"
            if not reported_torrent_id:
                console.print(f"[red]No reported torrent ID found in meta for trumpable processing on {tracker}[/red]")
                continue
            else:
                # Store per-tracker to avoid overwriting across multiple trackers
                meta[f'{tracker}_reported_torrent_id'] = reported_torrent_id

            trumping_reports, status = await self.get_tracker_trumps(meta, tracker, url, reported_torrent_id)
            if status != 200:
                console.print(f"[bold red]Failed to retrieve trumping reports from {tracker}. HTTP Status: {status}[/bold red]")
                # Mark this tracker as failed/skipped and continue to the next tracker
                console.print(f"[bold red]Marking {tracker} to be skipped due to API failure[/bold red]")
                if tracker not in meta['skip_upload_trackers']:
                    meta['skip_upload_trackers'].append(tracker)
                meta.setdefault('tracker_status', {})
                meta['tracker_status'].setdefault(tracker, {})
                meta['tracker_status'][tracker]['skip_upload'] = True
                continue
            if trumping_reports:
                console.print(f"[bold yellow]Found {len(trumping_reports)} existing trumping report/s on {tracker} for this release[/bold yellow]")
                for report in trumping_reports:
                    console.print(f"  [cyan]Report ID:[/cyan] {report.get('id')} - [cyan]Title:[/cyan] {report.get('title')}")
                    if report.get('trumping_torrent'):
                        for torrent in report.get('trumping_torrent', []):
                            torrent_name = torrent.get('name', 'Unknown')
                            torrent_id = torrent.get('id', 'N/A')
                            console.print(f"  [bold green]Already being trumped by:[/bold green] {torrent_name} (ID: {torrent_id})")
                    else:
                        console.print("  [yellow]The trumping torrent for this report seems to be in modq.....[/yellow]")
                try:
                    upload = cli_ui.ask_yes_no("Do you want to proceed with the upload anyway?", default=False)
                except (EOFError, KeyboardInterrupt):
                    console.print("[yellow]Prompt cancelled; treating as 'no' for safety.[/yellow]")
                    upload = False

                if not upload:
                    console.print(f"[bold red]Marking {tracker} to be skipped[/bold red]")
                    if tracker not in meta['skip_upload_trackers']:
                        meta['skip_upload_trackers'].append(tracker)
                    # Also mark in tracker_status when available (used elsewhere to skip upload)
                    meta.setdefault('tracker_status', {})
                    meta['tracker_status'].setdefault(tracker, {})
                    meta['tracker_status'][tracker]['skip_upload'] = True
                    continue
                console.print(f"[bold green]Proceeding with upload despite existing trumping reports on {tracker}[/bold green]")
            else:
                if meta['debug']:
                    console.print(f"[bold green]Will make a trumpable report for this upload at {trumping_trackers}[/bold green]")

        # Filter trumping trackers by skip marker (do not mutate meta['trackers'] here)
        active_trumping_trackers = [t for t in trumping_trackers if t not in meta.get('skip_upload_trackers', [])]
        meta['trumping_trackers'] = active_trumping_trackers
        if not active_trumping_trackers:
            if meta.get('debug'):
                console.print("[yellow]All trump-capable trackers were marked to skip; skipping trump report creation.[/yellow]")
            return False

        if not meta.get('tv_pack'):
            console.print("[yellow]Aither requires comparisons to be provided for trump reports.\n"
                          "Are the comparison images in the description or are you adding links?")
            try:
                where_compare = cli_ui.ask_string(
                    "Enter 'd' if in description, 'L' if you want to paste links, or press Enter to skip trumping:",
                    default=""
                )
            except (EOFError, KeyboardInterrupt):
                console.print("[yellow]Prompt cancelled; skipping trump report creation.[/yellow]")
                return False

            where_compare = (where_compare or "").strip()
            if where_compare.lower() == 'd':
                meta['screenshots_in_description'] = True
                return True
            elif where_compare.upper() == 'L':
                try:
                    reported_screenshots = cli_ui.ask_string(
                        "Paste screenshot links for the reported torrent (comma-separated):",
                        default=""
                    )
                    trumping_screenshots = cli_ui.ask_string(
                        "Paste screenshot links for the trumping torrent (comma-separated):",
                        default=""
                    )
                except (EOFError, KeyboardInterrupt):
                    console.print("[yellow]Prompt cancelled; skipping trump report creation.[/yellow]")
                    return False

                reported_screenshots = (reported_screenshots or "").strip()
                trumping_screenshots = (trumping_screenshots or "").strip()
                if not reported_screenshots or not trumping_screenshots:
                    console.print("[yellow]No screenshot links provided. Skipping trump report creation.[/yellow]")
                    return False

                meta['screenshots_reported_torrent'] = [link.strip() for link in reported_screenshots.split(',') if link.strip()]
                meta['screenshots_trumping_torrent'] = [link.strip() for link in trumping_screenshots.split(',') if link.strip()]
                if not meta['screenshots_reported_torrent'] or not meta['screenshots_trumping_torrent']:
                    console.print("[yellow]No valid screenshot links provided. Skipping trump report creation.[/yellow]")
                    return False
                return True
            else:
                console.print("[yellow]Skipping trump report creation as no comparison method provided.[/yellow]")
                return False
        else:
            if meta.get('debug'):
                console.print(f"[bold green]TV pack upload detected, skipping comparison images for trump report on {active_trumping_trackers}[/bold green]")
            return True

    async def get_tracker_trumps(self, meta, tracker, url, reported_torrent_id):
        if meta['debug']:
            console.print(f"[bold green]Searching for trumps on {tracker}[/bold green]")
        requests: list[dict[str, Any]] = []
        status_code = None
        headers = {
            'Authorization': f"Bearer {self.config['TRACKERS'][tracker]['api_key'].strip()}",
            'Accept': 'application/json'
        }

        params = {
            'reported_torrent_id': f"{reported_torrent_id}",
        }

        all_data: list[dict[str, Any]] = []
        next_cursor = None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                while True:
                    try:
                        # Add pagination cursor to params if we have one
                        if next_cursor:
                            params['cursor'] = next_cursor

                        response = await client.get(url=url, headers=headers, params=params)
                        status_code = response.status_code

                        if response.status_code == 200:
                            data = response.json()

                            if 'data' in data and isinstance(data['data'], list):
                                page_data = data['data']
                            elif 'results' in data and isinstance(data['results'], list):
                                page_data = data['results']
                            else:
                                console.print(f"[bold red]Unexpected response format: {type(data)}[/bold red]")
                                return requests, status_code

                            all_data.extend(page_data)

                            # Check for pagination
                            meta_info = data.get('meta', {})
                            if not isinstance(meta_info, dict):
                                console.print(f"[bold red]Unexpected 'meta' format: {type(meta_info)}[/bold red]")
                                break

                            next_cursor = meta_info.get('next_cursor')
                            if not next_cursor:
                                break  # Exit loop if there are no more pages
                            else:
                                # Rest between page fetches
                                console.print(f"[cyan]Fetched {len(page_data)} trumping reports, waiting 1 second before next page...[/cyan]")
                                await asyncio.sleep(1)
                        else:
                            console.print(f"[bold red]Failed to search trumps on {tracker}. HTTP Status: {response.status_code} - {response.text}[/bold red]")
                            break

                    except httpx.RequestError as e:
                        console.print(f"[bold red]HTTP Request failed: {e}[/bold red]")
                        break

                # Process all collected data
                try:
                    for each in all_data:
                        # Normalize trumping_torrent to always be a list
                        trumping_torrent = each.get('trumping_torrent')
                        if trumping_torrent is None:
                            trumping_torrent = []
                        elif isinstance(trumping_torrent, dict):
                            trumping_torrent = [trumping_torrent] if trumping_torrent else []

                        result = {
                            'id': each.get('id'),
                            'type': each.get('type'),
                            'title': each.get('title'),
                            'solved': each.get('solved'),
                            'reported_torrents': each.get('reported_torrents', []),
                            'trumping_torrent': trumping_torrent,
                        }
                        requests.append(result)

                except Exception as e:
                    console.print(f"[bold red]Error processing response data: {e}[/bold red]")
                    return requests, status_code

        except httpx.TimeoutException:
            console.print("[bold red]Request timed out after 10 seconds")
            status_code = None
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            status_code = None

        if meta['debug']:
            console.print(f"Total trumping reports retrieved: {len(requests)}")

        return requests, status_code

    async def make_trumpable_report(self, meta, tracker):
        """Create a trump report by POSTing to the /create endpoint"""
        if meta['debug']:
            console.print(f"[bold green]Creating trump report on {tracker}[/bold green]")

        tracker_instance = self._create_tracker_instance(tracker)
        if not tracker_instance:
            console.print(f"[red]Tracker {tracker} is not registered in tracker_class_map[/red]")
            return False

        base_url = getattr(tracker_instance, 'trumping_url', None)
        if not isinstance(base_url, str):
            console.print(f"[red]No trumping URL found for {tracker}[/red]")
            return False

        # Replace /filter with /create
        create_url = base_url.replace('/filter', '/create')

        headers = {
            'Authorization': f"Bearer {self.config['TRACKERS'][tracker]['api_key'].strip()}",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        # Read per-tracker reported_torrent_id, with fallback to legacy key for backwards compatibility
        reported_torrent_id = meta.get(f'{tracker}_reported_torrent_id') or meta.get('reported_torrent_id')
        if not reported_torrent_id:
            console.print(f"[red]No reported torrent ID found for {tracker}[/red]")
            return False
        try:
            trumping_torrent_id = meta['tracker_status'][tracker]['torrent_id']
        except KeyError:
            console.print(f"[red]No torrent ID found in meta for trumping torrent on {tracker}[/red]")
            console.print("[red]Either the upload failed, or you're in debug[/red]")
            if not meta.get('debug', False):
                return False
            # Set fallback for debug mode so payload construction doesn't fail
            trumping_torrent_id = None

        if meta.get('tv_pack'):
            message = "Upload Assistant season pack trump"
        elif meta.get('trump_reason') == 'exact_match':
            message = "Upload Assistant exact filename trump"
        elif meta.get('trump_reason') == 'trumpable_release':
            message = "Upload Assistant trumpable release trump"
        else:
            message = "Upload Assistant is trumping this torrent for reasons Audionut has not correctly caught. User selected yes at a prompt."

        payload = {
            'reported_torrent_id': reported_torrent_id,
            'trumping_torrent_id': trumping_torrent_id,
            'message': message
        }
        if 'screenshots_reported_torrent' in meta:
            payload['screenshots_reported_torrent'] = ','.join(meta['screenshots_reported_torrent'])
        if 'screenshots_trumping_torrent' in meta:
            payload['screenshots_trumping_torrent'] = ','.join(meta['screenshots_trumping_torrent'])
        if 'screenshots_in_description' in meta and meta['screenshots_in_description']:
            payload['message'] += " - User says comparison screenshots are in description."
        if not meta.get('debug', False):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(url=create_url, headers=headers, json=payload)
                    if response.status_code in (200, 201):
                        console.print(f"[bold green]Successfully created trump report on {tracker}[/bold green]")
                        return True
                    else:
                        console.print(f"[bold red]Failed to create trump report. HTTP Status: {response.status_code}[/bold red]")
                        return False

            except httpx.TimeoutException:
                console.print("[bold red]Request timed out after 10 seconds[/bold red]")
                return False
            except httpx.RequestError as e:
                console.print(f"[bold red]HTTP Request failed: {e}[/bold red]")
                return False
            except Exception as e:
                console.print(f"[bold red]Unexpected error: {e}[/bold red]")
                return False
        else:
            console.print("[bold yellow]Debug mode enabled, skipping actual trump report creation.[/bold yellow]")
            console.print(f"[cyan]POST URL: {create_url}[/cyan]")
            console.print(f"[cyan]Payload: {payload}[/cyan]")
            return True


tracker_class_map: dict[str, type[Any]] = {
    'ACM': ACM, 'AITHER': AITHER, 'ANT': ANT, 'AR': AR, 'ASC': ASC, 'AZ': AZ, 'BHD': BHD, 'BHDTV': BHDTV, 'BJS': BJS, 'BLU': BLU, 'BT': BT, 'CBR': CBR,
    'CZ': CZ, 'DC': DC, 'DP': DP, 'EMUW': EMUW, 'FNP': FNP, 'FF': FF, 'FL': FL, 'FRIKI': FRIKI, 'GPW': GPW, 'HDB': HDB, 'HDS': HDS, 'HDT': HDT, 'HHD': HHD, 'HUNO': HUNO, 'ITT': ITT,
    'IHD': IHD, 'IS': IS, 'LCD': LCD, 'LDU': LDU, 'LST': LST, 'LT': LT, 'MTV': MTV, 'NBL': NBL, 'OE': OE, 'OTW': OTW, 'PHD': PHD, 'PT': PT, 'PTP': PTP, 'PTER': PTER, 'PTS': PTS, 'PTT': PTT,
    'R4E': R4E, 'RAS': RAS, 'RF': RF, 'RTF': RTF, 'SAM': SAM, 'SHRI': SHRI, 'SN': SN, 'SP': SP, 'SPD': SPD, 'STC': STC, 'THR': THR,
    'TIK': TIK, 'TL': TL, 'TLZ': TLZ, 'TOS': TOS, 'TVC': TVC, 'TTG': TTG, 'TTR': TTR, 'ULCX': ULCX, 'UTP': UTP, 'YOINK': YOINK, 'YUS': YUS
}

api_trackers = {
    'ACM', 'AITHER', 'BHD', 'BLU', 'CBR', 'DP', 'EMUW', 'FNP', 'FRIKI', 'HHD', 'HUNO', 'IHD', 'ITT', 'LCD', 'LDU', 'LST', 'LT',
    'OE', 'OTW', 'PT', 'PTT', 'RAS', 'RF', 'R4E', 'SAM', 'SHRI', 'SP', 'STC', 'TIK', 'TLZ', 'TOS', 'TTR', 'ULCX', 'UTP', 'YOINK', 'YUS'
}

other_api_trackers = {
    'ANT', 'BHDTV', 'DC', 'GPW', 'NBL', 'RTF', 'SN', 'SPD', 'TL', 'TVC'
}

http_trackers = {
    'AR', 'ASC', 'AZ', 'BJS', 'BT', 'CZ', 'FF', 'FL', 'HDB', 'HDS', 'HDT', 'IS', 'MTV', 'PHD', 'PTER', 'PTS', 'TTG'
}
