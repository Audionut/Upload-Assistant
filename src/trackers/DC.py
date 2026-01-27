# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from typing import Any, Optional, cast

import aiofiles
import httpx

from cogs.redaction import Redaction
from src.console import console
from src.get_desc import DescriptionBuilder
from src.rehostimages import RehostImagesManager
from src.trackers.COMMON import COMMON


class DC:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.common = COMMON(config)
        self.rehost_images_manager = RehostImagesManager(config)
        self.tracker = 'DC'
        self.base_url = 'https://digitalcore.club'
        self.api_base_url = f'{self.base_url}/api/v1/torrents'
        self.torrent_url = f'{self.base_url}/torrent/'
        self.banned_groups = ['']
        self.approved_image_hosts = ['imgbox', 'imgbb', 'bhd', 'imgur', 'postimg', 'sharex']
        self.api_key = self.config['TRACKERS'][self.tracker].get('api_key')
        self.session = httpx.AsyncClient(headers={'X-API-KEY': self.api_key}, timeout=30.0)

    async def mediainfo(self, meta: dict[str, Any]) -> str:
        if meta.get('is_disc') == 'BDMV':
            mediainfo = await self.common.get_bdmv_mediainfo(meta, remove=['File size', 'Overall bit rate'])
        else:
            mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
            async with aiofiles.open(mi_path, encoding='utf-8') as f:
                mediainfo = await f.read()

        return mediainfo

    async def generate_description(self, meta: dict[str, Any]) -> str:
        builder = DescriptionBuilder(self.tracker, self.config)
        desc_parts: list[str] = []

        # Custom Header
        custom_header = await builder.get_custom_header()
        desc_parts.append(custom_header)

        # TV
        title, _episode_image, episode_overview = await builder.get_tv_info(meta)
        if episode_overview:
            desc_parts.append(f'[center]{title}[/center]')
            desc_parts.append(f'[center]{episode_overview}[/center]')

        # File information
        bdinfo_section = await builder.get_bdinfo_section(meta)
        desc_parts.append(bdinfo_section)

        # NFO
        nfo_content = meta.get('description_nfo_content')
        if isinstance(nfo_content, str) and nfo_content:
            desc_parts.append(f"[nfo]{nfo_content}[/nfo]")

        # User description
        user_description = await builder.get_user_description(meta)
        desc_parts.append(user_description)

        # Screenshots
        all_images: list[dict[str, Any]] = []

        menu_images = meta.get("menu_images")
        menu_images_list: list[Any] = []
        if isinstance(menu_images, list):
            menu_images_list = cast(list[Any], menu_images)
        all_images.extend(
            [cast(dict[str, Any], img) for img in menu_images_list if isinstance(img, dict)]
        )

        images_key = f"{self.tracker}_images_key"
        images_value = meta.get(images_key) if images_key in meta else meta.get("image_list")
        images_list: list[Any] = []
        if isinstance(images_value, list):
            images_list = cast(list[Any], images_value)
        all_images.extend(
            [cast(dict[str, Any], img) for img in images_list if isinstance(img, dict)]
        )

        if all_images:
            screenshots_block = ""
            for image in all_images:
                web_url = image.get("web_url")
                raw_url = image.get("raw_url")
                if isinstance(web_url, str) and isinstance(raw_url, str) and web_url and raw_url:
                    screenshots_block += f"[url={web_url}][img=350]{raw_url}[/img][/url] "
            if screenshots_block:
                desc_parts.append(f"[center]{screenshots_block}[/center]")

        # Tonemapped Header
        tonemapped_header = await builder.get_tonemapped_header(meta)
        desc_parts.append(tonemapped_header)

        # Signature
        desc_parts.append(f"[center][url=https://github.com/Audionut/Upload-Assistant]{meta['ua_signature']}[/url][/center]")

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        from src.bbcode import BBCODE
        bbcode = BBCODE()
        description = description.replace('[user]', '').replace('[/user]', '')
        description = description.replace('[align=left]', '').replace('[/align]', '')
        description = description.replace('[right]', '').replace('[/right]', '')
        description = description.replace('[align=right]', '').replace('[/align]', '')
        description = bbcode.remove_sup(description)
        description = bbcode.remove_sub(description)
        description = description.replace('[alert]', '').replace('[/alert]', '')
        description = description.replace('[note]', '').replace('[/note]', '')
        description = description.replace('[hr]', '').replace('[/hr]', '')
        description = description.replace('[h1]', '[u][b]').replace('[/h1]', '[/b][/u]')
        description = description.replace('[h2]', '[u][b]').replace('[/h2]', '[/b][/u]')
        description = description.replace('[h3]', '[u][b]').replace('[/h3]', '[/b][/u]')
        description = description.replace('[ul]', '').replace('[/ul]', '')
        description = description.replace('[ol]', '').replace('[/ol]', '')
        description = description.replace('[*] ', '• ').replace('[*]', '• ')
        description = bbcode.convert_named_spoiler_to_normal_spoiler(description)
        description = bbcode.convert_comparison_to_centered(description, 1000)
        description = description.strip()
        description = bbcode.remove_extra_lines(description)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as description_file:
            await description_file.write(description)

        return description

    async def get_category_id(self, meta: dict[str, Any]) -> Optional[int]:
        resolution = meta.get('resolution', '')
        category = meta.get('category', '')
        is_disc = meta.get('is_disc', '')
        tv_pack = meta.get('tv_pack', '')
        sd = meta.get('sd', '')

        if is_disc == 'BDMV':
            if resolution == '1080p' and category == 'MOVIE':
                return 3
            elif resolution == '2160p' and category == 'MOVIE':
                return 38
            elif category == 'TV':
                return 14
        if is_disc == 'DVD':
            if category == 'MOVIE':
                return 1
            elif category == 'TV':
                return 11
        if category == 'TV' and tv_pack == 1:
            return 12
        if sd == 1:
            if category == 'MOVIE':
                return 2
            elif category == 'TV':
                return 10
        category_map = {
            'MOVIE': {'2160p': 4, '1080p': 6, '1080i': 6, '720p': 5},
            'TV': {'2160p': 13, '1080p': 9, '1080i': 9, '720p': 8},
        }
        if category in category_map:
            return category_map[category].get(resolution)
        return None

    async def search_existing(self, meta: dict[str, Any], _) -> list[dict[str, Any]]:
        imdb_id = meta.get('imdb_info', {}).get('imdbID')
        category_id = await self.get_category_id(meta)
        if not imdb_id:
            console.print(f'[bold yellow]Cannot perform search on {self.tracker}: IMDb ID not found in metadata.[/bold yellow]')
            return []

        search_params = {'searchText': imdb_id}
        search_results: list[Any] = []
        dupes: list[dict[str, Any]] = []
        try:
            response = await self.session.get(self.api_base_url, params=search_params, headers=self.session.headers, timeout=15)
            response.raise_for_status()

            if response.text and response.text != '[]':
                json_data = response.json()
                if isinstance(json_data, list):
                    search_results = cast(list[Any], json_data)
                for each in search_results:
                    if not isinstance(each, dict):
                        continue
                    each_dict = cast(dict[str, Any], each)
                    if each_dict.get('category') == category_id:
                        name = each_dict.get('name')
                        torrent_id = each_dict.get('id')
                        size = each_dict.get('size')
                        torrent_link = f'{self.torrent_url}{torrent_id}/' if torrent_id else None
                        dupe_entry: dict[str, Any] = {
                            'name': name,
                            'size': size,
                            'link': torrent_link
                        }
                        dupes.append(dupe_entry)

                return dupes

        except Exception as e:
            console.print(f'[bold red]Error searching for IMDb ID {imdb_id} on {self.tracker}: {e}[/bold red]')

        return []

    async def edit_name(self, meta: dict[str, Any]) -> str:
        """
        Edits the name according to DC's naming conventions.
        Scene uploads should use the scene name.
        Scene uploads should also have "[UNRAR]" in the name, as the UA only uploads unzipped files, which are considered "altered".
        https://digitalcore.club/forum/17/topic/1051/uploading-for-beginners

        Mod mentioned that adding [UNRAR] is unnecessary, but according to my tests, their system does not accept it if there is already a release with the same title.
        Mod also mentioned that metadata-based titles are acceptable.
        https://digitalcore.club/forum/6/topic/2810/clarification-needed-p2p-non-scene-torrent-naming-conventions
        """
        scene_name = meta.get("scene_name") or ""
        clean_name = meta.get("clean_name") or ""

        dc_name = scene_name if scene_name else clean_name
        # T1)  Acceptable characters are as follows:
        #         ABCDEFGHIJKLMNOPQRSTUVWXYZ
        #         abcdefghijklmnopqrstuvwxyz
        #         0123456789 . -
        # https://scenerules.org/html/2014_BLURAY.html
        dc_name = "".join(c for c in dc_name if c.isalnum() or c in (" ", ".", "-"))
        if scene_name:
            dc_name += " [UNRAR]"

        return dc_name

    async def check_image_hosts(self, meta: dict[str, Any]) -> None:
        url_host_mapping = {
            'ibb.co': 'imgbb',
            'imgbox.com': 'imgbox',
            'beyondhd.co': 'bhd',
            'imgur.com': 'imgur',
            'postimg.cc': 'postimg',
            'digitalcore.club': 'sharex',
            'img.digitalcore.club': 'sharex'
        }
        await self.rehost_images_manager.check_hosts(
            meta,
            self.tracker,
            url_host_mapping=url_host_mapping,
            img_host_index=1,
            approved_image_hosts=self.approved_image_hosts,
        )
        return

    async def fetch_data(self, meta: dict[str, Any]) -> dict[str, Any]:
        anon = '1' if meta['anon'] or self.config['TRACKERS'][self.tracker].get('anon', False) else '0'

        data = {
            'category': await self.get_category_id(meta),
            'imdbId': meta.get('imdb_info', {}).get('imdbID', ''),
            'nfo': await self.generate_description(meta),
            'mediainfo': await self.mediainfo(meta),
            'reqid': '0',
            'section': 'new',
            'frileech': '1',
            'anonymousUpload': anon,
            'p2p': '0',
            'unrar': '1',
        }

        return data

    async def upload(self, meta: dict[str, Any], _) -> bool:
        data = await self.fetch_data(meta)
        torrent_title = await self.edit_name(meta)
        response = None

        if not meta.get('debug', False):
            try:
                upload_url = f'{self.api_base_url}/upload'
                await self.common.create_torrent_for_upload(meta, self.tracker, 'DigitalCore.club')
                torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

                async with aiofiles.open(torrent_path, 'rb') as torrent_file:
                    torrent_bytes = await torrent_file.read()
                files = {'file': (torrent_title + '.torrent', torrent_bytes, 'application/x-bittorrent')}

                response = await self.session.post(upload_url, data=data, files=files, headers=dict(self.session.headers), timeout=90)
                response.raise_for_status()
                response_json = response.json()
                response_data: dict[str, Any] = cast(dict[str, Any], response_json) if isinstance(response_json, dict) else {}

                if response.status_code == 200 and response_data.get('id'):
                    torrent_id = str(response_data['id'])
                    meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id + '/'
                    meta['tracker_status'][self.tracker]['status_message'] = response_data.get('message')

                    await self.common.download_tracker_torrent(
                        meta,
                        self.tracker,
                        headers=dict(self.session.headers),
                        downurl=f'{self.api_base_url}/download/{torrent_id}'
                    )
                    return True

                else:
                    meta['tracker_status'][self.tracker]['status_message'] = f"data error: {response_data.get('message', 'Unknown API error.')}"
                    return False

            except httpx.HTTPStatusError as e:
                meta['tracker_status'][self.tracker]['status_message'] = f'data error: HTTP {e.response.status_code} - {e.response.text}'
                return False
            except httpx.TimeoutException:
                meta['tracker_status'][self.tracker]['status_message'] = f'data error: Request timed out after {self.session.timeout.write} seconds'
                return False
            except httpx.RequestError as e:
                resp_text = getattr(getattr(e, 'response', None), 'text', 'No response received')
                meta['tracker_status'][self.tracker]['status_message'] = f'data error: Unable to upload. Error: {e}.\nResponse: {resp_text}'
                return False
            except Exception as e:
                resp_text = response.text if response is not None else 'No response received'
                meta['tracker_status'][self.tracker]['status_message'] = f'data error: It may have uploaded, go check. Error: {e}.\nResponse: {resp_text}'
                return False

        else:
            console.print("[cyan]DC Request Data:")
            console.print(Redaction.redact_private_info(data))
            meta['tracker_status'][self.tracker]['status_message'] = 'Debug mode enabled, not uploading'
            await self.common.create_torrent_for_upload(meta, f"{self.tracker}" + "_DEBUG", f"{self.tracker}" + "_DEBUG", announce_url="https://fake.tracker")
            return True  # Debug mode - simulated success
