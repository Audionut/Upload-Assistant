# -*- coding: utf-8 -*-
import json
import requests
import httpx

from src.trackers.COMMON import COMMON
from src.console import console


class NBL():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """
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
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'r', encoding='utf-8').read().strip()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent", 'rb')
        files = {'file_input': open_torrent}
        data = {
            'api_key': self.api_key,
            'tvmazeid': int(meta.get('tvmaze_id', 0)),
            'mediainfo': mi_dump,
            'category': await self.get_cat_id(meta),
            'ignoredupes': 'on'
        }

        if meta['debug'] is False:
            response = requests.post(url=self.upload_url, files=files, data=data)
            try:
                if response.ok:
                    response = response.json()
                    meta['tracker_status'][self.tracker]['status_message'] = response
                else:
                    meta['tracker_status'][self.tracker]['status_message'] = response.text
            except Exception:
                console.print_exception()
                console.print("[bold yellow]It may have uploaded, go check")
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()

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
                                dupes.append(each['rls_name'])
                    except json.JSONDecodeError:
                        console.print("[bold yellow]Response content is not valid JSON. Skipping this API call.")
                        meta['skipping'] = "NBL"
                else:
                    console.print(f"[bold red]HTTP request failed. Status: {response.status_code}")
                    meta['skipping'] = "NBL"

        except httpx.TimeoutException:
            console.print("[bold red]Request timed out after 5 seconds")
            meta['skipping'] = "NBL"
        except httpx.RequestError as e:
            console.print(f"[bold red]An error occurred while making the request: {e}")
            meta['skipping'] = "NBL"
        except KeyError as e:
            console.print(f"[bold red]Unexpected KeyError: {e}")
            if 'result' not in response.json():
                console.print("[red]NBL API returned an unexpected response. Please manually check for dupes.")
                dupes.append("ERROR: PLEASE CHECK FOR EXISTING RELEASES MANUALLY")
        except Exception as e:
            meta['skipping'] = "NBL"
            console.print(f"[bold red]Unexpected error: {e}")
            console.print_exception()

        return dupes
