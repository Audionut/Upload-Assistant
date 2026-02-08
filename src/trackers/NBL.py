# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import json
from typing import Any, Optional, Union, cast

import aiofiles
import cli_ui
import httpx

from src.console import console
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class NBL:
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """

    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.tracker = 'NBL'
        self.source_flag = 'NBL'
        self.upload_url = 'https://nebulance.io/upload.php'
        self.search_url = 'https://nebulance.io/api.php'
        self.api_key = str(self.config['TRACKERS'][self.tracker]['api_key']).strip()
        self.banned_groups = ['0neshot', '3LTON', '4yEo', '[Oj]', 'AFG', 'AkihitoSubs', 'AniHLS', 'Anime Time', 'AnimeRG', 'AniURL', 'ASW', 'BakedFish',
                              'bonkai77', 'Cleo', 'DeadFish', 'DeeJayAhmed', 'ELiTE', 'EMBER', 'eSc', 'EVO', 'FGT', 'FUM', 'GERMini', 'HAiKU', 'Hi10', 'ION10',
                              'JacobSwaggedUp', 'JIVE', 'Judas', 'LOAD', 'MeGusta', 'Mr.Deadpool', 'mSD', 'NemDiggers', 'neoHEVC', 'NhaNc3', 'NOIVTC',
                              'PlaySD', 'playXD', 'project-gxs', 'PSA', 'QaS', 'Ranger', 'RAPiDCOWS', 'Raze', 'Reaktor', 'REsuRRecTioN', 'RMTeam', 'ROBOTS',
                              'SpaceFish', 'SPASM', 'SSA', 'Telly', 'Tenrai-Sensei', 'TM', 'Trix', 'URANiME', 'VipapkStudios', 'ViSiON', 'Wardevil', 'xRed',
                              'XS', 'YakuboEncodes', 'YuiSubs', 'ZKBL', 'ZmN', 'ZMNT']


    def get_cat_id(self, meta: Meta) -> int:
        cat_id = 3 if meta.get('tv_pack', 0) == 1 else 1
        return cat_id

    async def edit_desc(self, _meta: Meta) -> None:
        # Leave this in so manual works
        return

    async def upload(self, meta: Meta, _disctype: str, _torrent_bytes: Any = None) -> bool:
        common = COMMON(config=self.config)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag, torrent_bytes=_torrent_bytes)

        if meta['bdinfo'] is not None:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", encoding='utf-8') as f:
                mi_dump = await f.read()
        else:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", encoding='utf-8') as f:
                mi_dump = await f.read()
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        async with aiofiles.open(torrent_file_path, 'rb') as f:
            torrent_bytes = await f.read()
        files: dict[str, tuple[str, bytes, str]] = {
            'file_input': ('torrent.torrent', torrent_bytes, 'application/x-bittorrent')
        }
        data: dict[str, Any] = {
            'api_key': self.api_key,
            'tvmazeid': int(meta.get('tvmaze_id', 0)),
            'mediainfo': mi_dump,
            'category': self.get_cat_id(meta),
            'ignoredupes': 'on'
        }

        try:
            if not meta['debug']:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(url=self.upload_url, files=files, data=data)
                    if response.status_code in [200, 201]:
                        try:
                            response_data = response.json()
                            meta['tracker_status'][self.tracker]['status_message'] = response_data
                            return True
                        except json.JSONDecodeError:
                            meta['tracker_status'][self.tracker]['status_message'] = "data error: NBL json decode error, the API is probably down"
                            return False
                    else:
                        response_data = {
                            "error": f"Unexpected status code: {response.status_code}",
                            "response_content": response.text
                        }
                        meta['tracker_status'][self.tracker]['status_message'] = response_data
                    return False
            else:
                console.print("[cyan]NBL Request Data:")
                console.print(data)
                meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
                await common.create_torrent_for_upload(
                    meta,
                    f"{self.tracker}" + "_DEBUG",
                    f"{self.tracker}" + "_DEBUG",
                    announce_url="https://fake.tracker",
                    torrent_bytes=_torrent_bytes,
                )
                return True  # Debug mode - simulated success
        except Exception as e:
            meta['tracker_status'][self.tracker]['status_message'] = f"data error: Upload failed: {e}"
            return False

    async def search_existing(self, meta: Meta, _disctype: str) -> Union[list[dict[str, Any]], bool]:
        if meta['category'] != 'TV':
            if meta['tvmaze_id'] != 0:
                if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                    console.print("[red]Only TV or TV Movies are allowed at NBL, this has a tvmaze ID[/red]")
                    if not cli_ui.ask_yes_no("Do you want to upload it?", default=False):
                        meta['skipping'] = "NBL"
                        return []
                else:
                    meta['skipping'] = "NBL"
                    return []
            else:
                if not meta['unattended']:
                    console.print("[red]Only TV Is allowed at NBL")
                meta['skipping'] = "NBL"
                return []

        if meta['valid_mi'] is False:
            console.print(f"[bold red]No unique ID in mediainfo, skipping {self.tracker} upload.")
            return False

        if meta.get('is_disc') is not None:
            if not meta['unattended']:
                console.print('[bold red]NBL does not allow raw discs')
            meta['skipping'] = "NBL"
            return []

        dupes: list[dict[str, Any]] = []

        if int(meta.get('tvmaze_id', 0) or 0) != 0:
            search_term: dict[str, Any] = {'tvmaze': int(meta['tvmaze_id'])}
        elif int(meta.get('imdb_id', 0) or 0) != 0:
            search_term = {'imdb': meta.get('imdb')}
        else:
            search_term = {'series': meta['title']}
        payload: dict[str, Any] = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getTorrents',
            'params': [
                self.api_key,
                search_term
            ]
        }

        response: Optional[httpx.Response] = None
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(self.search_url, json=payload)
                if response.status_code == 200:
                    try:
                        data = cast(dict[str, Any], response.json())
                        result = cast(dict[str, Any], data.get('result', {}))
                        items = cast(list[dict[str, Any]], result.get('items', []))
                        for each in items:
                            tags_value = each.get('tags', [])
                            tags = cast(list[Any], tags_value) if isinstance(tags_value, list) else []
                            if meta['resolution'] in tags:
                                file_list_value = each.get('file_list', [])
                                file_list = cast(list[Any], file_list_value) if isinstance(file_list_value, list) else []
                                files_str = ', '.join(str(item) for item in file_list) if file_list else str(cast(Any, file_list_value))
                                result = {
                                    'name': str(each.get('rls_name', '')),
                                    'files': files_str,
                                    'size': int(each.get('size', 0)),
                                    'link': f"https://nebulance.io/torrents.php?id={each.get('group_id', '')}",
                                    'file_count': len(file_list) if file_list else 1,
                                    'download': str(each.get('download', '')),
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
            if response is not None and 'result' not in response.json():
                console.print("[red]NBL API returned an unexpected response. Please manually check for dupes.")
                dupes.append({
                    'name': "ERROR: PLEASE CHECK FOR EXISTING RELEASES MANUALLY",
                    'files': '',
                    'size': 0,
                    'link': '',
                    'file_count': 0,
                    'download': ''
                })
        except Exception as e:
            meta['skipping'] = "NBL"
            console.print(f"[bold red]NBL unexpected error: {e}")
            console.print_exception()

        return dupes
