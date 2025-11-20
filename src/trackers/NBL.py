# -*- coding: utf-8 -*-
import json
import aiofiles
import httpx

from src.trackers.COMMON import COMMON
from src.console import console


class NBL():

    def __init__(self, config):
        self.config = config
        self.tracker = 'NBL'
        self.source_flag = 'NBL'
        self.upload_url = 'https://nebulance.io/upload.php'
        self.search_url = 'https://nebulance.io/api.php'
        self.api_key = self.config['TRACKERS'][self.tracker]['api_key'].strip()
        self.banned_groups = ['0neshot', '3LTON', '4yEo', '[Oj]', 'AFG', 'AkihitoSubs', 'AniHLS', 'Anime Time', 'AnimeRG', 'AniURL', 'ASW', 'BakedFish',
                              'bonkai77', 'Cleo', 'DeadFish', 'DeeJayAhmed', 'ELiTE', 'EMBER', 'eSc', 'EVO', 'FGT', 'FUM', 'GERMini', 'HAiKU', 'Hi10', 'ION10',
                              'JacobSwaggedUp', 'JIVE', 'Judas', 'LOAD', 'MeGusta', 'Mr.Deadpool', 'mSD', 'NemDiggers', 'neoHEVC', 'NhaNc3', 'NOIVTC',
                              'PlaySD', 'playXD', 'project-gxs', 'PSA', 'QaS', 'Ranger', 'RAPiDCOWS', 'Raze', 'Reaktor', 'REsuRRecTioN', 'RMTeam', 'ROBOTS',
                              'SpaceFish', 'SPASM', 'SSA', 'Telly', 'Tenrai-Sensei', 'TM', 'Trix', 'URANiME', 'VipapkStudios', 'ViSiON', 'Wardevil', 'xRed',
                              'XS', 'YakuboEncodes', 'YuiSubs', 'ZKBL', 'ZmN', 'ZMNT']
        pass

    async def get_cat_id(self, meta):
        if meta.get('tv_pack', 0) == 1:
            cat_id = 3
        else:
            cat_id = 1
        return cat_id

    async def edit_desc(self, meta):
        # Leave this in so manual works
        return

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)

        if meta['bdinfo'] is not None:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8') as f:
                mi_dump = await f.read()
        else:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8') as f:
                mi_dump = await f.read()
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        async with aiofiles.open(torrent_file_path, 'rb') as f:
            torrent_bytes = await f.read()
        files = {'file_input': ('torrent.torrent', torrent_bytes, 'application/x-bittorrent')}
        data = {
            'api_key': self.api_key,
            'tvmazeid': int(meta.get('tvmaze_id', 0)),
            'mediainfo': mi_dump,
            'category': await self.get_cat_id(meta),
            'ignoredupes': 'on'
        }

        try:
            if not meta['debug']:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(url=self.upload_url, files=files, data=data)
                    if response.status_code in [200, 201]:
                        try:
                            response_data = response.json()
                        except json.JSONDecodeError:
                            meta['tracker_status'][self.tracker]['status_message'] = "data error: NBL json decode error, the API is probably down"
                            return
                    else:
                        response_data = {
                            "error": f"Unexpected status code: {response.status_code}",
                            "response_content": response.text
                        }
                    meta['tracker_status'][self.tracker]['status_message'] = response_data
            else:
                console.print("[cyan]NBL Request Data:")
                console.print(data)
                meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        except Exception as e:
            meta['tracker_status'][self.tracker]['status_message'] = f"data error: Upload failed: {e}"

    async def search_existing(self, meta, disctype):
        if meta['category'] != 'TV':
            if not meta['unattended']:
                console.print("[red]Only TV Is allowed at NBL")
            meta['skipping'] = "NBL"
            return []

        if meta.get('is_disc') is not None:
            if not meta['unattended']:
                console.print('[bold red]NBL does not allow raw discs')
            meta['skipping'] = "NBL"
            return []

        dupes = []

        if int(meta.get('tvmaze_id', 0)) != 0:
            search_term = {'tvmaze': int(meta['tvmaze_id'])}
        elif int(meta.get('imdb_id')) != 0:
            search_term = {'imdb': meta.get('imdb')}
        else:
            search_term = {'series': meta['title']}
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getTorrents',
            'params': [
                self.api_key,
                search_term
            ]
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(self.search_url, json=payload)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        for each in data.get('result', {}).get('items', []):
                            if meta['resolution'] in each.get('tags', []):
                                file_list = each.get('file_list', [])
                                result = {
                                    'name': each.get('rls_name', ''),
                                    'files': ', '.join(file_list) if isinstance(file_list, list) else str(file_list),
                                    'size': int(each.get('size', 0)),
                                    'link': f'https://nebulance.io/torrents.php?id={each.get("group_id", "")}',
                                    'file_count': len(file_list) if isinstance(file_list, list) else 1,
                                }
                                dupes.append(result)
                    except json.JSONDecodeError:
                        console.print("[bold yellow]NBL response content is not valid JSON. Skipping this API call.")
                        meta['skipping'] = "NBL"
                else:
                    console.print(f"[bold red]NBL HTTP request failed. Status: {response.status_code}")
                    meta['skipping'] = "NBL"

        except httpx.TimeoutException:
            console.print("[bold red]NBL request timed out after 5 seconds")
            meta['skipping'] = "NBL"
        except httpx.RequestError as e:
            console.print(f"[bold red]NBL an error occurred while making the request: {e}")
            meta['skipping'] = "NBL"
        except KeyError as e:
            console.print(f"[bold red]Unexpected KeyError: {e}")
            if 'result' not in response.json():
                console.print("[red]NBL API returned an unexpected response. Please manually check for dupes.")
                dupes.append("ERROR: PLEASE CHECK FOR EXISTING RELEASES MANUALLY")
        except Exception as e:
            meta['skipping'] = "NBL"
            console.print(f"[bold red]NBL unexpected error: {e}")
            console.print_exception()

        return dupes

    # required for tracker type mapping
    is_other_api = True
