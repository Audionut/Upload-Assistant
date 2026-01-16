# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import os
import traceback
from typing import Any, Optional, Union, cast

import requests
from pymediainfo import MediaInfo

from cogs.redaction import Redaction
from src.console import console
from src.trackers.COMMON import COMMON


class BHDTV:
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.tracker = 'BHDTV'
        self.source_flag = 'BIT-HDTV'
        # search not implemented
        # self.search_url = 'https://api.bit-hdtv.com/torrent/search/advanced'
        self.upload_url = 'https://www.bit-hdtv.com/takeupload.php'
        # self.forum_link = 'https://www.bit-hdtv.com/rules.php'
        self.banned_groups = []
        pass

    async def upload(self, meta: dict[str, Any], disctype: str) -> bool:
        common = COMMON(config=self.config)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag)
        await self.edit_desc(meta)
        cat_id = await self.get_cat_id(meta)
        sub_cat_id = ""
        if meta['category'] == 'MOVIE':
            sub_cat_id = await self.get_type_movie_id(meta)
        elif meta['category'] == 'TV' and not meta['tv_pack']:
            sub_cat_id = await self.get_type_tv_id(meta['type'])
        else:
            # must be TV pack
            sub_cat_id = await self.get_type_tv_pack_id(meta['type'])

        resolution_id = await self.get_res_id(meta['resolution'])
        # region_id = await common.unit3d_region_ids(meta.get('region'))
        # distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))

        if meta['bdinfo'] is not None:
            mi_dump = None
            with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", encoding='utf-8') as bd_file:
                bd_dump = bd_file.read()
        else:
            with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", encoding='utf-8') as mi_file:
                mi_dump = mi_file.read()
            bd_dump = None
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", encoding='utf-8') as desc_file:
            desc = desc_file.read()

        media_info = ""
        if meta['is_disc'] != 'BDMV':
            filelist = cast(list[str], meta.get('filelist') or [])
            video = filelist[0] if filelist else str(meta.get('path') or "")
            mi_template = os.path.abspath(f"{meta['base_dir']}/data/templates/MEDIAINFO.txt")
            if os.path.exists(mi_template):
                media_info = str(MediaInfo.parse(video, output="STRING", full=False,
                                                mediainfo_options={"inform": f"file://{mi_template}"}))

        data: dict[str, Any] = {
            'api_key': str(self.config['TRACKERS'][self.tracker]['api_key']).strip(),
            'name': str(meta['name']).replace(' ', '.').replace(':.', '.').replace(':', '.').replace('DD+', 'DDP'),
            'mediainfo': mi_dump if bd_dump is None else bd_dump,
            'cat': cat_id,
            'subcat': sub_cat_id,
            'resolution': resolution_id,
            # 'anon': anon,
            # admins asked to remove short description.
            'sdescr': " ",
            'descr': media_info if bd_dump is None else "Disc so Check Mediainfo dump ",
            'screen': desc,
            'url': f"https://www.tvmaze.com/shows/{meta['tvmaze_id']}" if meta['category'] == 'TV' else str(meta.get('imdb_info', {}).get('imdb_url', '')),
            'format': 'json'
        }

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        with open(torrent_path, 'rb') as open_torrent:
            files = {'file': open_torrent}

            if meta['debug'] is False:
                response = requests.post(url=self.upload_url, data=data, files=files, timeout=30)
                parsed: Union[Any, None] = None
                if response:
                    try:
                        parsed = response.json()
                        meta['tracker_status'][self.tracker]['status_message'] = parsed
                    except Exception:
                        console.print("[cyan]It may have uploaded, go check")
                        console.print(Redaction.redact_private_info(data))
                        traceback.print_exc()

                parsed_data: Optional[dict[str, Any]] = cast(Optional[dict[str, Any]], parsed) if isinstance(parsed, dict) else None
                data_block: Optional[dict[str, Any]] = parsed_data.get('data') if parsed_data else None
                if isinstance(data_block, dict) and 'view' in data_block:
                    my_announce_url = self.config['TRACKERS']['BHDTV'].get('my_announce_url')
                    if my_announce_url:
                        await common.create_torrent_ready_to_seed(
                            meta,
                            self.tracker,
                            self.source_flag,
                            my_announce_url,
                            str(data_block['view'])
                        )
                        return True
                return False

            console.print("[cyan]BHDTV Request Data:")
            console.print(Redaction.redact_private_info(data))
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
            await common.create_torrent_for_upload(meta, f"{self.tracker}" + "_DEBUG", f"{self.tracker}" + "_DEBUG", announce_url="https://fake.tracker")
            return True

    async def get_cat_id(self, meta: dict[str, Any]) -> str:
        category_id = '0'
        if meta['category'] == 'MOVIE':
            category_id = '7'
        elif meta['tv_pack']:
            category_id = '12'
        else:
            # must be tv episode
            category_id = '10'
        return category_id

    async def get_type_movie_id(self, meta: dict[str, Any]) -> str:
        type_id = '0'
        if meta['type'] == 'DISC':
            type_id = '46' if meta['3D'] else '2'
        elif meta['type'] == 'REMUX':
            if str(meta['name']).__contains__('265'):
                type_id = '48'
            elif meta['3D']:
                type_id = '45'
            else:
                type_id = '2'
        elif meta['type'] == 'HDTV':
            type_id = '6'
        elif meta['type'] == 'ENCODE':
            if str(meta['name']).__contains__('265'):
                type_id = '43'
            elif meta['3D']:
                type_id = '44'
            else:
                type_id = '1'
        elif meta['type'] == 'WEBDL' or meta['type'] == 'WEBRIP':
            type_id = '5'

        return type_id

    async def get_type_tv_id(self, type: str) -> str:
        type_id = {
            'HDTV': '7',
            'WEBDL': '8',
            'WEBRIP': '8',
            # 'WEBRIP': '55',
            # 'SD': '59',
            'ENCODE': '10',
            'REMUX': '11',
            'DISC': '12',
        }.get(type, '0')
        return type_id

    async def get_type_tv_pack_id(self, type: str) -> str:
        type_id = {
            'HDTV': '13',
            'WEBDL': '14',
            'WEBRIP': '8',
            # 'WEBRIP': '55',
            # 'SD': '59',
            'ENCODE': '16',
            'REMUX': '17',
            'DISC': '18',
        }.get(type, '0')
        return type_id

    async def get_res_id(self, resolution: str) -> str:
        resolution_id = {
            '2160p': '4',
            '1080p': '3',
            '1080i': '2',
            '720p': '1'
        }.get(resolution, '10')
        return resolution_id

    async def edit_desc(self, meta: dict[str, Any]) -> None:
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", encoding='utf-8') as base_file:
            base = base_file.read()
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as desc:
            desc.write(base.replace("[img=250]", "[img=250x250]"))
            images = cast(list[dict[str, Any]], meta.get('image_list') or [])
            if len(images) > 0:
                for each in range(len(images)):
                    web_url = images[each]['web_url']
                    img_url = images[each]['img_url']
                    desc.write(f"[url={web_url}][img]{img_url}[/img][/url] ")
            # desc.write(common.get_links(meta, "[COLOR=red][size=4]", "[/size][/color]"))
        return None

    async def search_existing(self, meta: dict[str, Any], disctype: str) -> list[str]:
        console.print("[red]Dupes must be checked Manually")
        return ['Dupes must be checked Manually']
        # hopefully someone else has the time to implement this.
