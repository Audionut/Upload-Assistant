# -*- coding: utf-8 -*-
# import discord
import os
import asyncio
import requests
import platform
import httpx
import json
from pymediainfo import MediaInfo
from pathlib import Path
from src.trackers.COMMON import COMMON
from src.console import console
from src.torrentcreate import create_torrent


class ANT():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """

    def __init__(self, config):
        self.config = config
        self.tracker = 'ANT'
        self.source_flag = 'ANT'
        self.search_url = 'https://anthelion.me/api.php'
        self.upload_url = 'https://anthelion.me/api.php'
        self.banned_groups = [
            '3LTON', '4yEo', 'ADE', 'AFG', 'AniHLS', 'AnimeRG', 'AniURL', 'AROMA', 'aXXo', 'Brrip', 'CHD', 'CM8',
            'CrEwSaDe', 'd3g', 'DDR', 'DNL', 'DeadFish', 'ELiTE', 'eSc', 'FaNGDiNG0', 'FGT', 'Flights', 'FRDS',
            'FUM', 'HAiKU', 'HD2DVD', 'HDS', 'HDTime', 'Hi10', 'ION10', 'iPlanet', 'JIVE', 'KiNGDOM', 'Leffe',
            'LiGaS', 'LOAD', 'MeGusta', 'MkvCage', 'mHD', 'mSD', 'NhaNc3', 'nHD', 'NOIVTC', 'nSD', 'Oj', 'Ozlem',
            'PiRaTeS', 'PRoDJi', 'RAPiDCOWS', 'RARBG', 'RetroPeeps', 'RDN', 'REsuRRecTioN', 'RMTeam', 'SANTi',
            'SicFoI', 'SPASM', 'SPDVD', 'STUTTERSHIT', 'TBS', 'Telly', 'TM', 'UPiNSMOKE', 'URANiME', 'WAF', 'xRed',
            'XS', 'YIFY', 'YTS', 'Zeus', 'ZKBL', 'ZmN', 'ZMNT'
        ]
        self.signature = None
        pass

    async def get_flags(self, meta):
        flags = []
        for each in ['Directors', 'Extended', 'Uncut', 'Unrated', '4KRemaster']:
            if each in meta['edition'].replace("'", ""):
                flags.append(each)
        for each in ['Dual-Audio', 'Atmos']:
            if each in meta['audio']:
                flags.append(each.replace('-', ''))
        if meta.get('has_commentary', False):
            flags.append('Commentary')
        if meta['3D'] == "3D":
            flags.append('3D')
        if "HDR" in meta['hdr']:
            flags.append('HDR10')
        if "DV" in meta['hdr']:
            flags.append('DV')
        if "Criterion" in meta.get('distributor', ''):
            flags.append('Criterion')
        if "REMUX" in meta['type']:
            flags.append('Remux')
        return flags

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        torrent_filename = "BASE"
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"
        torrent_file_size_kib = os.path.getsize(torrent_path) / 1024

        # Trigger regeneration automatically if size constraints aren't met
        if torrent_file_size_kib > 250:  # 250 KiB
            console.print("[yellow]Existing .torrent exceeds 250 KiB and will be regenerated to fit constraints.")
            meta['max_piece_size'] = '256'  # 256 MiB
            create_torrent(meta, Path(meta['path']), "ANT")
            torrent_filename = "ANT"

        await common.edit_torrent(meta, self.tracker, self.source_flag, torrent_filename=torrent_filename)
        flags = await self.get_flags(meta)

        if meta['bdinfo'] is not None:
            bd_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
            bd_dump = f'[spoiler=BDInfo][pre]{bd_dump}[/pre][/spoiler]'
            path = os.path.join(meta['bdinfo']['path'], 'STREAM')
            longest_file = max(
                meta['bdinfo']['files'],
                key=lambda x: x.get('length', 0)
            )
            file_name = longest_file['file'].lower()
            m2ts = os.path.join(path, file_name)
            media_info_output = str(MediaInfo.parse(m2ts, output="text", full=False))
            mi_dump = media_info_output.replace('\r\n', '\n')
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent", 'rb')
        files = {'file_input': open_torrent}
        data = {
            'api_key': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'action': 'upload',
            'tmdbid': meta['tmdb'],
            'mediainfo': mi_dump,
            'flags[]': flags,
            'screenshots': '\n'.join([x['raw_url'] for x in meta['image_list']][:4]),
        }
        if meta['bdinfo'] is not None:
            data.update({
                'media': 'Blu-ray',
                'releasegroup': str(meta['tag'])[1:],
                'release_desc': bd_dump,
                'flagchangereason': "BDMV Uploaded with Upload Assistant"})
        if meta['scene']:
            # ID of "Scene?" checkbox on upload form is actually "censored"
            data['censored'] = 1
        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        }

        try:
            if not meta['debug']:
                response = requests.post(url=self.upload_url, files=files, data=data, headers=headers)
                if response.status_code in [200, 201]:
                    response_data = response.json()
                    meta['tracker_status'][self.tracker]['status_message'] = response_data
                elif response.status_code == 502:
                    response_data = {
                        "error": "Bad Gateway",
                        "site seems down": "https://ant.trackerstatus.info/"
                    }
                    meta['tracker_status'][self.tracker]['status_message'] = f"data error - {response_data}"
                else:
                    response_data = {
                        "error": f"Unexpected status code: {response.status_code}",
                        "response_content": response.text
                    }
                    meta['tracker_status'][self.tracker]['status_message'] = f"data error - {response_data}"
            else:
                console.print("[cyan]Request Data:")
                console.print(data)
                meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        finally:
            open_torrent.close()

    async def edit_desc(self, meta):
        return

    async def search_existing(self, meta, disctype):
        if meta.get('category') == "TV":
            if not meta['unattended']:
                console.print('[bold red]ANT only ALLOWS Movies.')
            meta['skipping'] = "ANT"
            return []
        dupes = []
        params = {
            'apikey': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            't': 'search',
            'o': 'json'
        }
        if str(meta['tmdb']) != 0:
            params['tmdb'] = meta['tmdb']
        elif int(meta['imdb_id']) != 0:
            params['imdb'] = meta['imdb']

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url='https://anthelion.me/api', params=params)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        target_resolution = meta.get('resolution', '').lower()

                        for each in data.get('item', []):
                            if target_resolution and each.get('resolution', '').lower() != target_resolution.lower():
                                if meta.get('debug'):
                                    console.print(f"[yellow]Skipping {each.get('fileName')} - resolution mismatch: {each.get('resolution')} vs {target_resolution}")
                                continue

                            largest_file = None
                            if 'files' in each and len(each['files']) > 0:
                                largest = each['files'][0]
                                for file in each['files']:
                                    if int(file.get('size', 0)) > int(largest.get('size', 0)):
                                        largest = file
                                largest_file = largest.get('name', '')

                            result = {
                                'name': largest_file or each.get('fileName', ''),
                                'size': int(each.get('size', 0)),
                                'flags': each.get('flags', [])
                            }
                            dupes.append(result)

                            if meta.get('debug'):
                                console.print(f"[green]Found potential dupe: {result['name']} ({result['size']} bytes)")

                    except json.JSONDecodeError:
                        console.print("[bold yellow]ANT Response content is not valid JSON. Skipping this API call.")
                        meta['skipping'] = "ANT"
                else:
                    console.print(f"[bold red]ANT Failed to search torrents. HTTP Status: {response.status_code}")
                    meta['skipping'] = "ANT"
        except httpx.TimeoutException:
            console.print("[bold red]ANT Request timed out after 5 seconds")
            meta['skipping'] = "ANT"
        except httpx.RequestError as e:
            console.print(f"[bold red]ANT Unable to search for existing torrents: {e}")
            meta['skipping'] = "ANT"
        except Exception as e:
            console.print(f"[bold red]ANT Unexpected error: {e}")
            meta['skipping'] = "ANT"
            await asyncio.sleep(5)

        return dupes
