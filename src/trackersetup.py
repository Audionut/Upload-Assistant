from src.trackers.AR import AR
from src.trackers.HUNO import HUNO
from src.trackers.BLU import BLU
from src.trackers.BHD import BHD
from src.trackers.AITHER import AITHER
from src.trackers.STC import STC
from src.trackers.R4E import R4E
from src.trackers.THR import THR
from src.trackers.STT import STT
from src.trackers.HP import HP
from src.trackers.PTP import PTP
from src.trackers.SN import SN
from src.trackers.ACM import ACM
from src.trackers.HDB import HDB
from src.trackers.LCD import LCD
from src.trackers.TTG import TTG
from src.trackers.LST import LST
from src.trackers.FRIKI import FRIKI
from src.trackers.FL import FL
from src.trackers.LT import LT
from src.trackers.NBL import NBL
from src.trackers.ANT import ANT
from src.trackers.PTER import PTER
from src.trackers.MTV import MTV
from src.trackers.JPTV import JPTV
from src.trackers.TL import TL
from src.trackers.HDT import HDT
from src.trackers.RF import RF
from src.trackers.OE import OE
from src.trackers.BHDTV import BHDTV
from src.trackers.RTF import RTF
from src.trackers.OTW import OTW
from src.trackers.FNP import FNP
from src.trackers.CBR import CBR
from src.trackers.UTP import UTP
from src.trackers.AL import AL
from src.trackers.SHRI import SHRI
from src.trackers.TIK import TIK
from src.trackers.TVC import TVC
from src.trackers.PSS import PSS
from src.trackers.ULCX import ULCX
from src.trackers.SPD import SPD
from src.trackers.YOINK import YOINK
from src.trackers.HHD import HHD
from src.trackers.SP import SP
from src.console import console
import httpx
import aiofiles
import os
import json
from datetime import datetime, timedelta
import asyncio


class TRACKER_SETUP:
    def __init__(self, config):
        self.config = config
        # Add initialization details here
        pass

    def trackers_enabled(self, meta):
        from data.config import config
        if meta.get('trackers', None) is not None:
            trackers = meta['trackers']
        else:
            trackers = config['TRACKERS']['default_trackers']
        if "," in trackers:
            trackers = trackers.split(',')

        if isinstance(trackers, str):
            trackers = trackers.split(',')
        trackers = [s.strip().upper() for s in trackers]
        if meta.get('manual', False):
            trackers.insert(0, "MANUAL")
        return trackers

    async def get_banned_groups(self, meta, tracker):
        file_path = os.path.join(meta['base_dir'], 'data', 'banned', f'{tracker}_banned_groups.json')

        # Check if we need to update
        if not await self.should_update(file_path):
            return file_path

        url = None
        if tracker.upper() == "AITHER":
            url = f'https://{tracker}.cc/api/blacklists/releasegroups'
        elif tracker.upper() == "LST":
            url = f"https://{tracker}.gg/api/bannedReleaseGroups"

        if not url:
            console.print(f"Error: Tracker '{tracker}' is not supported.")
            return None

        headers = {
            'Authorization': f"Bearer {self.config['TRACKERS'][tracker]['api_key'].strip()}",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    await self.write_banned_groups_to_file(file_path, data)
                    return file_path
                elif response.status_code == 404:
                    console.print(f"Error: Tracker '{tracker}' returned 404 for the banned groups API.")
                else:
                    console.print(f"Error: Received status code {response.status_code} for tracker '{tracker}'.")
            except httpx.RequestError as e:
                console.print(f"HTTP Request failed for tracker '{tracker}': {e}")

        return None

    async def write_banned_groups_to_file(self, file_path, json_data):
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            names = [item['name'] for item in json_data.get('data', [])]
            names_csv = ', '.join(names)
            file_content = {
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "banned_groups": names_csv,
                "raw_data": json_data
            }
            async with aiofiles.open(file_path, mode='w') as file:
                await file.write(json.dumps(file_content, indent=4))
            console.print(f"File '{file_path}' updated successfully with {len(names)} groups.")
        except Exception as e:
            console.print(f"An error occurred: {e}")

    async def should_update(self, file_path):
        try:
            async with aiofiles.open(file_path, mode='r') as file:
                content = await file.read()
                data = json.loads(content)
                last_updated = datetime.strptime(data['last_updated'], "%Y-%m-%d")
                return datetime.now() >= last_updated + timedelta(days=2)
        except FileNotFoundError:
            return True
        except Exception as e:
            console.print(f"Error reading file: {e}")
            return True

    async def check_banned_group(self, tracker, banned_group_list, meta):
        result = False
        if not meta['tag']:
            result = False
            return result

        if tracker.upper() in ("AITHER", "LST"):
            file_path = await self.get_banned_groups(meta, tracker)
            if not file_path:
                console.print(f"[bold red]Failed to load banned groups for '{tracker}'.")
                return result  # Early exit with False

            # Try to load the banned groups from the file
            try:
                async with aiofiles.open(file_path, mode='r') as file:
                    content = await file.read()
                    data = json.loads(content)
                    banned_groups = data.get("banned_groups", "")
                    if banned_groups:
                        banned_group_list.extend(banned_groups.split(", "))
            except FileNotFoundError:
                console.print(f"[bold red]Banned group file for '{tracker}' not found.")
                return result  # File not found, return False
            except json.JSONDecodeError:
                console.print(f"[bold red]Failed to parse banned group file for '{tracker}'.")
                return result  # Invalid JSON, return False

        for tag in banned_group_list:
            if isinstance(tag, list):
                if meta['tag'][1:].lower() == tag[0].lower():
                    console.print(f"[bold yellow]{meta['tag'][1:]}[/bold yellow][bold red] was found on [bold yellow]{tracker}'s[/bold yellow] list of banned groups.")
                    console.print(f"[bold red]NOTE: [bold yellow]{tag[1]}")
                    await asyncio.sleep(5)
                    result = True
            else:
                if meta['tag'][1:].lower() == tag.lower():
                    console.print(f"[bold yellow]{meta['tag'][1:]}[/bold yellow][bold red] was found on [bold yellow]{tracker}'s[/bold yellow] list of banned groups.")
                    await asyncio.sleep(5)
                    result = True
        return result

    async def write_internal_claims_to_file(self, file_path, data):
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            claims_data = data.get('data', [])
            if not isinstance(claims_data, list):
                console.print("The 'data' key is missing or not a list. Aborting.")
                return

            extracted_data = []
            for item in claims_data:
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
                console.print("No valid claims found to write.")
                return

            titles_csv = ', '.join([data['title'] for data in extracted_data])

            file_content = {
                "last_updated": datetime.now().strftime("%Y-%m-%d"),
                "titles_csv": titles_csv,
                "extracted_data": extracted_data,
                "raw_data": claims_data
            }

            async with aiofiles.open(file_path, mode='w') as file:
                await file.write(json.dumps(file_content, indent=4))

            console.print(f"File '{file_path}' updated successfully with {len(extracted_data)} claims.")
        except Exception as e:
            console.print(f"An error occurred: {e}")

    async def get_torrent_claims(self, meta, tracker):
        file_path = os.path.join(meta['base_dir'], 'data', 'banned', f'{tracker}_claimed_releases.json')

        # Check if we need to update
        if not await self.should_update(file_path):
            return await self.check_tracker_claims(meta, tracker)

        url = f'https://{tracker}.cc/api/internals/claim'
        headers = {
            'Authorization': f"Bearer {self.config['TRACKERS'][tracker]['api_key'].strip()}",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    await self.write_internal_claims_to_file(file_path, data)
                    return await self.check_tracker_claims(meta, tracker)
                else:
                    console.print(f"Error: Received status code {response.status_code}")
                    return False
            except httpx.RequestError as e:
                console.print(f"HTTP Request failed: {e}")
                return False

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
                tracker_class = tracker_class_map.get(tracker_name.upper())
                if not tracker_class:
                    console.print(f"[red]Tracker {tracker_name} is not registered in tracker_class_map[/red]")
                    return False

                tracker_instance = tracker_class(self.config)
                all_types = await tracker_instance.get_type_id()
                type_names = meta.get('type', [])
                if isinstance(type_names, str):
                    type_names = [type_names]

                type_ids = [all_types.get(type_name) for type_name in type_names]
                if None in type_ids:
                    console.print("[yellow]Warning: Some types in meta not found in tracker type mapping.[/yellow]")

                all_resolutions = await tracker_instance.get_res_id()
                resolution_names = meta.get('resolution', [])
                if isinstance(resolution_names, str):
                    resolution_names = [resolution_names]

                resolution_ids = [all_resolutions.get(res_name) for res_name in resolution_names]
                if None in resolution_ids:
                    console.print("[yellow]Warning: Some resolutions in meta not found in tracker resolution mapping.[/yellow]")

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
                seasonint = int(metaseason)
                file_path = os.path.join(meta['base_dir'], 'data', 'banned', f'{tracker_name}_claimed_releases.json')
                if not os.path.exists(file_path):
                    console.print(f"[red]No claim data file found for {tracker_name}[/red]")
                    return False

                with open(file_path, 'r') as file:
                    extracted_data = json.load(file).get('extracted_data', [])

                for item in extracted_data:
                    title = item.get('title')
                    season = item.get('season')
                    api_tmdb_id = item.get('tmdb_id')
                    api_resolutions = item.get('resolutions', [])
                    api_types = item.get('types', [])

                    if (
                        api_tmdb_id in tmdb_id
                        and season == seasonint
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


tracker_class_map = {
    'ACM': ACM, 'AITHER': AITHER, 'AL': AL, 'ANT': ANT, 'AR': AR, 'BHD': BHD, 'BHDTV': BHDTV, 'BLU': BLU, 'CBR': CBR,
    'FNP': FNP, 'FL': FL, 'FRIKI': FRIKI, 'HDB': HDB, 'HDT': HDT, 'HHD': HHD, 'HP': HP, 'HUNO': HUNO, 'JPTV': JPTV, 'LCD': LCD,
    'LST': LST, 'LT': LT, 'MTV': MTV, 'NBL': NBL, 'OE': OE, 'OTW': OTW, 'PSS': PSS, 'PTP': PTP, 'PTER': PTER,
    'R4E': R4E, 'RF': RF, 'RTF': RTF, 'SHRI': SHRI, 'SN': SN, 'SP': SP, 'SPD': SPD, 'STC': STC, 'STT': STT, 'THR': THR,
    'TIK': TIK, 'TL': TL, 'TVC': TVC, 'TTG': TTG, 'ULCX': ULCX, 'UTP': UTP, 'YOINK': YOINK,
}

api_trackers = {
    'ACM', 'AITHER', 'AL', 'BHD', 'BLU', 'CBR', 'FNP', 'FRIKI', 'HHD', 'HUNO', 'JPTV', 'LCD', 'LST', 'LT',
    'OE', 'OTW', 'PSS', 'RF', 'R4E', 'SHRI', 'SP', 'STC', 'STT', 'TIK', 'ULCX', 'UTP', 'YOINK'
}

other_api_trackers = {
    'ANT', 'BHDTV', 'NBL', 'RTF', 'SN', 'SPD', 'TL', 'TVC'
}

http_trackers = {
    'AR', 'FL', 'HDB', 'HDT', 'MTV', 'PTER', 'TTG'
}
