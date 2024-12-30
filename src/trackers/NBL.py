# -*- coding: utf-8 -*-
import asyncio
import requests
from guessit import guessit
import httpx
import aiofiles
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

    async def file_exists_async(self, file_path):
        try:
            async with aiofiles.open(file_path, 'r'):
                return True
        except FileNotFoundError:
            return False

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)

        if meta['bdinfo'] is not None:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8') as file:
                mi_dump = await file.read()
        else:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'r', encoding='utf-8') as file:
                mi_dump = await file.read()
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent"
        file_exists = await self.file_exists_async(torrent_file_path)
        if not file_exists:
            meta['not_uploading'] = True
            return

        async with aiofiles.open(torrent_file_path, 'rb') as open_torrent:
            file_content = await open_torrent.read()
        files = {'file_input': ('torrent_file.torrent', file_content)}
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
                    console.print(response.get('message', response))
                else:
                    console.print(response)
                    console.print(response.text)
            except Exception:
                console.print_exception()
                console.print("[bold yellow]It may have uploaded, go check")
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
        await open_torrent.close()

    async def search_existing(self, meta, disctype):
        if meta['category'] != 'TV':
            console.print("[red]Only TV Is allowed at NBL")
            meta['skipping'] = "NBL"
            return []

        if meta.get('is_disc') is not None:
            console.print('[bold red]NBL does not allow raw discs')
            meta['skipping'] = "NBL"
            return []

        dupes = []
        console.print("[yellow]Searching for existing torrents on NBL...")

        if int(meta.get('tvmaze_id', 0)) != 0:
            search_term = {'tvmaze': int(meta['tvmaze_id'])}
        elif int(meta.get('imdb_id', '0').replace('tt', '')) != 0:
            search_term = {'imdb': meta.get('imdb_id', '0').replace('tt', '')}
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
                    data = response.json()
                    for each in data['result']['items']:
                        if meta['resolution'] in each['tags']:
                            if meta.get('tv_pack', 0) == 1:
                                if each['cat'] == "Season" and int(guessit(each['rls_name']).get('season', '1')) == int(meta.get('season_int')):
                                    dupes.append(each['rls_name'])
                            elif int(guessit(each['rls_name']).get('episode', '0')) == int(meta.get('episode_int')):
                                dupes.append(each['rls_name'])
                else:
                    console.print(f"[bold red]HTTP request failed. Status: {response.status_code}")

        except httpx.HTTPStatusError as e:
            console.print(f"[bold red]HTTP error occurred: {e}")
        except httpx.RequestError as e:
            console.print(f"[bold red]An error occurred while making the request: {e}")
        except httpx.JSONDecodeError:
            console.print('[bold red]Unable to search for existing torrents on site. Either the site is down or your API key is incorrect')
            await asyncio.sleep(5)
        except KeyError as e:
            console.print(f"[bold red]Unexpected KeyError: {e}")
            if 'result' not in response.json():
                console.print(f"Search Term: {search_term}")
                console.print('[red]NBL API Returned an unexpected response, please manually check for dupes')
                dupes.append("ERROR: PLEASE CHECK FOR EXISTING RELEASES MANUALLY")
            await asyncio.sleep(5)
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            console.print_exception()

        return dupes
