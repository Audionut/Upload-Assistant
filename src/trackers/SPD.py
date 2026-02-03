# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# import discord
import base64
import glob
import os
import re
import unicodedata
from typing import Any, Optional, cast

import aiofiles
import httpx

from cogs.redaction import Redaction
from src.bbcode import BBCODE
from src.console import console
from src.get_desc import DescriptionBuilder

from .COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class SPD:
    def __init__(self, config: Config) -> None:
        self.url = "https://speedapp.io"
        self.config: Config = config
        self.common = COMMON(config)
        self.tracker = 'SPD'
        self.upload_url = 'https://speedapp.io/api/upload'
        self.torrent_url = 'https://speedapp.io/browse/'
        self.banned_groups = []
        self.banned_url = 'https://speedapp.io/api/torrent/release-group/blacklist'
        api_key = str(self.config['TRACKERS'][self.tracker]['api_key'])
        self.session = httpx.AsyncClient(headers={
            'User-Agent': "Upload Assistant",
            'accept': 'application/json',
            'Authorization': api_key,
        }, timeout=30.0)

    def get_cat_id(self, meta: Meta) -> Optional[str]:
        subtitle_value = meta.get('subtitle_languages')
        subtitle_langs = cast(list[Any], subtitle_value) if isinstance(subtitle_value, list) else []

        audio_value = meta.get('audio_languages')
        audio_langs = cast(list[Any], audio_value) if isinstance(audio_value, list) else []

        langs = [str(lang).lower() for lang in subtitle_langs + audio_langs]
        romanian = 'romanian' in langs

        origin_countries = cast(list[Any], meta.get('origin_country', []))
        category = str(meta.get('category', ''))
        if 'RO' in origin_countries:
            if category == 'TV':
                return '60'
            elif category == 'MOVIE':
                return '59'

        # documentary
        genres = str(meta.get("genres", ""))
        keywords = str(meta.get("keywords", ""))
        if 'documentary' in genres.lower() or 'documentary' in keywords.lower():
            return '63' if romanian else '9'

        # anime
        if meta.get('anime'):
            return '3'

        # TV
        if category == 'TV':
            if meta.get('tv_pack'):
                return '66' if romanian else '41'
            elif meta.get('sd'):
                return '46' if romanian else '45'
            return '44' if romanian else '43'

        # MOVIE
        if category == 'MOVIE':
            resolution = str(meta.get('resolution', ''))
            media_type = str(meta.get('type', ''))
            if resolution == '2160p' and media_type != 'DISC':
                return '57' if romanian else '61'
            if media_type in ('REMUX', 'WEBDL', 'WEBRIP', 'HDTV', 'ENCODE'):
                return '29' if romanian else '8'
            if media_type == 'DISC':
                return '24' if romanian else '17'
            if media_type == 'SD':
                return '35' if romanian else '10'

        return None

    async def get_file_info(self, meta: Meta) -> tuple[Optional[str], Optional[str]]:
        base_path = f"{meta['base_dir']}/tmp/{meta['uuid']}"

        if meta.get('bdinfo'):
            async with aiofiles.open(
                f"{base_path}/BD_SUMMARY_00.txt",
                encoding='utf-8',
            ) as bd_file:
                bd_info = await bd_file.read()
            return None, bd_info
        else:
            async with aiofiles.open(
                f"{base_path}/MEDIAINFO_CLEANPATH.txt",
                encoding='utf-8',
            ) as mi_file:
                media_info = await mi_file.read()
            return media_info, None

    def get_screenshots(self, meta: Meta) -> list[str]:
        images = cast(list[dict[str, Any]], meta.get('menu_images', [])) + cast(
            list[dict[str, Any]], meta.get('image_list', [])
        )
        return [image['raw_url'] for image in images if image.get('raw_url')]

    async def search_existing(self, meta: Meta, _disctype: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        search_url = 'https://speedapp.io/api/torrent'

        params: dict[str, str] = {}
        if int(meta.get('imdb_id', 0) or 0) != 0:
            imdb_info = cast(dict[str, Any], meta.get('imdb_info', {}))
            params['imdbId'] = str(imdb_info.get('imdbID', ''))
        else:
            search_title = str(meta.get('title', '')).replace(':', '').replace("'", '').replace(',', '')
            params['search'] = search_title

        try:
            response = await self.session.get(url=search_url, params=params, headers=self.session.headers)

            if response.status_code == 200:
                data = cast(list[dict[str, Any]], response.json())
                for each in data:
                    name = each.get('name')
                    size = each.get('size')
                    link = f'{self.torrent_url}{each.get("id")}/'

                    if name:
                        results.append({
                            'name': str(name),
                            'size': size,
                            'link': link
                        })
                return results
            else:
                console.print(f'[bold red]HTTP request failed. Status: {response.status_code}')

        except Exception as e:
            console.print(f'[bold red]Unexpected error: {e}')
            console.print_exception()

        return results

    async def search_channel(self, meta: Meta) -> Optional[int]:
        spd_channel = meta.get('spd_channel', '') or self.config['TRACKERS'][self.tracker].get('channel', '')

        # if no channel is specified, use the default
        if not spd_channel:
            return 1

        # return the channel as int if it's already an integer
        if isinstance(spd_channel, int):
            return spd_channel

        # if user enters id as a string number
        if isinstance(spd_channel, str) and spd_channel.isdigit():
            return int(spd_channel)

        params: dict[str, str] = {
            'search': str(spd_channel)
        }

        try:
            response = await self.session.get(url=self.url + '/api/channel', params=params, headers=self.session.headers)

            if response.status_code == 200:
                data = cast(list[dict[str, Any]], response.json())
                for entry in data:
                    channel_id = entry.get('id')
                    tag = entry.get('tag')

                    if channel_id and tag:
                        if tag != spd_channel:
                            console.print(f'[{self.tracker}]: Unable to find a matching channel based on your input. Please check if you entered it correctly.')
                            return
                        else:
                            return int(channel_id)
                    else:
                        console.print(f'[{self.tracker}]: Could not find the channel ID. Please check if you entered it correctly.')
                console.print(f"[{self.tracker}]: Unable to find a matching channel for '{spd_channel}'.")

        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            console.print_exception()

    async def edit_desc(self, meta: Meta) -> str:
        builder = DescriptionBuilder(self.tracker, self.config)
        desc_parts: list[str] = []

        user_description = builder.get_user_description(meta)
        title, episode_image, episode_overview = builder.get_tv_info(meta, resize=True)
        if user_description or episode_overview:  # Avoid unnecessary descriptions
            # Custom Header
            desc_parts.append(builder.get_custom_header())

            # Logo
            logo_resize_url = str(meta.get('tmdb_logo', ''))
            if logo_resize_url:
                desc_parts.append(f"[center][img]https://image.tmdb.org/t/p/w300/{logo_resize_url}[/img][/center]")

            # TV
            if episode_overview:
                desc_parts.append(f'[center]{title}[/center]')

                if episode_image:
                    desc_parts.append(f"[center][img]{episode_image}[/img][/center]")

                desc_parts.append(f'[center]{episode_overview}[/center]')

            # User description
            desc_parts.append(user_description)

        # Tonemapped Header
        desc_parts.append(builder.get_tonemapped_header(meta))

        # Signature
        desc_parts.append(
            f"[url=https://github.com/Audionut/Upload-Assistant]{meta.get('ua_signature', '')}[/url]"
        )

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        bbcode = BBCODE()
        description = bbcode.remove_img_resize(description)
        description = bbcode.convert_named_spoiler_to_normal_spoiler(description)
        description = bbcode.remove_extra_lines(description)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as description_file:
            await description_file.write(description)

        return description

    def edit_name(self, meta: Meta) -> str:
        torrent_name = str(meta.get('name', ''))

        name = torrent_name.replace(':', ' -')
        name = unicodedata.normalize("NFKD", name)
        name = name.encode("ascii", "ignore").decode("ascii")
        name = re.sub(r'[\\/*?"<>|]', '', name)

        return re.sub(r"\s{2,}", " ", name)

    async def encode_to_base64(self, file_path: str) -> str:
        async with aiofiles.open(file_path, 'rb') as binary_file:
            binary_file_data = await binary_file.read()
            base64_encoded_data = base64.b64encode(binary_file_data)
            return base64_encoded_data.decode('utf-8')

    async def get_nfo(self, meta: Meta, nfo_bytes: Optional[bytes] = None) -> Optional[str]:
        if nfo_bytes is not None:
            return base64.b64encode(nfo_bytes).decode("utf-8")
        cached_bytes = meta.get("cached_nfo_bytes")
        if cached_bytes:
            return base64.b64encode(bytes(cached_bytes)).decode("utf-8")
        nfo_dir = os.path.join(meta['base_dir'], "tmp", meta['uuid'])
        nfo_files = glob.glob(os.path.join(nfo_dir, "*.nfo"))

        if nfo_files:
            nfo = await self.encode_to_base64(nfo_files[0])
            return nfo

        return None

    async def fetch_data(
        self,
        meta: Meta,
        torrent_bytes: Optional[bytes] = None,
        nfo_bytes: Optional[bytes] = None,
    ) -> dict[str, Any]:
        media_info, bd_info = await self.get_file_info(meta)

        data: dict[str, Any] = {
            'bdInfo': bd_info,
            'coverPhotoUrl': str(meta.get('backdrop', '')),
            'description': str(meta.get('genres', '')),
            'media_info': media_info,
            'name': self.edit_name(meta),
            'nfo': await self.get_nfo(meta, nfo_bytes=nfo_bytes),
            'plot': str(meta.get('overview_meta', '') or meta.get('overview', '')),
            'poster': str(meta.get('poster', '')),
            'technicalDetails': await self.edit_desc(meta),
            'screenshots': self.get_screenshots(meta),
            'type': self.get_cat_id(meta),
            'url': str(cast(dict[str, Any], meta.get('imdb_info', {})).get('imdb_url', '')),
        }

        if torrent_bytes is None:
            data['file'] = await self.encode_to_base64(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")
        else:
            data['file'] = base64.b64encode(torrent_bytes).decode('utf-8')
        if meta.get('debug') is True:
            data['file'] = str(data['file'])[:50] + '...[DEBUG MODE]'
            if data.get('nfo'):
                data['nfo'] = str(data['nfo'])[:50] + '...[DEBUG MODE]'

        return data

    async def upload(self, meta: Meta, _disctype: str, torrent_bytes: Optional[bytes] = None) -> Optional[bool]:
        nfo_bytes = cast(Optional[bytes], meta.get("cached_nfo_bytes"))
        data = await self.fetch_data(meta, torrent_bytes, nfo_bytes=nfo_bytes)
        tracker_status = cast(dict[str, Any], meta.get('tracker_status', {}))
        tracker_status.setdefault(self.tracker, {})

        channel = await self.search_channel(meta)
        if channel is None:
            meta['skipping'] = f"{self.tracker}"
            return
        channel = str(channel)
        data['channel'] = channel

        torrent_id = ''

        if not bool(meta.get('debug')):
            response = None
            try:
                response = await self.session.post(url=self.upload_url, json=data, headers=self.session.headers)
                response.raise_for_status()
                response = response.json()
                if response.get('status') is True and response.get('error') is False:
                    tracker_status[self.tracker]['status_message'] = "Torrent uploaded successfully."

                    if 'downloadUrl' in response:
                        torrent_id = str(response.get('torrent', {}).get('id', ''))
                        if torrent_id:
                            tracker_status[self.tracker]['torrent_id'] = torrent_id

                        download_url = f"{self.url}/api/torrent/{torrent_id}/download"
                        await self.common.download_tracker_torrent(
                            meta,
                            tracker=self.tracker,
                            headers={'Authorization': str(self.config['TRACKERS'][self.tracker]['api_key'])},
                            downurl=download_url
                        )
                        return True

                    else:
                        tracker_status[self.tracker]['status_message'] = (
                            'data error: No downloadUrl in response, check manually if it uploaded. '
                            f'Response: \n{response}'
                        )
                        return False

                else:
                    tracker_status[self.tracker]['status_message'] = f'data error: {response}'
                    return False

            except httpx.HTTPStatusError as e:
                tracker_status[self.tracker]['status_message'] = f'data error: HTTP {e.response.status_code} - {e.response.text}'
                return False
            except httpx.TimeoutException:
                tracker_status[self.tracker]['status_message'] = f'data error: Request timed out after {self.session.timeout.write} seconds'
                return False
            except httpx.RequestError as e:
                response_info = "no response"
                if response is not None:
                    response_info = getattr(response, 'text', str(response))
                tracker_status[self.tracker]['status_message'] = f'data error: Unable to upload. Error: {e!r}.\nResponse: {response_info}'
                return False
            except Exception as e:
                response_info = "no response"
                if response is not None:
                    response_info = getattr(response, 'text', str(response))
                tracker_status[self.tracker]['status_message'] = f'data error: It may have uploaded, go check. Error: {e!r}.\nResponse: {response_info}'
                return False

        else:
            console.print("[cyan]SPD Request Data:")
            console.print(Redaction.redact_private_info(data))
            tracker_status[self.tracker]['status_message'] = "Debug mode enabled, not uploading."
            await self.common.create_torrent_for_upload(
                meta,
                f"{self.tracker}" + "_DEBUG",
                f"{self.tracker}" + "_DEBUG",
                announce_url="https://fake.tracker",
                torrent_bytes=torrent_bytes,
            )
            return True  # Debug mode - simulated success
