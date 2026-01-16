# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
from typing import Any, Optional, cast

import httpx
import requests

from cogs.redaction import Redaction
from src.console import console
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class SN:
    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.tracker = 'SN'
        self.source_flag = 'Swarmazon'
        self.upload_url = 'https://swarmazon.club/api/upload.php'
        self.forum_link = 'https://swarmazon.club/php/forum.php?forum_page=2-swarmazon-rules'
        self.search_url = 'https://swarmazon.club/api/search.php'
        self.banned_groups = [""]
        pass

    async def get_type_id(self, type: str) -> str:
        type_id = {
            'BluRay': '3',
            'Web': '1',
            # boxset is 4
            # 'NA': '4',
            'DVD': '2'
        }.get(type, '0')
        return type_id

    async def upload(self, meta: Meta, disctype: str) -> bool:
        common = COMMON(config=self.config)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag)
        # await common.unit3d_edit_desc(meta, self.tracker, self.forum_link)
        await self.edit_desc(meta)
        cat_id = ""
        sub_cat_id = ""
        # cat_id = await self.get_cat_id(meta)

        # Anime
        if meta.get('mal_id'):
            cat_id = '7'
            sub_cat_id = '47'

            demographics_map = {
                'Shounen': '27',
                'Seinen': '28',
                'Shoujo': '29',
                'Josei': '30',
                'Kodomo': '31',
                'Mina': '47'
            }

            demographic = str(meta.get('demographic', 'Mina'))
            sub_cat_id = demographics_map.get(demographic, sub_cat_id)

        category = str(meta.get('category', ''))
        if category == 'MOVIE':
            cat_id = '1'
            # sub cat is source so using source to get
            sub_cat_id = await self.get_type_id(str(meta.get('source', '')))
        elif category == 'TV':
            cat_id = '2'
            sub_cat_id = '6' if bool(meta.get('tv_pack')) else '5'
            # todo need to do a check for docs and add as subcat

        mi_dump: Optional[str]
        bd_dump: Optional[str]
        if meta.get('bdinfo') is not None:
            mi_dump = None
            with open(
                f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt",
                encoding='utf-8',
            ) as bd_file:
                bd_dump = bd_file.read()
        else:
            with open(
                f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt",
                encoding='utf-8',
            ) as mi_file:
                mi_dump = mi_file.read()
            bd_dump = None
        with open(
            f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt",
            encoding='utf-8',
        ) as desc_file:
            desc = desc_file.read()

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent", 'rb') as f:
            tfile = f.read()

        # uploading torrent file.
        files = {
            'torrent': (f"{meta['name']}.torrent", tfile)
        }

        # adding bd_dump to description if it exits and adding empty string to mediainfo
        if bd_dump:
            desc += "\n\n" + bd_dump
            mi_dump = ""

        api_key = str(self.config['TRACKERS'][self.tracker]['api_key']).strip()
        data: dict[str, Any] = {
            'api_key': api_key,
            'name': str(meta.get('name', '')),
            'category_id': cat_id,
            'type_id': sub_cat_id,
            'media_ref': f"tt{meta.get('imdb', '')}",
            'description': desc,
            'media_info': mi_dump

        }

        if not bool(meta.get('debug')):
            response = requests.request("POST", url=self.upload_url, data=data, files=files, timeout=30)

            try:
                if response.json().get('success'):
                    tracker_status = cast(dict[str, Any], meta.get('tracker_status', {}))
                    tracker_status.setdefault(self.tracker, {})
                    tracker_status[self.tracker]['status_message'] = response.json()['link']
                    if 'link' in response.json():
                        announce_url = str(
                            self.config['TRACKERS'][self.tracker].get('announce_url', '')
                        )
                        await common.create_torrent_ready_to_seed(
                            meta,
                            self.tracker,
                            self.source_flag,
                            announce_url,
                            str(response.json()['link']),
                        )
                        return True
                    else:
                        console.print("[red]No Link in Response")
                        return False
                else:
                    console.print("[red]Did not upload successfully")
                    console.print(response.json())
                    return False
            except Exception:
                console.print("[red]Error! It may have uploaded, go check")
                console.print(data)
                console.print_exception()
                return False
        else:
            console.print("[cyan]SN Request Data:")
            console.print(Redaction.redact_private_info(data))
            tracker_status = cast(dict[str, Any], meta.get('tracker_status', {}))
            tracker_status.setdefault(self.tracker, {})
            tracker_status[self.tracker]['status_message'] = "Debug mode enabled, not uploading."
            await common.create_torrent_for_upload(meta, f"{self.tracker}" + "_DEBUG", f"{self.tracker}" + "_DEBUG", announce_url="https://fake.tracker")
            return True  # Debug mode - simulated success

    async def edit_desc(self, meta: Meta) -> None:
        with open(
            f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt",
            encoding='utf-8',
        ) as base_file:
            base = base_file.read()
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as desc:
            desc.write(base)
            images = cast(list[dict[str, Any]], meta.get('image_list', []))
            if images:
                desc.write("[center]")
                for image in images:
                    web_url = image.get('web_url')
                    img_url = image.get('img_url')
                    if not web_url or not img_url:
                        continue
                    desc.write(f"[url={web_url}][img=720]{img_url}[/img][/url]")
                desc.write("[/center]")
            desc.write(f"\n[center][url={self.forum_link}]Simplicity, Socializing and Sharing![/url][/center]")
            desc.close()
        return

    async def search_existing(self, meta: Meta, disctype: str) -> list[str]:
        dupes: list[str] = []
        api_key = str(self.config['TRACKERS'][self.tracker]['api_key']).strip()
        params: dict[str, str] = {
            'api_key': api_key
        }

        # Determine search parameters based on metadata
        imdb_id = int(meta.get('imdb_id', 0) or 0)
        category = str(meta.get('category', ''))
        title = str(meta.get('title', ''))
        if imdb_id == 0:
            if category == 'TV':
                params['filter'] = f"{title}{meta.get('season', '')}"
            else:
                params['filter'] = title
        else:
            params['media_ref'] = f"tt{meta.get('imdb', '')}"
            if category == 'TV':
                params['filter'] = f"{meta.get('season', '')}"
            else:
                params['filter'] = str(meta.get('resolution', ''))

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.search_url, params=params)
                if response.status_code == 200:
                    data = cast(dict[str, Any], response.json())
                    items = cast(list[dict[str, Any]], data.get('data', []))
                    for item in items:
                        result = item.get('name')
                        if result:
                            dupes.append(str(result))
                else:
                    console.print(f"[bold red]HTTP request failed. Status: {response.status_code}")

        except httpx.TimeoutException:
            console.print("[bold red]Request timed out while searching for existing torrents.")
        except httpx.RequestError as e:
            console.print(f"[bold red]An error occurred while making the request: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            console.print_exception()
            await asyncio.sleep(5)

        return dupes
