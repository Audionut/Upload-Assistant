# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import json
import os
import platform
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, cast
from urllib.parse import urlparse

import aiofiles
import cli_ui
import httpx
import langcodes
import pycountry
from bs4 import BeautifulSoup, Tag
from langcodes.tag_parser import LanguageTagError

from src.bbcode import BBCODE
from src.console import console
from src.cookie_auth import CookieAuthUploader, CookieValidator
from src.get_desc import DescriptionBuilder
from src.languages import languages_manager
from src.tmdb import TmdbManager
from src.trackers.COMMON import COMMON


class BJS:
    secret_token: str = ''
    already_has_the_info: bool = False
    database_title: str = ''

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.tmdb_manager = TmdbManager(config)
        self.common = COMMON(config)
        self.cookie_validator = CookieValidator(config)
        self.cookie_auth_uploader = CookieAuthUploader(config)
        self.tracker = 'BJS'
        self.banned_groups: list[str] = []
        self.source_flag = 'BJ'
        self.base_url = 'https://bj-share.info'
        self.torrent_url = 'https://bj-share.info/torrents.php?torrentid='
        self.requests_url = f'{self.base_url}/requests.php?'
        self.auth_token = None
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f'Upload Assistant ({platform.system()} {platform.release()})'
        }, timeout=60.0)
        self.main_tmdb_data: dict[str, Any] = {}
        self.episode_tmdb_data: dict[str, Any] = {}
        self.semaphore = asyncio.Semaphore(1)

    def get_additional_checks(self, meta: dict[str, Any]) -> bool:
        should_continue = True

        # Stops uploading when an external subtitle is detected
        video_path = meta.get('path', '')
        directory: str = video_path if os.path.isdir(video_path) else os.path.dirname(video_path)
        subtitle_extensions = ('.srt', '.sub', '.ass', '.ssa', '.idx', '.smi', '.psb')

        if any(f.lower().endswith(subtitle_extensions) for f in os.listdir(directory)):
            console.print(f'{self.tracker}: [bold red]ERRO: Esta ferramenta não suporta o upload de legendas em arquivos separados.[/bold red]')
            return False

        return should_continue

    async def validate_credentials(self, meta: dict[str, Any]) -> bool:
        cookie_jar = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        if cookie_jar:
            self.session.cookies = cookie_jar
            if await self.cookie_validator.cookie_validation(
                meta=meta,
                tracker=self.tracker,
                test_url=f'{self.base_url}/upload.php',
                error_text='login.php',
                token_pattern=r'name="auth" value="([^"]+)"'  # nosec B106
            ):
                return True

        return False

    async def load_localized_data(self, meta: dict[str, Any]) -> None:
        localized_data_file: str = f'{meta["base_dir"]}/tmp/{meta["uuid"]}/tmdb_localized_data.json'
        main_ptbr_data: dict[str, Any] = {}
        episode_ptbr_data: dict[str, Any] = {}
        data: dict[str, Any] = {}

        if os.path.isfile(localized_data_file):
            try:
                async with aiofiles.open(localized_data_file, encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)
            except json.JSONDecodeError:
                console.print(f'Warning: Could not decode JSON from {localized_data_file}', markup=False)
                data = {}
            except Exception as e:
                console.print(f'Error reading file {localized_data_file}: {e}', markup=False)
                data = {}

        main_ptbr_data = dict(data.get('pt-BR', {})).get('main', {})

        if not main_ptbr_data:
            main_ptbr_data = await self.tmdb_manager.get_tmdb_localized_data(
                meta,
                data_type='main',
                language='pt-BR',
                append_to_response='credits,videos,content_ratings'
            )

        if self.config['DEFAULT']['episode_overview'] and meta['category'] == 'TV' and not meta.get('tv_pack'):
            episode_ptbr_data = data.get('pt-BR', {}).get('episode')
            if not episode_ptbr_data:
                episode_ptbr_data = await self.tmdb_manager.get_tmdb_localized_data(
                    meta,
                    data_type='episode',
                    language='pt-BR',
                    append_to_response=''
                )

        self.main_tmdb_data = main_ptbr_data or {}
        self.episode_tmdb_data = episode_ptbr_data or {}

        return

    def get_container(self, meta: dict[str, Any]) -> str:
        container: str = meta.get('container', '')
        if container in ['mkv', 'mp4', 'avi', 'vob', 'm2ts', 'ts']:
            return container.upper()

        return 'Outro'

    def get_type(self, meta: dict[str, Any]) -> str:
        if meta.get('anime'):
            return '13'

        category_map = {
            'TV': '1',
            'MOVIE': '0'
        }

        return category_map.get(meta['category'], '0')

    def get_languages(self) -> str:
        possible_languages = {
            'Alemão', 'Árabe', 'Argelino', 'Búlgaro', 'Cantonês', 'Chinês',
            'Coreano', 'Croata', 'Dinamarquês', 'Egípcio', 'Espanhol', 'Estoniano',
            'Filipino', 'Finlandês', 'Francês', 'Grego', 'Hebraico', 'Hindi',
            'Holandês', 'Húngaro', 'Indonésio', 'Inglês', 'Islandês', 'Italiano',
            'Japonês', 'Macedônio', 'Malaio', 'Marati', 'Nigeriano', 'Norueguês',
            'Persa', 'Polaco', 'Polonês', 'Português', 'Português (pt)', 'Romeno',
            'Russo', 'Sueco', 'Tailandês', 'Tamil', 'Tcheco', 'Telugo', 'Turco',
            'Ucraniano', 'Urdu', 'Vietnamita', 'Zulu', 'Outro'
        }
        lang_code = self.main_tmdb_data.get('original_language')
        origin_countries = self.main_tmdb_data.get('origin_country', [])

        if not lang_code:
            return 'Outro'

        language_name = None

        if lang_code == 'pt':
            language_name = 'Português (pt)' if 'PT' in origin_countries else 'Português'
        else:
            try:
                language_name = langcodes.Language.make(lang_code).display_name('pt').capitalize()
            except LanguageTagError:
                language_name = lang_code

        if language_name in possible_languages:
            return language_name
        else:
            return 'Outro'

    async def get_audio(self, meta: dict[str, Any]) -> str:
        if not meta.get('language_checked', False):
            await languages_manager.process_desc_language(meta, tracker=self.tracker)

        audio_languages = set(meta.get('audio_languages', []))

        portuguese_languages = ['Portuguese', 'Português', 'pt']

        has_pt_audio = any(lang in portuguese_languages for lang in audio_languages)

        original_lang = str(meta.get('original_language', '')).lower()
        is_original_pt = original_lang in portuguese_languages

        if has_pt_audio:
            if is_original_pt:
                return 'Nacional'
            elif len(audio_languages) > 1:
                return 'Dual Áudio'
            else:
                return 'Dublado'

        return 'Legendado'

    async def get_subtitle(self, meta: dict[str, Any]) -> str:
        if not meta.get('language_checked', False):
            await languages_manager.process_desc_language(meta, tracker=self.tracker)
        found_language_strings = meta.get('subtitle_languages', [])

        subtitle_type = 'Nenhuma'

        if 'Portuguese' in found_language_strings:
            subtitle_type = 'Embutida'

        return subtitle_type

    def get_resolution(self, meta: dict[str, Any]) -> tuple[str, str]:
        width, height = '0', '0'

        if meta.get('is_disc') == 'BDMV':
            resolution_str = str(meta.get('resolution', ''))
            try:
                height_num = int(resolution_str.lower().replace('p', '').replace('i', ''))
                height = str(height_num)

                width_num = round((16 / 9) * height_num)
                width = str(width_num)
            except (ValueError, TypeError):
                pass

        else:
            video_mi = meta['mediainfo']['media']['track'][1]
            width = video_mi['Width']
            height = video_mi['Height']

        return width, height

    def get_video_codec(self, meta: dict[str, Any]) -> str:
        codec_map = {
            'x265': 'x265',
            'h.265': 'H.265',
            'x264': 'x264',
            'h.264': 'H.264',
            'av1': 'AV1',
            'divx': 'DivX',
            'h.263': 'H.263',
            'kvcd': 'KVCD',
            'mpeg-1': 'MPEG-1',
            'mpeg-2': 'MPEG-2',
            'realvideo': 'RealVideo',
            'vc-1': 'VC-1',
            'vp6': 'VP6',
            'vp8': 'VP8',
            'vp9': 'VP9',
            'windows media video': 'Windows Media Video',
            'xvid': 'XviD',
            'hevc': 'H.265',
            'avc': 'H.264',
        }

        video_encode = str(meta.get('video_encode', '')).lower()
        video_codec = str(meta.get('video_codec', ''))

        search_text = f'{video_encode} {video_codec.lower()}'

        for key, value in codec_map.items():
            if key in search_text:
                return value

        return video_codec if video_codec else 'Outro'

    def get_audio_codec(self, meta: dict[str, Any]) -> str:
        priority_order = [
            'DTS-X', 'E-AC-3 JOC', 'TrueHD', 'DTS-HD', 'LPCM', 'PCM', 'FLAC',
            'DTS-ES', 'DTS', 'E-AC-3', 'AC3', 'AAC', 'Opus', 'Vorbis', 'MP3', 'MP2'
        ]

        codec_map = {
            'DTS-X': ['DTS:X', 'DTS-X'],
            'E-AC-3 JOC': ['E-AC-3 JOC', 'DD+ JOC'],
            'TrueHD': ['TRUEHD'],
            'DTS-HD': ['DTS-HD', 'DTSHD'],
            'LPCM': ['LPCM'],
            'PCM': ['PCM'],
            'FLAC': ['FLAC'],
            'DTS-ES': ['DTS-ES'],
            'DTS': ['DTS'],
            'E-AC-3': ['E-AC-3', 'DD+'],
            'AC3': ['AC3', 'DD'],
            'AAC': ['AAC'],
            'Opus': ['OPUS'],
            'Vorbis': ['VORBIS'],
            'MP2': ['MP2'],
            'MP3': ['MP3']
        }

        audio_description = meta.get('audio')

        if not audio_description or not isinstance(audio_description, str):
            return 'Outro'

        audio_upper = audio_description.upper()

        for codec_name in priority_order:
            search_terms = codec_map.get(codec_name, [])

            for term in search_terms:
                if term.upper() in audio_upper:
                    return codec_name

        return 'Outro'

    def get_title(self, meta: dict[str, Any]) -> tuple[str, str]:
        original_title = meta['title']
        brazilian_title = ""

        if BJS.database_title:
            original_title = BJS.database_title

        tmdb_title = self.main_tmdb_data.get('name') or self.main_tmdb_data.get('title')
        if tmdb_title and tmdb_title != meta.get('title'):
            brazilian_title = tmdb_title

        return original_title, brazilian_title

    async def build_description(self, meta: dict[str, Any]) -> str:
        builder = DescriptionBuilder(self.tracker, self.config)
        desc_parts: list[str] = []

        # Custom Header
        desc_parts.append(await builder.get_custom_header())

        # Logo
        logo_resize_url = str(meta.get("tmdb_logo", ""))
        if logo_resize_url:
            if logo_resize_url.endswith(".svg"):
                logo_resize_url = logo_resize_url.replace(".svg", ".png")
            desc_parts.append(f"[align=center][img]https://image.tmdb.org/t/p/w300/{logo_resize_url}[/img][/align]")

        # TV
        title = self.episode_tmdb_data.get('name', '')
        episode_image = self.episode_tmdb_data.get('still_path', '')
        episode_overview = self.episode_tmdb_data.get('overview', '')

        if episode_overview:
            desc_parts.append(f'[align=center]{title}[/align]')

            if episode_image:
                desc_parts.append(f"[align=center][img]https://image.tmdb.org/t/p/w300{episode_image}[/img][/align]")

            desc_parts.append(f'[align=center]{episode_overview}[/align]')

        # File information
        if meta.get('is_disc', '') == 'DVD':
            desc_parts.append(f'[hide=DVD MediaInfo][pre]{await builder.get_mediainfo_section(meta)}[/pre][/hide]')

        bd_info = await builder.get_bdinfo_section(meta)
        if bd_info:
            desc_parts.append(f'[hide=BDInfo][pre]{bd_info}[/pre][/hide]')

        # User description
        desc_parts.append(await builder.get_user_description(meta))

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta))

        # Signature
        desc_parts.append(f"[align=center][url=https://github.com/Audionut/Upload-Assistant]Upload realizado via {meta['ua_name']} {meta['current_version']}[/url][/align]")

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        bbcode = BBCODE()
        description = bbcode.convert_named_spoiler_to_named_hide(description)
        description = bbcode.convert_spoiler_to_hide(description)
        description = bbcode.remove_img_resize(description)
        description = bbcode.convert_to_align(description)
        description = bbcode.remove_list(description)
        description = bbcode.remove_extra_lines(description)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as description_file:
            await description_file.write(description)

        return description

    def get_trailer(self, meta: dict[str, Any]) -> str:
        video_results: list[dict[str, Any]] = dict(self.main_tmdb_data.get('videos', {})).get('results', [])
        youtube_code = video_results[-1].get('key', '') if video_results else ''
        youtube = f'http://www.youtube.com/watch?v={youtube_code}' if youtube_code else meta.get('youtube') or ''

        return youtube

    def get_rating(self) -> str:
        ratings: list[dict[str, Any]] = dict(self.main_tmdb_data.get('content_ratings', {})).get('results', [])

        if not ratings:
            return ''

        valid_br_ratings = {'L', '10', '12', '14', '16', '18'}

        br_rating = ''
        us_rating = ''

        for item in ratings:
            if item.get('iso_3166_1') == 'BR' and item.get('rating') in valid_br_ratings:
                br_rating = item['rating']
                br_rating = 'Livre' if br_rating == 'L' else f'{br_rating} anos'
                break

            # Use US rating as fallback
            if item.get('iso_3166_1') == 'US' and not us_rating:
                us_rating = item.get('rating', '')

        return br_rating or us_rating or ''

    async def get_tags(self) -> str:
        tags = ''
        genres_data: list[dict[str, Any]] = self.main_tmdb_data.get('genres', [])
        genre_names: list[str] = []

        for g in genres_data:
            name: str = g.get('name', '')
            if name.strip():
                genre_names.append(name)

            if genre_names:
                tags = ', '.join(
                    unicodedata.normalize('NFKD', name)
                    .encode('ASCII', 'ignore')
                    .decode('utf-8')
                    .replace(' ', '.')
                    .lower()
                    for name in genre_names
                )

        if not tags:
             tags_raw = await asyncio.to_thread(cli_ui.ask_string, f'Digite os gêneros (no formato do {self.tracker}): ')
             tags = (tags_raw or "").strip()

        return tags

    def _extract_upload_params(self, meta: dict[str, Any]) -> dict[str, Any]:
        is_tv_pack = bool(meta.get('tv_pack'))
        upload_season_num = None
        upload_episode_num = None
        upload_resolution = meta.get('resolution')

        if meta['category'] == 'TV':
            season_match = meta.get('season', '').replace('S', '')
            if season_match:
                upload_season_num = season_match

            if not is_tv_pack:
                episode_match = meta.get('episode', '').replace('E', '')
                if episode_match:
                    upload_episode_num = episode_match

        return {
            'is_tv_pack': is_tv_pack,
            'upload_season_num': upload_season_num,
            'upload_episode_num': upload_episode_num,
            'upload_resolution': upload_resolution
        }

    def _check_episode_on_page(self, torrent_table: Optional[Tag], upload_season_num: str, upload_episode_num: str) -> bool:
        if not upload_season_num or not upload_episode_num or not torrent_table:
            return False

        temp_season_on_page: str = ""
        upload_episode_str = f'E{upload_episode_num}'

        for row in torrent_table.find_all('tr'):
            row_classes = row.get('class')
            if isinstance(row_classes, list) and 'season_header' in row_classes:
                s_match = re.search(r'Temporada (\d+)', row.get_text(strip=True))
                if s_match:
                    temp_season_on_page = s_match.group(1)
                continue

            if (temp_season_on_page == upload_season_num and str(row.get('id', '')).startswith('torrent')):
                link = row.find('a', onclick=re.compile(r'loadIfNeeded\('))
                if (link and re.search(r'\b' + re.escape(upload_episode_str) + r'\b', link.get_text(strip=True))):
                    return True
        return False

    def _should_process_torrent(self, row: Tag, current_season: str, current_resolution: str, params: dict[str, Any], episode_found_on_page: bool, meta: dict[str, Any]) -> tuple[bool, bool]:
        link = row.find('a', onclick=re.compile(r'loadIfNeeded\('))

        if not isinstance(link, Tag):
            return False, False

        description_text = ' '.join(link.get_text(strip=True).split())

        # TV Logic
        if meta['category'] == 'TV':
            if current_season == params['upload_season_num']:
                existing_episode_match = re.search(r'E(\d+)', description_text)
                is_current_row_a_pack = not existing_episode_match

                if params['is_tv_pack']:
                    return is_current_row_a_pack, False
                else:
                    if episode_found_on_page:
                        if existing_episode_match:
                            existing_episode_num = existing_episode_match.group(1)
                            return existing_episode_num == params['upload_episode_num'], False
                    else:
                        return is_current_row_a_pack, True

        # Movie Logic
        elif meta['category'] == 'MOVIE' and params['upload_resolution'] and current_resolution == params['upload_resolution']:
            return True, False

        return False, False

    def _extract_torrent_ids(self, rows_to_process: list[tuple[Tag, bool]]) -> list[dict[str, Any]]:
        ajax_tasks: list[dict[str, Any]] = []

        for row, process_folder_name in rows_to_process:
            id_link = row.find('a', onclick=re.compile(r'loadIfNeeded\('))
            if not id_link:
                continue

            onclick_attr = str(id_link['onclick'])
            id_match = re.search(r"loadIfNeeded\('(\d+)',\s*'(\d+)'", onclick_attr)
            if not id_match:
                continue

            torrent_id = id_match.group(1)
            group_id = id_match.group(2)
            description_text = ' '.join(id_link.get_text(strip=True).split())
            torrent_link = f'{self.torrent_url}{torrent_id}'

            size_tag = row.find('td', class_='number_column nobr')
            torrent_size_str = size_tag.get_text(strip=True) if size_tag else None

            ajax_tasks.append({
                'torrent_id': torrent_id,
                'group_id': group_id,
                'description_text': description_text,
                'process_folder_name': process_folder_name,
                'size': torrent_size_str,
                'link': torrent_link
            })

        return ajax_tasks

    async def _fetch_torrent_content(self, task_info: dict[str, Any]) -> dict[str, Any]:
        torrent_id = task_info['torrent_id']
        group_id = task_info['group_id']
        ajax_url = f'{self.base_url}/ajax.php?action=torrent_content&torrentid={torrent_id}&groupid={group_id}'

        max_retries = 3
        base_delay = 5
        last_error: Optional[Exception] = None

        async def _attempt_fetch() -> tuple[Optional[BeautifulSoup], Optional[Exception]]:
            try:
                async with self.semaphore:
                    ajax_response = await self.session.get(ajax_url)
                    ajax_response.raise_for_status()
                    ajax_soup = BeautifulSoup(ajax_response.text, "html.parser")
                return ajax_soup, None
            except Exception as e:
                return None, e

        for attempt in range(1, max_retries + 1):
            ajax_soup, error = await _attempt_fetch()
            if ajax_soup is not None:
                return {
                    'success': True,
                    'soup': ajax_soup,
                    'task_info': task_info
                }

            last_error = error
            if attempt < max_retries:
                await asyncio.sleep(base_delay * (2 ** (attempt - 1)))

        console.print(f'[yellow]Não foi possível buscar a lista de arquivos para o torrent {torrent_id}: {last_error}[/yellow]')
        return {
            'success': False,
            'error': last_error,
            'task_info': task_info
        }

    def _extract_item_name(self, ajax_soup: BeautifulSoup, description_text: str, is_tv_pack: bool, process_folder_name: bool) -> str:
        item_name: str = ""

        is_existing_torrent_a_disc = any(
            keyword in description_text.lower()
            for keyword in ['bd25', 'bd50', 'bd66', 'bd100', 'dvd5', 'dvd9', 'm2ts']
        )

        if is_existing_torrent_a_disc or is_tv_pack or process_folder_name:
            path_div = ajax_soup.find('div', class_='filelist_path')
            if isinstance(path_div, Tag) and path_div.get_text(strip=True):
                item_name = path_div.get_text(strip=True).strip('/')
            else:
                file_table = ajax_soup.find('table', class_='filelist_table')
                if isinstance(file_table, Tag):
                    first_file_row = file_table.find('tr', class_=lambda x: x != 'colhead_dark')
                    if isinstance(first_file_row, Tag):
                        first_td = first_file_row.find('td')
                        if isinstance(first_td, Tag):
                            item_name = first_td.get_text(strip=True)
        else:
            file_table = ajax_soup.find('table', class_='filelist_table')
            if isinstance(file_table, Tag):
                first_row = file_table.find('tr', class_=lambda x: x != 'colhead_dark')
                if isinstance(first_row, Tag):
                    first_td = first_row.find('td')
                    if isinstance(first_td, Tag):
                        item_name = first_td.get_text(strip=True)

        return item_name

    async def _process_ajax_responses(self, ajax_tasks: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, str]]:
        found_items: list[dict[str, str]] = []

        if not ajax_tasks:
            return found_items

        ajax_results = await asyncio.gather(
            *[self._fetch_torrent_content(task) for task in ajax_tasks],
            return_exceptions=True
        )

        for result in ajax_results:
            if isinstance(result, Exception):
                console.print(f'[yellow]Error in AJAX call: {result}[/yellow]')
                continue

            fetch_result = cast(dict[str, Any], result)
            if not fetch_result.get('success'):
                continue

            task_info = fetch_result.get('task_info', {})
            soup_obj = fetch_result.get('soup')

            if not isinstance(task_info, dict) or not isinstance(soup_obj, BeautifulSoup):
                continue

            task_info = cast(dict[str, Any], task_info)
            description_text = str(task_info.get('description_text', ''))
            process_folder_name = bool(task_info.get('process_folder_name'))

            item_name = self._extract_item_name(
                soup_obj,
                description_text,
                params['is_tv_pack'],
                process_folder_name
            )

            torrent_description = ""
            desc_block = soup_obj.find(
                lambda tag: tag.name == "blockquote" and "Informações Adicionais:" in tag.get_text()
            )

            if desc_block:
                torrent_description = desc_block.get_text("\n", strip=True)

            if item_name:
                found_items.append({
                    'name': item_name,
                    'size': str(task_info.get('size') or ''),
                    'link': str(task_info.get('link') or ''),
                    'description': torrent_description,
                })

        return found_items

    async def _fetch_search_page(self, meta: dict[str, Any]) -> BeautifulSoup:
        search_url = f"{self.base_url}/torrents.php?searchstr={meta['imdb_info']['imdbID']}"

        response = await self.session.get(search_url)
        if response.status_code in [301, 302, 307] and 'Location' in response.headers:
            redirect_url = f"{self.base_url}/{response.headers['Location']}"
            response = await self.session.get(redirect_url)

        return BeautifulSoup(response.text, 'html.parser')

    def get_database_title(self, soup: BeautifulSoup) -> str:
        """
        Extracts the original title to ensure consistency with the BJS database.
        Since BJS treats different titles as unique entries regardless of IMDb parity,
        this value is used to match existing records.
        """
        original_title = ''
        info_boxes = soup.find_all('div', class_='box')
        target_box = None

        for box in info_boxes:
            header_div = box.find('div', class_='head')
            if header_div and 'Informações' in header_div.get_text():
                target_box = box
                break

        if target_box:
            rows = target_box.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label_text = cells[0].get_text(strip=True)
                    if 'Título Original:' in label_text or 'Título:' in label_text:
                        original_title = cells[1].get_text(strip=True)
                        break

        return original_title

    async def search_existing(self, meta: dict[str, Any], _) -> list[dict[str, str]]:
        dupes: list[dict[str, str]] = []
        should_continue = self.get_additional_checks(meta)
        if not should_continue:
            meta['skipping'] = f'{self.tracker}'
            return dupes

        if not dict(meta.get('imdb_info', {})).get('imdbID'):
            console.print(f"{self.tracker}: [bold red]IMDb ID not found in metadata. Skipping duplicate check.[/bold red]")
            return dupes

        try:
            cookie_jar = await self.cookie_validator.load_session_cookies(meta, self.tracker)
            if cookie_jar:
                self.session.cookies = cookie_jar

            BJS.already_has_the_info = False
            BJS.database_title = ''
            params: dict[str, Any] = self._extract_upload_params(meta)

            soup = await self._fetch_search_page(meta)
            torrent_details_table: Optional[Tag] = soup.find('div', class_='main_column')

            if torrent_details_table:
                BJS.already_has_the_info = True
                BJS.database_title = self.get_database_title(soup)
            else:
                return dupes

            episode_found_on_page = False
            if (meta['category'] == 'TV' and not params['is_tv_pack'] and params['upload_season_num'] and params['upload_episode_num']):
                episode_found_on_page = self._check_episode_on_page(
                    torrent_details_table,
                    params['upload_season_num'],
                    params['upload_episode_num']
                )

            rows_to_process: list[tuple[Tag, bool]] = []
            current_season_on_page = ""
            current_resolution_on_page = ""

            for row in torrent_details_table.find_all('tr'):
                row_classes = row.get('class')
                if isinstance(row_classes, list):
                    if 'resolution_header' in row_classes:
                        header_text = row.get_text(strip=True)
                        resolution_match = re.search(r'(\d{3,4}p)', header_text)
                        if resolution_match:
                            current_resolution_on_page = resolution_match.group(1)
                        continue

                    if 'season_header' in row_classes:
                        season_header_text = row.get_text(strip=True)
                        season_match = re.search(r'Temporada (\d+)', season_header_text)
                        if season_match:
                            current_season_on_page = season_match.group(1)
                        continue

                    row_id = row.get('id')
                    if isinstance(row_id, str) and not row_id.startswith('torrent'):
                        continue

                    id_link = row.find('a', onclick=re.compile(r'loadIfNeeded\('))
                    if not id_link:
                        continue

                    should_process, process_folder_name = self._should_process_torrent(
                        row, current_season_on_page, current_resolution_on_page,
                        params, episode_found_on_page, meta
                    )

                    if should_process:
                        rows_to_process.append((row, process_folder_name))

            ajax_tasks = self._extract_torrent_ids(rows_to_process)
            dupes = await self._process_ajax_responses(ajax_tasks, params)

            return dupes

        except Exception as e:
            console.print(f'[bold red]Ocorreu um erro inesperado ao processar a busca: {e}[/bold red]')
            import traceback
            traceback.print_exc()
            return dupes

    def get_edition(self, meta: dict[str, Any]) -> str:
        edition_str = str(meta.get('edition', '')).lower()
        if not edition_str:
            return ''

        edition_map = {
            "director's cut": "Director's Cut",
            'extended': 'Extended Edition',
            'imax': 'IMAX',
            'open matte': 'Open Matte',
            'noir': 'Noir Edition',
            'theatrical': 'Theatrical Cut',
            'uncut': 'Uncut',
            'unrated': 'Unrated',
            'uncensored': 'Uncensored',
        }

        for keyword, label in edition_map.items():
            if keyword in edition_str:
                return label

        return ''

    def get_bitrate(self, meta: dict[str, Any]) -> str:
        if meta.get('type') == 'DISC':
            is_disc_type = meta.get('is_disc')

            if is_disc_type == 'BDMV':
                disctype = str(meta.get('disctype', ''))
                if disctype in ['BD100', 'BD66', 'BD50', 'BD25']:
                    return disctype

                try:
                    size_in_gb = meta['bdinfo']['size']
                except (KeyError, IndexError, TypeError):
                    size_in_gb = 0

                if size_in_gb > 66:
                    return 'BD100'
                elif size_in_gb > 50:
                    return 'BD66'
                elif size_in_gb > 25:
                    return 'BD50'
                else:
                    return 'BD25'

            elif is_disc_type == 'DVD':
                dvd_size = str(meta.get('dvd_size', ''))
                if dvd_size in ['DVD9', 'DVD5']:
                    return dvd_size
                return 'DVD9'

        source_type = meta.get('type')

        if not source_type or not isinstance(source_type, str):
            return 'Outro'

        keyword_map = {
            'webdl': 'WEB-DL',
            'webrip': 'WEBRip',
            'web': 'WEB',
            'remux': 'Blu-ray',
            'encode': 'Blu-ray',
            'bdrip': 'BDRip',
            'brrip': 'BRRip',
            'hdtv': 'HDTV',
            'sdtv': 'SDTV',
            'dvdrip': 'DVDRip',
            'hd-dvd': 'HD DVD',
            'dvdscr': 'DVDScr',
            'hdrip': 'HDRip',
            'hdtc': 'HDTC',
            'pdtv': 'PDTV',
            'tc': 'TC',
            'uhdtv': 'UHDTV',
            'vhsrip': 'VHSRip',
            'tvrip': 'TVRip',
        }

        return keyword_map.get(source_type.lower(), 'Outro')

    async def img_host(self, image_bytes: bytes, filename: str) -> Optional[str]:
        upload_url = f'{self.base_url}/ajax.php?action=screen_up'
        headers = {
            'Referer': f'{self.base_url}/upload.php',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
        }
        files = {'file': (filename, image_bytes, 'image/png')}

        try:
            response = await self.session.post(
                upload_url, headers=headers, files=files, timeout=120
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()

            img_url = None
            if data.get('url') and str(data.get('url', '')).startswith('http'):
                img_url = str(data.get('url', '')).replace('\\/', '/')
            else:
                console.print(f'{self.tracker}: [bold red]The image host appears to be down.[/bold red]')

            return img_url
        except Exception as e:
            console.print(f'Exceção no upload de {filename}: {e}', markup=False)
            return None

    async def get_cover(self, meta: dict[str, Any]):
        cover_path = self.main_tmdb_data.get('poster_path') or meta.get('tmdb_poster')
        if not cover_path:
            console.print('Nenhum poster_path encontrado nos dados do TMDB.', markup=False)
            return None

        cover_tmdb_url = f'https://image.tmdb.org/t/p/w500{cover_path}'
        if BJS.already_has_the_info:
            return cover_tmdb_url

        try:
            response = await self.session.get(cover_tmdb_url, timeout=120)
            response.raise_for_status()
            image_bytes = response.content
            filename = os.path.basename(cover_path)

            return await self.img_host(image_bytes, filename)
        except Exception as e:
            console.print(f'Falha ao processar pôster da URL {cover_tmdb_url}: {e}', markup=False)
            return None

    async def get_screenshots(self, meta: dict[str, Any]) -> list[str]:
        screenshot_dir = Path(meta["base_dir"]) / "tmp" / meta["uuid"]
        local_files = sorted(screenshot_dir.glob("*.png"))

        disc_menu_links = [img.get("raw_url") for img in meta.get("menu_images", []) if img.get("raw_url")][
            :3
        ]

        async def upload_local_file(path: Path):
            async with aiofiles.open(path, "rb") as f:
                image_bytes = await f.read()
            return await self.img_host(image_bytes, os.path.basename(path))

        async def upload_remote_file(url: str):
            try:
                response = await self.session.get(url, timeout=120)
                response.raise_for_status()
                image_bytes = response.content
                filename = os.path.basename(urlparse(url).path) or "screenshot.png"
                return await self.img_host(image_bytes, filename)
            except Exception as e:
                console.print(f"Failed to process screenshot from URL {url}: {e}", markup=False)
                return None

        results: list[str] = []

        # Upload menu images
        for url in disc_menu_links:
            result = await upload_remote_file(url)
            if result:
                results.append(result)

        # Use existing files
        if local_files:
            paths: list[Path] = local_files[: 6 - len(results)]

            for coro in asyncio.as_completed([upload_local_file(p) for p in paths]):
                result = await coro
                if result:
                    results.append(result)

        else:
            image_links = [img.get("raw_url") for img in meta.get("image_list", []) if img.get("raw_url")][
                : 6 - len(results)
            ]

            for coro in asyncio.as_completed([upload_remote_file(url) for url in image_links]):
                result = await coro
                if result:
                    results.append(result)

        return results

    def get_runtime(self, meta: dict[str, Any]) -> dict[str, int]:
        """
        Extracts runtime from metadata and converts total minutes into hours and minutes.
        """
        raw_runtime = meta.get('runtime', 0)

        try:
            total_minutes = max(0, int(raw_runtime))
        except (ValueError, TypeError):
            total_minutes = 0

        hours, minutes = divmod(total_minutes, 60)

        return {
            'hours': hours,
            'minutes': minutes
        }

    def get_release_date(self) -> str:
        raw_date_string = self.main_tmdb_data.get('first_air_date') or self.main_tmdb_data.get('release_date')

        if not raw_date_string:
            return ''

        try:
            date_object = datetime.strptime(raw_date_string, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            formatted_date = date_object.strftime('%d %b %Y')

            return formatted_date

        except ValueError:
            return ''

    def find_remaster_tags(self, meta: dict[str, Any]) -> set[str]:
        found_tags: set[str] = set()

        edition = self.get_edition(meta)
        if edition:
            found_tags.add(edition)

        audio_string = meta.get('audio', '')
        if 'Atmos' in audio_string:
            found_tags.add('Dolby Atmos')

        is_10_bit = False
        if meta.get('is_disc') == 'BDMV':
            try:
                bit_depth_str = meta['discs'][0]['bdinfo']['video'][0]['bit_depth']
                if '10' in bit_depth_str:
                    is_10_bit = True
            except (KeyError, IndexError, TypeError):
                pass
        else:
            if str(meta.get('bit_depth')) == '10':
                is_10_bit = True

        if is_10_bit:
            found_tags.add('10-bit')

        hdr_string = str(meta.get('hdr', '')).upper()
        if 'DV' in hdr_string:
            found_tags.add('Dolby Vision')
        if 'HDR10+' in hdr_string:
            found_tags.add('HDR10+')
        if 'HDR' in hdr_string and 'HDR10+' not in hdr_string:
            found_tags.add('HDR10')

        if meta.get('type') == 'REMUX':
            found_tags.add('Remux')
        if meta.get('extras'):
            found_tags.add('Com extras')
        if meta.get('has_commentary', False) or meta.get('manual_commentary', False):
            found_tags.add('Com comentários')

        return found_tags

    def build_remaster_title(self, meta: dict[str, Any]) -> str:
        tag_priority = [
            'Dolby Atmos',
            'Remux',
            "Director's Cut",
            'Extended Edition',
            'IMAX',
            'Open Matte',
            'Noir Edition',
            'Theatrical Cut',
            'Uncut',
            'Unrated',
            'Uncensored',
            '10-bit',
            'Dolby Vision',
            'HDR10+',
            'HDR10',
            'Com extras',
            'Com comentários'
        ]
        available_tags = self.find_remaster_tags(meta)

        ordered_tags = [tag for tag in tag_priority if tag in available_tags]

        return ' / '.join(ordered_tags)

    async def get_credits(self, meta: dict[str, Any], role: str) -> str:
        if BJS.already_has_the_info:
            return 'N/A'

        role_map = {
            'director': ('directors', 'tmdb_directors'),
            'creator': ('creators', 'tmdb_creators'),
            'cast': ('stars', 'tmdb_cast'),
        }

        prompt_labels = {
            'director': 'Diretor(es)',
            'creator': 'Criador(es)',
            'cast': 'Elenco',
        }

        if role not in role_map:
            return 'N/A'

        imdb_key, tmdb_key = role_map[role]

        imdb_data: dict[str, Any] = meta.get('imdb_info', {})
        imdb_names = imdb_data.get(imdb_key, [])
        tmdb_names = meta.get(tmdb_key, [])
        names = imdb_names + tmdb_names

        unique_names = list(dict.fromkeys(names))[:5]

        if unique_names:
            return ', '.join(unique_names)

        display_name = prompt_labels.get(role, role.capitalize())
        prompt_message = (
            f'{display_name} não encontrado(s).\n'
            'Por favor, insira manualmente (separados por vírgula): '
        )

        user_input_raw = await asyncio.to_thread(cli_ui.ask_string, f'{prompt_message}')
        user_input = (user_input_raw or "").strip()
        if user_input:
            return user_input

        return 'skipped'

    def get_imdb_rating(self, meta: dict[str, Any]):
        imdb_info = dict(meta.get('imdb_info', {}))
        rating = imdb_info.get('rating')

        if not rating:
            return "N/A"

        return str(rating)

    async def get_requests(self, meta: dict[str, Any]) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        if not self.config['DEFAULT'].get('search_requests', False) and not meta.get('search_requests', False):
            return results
        else:
            try:
                cookie_jar = await self.cookie_validator.load_session_cookies(meta, self.tracker)
                if cookie_jar:
                    self.session.cookies = cookie_jar
                cat = meta['category']
                if cat == 'TV':
                    cat = 2
                if cat == 'MOVIE':
                    cat = 1
                if meta.get('anime'):
                    cat = 14

                query = meta['title']

                search_url = f'{self.requests_url}submit=true&search={query}&showall=on&filter_cat[{cat}]=1'

                response = await self.session.get(search_url)
                response.raise_for_status()
                response_results_text = response.text

                soup = BeautifulSoup(response_results_text, 'html.parser')

                request_rows = soup.select('#torrent_table tr.torrent')

                for row in request_rows:
                    all_tds = row.find_all('td')
                    if not all_tds or len(all_tds) < 5:
                        continue

                    info_cell = all_tds[1]

                    link_element = info_cell.select_one('a[href*="requests.php?action=view"]')
                    quality_element = info_cell.select_one('b')

                    if not isinstance(link_element, Tag) or not isinstance(quality_element, Tag):
                        continue

                    name: str = str(link_element.text).strip()
                    quality: str = str(quality_element.text).strip()
                    url = link_element.get('href')
                    if isinstance(url, str):
                        link: str = url
                    else:
                        link = ''

                    reward_td = all_tds[3]
                    reward_parts = [td.text.replace('\xa0', ' ').strip() for td in reward_td.select('tr > td:first-child')]
                    reward = ' / '.join(reward_parts)

                    results.append({
                        'Name': name,
                        'Quality': quality,
                        'Reward': reward,
                        'Link': link,
                    })

                if results:
                    message = f'\n{self.tracker}: [bold yellow]Seu upload pode atender o(s) seguinte(s) pedido(s), confira:[/bold yellow]\n\n'
                    for r in results:
                        message += f"[bold green]Nome:[/bold green] {r['Name']}\n"
                        message += f"[bold green]Qualidade:[/bold green] {r['Quality']}\n"
                        message += f"[bold green]Recompensa:[/bold green] {r['Reward']}\n"
                        message += f"[bold green]Link:[/bold green] {self.base_url}/{r['Link']}\n\n"
                    console.print(message)

                return results

            except Exception as e:
                console.print(f'[bold red]Ocorreu um erro ao buscar pedido(s) no {self.tracker}: {e}[/bold red]')
                import traceback
                console.print(traceback.format_exc())
                return results

    async def get_data(self, meta: dict[str, Any]) -> dict[str, Any]:
        cookie_jar = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        if cookie_jar:
            self.session.cookies = cookie_jar
        await self.load_localized_data(meta)
        category = meta['category']
        original_title, brazilian_title = self.get_title(meta)
        width, height = self.get_resolution(meta)

        data: dict[str, Any] = {}

        # These fields are common across all upload types
        data.update({
            'audio': await self.get_audio(meta),
            'auth': BJS.secret_token,
            'codecaudio': self.get_audio_codec(meta),
            'codecvideo': self.get_video_codec(meta),
            'duracaoHR': self.get_runtime(meta).get('hours'),
            'duracaoMIN': self.get_runtime(meta).get('minutes'),
            'duracaotipo': 'selectbox',
            'fichatecnica': await self.build_description(meta),
            'formato': self.get_container(meta),
            'idioma': self.get_languages(),
            'imdblink': self.get_imdblink(meta),
            'qualidade': self.get_bitrate(meta),
            'release': meta.get('service_longname', ''),
            'remaster_title': self.build_remaster_title(meta),
            'resolucaoh': height,
            'resolucaow': width,
            'sinopse': await self.get_overview(),
            'submit': 'true',
            'tags': await self.get_tags(),
            'tipolegenda': await self.get_subtitle(meta),
            'title': original_title,
            'titulobrasileiro': brazilian_title,
            'traileryoutube': self.get_trailer(meta),
            'type': self.get_type(meta),
            'year': self.get_year(meta),
        })

        # These fields are common in movies and TV shows, even if it's anime
        if category == 'MOVIE':
            data.update({
                'adulto': self.get_adulto(meta),
                'diretor': await self.get_credits(meta, 'director'),
            })

        if category == 'TV':
            data.update({
                'diretor': await self.get_credits(meta, 'creator'),
                'tipo': 'episode' if meta.get('tv_pack') == 0 else 'season',
                'season': meta.get('season_int', ''),
                'episode': meta.get('episode_int', ''),
            })

        # These fields are common in movies and TV shows, if not Anime
        if not meta.get('anime'):
            data.update({
                'validimdb': 'yes',
                'imdbrating': self.get_imdb_rating(meta),
                'elenco': await self.get_credits(meta, 'cast'),
            })
            if category == 'MOVIE':
                data.update({
                    'datalancamento': self.get_release_date(),
                })

            if category == 'TV':
                # Convert country code to name
                country_list = [
                    country.name
                    for code in self.main_tmdb_data.get('origin_country', [])
                    if (country := pycountry.countries.get(alpha_2=code))
                ]
                data.update({
                    'network': ', '.join([p.get('name', '') for p in self.main_tmdb_data.get('networks', [])]) or '',  # Optional
                    'numtemporadas': self.main_tmdb_data.get('number_of_seasons', ''),  # Optional
                    'datalancamento': self.get_release_date(),
                    'pais': ', '.join(country_list),  # Optional
                    'diretorserie': ', '.join(set(meta.get('tmdb_directors', []) or meta.get('imdb_info', {}).get('directors', [])[:5])),  # Optional
                    'avaliacao': self.get_rating(),  # Optional
                })

        # Anime-specific data
        if meta.get('anime'):
            if category == 'MOVIE':
                data.update({
                    'tipo': 'movie',
                })
            if category == 'TV':
                data.update({
                    'adulto': self.get_adulto(meta),
                })

        # Anon
        anon = not (meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False))
        if anon:
            data.update({
                'anonymous': 'on'
            })
            if self.config['TRACKERS'][self.tracker].get('show_group_if_anon', False):
                data.update({
                    'anonymousshowgroup': 'on'
                })

        # Internal
        if (
            self.config['TRACKERS'][self.tracker].get('internal', False) is True
            and meta['tag'] != ''
            and meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])
        ):
            data.update({
                'internalrel': 1,
            })

        # Only upload images if not debugging
        if not meta.get('debug', False):
            data.update({
                'image': await self.get_cover(meta),
                'screenshots[]': await self.get_screenshots(meta),
            })

        return data

    def get_year(self, meta: dict[str, Any]) -> str:
        start_year = meta.get("year", "N/A")
        imdb_info = dict(meta.get("imdb_info", {}))
        end_year = imdb_info.get("end_year")

        year_label = f"{start_year}-{end_year}" if end_year else f"{start_year}-"

        return year_label

    def get_adulto(self, meta: dict[str, Any]) -> str:
        """
        Check for adult classification eligibility.

        Adheres to upload guidelines where:
        - Movies: Classified as adult only if pornographic.
        - Anime TV Shows: Classified as adult only if hentai.
        """
        adult_yes = "1"
        adult_no = "2"

        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ["xxx", "erotic", "porn", "adult", "orgy"]

        if meta.get("anime", False) and "hentai" in genres.lower():
            return adult_yes

        if any(
            re.search(rf"(^|,\s*){re.escape(keyword)}(\s*,|$)", genres, re.IGNORECASE)
            for keyword in adult_keywords
        ):
            return adult_yes

        return adult_no

    def get_imdblink(self, meta: dict[str, Any]) -> str:
        """
        Get the media identifier for the upload.
        Uses IMDb ID as primary source, falling back to TMDb ID if unavailable.

        Accepted formats:
            IMDb: tt12345
            TMDb: movie12345 or tv12345
        """
        imdb_info = dict(meta.get("imdb_info", {}))
        imdbid = str(imdb_info.get("imdbID", ""))
        if imdbid:
            return imdbid

        category = str(meta.get("category", "")).upper()
        tmdb_id = meta.get("tmdb_id")

        if category in ["MOVIE", "TV"] and tmdb_id:
            return f"{category}{tmdb_id}".lower()

        return ""

    async def get_overview(self) -> str:
        overview = self.main_tmdb_data.get('overview', '')
        if isinstance(overview, str) and overview.strip():
            return overview

        if not BJS.already_has_the_info:
            console.print(
                f"{self.tracker}: [bold red]Sinopse não encontrada no TMDb. Por favor, insira manualmente.[/bold red]"
            )
            user_input_raw = await asyncio.to_thread(cli_ui.ask_string, f'"{self.tracker}: [green]Digite a sinopse:[/green]"')
            user_input = (user_input_raw or "").strip()
            if user_input:
                return user_input
            return 'N/A'

        return 'N/A'

    def check_data(self, meta: dict[str, Any], data: dict[str, Any]) -> str:
        if not meta.get("debug", False) and len(data["screenshots[]"]) < 2:
            return "The number of successful screenshots uploaded is less than 2."

        if any(
            value == "skipped" for value in (data.get("diretor"), data.get("elenco"), data.get("creators"))
        ):
            return "Missing required credits information (director/cast/creator)."

        if not data.get("imdblink"):
            return "Missing IMDb or TMDb identifier."

        return ""

    async def upload(self, meta: dict[str, Any], _):
        data = await self.get_data(meta)

        issue = self.check_data(meta, data)
        if issue:
            meta["tracker_status"][self.tracker]["status_message"] = f'data error - {issue}'
            return False
        else:
            is_uploaded = await self.cookie_auth_uploader.handle_upload(
                meta=meta,
                tracker=self.tracker,
                source_flag=self.source_flag,
                torrent_url=self.torrent_url,
                data=data,
                torrent_field_name='file_input',
                upload_cookies=self.session.cookies,
                upload_url=f"{self.base_url}/upload.php",
                id_pattern=r'torrentid=(\d+)',
                success_text="action=download&id=",
            )

        return is_uploaded
