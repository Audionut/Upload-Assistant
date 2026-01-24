# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from __future__ import annotations

import os
from typing import Any, Optional, cast

import aiofiles
import httpx
from bs4 import BeautifulSoup

from src.console import console
from src.cookie_auth import CookieAuthUploader, CookieValidator
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class SSD:
    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.common = COMMON(config)
        self.cookie_validator = CookieValidator(config)
        self.cookie_auth_uploader = CookieAuthUploader(config)
        self.tracker = "SSD"
        self.source_flag = "SSD"
        tracker_cfg = cast(dict[str, Any], config.get('TRACKERS', {}).get(self.tracker, {}))
        self.base_url = str(tracker_cfg.get('base_url', 'https://on.springsunday.net')).rstrip('/')
        self.torrent_url = f"{self.base_url}/details.php?id="
        self.ptgen_api = str(tracker_cfg.get('ptgen_api', '')).strip()
        self.ptgen_retry = int(tracker_cfg.get('ptgen_retry', 3))
        self.banned_groups: list[str] = []
        self.session = httpx.AsyncClient(timeout=60.0)

    async def validate_credentials(self, meta: Meta) -> bool:
        cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        self.session.cookies = cast(Any, cookies)
        return await self.cookie_validator.cookie_validation(
            meta=meta,
            tracker=self.tracker,
            test_url=f'{self.base_url}/upload.php',
            success_text='logout.php',
        )

    async def search_existing(self, meta: Meta, _disctype: str) -> Optional[list[str]]:
        imdb_id_raw = str(meta.get('imdb_id', '0')).replace('tt', '').strip()
        if not imdb_id_raw.isdigit() or int(imdb_id_raw) == 0:
            return []

        imdb_id = f"tt{imdb_id_raw.zfill(7)}"
        search_url = f"{self.base_url}/torrents.php"
        params = {
            'incldead': 1,
            'search': imdb_id,
            'search_area': 4,
        }
        try:
            response = await self.session.get(search_url, params=params, cookies=self.session.cookies)
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        torrents_table = soup.find('table', class_='torrents')
        if not torrents_table:
            return []

        found_items: list[str] = []
        for torrent_table in torrents_table.find_all('table', class_='torrentname'):
            name_tag = torrent_table.find('b')
            if name_tag:
                found_items.append(name_tag.get_text(strip=True))
        return found_items

    async def get_type(self, meta: Meta) -> str:
        category = str(meta.get('category', '')).upper()
        if category == 'MOVIE':
            return '501'
        if category == 'TV':
            return '502'

        genres_value = meta.get("genres", [])
        keywords_value = meta.get("keywords", [])
        genres = ' '.join(genres_value).lower() if isinstance(genres_value, list) else str(genres_value).lower()
        keywords = ' '.join(keywords_value).lower() if isinstance(keywords_value, list) else str(keywords_value).lower()

        if 'documentary' in genres or 'documentary' in keywords:
            return '503'
        if 'sport' in genres or 'sports' in keywords:
            return '506'
        if 'music' in genres or 'music' in keywords:
            return '508'

        return '509'

    async def get_source_sel(self, meta: Meta) -> str:
        ptgen = cast(dict[str, Any], meta.get('ptgen', {}))
        regions_value = ptgen.get('region', [])
        regions = cast(list[str], regions_value) if isinstance(regions_value, list) else []
        region_map = {
            '中国大陆': '1',
            '中国香港': '2',
            '中国台湾': '3',
            '美国': '4',
            '英国': '4',
            '法国': '4',
            '德国': '4',
            '西班牙': '4',
            '意大利': '4',
            '加拿大': '4',
            '澳大利亚': '4',
            '日本': '5',
            '韩国': '6',
            '印度': '7',
            '俄罗斯': '8',
            '泰国': '9',
        }
        for region in regions:
            if region in region_map:
                return region_map[region]

        origin_countries_value = meta.get('origin_country', [])
        origin_countries = cast(list[str], origin_countries_value) if isinstance(origin_countries_value, list) else []
        western_countries = {
            'US', 'GB', 'CA', 'AU', 'NZ', 'FR', 'DE', 'ES', 'IT', 'NL', 'BE', 'CH', 'AT', 'IE', 'DK', 'NO',
            'SE', 'FI', 'PT', 'GR', 'PL', 'CZ', 'HU', 'RO', 'BG', 'UA'
        }
        if 'CN' in origin_countries:
            return '1'
        if 'HK' in origin_countries:
            return '2'
        if 'TW' in origin_countries:
            return '3'
        if any(code in western_countries for code in origin_countries):
            return '4'
        if 'JP' in origin_countries:
            return '5'
        if 'KR' in origin_countries:
            return '6'
        if 'IN' in origin_countries:
            return '7'
        if 'RU' in origin_countries:
            return '8'
        if 'TH' in origin_countries:
            return '9'

        return '99'

    async def get_medium_sel(self, meta: Meta) -> str:
        if meta.get('is_disc', '') == 'BDMV':
            return '1'
        if meta.get('is_disc', '') == 'DVD':
            return '3'

        type_value = str(meta.get('type', '')).upper()
        medium_map = {
            'REMUX': '4',
            'MINIBD': '2',
            'BDRIP': '6',
            'ENCODE': '6',
            'WEBDL': '7',
            'WEBRIP': '8',
            'HDTV': '5',
            'TVRIP': '9',
            'DVDRIP': '10',
            'CD': '11',
        }
        return medium_map.get(type_value, '99')

    async def get_standard_sel(self, meta: Meta) -> str:
        res_map = {
            '2160p': '1',
            '1080p': '2',
            '1080i': '3',
            '720p': '4',
            'SD': '5',
        }
        return res_map.get(str(meta.get('resolution', '')).lower(), '99')

    async def get_codec_sel(self, meta: Meta) -> str:
        codec_value = str(meta.get('video_codec', meta.get('video_encode', '')))
        codec_value = codec_value.lower()
        if 'hevc' in codec_value or 'h.265' in codec_value or 'x265' in codec_value:
            return '1'
        if 'avc' in codec_value or 'h.264' in codec_value or 'x264' in codec_value:
            return '2'
        if 'vc-1' in codec_value:
            return '3'
        if 'mpeg-2' in codec_value or 'mpeg2' in codec_value:
            return '4'
        if 'av1' in codec_value:
            return '5'
        return '99'

    async def get_audiocodec_sel(self, meta: Meta) -> str:
        audio = str(meta.get('audio', '')).upper()
        if 'DTS-HD' in audio:
            return '1'
        if 'TRUEHD' in audio:
            return '2'
        if 'LPCM' in audio:
            return '6'
        if 'DTS' in audio:
            return '3'
        if 'E-AC-3' in audio or 'EAC3' in audio or 'DDP' in audio:
            return '11'
        if 'AC-3' in audio or 'AC3' in audio:
            return '4'
        if 'AAC' in audio:
            return '5'
        if 'FLAC' in audio:
            return '7'
        if 'APE' in audio:
            return '8'
        if 'WAV' in audio:
            return '9'
        if 'MP3' in audio:
            return '10'
        if 'OPUS' in audio:
            return '12'
        if 'AV3A' in audio:
            return '13'
        return '99'

    async def get_team_sel(self) -> str:
        tracker_cfg = cast(dict[str, Any], self.config.get('TRACKERS', {}).get(self.tracker, {}))
        team_sel = tracker_cfg.get('team_sel', 0)
        return str(team_sel) if team_sel is not None else '0'

    async def get_media_info(self, meta: Meta) -> str:
        if meta.get('is_disc') == 'BDMV':
            bd_summary = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if os.path.exists(bd_summary):
                async with aiofiles.open(bd_summary, encoding='utf-8') as f:
                    return await f.read()

        mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
        if os.path.exists(mi_path):
            async with aiofiles.open(mi_path, encoding='utf-8') as f:
                return await f.read()
        return ''

    async def get_description(self, meta: Meta, ptgen_text: str) -> str:
        desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        if os.path.exists(desc_path):
            async with aiofiles.open(desc_path, encoding='utf-8') as f:
                return await f.read()
        return ptgen_text

    async def get_screenshots(self, meta: Meta) -> str:
        images_value = meta.get(f'{self.tracker}_images_key', meta.get('image_list', []))
        images = cast(list[dict[str, Any]], images_value) if isinstance(images_value, list) else []
        raw_urls = [str(image.get('raw_url', '')).strip() for image in images if image.get('raw_url')]
        return "\n".join(raw_urls)

    async def get_douban_url(self, meta: Meta) -> tuple[str, str]:
        douban_url = str(meta.get('douban_url', '')).strip()
        ptgen_text = ''

        if not douban_url:
            ptgen = cast(dict[str, Any], meta.get('ptgen', {}))
            data_value = ptgen.get('data', [])
            data = cast(list[dict[str, Any]], data_value) if isinstance(data_value, list) else []
            if data:
                douban_url = str(data[0].get('link', '')).strip()

        if not douban_url:
            ptgen_text = await self.common.ptgen(meta, self.ptgen_api, self.ptgen_retry)
            ptgen = cast(dict[str, Any], meta.get('ptgen', {}))
            data_value = ptgen.get('data', [])
            data = cast(list[dict[str, Any]], data_value) if isinstance(data_value, list) else []
            if data:
                douban_url = str(data[0].get('link', '')).strip()

        if not douban_url:
            console.print("[red]Unable to determine Douban URL from PTGEN output.[/red]")
            douban_url = console.input("[yellow]Please enter Douban URL: [/yellow]")

        if not ptgen_text:
            ptgen_text = str(meta.get('ptgen', {}).get('format', '')).strip()

        return douban_url, ptgen_text

    def get_tag_flags(self, meta: Meta) -> dict[str, str]:
        flags: dict[str, str] = {}
        if meta.get('anime'):
            flags['animation'] = '1'
        if meta.get('tv_pack'):
            flags['pack'] = '1'
        if meta.get('dolby_vision'):
            flags['dovi'] = '1'
        if meta.get('hdr10_plus'):
            flags['hdr10plus'] = '1'
        if meta.get('hlg'):
            flags['hlg'] = '1'

        hdr = str(meta.get('hdr', '')).upper()
        if 'HDR10' in hdr or (hdr and hdr != 'NONE'):
            flags['hdr10'] = '1'

        if meta.get('is_disc') == 'BDMV':
            flags['untouched'] = '1'

        if self.config['TRACKERS'].get(self.tracker, {}).get('internal', False):
            tag = str(meta.get('tag', '')).lstrip('[]').rstrip(']')
            internal_groups = self.config['TRACKERS'].get(self.tracker, {}).get('internal_groups', [])
            if tag and tag in internal_groups:
                flags['internal'] = '1'

        return flags

    async def get_data(self, meta: Meta) -> dict[str, Any]:
        douban_url, ptgen_text = await self.get_douban_url(meta)
        description = await self.get_description(meta, ptgen_text)
        media_info = await self.get_media_info(meta)

        data: dict[str, Any] = {
            'name': meta['name'],
            'small_descr': str(meta.get('title', '')).strip(),
            'url': douban_url,
            'descr': description,
            'type': await self.get_type(meta),
            'source_sel': await self.get_source_sel(meta),
            'medium_sel': await self.get_medium_sel(meta),
            'standard_sel': await self.get_standard_sel(meta),
            'codec_sel': await self.get_codec_sel(meta),
            'audiocodec_sel': await self.get_audiocodec_sel(meta),
            'team_sel': await self.get_team_sel(),
            'Media_BDInfo': media_info,
            'url_vimages': await self.get_screenshots(meta),
            'url_poster': str(meta.get('imdb_info', {}).get('cover', meta.get('cover', ''))).strip(),
        }
        data.update(self.get_tag_flags(meta))
        return data

    async def upload(self, meta: Meta, _disctype: str) -> bool:
        cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        self.session.cookies = cast(Any, cookies)
        data = await self.get_data(meta)

        is_uploaded = await self.cookie_auth_uploader.handle_upload(
            meta=meta,
            tracker=self.tracker,
            source_flag=self.source_flag,
            torrent_url=self.torrent_url,
            data=data,
            torrent_field_name='file',
            upload_cookies=self.session.cookies,
            upload_url=f"{self.base_url}/takeupload.php",
            id_pattern=r'details\.php\?id=(\d+)',
            success_status_code="302, 303",
        )

        return is_uploaded
