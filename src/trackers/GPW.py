# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import json
import os
import re
import unicodedata
from typing import Any, cast

import aiofiles
import cli_ui
import httpx
from bs4 import BeautifulSoup

from cogs.redaction import Redaction
from src.bbcode import BBCODE
from src.console import console
from src.get_desc import DescriptionBuilder
from src.languages import languages_manager
from src.rehostimages import RehostImagesManager
from src.tmdb import TmdbManager
from src.trackers.COMMON import COMMON


class GPW:
    group_id: str = ""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.rehost_images_manager = RehostImagesManager(config)
        self.common = COMMON(config)
        self.tmdb_manager = TmdbManager(config)
        self.tracker = 'GPW'
        self.source_flag = 'GreatPosterWall'
        self.base_url = 'https://greatposterwall.com'
        self.torrent_url = f'{self.base_url}/torrents.php?torrentid='
        self.announce = self.config['TRACKERS'][self.tracker]['announce_url']
        self.api_key = self.config['TRACKERS'][self.tracker]['api_key']
        self.auth_token = None
        self.tmdb_data: dict[str, Any] = {}
        self.banned_groups = [
            "ALT", "aXXo", "BATWEB", "BlackTV", "BitsTV", "BMDRu", "BRrip", "CM8", "CrEwSaDe", "CTFOH", "CTRLHD",
            "DDHDTV", "DNL", "DreamHD", "ENTHD", "FaNGDiNG0", "FGT", "HD2DVD", "HDTime", "HDT", "Huawei", "GPTHD",
            "ION10", "iPlanet", "KiNGDOM", "Leffe", "Mp4Ba", "mHD", "MiniHD", "mSD", "MOMOWEB", "nHD", "nikt0", "NSBC",
            "nSD", "NhaNc3", "NukeHD", "OFT", "PRODJi", "RARBG", "RDN", "SANTi", "SeeHD", "SeeWEB", "SM737", "SonyHD",
            "STUTTERSHIT", "TAGWEB", "ViSION", "VXT", "WAF", "x0r", "Xiaomi", "YIFY",
        ]
        self.approved_image_hosts = ['kshare', 'pixhost', 'ptpimg', 'pterclub', 'ilikeshots', 'imgbox']
        self.url_host_mapping = {
            'kshare.club': 'kshare',
            'pixhost.to': 'pixhost',
            'imgbox.com': 'imgbox',
            'ptpimg.me': 'ptpimg',
            'img.pterclub.com': 'pterclub',
            'yes.ilikeshots.club': 'ilikeshots',
        }

    async def load_cookies(self, meta: dict[str, Any]) -> Any:
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        if not os.path.exists(cookie_file):
            return False

        return await self.common.parseCookieFile(cookie_file)

    async def load_localized_data(self, meta: dict[str, Any]) -> None:
        localized_data_file = f'{meta["base_dir"]}/tmp/{meta["uuid"]}/tmdb_localized_data.json'
        main_ch_data: dict[str, Any] = {}
        data: dict[str, Any] = {}

        if os.path.isfile(localized_data_file):
            try:
                async with aiofiles.open(localized_data_file, encoding='utf-8') as f:
                    content = await f.read()
                    loaded_data = json.loads(content)
                    data = cast(dict[str, Any], loaded_data) if isinstance(loaded_data, dict) else {}
            except json.JSONDecodeError:
                console.print(f'Warning: Could not decode JSON from {localized_data_file}', markup=False)
                data = {}
            except Exception as e:
                console.print(f'Error reading file {localized_data_file}: {e}', markup=False)
                data = {}

        ch_data = data.get('zh-cn')
        if isinstance(ch_data, dict):
            ch_dict = cast(dict[str, Any], ch_data)
            main_value = ch_dict.get('main')
            main_ch_data = cast(dict[str, Any], main_value) if isinstance(main_value, dict) else {}

        if not main_ch_data:
            localized_main = await self.tmdb_manager.get_tmdb_localized_data(
                meta,
                data_type='main',
                language='zh-cn',
                append_to_response='credits'
            )
            main_ch_data = localized_main or {}

        self.tmdb_data = main_ch_data

        return

    def get_container(self, meta: dict[str, Any]) -> str:
        container_value = meta.get('container', '')
        container = container_value if isinstance(container_value, str) else ''
        if container == 'm2ts':
            return container
        elif container == 'vob':
            return 'VOB IFO'
        elif container in ['avi', 'mpg', 'mp4', 'mkv']:
            return container.upper()

        return 'Other'

    async def get_subtitle(self, meta: dict[str, Any]) -> list[str]:
        if not meta.get('language_checked', False):
            await languages_manager.process_desc_language(meta, tracker=self.tracker)

        found_language_strings_raw = meta.get('subtitle_languages')
        if not isinstance(found_language_strings_raw, list):
            return []

        found_language_strings_list = cast(list[Any], found_language_strings_raw)
        found_language_strings = [lang for lang in found_language_strings_list if isinstance(lang, str)]
        return [lang.lower() for lang in found_language_strings]

    async def get_ch_dubs(self, meta: dict[str, Any]) -> bool:
        if not meta.get('language_checked', False):
            await languages_manager.process_desc_language(meta, tracker=self.tracker)

        found_language_strings_raw = meta.get('audio_languages')
        if not isinstance(found_language_strings_raw, list):
            return False
        found_language_strings_list = cast(list[Any], found_language_strings_raw)
        found_language_strings = [lang for lang in found_language_strings_list if isinstance(lang, str)]

        chinese_languages = {'mandarin', 'chinese', 'zh', 'zh-cn', 'zh-hans', 'zh-hant', 'putonghua', '国语', '普通话'}
        return any(lang.strip().lower() in chinese_languages for lang in found_language_strings)

    def get_codec(self, meta: dict[str, Any]) -> str:
        video_encode = str(meta.get("video_encode", "")).strip().lower()
        codec_final = str(meta.get("video_codec", "")).strip().lower()

        codec_map = {
            'divx': 'DivX',
            'xvid': 'XviD',
            'x264': 'x264',
            'h.264': 'H.264',
            'x265': 'x265',
            'h.265': 'H.265',
            'hevc': 'H.265',
        }

        for key, value in codec_map.items():
            if key in video_encode or key in codec_final:
                return value

        return 'Other'

    def get_audio_codec(self, meta: dict[str, Any]) -> str:
        priority_order = [
            'DTS-X', 'E-AC-3 JOC', 'TrueHD', 'DTS-HD', 'PCM', 'FLAC', 'DTS-ES',
            'DTS', 'E-AC-3', 'AC3', 'AAC', 'Opus', 'Vorbis', 'MP3', 'MP2'
        ]

        codec_map = {
            'DTS-X': ['DTS:X'],
            'E-AC-3 JOC': ['DD+ 5.1 Atmos', 'DD+ 7.1 Atmos'],
            'TrueHD': ['TrueHD'],
            'DTS-HD': ['DTS-HD'],
            'PCM': ['LPCM'],
            'FLAC': ['FLAC'],
            'DTS-ES': ['DTS-ES'],
            'DTS': ['DTS'],
            'E-AC-3': ['DD+'],
            'AC3': ['DD'],
            'AAC': ['AAC'],
            'Opus': ['Opus'],
            'Vorbis': ['VORBIS'],
            'MP2': ['MP2'],
            'MP3': ['MP3']
        }

        audio_description = meta.get('audio')

        if not audio_description or not isinstance(audio_description, str):
            return 'Outro'

        for codec_name in priority_order:
            search_terms = codec_map.get(codec_name, [])

            for term in search_terms:
                if term in audio_description:
                    return codec_name

        return 'Outro'

    def get_title(self, meta: dict[str, Any]) -> str:
        title_value = self.tmdb_data.get('name') or self.tmdb_data.get('title') or ''
        title = title_value if isinstance(title_value, str) else ''

        return title if title and title != meta.get('title') else ''

    async def check_image_hosts(self, meta: dict[str, Any]) -> None:
        # Rule: 2.2.1. Screenshots: They have to be saved at kshare.club, pixhost.to, ptpimg.me, img.pterclub.com, yes.ilikeshots.club, imgbox.com, s3.pterclub.com
        await self.rehost_images_manager.check_hosts(
            meta,
            self.tracker,
            url_host_mapping=self.url_host_mapping,
            img_host_index=1,
            approved_image_hosts=self.approved_image_hosts,
        )
        return

    async def get_release_desc(self, meta: dict[str, Any]) -> str:
        builder = DescriptionBuilder(self.tracker, self.config)
        desc_parts: list[str] = []

        # Custom Header
        custom_header = await builder.get_custom_header()
        desc_parts.append(custom_header)

        # Logo
        logo, logo_size = await builder.get_logo_section(meta)
        if logo and logo_size:
            if logo.endswith(".svg"):
                logo = logo.replace(".svg", ".png")
            desc_parts.append(f'[center][img={logo_size}]{logo}[/img][/center]')

        # NFO
        nfo_content = meta.get('description_nfo_content')
        if isinstance(nfo_content, str) and nfo_content:
            desc_parts.append(f"[pre]{nfo_content}[/pre]")

        # User description
        user_description = await builder.get_user_description(meta)
        desc_parts.append(user_description)

        # Disc menus screenshots header
        menu_header = await builder.menu_screenshot_header(meta)
        desc_parts.append(menu_header)

        # Disc menus screenshots
        menu_key = f'{self.tracker}_menu_images_key'
        menu_images_value = meta.get(menu_key) if menu_key in meta else meta.get('menu_images', [])
        if isinstance(menu_images_value, list) and menu_images_value:
            menu_screenshots_block = ''
            menu_images_list = cast(list[Any], menu_images_value)
            for image in menu_images_list:
                if not isinstance(image, dict):
                    continue
                image_dict = cast(dict[str, Any], image)
                raw_url = image_dict.get('raw_url')
                if isinstance(raw_url, str) and raw_url:
                    menu_screenshots_block += f"[img]{raw_url}[/img]\n"
            desc_parts.append('[center]\n' + menu_screenshots_block + '[/center]')

        # Screenshot Header
        screenshot_header = await builder.screenshot_header()
        desc_parts.append(screenshot_header)

        # Screenshots
        images_key = f'{self.tracker}_images_key'
        images_value = meta.get(images_key) if images_key in meta else meta.get('image_list', [])
        if isinstance(images_value, list) and images_value:
            screenshots_block = ''
            images_list = cast(list[Any], images_value)
            for image in images_list:
                if not isinstance(image, dict):
                    continue
                image_dict = cast(dict[str, Any], image)
                raw_url = image_dict.get('raw_url')
                if isinstance(raw_url, str) and raw_url:
                    screenshots_block += f"[img]{raw_url}[/img]\n"
            desc_parts.append('[center]\n' + screenshots_block + '[/center]')

        # Tonemapped Header
        tonemapped_header = await builder.get_tonemapped_header(meta)
        desc_parts.append(tonemapped_header)

        # Signature
        desc_parts.append(f"[align=right][url=https://github.com/Audionut/Upload-Assistant][size=1]{meta['ua_signature']}[/size][/url][/align]")

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        bbcode = BBCODE()
        description = bbcode.remove_sup(description)
        description = bbcode.remove_sub(description)
        description = bbcode.convert_to_align(description)
        description = bbcode.remove_list(description)
        description = bbcode.remove_extra_lines(description)

        if meta["debug"]:
            desc_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
            console.print(f"DEBUG: Saving final description to [yellow]{desc_file}[/yellow]")
            async with aiofiles.open(desc_file, "w", encoding="utf-8") as description_file:
                await description_file.write(description)

        return description

    def get_trailer(self, meta: dict[str, Any]) -> str:
        video_results: list[dict[str, Any]] = []
        videos = self.tmdb_data.get('videos')
        if isinstance(videos, dict):
            videos_dict = cast(dict[str, Any], videos)
            results = videos_dict.get('results')
            if isinstance(results, list):
                results_list = cast(list[Any], results)
                video_results.extend(
                    cast(dict[str, Any], result)
                    for result in results_list
                    if isinstance(result, dict)
                )

        youtube = ''

        if video_results:
            youtube_value = video_results[-1].get('key', '')
            youtube = youtube_value if isinstance(youtube_value, str) else ''

        if not youtube:
            meta_trailer = str(meta.get("youtube", ""))
            if meta_trailer:
                youtube = meta_trailer.replace('https://www.youtube.com/watch?v=', '').replace('/', '')

        return youtube

    async def get_tags(self, meta: dict[str, Any]) -> str:
        tags = ''

        genres = meta.get('genres', '')
        if genres and isinstance(genres, str):
            genre_names = [g.strip() for g in genres.split(',') if g.strip()]
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
           tags_raw = await asyncio.to_thread(cli_ui.ask_string, f'Enter the genres (in {self.tracker} format): ')
           tags = (tags_raw or "").strip()

        return tags

    def get_additional_checks(self, meta: dict[str, Any]) -> bool:
        if meta['category'] != 'MOVIE':
            console.print(f'{self.tracker}: Only feature films, short films, and live performances are permitted on {self.tracker}')
            return False

        media_type = str(meta.get("type", "")).lower()
        tag = str(meta.get("tag", "")).strip().lower()
        if media_type == "remux" and tag in ("-hdt", "-frds"):
            console.print(f"{self.tracker}: Remuxes from {meta['tag']} are not allowed on {self.tracker}")
            return False
        if media_type == "webdl" and tag == "-evo":
            console.print(f"{self.tracker}: WEB-DLs from {meta['tag']} are not allowed on {self.tracker}")
            return False

        return True

    async def search_existing(self, meta: dict[str, Any], _disctype: str) -> list[dict[str, str]]:
        dupes: list[dict[str, str]] = []

        if not self.get_additional_checks(meta):
            return []

        group_id = await self.get_groupid(meta)
        if not group_id:
            return []

        imdb = dict(meta.get("imdb_info", {})).get("imdbID", "")
        if not imdb:
            console.print(f"{self.tracker}: IMDb ID not found in metadata. Skipping search.")
            return []

        cookies = await self.load_cookies(meta)
        if not cookies:
            search_url = f'{self.base_url}/api.php?api_key={self.api_key}&action=torrent&imdbID={imdb}'
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(search_url)
                    response.raise_for_status()
                    data = response.json()
                    data_dict = cast(dict[str, Any], data) if isinstance(data, dict) else {}

                    if data_dict.get("status") == 200 and "response" in data_dict:
                        response_list_raw = data_dict.get('response')
                        response_list = cast(list[Any], response_list_raw) if isinstance(response_list_raw, list) else []
                        for item in response_list:
                            if not isinstance(item, dict):
                                continue
                            item_dict = cast(dict[str, Any], item)
                            name = item_dict.get('Name', '')
                            year = item_dict.get('Year', '')
                            resolution = item_dict.get('Resolution', '')
                            source = item_dict.get('Source', '')
                            processing = item_dict.get('Processing', '')
                            remaster = item_dict.get('RemasterTitle', '')
                            codec = item_dict.get('Codec', '')

                            formatted = f'{name} {year} {resolution} {source} {processing} {remaster} {codec}'.strip()
                            formatted = re.sub(r'\s{2,}', ' ', formatted)
                            dupes.append({"name": formatted})
                        return dupes
                    else:
                        return []
            except Exception as e:
                console.print(f'An unexpected error occurred while processing the search: {e}', markup=False)
            return []

        else:
            imdb_value = str(imdb or '')
            search_url = f'{self.base_url}/torrents.php?groupname={imdb_value.upper()}'  # using TT in imdb returns the search page instead of redirecting to the group page
            found_items: list[dict[str, Any]] = []

            try:
                async with httpx.AsyncClient(cookies=cookies, timeout=30, headers={'User-Agent': 'Upload Assistant/2.3'}) as client:
                    response = await client.get(search_url)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'html.parser')

                    torrent_table = soup.find('table', id='torrent_table')
                    if not torrent_table:
                        return []

                    for torrent_row in torrent_table.find_all('tr', class_='TableTorrent-rowTitle'):
                        title_link = torrent_row.find('a', href=re.compile(r'torrentid=\d+'))
                        if not title_link:
                            continue

                        tooltip_value = title_link.get('data-tooltip')
                        if not isinstance(tooltip_value, str):
                            continue

                        name = tooltip_value

                        size_cell = torrent_row.find('td', class_='TableTorrent-cellStatSize')
                        size = size_cell.get_text(strip=True) if size_cell else None

                        href_value = title_link.get('href')
                        href_text = href_value if isinstance(href_value, str) else ''
                        match = re.search(r'torrentid=(\d+)', href_text)
                        torrent_link = f'{self.torrent_url}{match.group(1)}' if match else None

                        dupe_entry = {
                            'name': name,
                            'size': size,
                            'link': torrent_link
                        }

                        found_items.append(dupe_entry)

                    if found_items:
                        await self.get_slots(meta, client, GPW.group_id)

                    return found_items

            except httpx.HTTPError as e:
                console.print(f'An HTTP error occurred: {e}', markup=False)
                return []
            except Exception as e:
                console.print(f'An unexpected error occurred while processing the search: {e}', markup=False)
                return []

    async def get_slots(self, meta: dict[str, Any], client: httpx.AsyncClient, group_id: str) -> None:
        url = f'{self.base_url}/torrents.php?id={group_id}'

        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            console.print(f'Error on request: {e.response.status_code} - {e.response.reason_phrase}', markup=False)
            return

        soup = BeautifulSoup(response.text, 'html.parser')

        empty_slot_rows = soup.find_all('tr', class_='TableTorrent-rowEmptySlotNote')

        for row in empty_slot_rows:
            edition_id = row.get('edition-id')
            resolution = ''

            if edition_id == '1':
                resolution = 'SD'
            elif edition_id == '3':
                resolution = '2160p'

            if not resolution:
                slot_cell = row.find('td', class_='TableTorrent-cellEmptySlotNote')
                slot_type_tag = slot_cell.find('i') if slot_cell else None
                if slot_type_tag:
                    resolution = slot_type_tag.get_text(strip=True).replace('empty slots:', '').strip()

            slot_names: list[str] = []

            i_tags = row.find_all('i')
            for tag in i_tags:
                text = tag.get_text(strip=True)
                if 'empty slots:' not in text:
                    slot_names.append(text)

            span_tags = row.find_all('span', class_='tooltipstered')
            for tag in span_tags:
                icon = tag.find('i')
                if icon:
                    slot_names.append(icon.get_text(strip=True))

            final_slots_list = sorted(set(slot_names))
            formatted_slots = [f'- {slot}' for slot in final_slots_list]
            final_slots = '\n'.join(formatted_slots)

            if final_slots:
                final_slots = final_slots.replace('Slot', '').replace('Empty slots:', '').strip()
                if resolution == meta.get('resolution'):
                    console.print(f'\n[green]Available Slots for[/green] {resolution}:')
                    console.print(f'{final_slots}\n')

    async def get_media_info(self, meta: dict[str, Any]) -> str:
        info_file_path = ''
        if meta.get('is_disc') == 'BDMV':
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/BD_SUMMARY_00.txt"
        else:
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MEDIAINFO_CLEANPATH.txt"

        if os.path.exists(info_file_path):
            try:
                async with aiofiles.open(info_file_path, encoding='utf-8') as f:
                    return await f.read()
            except Exception as e:
                console.print(f'[bold red]Error reading info file at {info_file_path}: {e}[/bold red]')
                return ''
        else:
            console.print(f'[bold red]Info file not found: {info_file_path}[/bold red]')
            return ''

    def get_edition(self, meta: dict[str, Any]) -> str:
        edition_str = str(meta.get("edition", "")).lower()
        if not edition_str:
            return ''

        edition_map = {
            "director's cut": "Director's Cut",
            'theatrical': 'Theatrical Cut',
            'extended': 'Extended',
            'uncut': 'Uncut',
            'unrated': 'Unrated',
            'imax': 'IMAX',
            'noir': 'Noir',
            'remastered': 'Remastered',
        }

        for keyword, label in edition_map.items():
            if keyword in edition_str:
                return label

        return ''

    def get_processing_other(self, meta: dict[str, Any]) -> str:
        if meta.get('type') == 'DISC':
            is_disc_type = meta.get('is_disc')

            if is_disc_type == 'BDMV':
                disctype = meta.get('disctype')
                if isinstance(disctype, str) and disctype in ['BD100', 'BD66', 'BD50', 'BD25']:
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
                dvd_size = meta.get('dvd_size')
                if isinstance(dvd_size, str) and dvd_size in ['DVD9', 'DVD5']:
                    return dvd_size
                return 'DVD9'

        return ""

    def get_screens(self, meta: dict[str, Any]) -> list[str]:
        images_value = meta.get('image_list', [])
        images_list: list[Any] = cast(list[Any], images_value) if isinstance(images_value, list) else []
        screenshot_urls: list[str] = []
        for image in images_list:
            if not isinstance(image, dict):
                continue
            image_dict = cast(dict[str, Any], image)
            raw_url = image_dict.get('raw_url')
            if isinstance(raw_url, str) and raw_url:
                screenshot_urls.append(raw_url)

        return screenshot_urls

    def get_credits(self, meta: dict[str, Any]) -> str:
        director_entries: list[str] = []

        imdb_directors = dict(meta.get("imdb_info", {})).get("directors")
        if isinstance(imdb_directors, list):
            imdb_directors_list = cast(list[Any], imdb_directors)
            director_entries.extend(name for name in imdb_directors_list if isinstance(name, str))

        tmdb_directors = meta.get('tmdb_directors')
        if isinstance(tmdb_directors, list):
            tmdb_directors_list = cast(list[Any], tmdb_directors)
            director_entries.extend(name for name in tmdb_directors_list if isinstance(name, str))

        if director_entries:
            unique_names = list(dict.fromkeys(director_entries))[:5]
            return ', '.join(unique_names)

        return 'N/A'

    def get_remaster_title(self, meta: dict[str, Any]) -> str:
        found_tags: list[str] = []

        def add_tag(tag_id: str) -> None:
            if tag_id and tag_id not in found_tags:
                found_tags.append(tag_id)

        # Collections
        distributor = str(meta.get("distributor", "")).upper()
        if distributor in ('WARNER ARCHIVE', 'WARNER ARCHIVE COLLECTION', 'WAC'):
            add_tag('warner_archive_collection')
        elif distributor in ('CRITERION', 'CRITERION COLLECTION', 'CC'):
            add_tag('the_criterion_collection')
        elif distributor in ('MASTERS OF CINEMA', 'MOC'):
            add_tag('masters_of_cinema')

        # Editions
        edition = str(meta.get("edition", "")).lower()
        if "director's cut" in edition:
            add_tag('director_s_cut')
        elif 'extended' in edition:
            add_tag('extended_edition')
        elif 'theatrical' in edition:
            add_tag('theatrical_cut')
        elif 'rifftrax' in edition:
            add_tag('rifftrax')
        elif 'uncut' in edition:
            add_tag('uncut')
        elif 'unrated' in edition:
            add_tag('unrated')

        # Audio
        if meta.get('dual_audio', False):
            add_tag('dual_audio')

        if meta.get('extras'):
            add_tag('extras')

        # Commentary
        has_commentary = meta.get('has_commentary', False) or meta.get('manual_commentary', False)

        # Ensure 'with_commentary' is last if it exists
        if has_commentary:
            add_tag('with_commentary')
            if 'with_commentary' in found_tags:
                found_tags.remove('with_commentary')
                found_tags.append('with_commentary')

        if not found_tags:
            return ""

        remaster_title_show = ' / '.join(found_tags)

        return remaster_title_show

    async def get_groupid(self, meta: dict[str, Any]) -> bool:
        search_url = f"{self.base_url}/api.php?api_key={self.api_key}&action=torrent&req=group&imdbID={meta.get('imdb_info', {}).get('imdbID')}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(search_url)
                response.raise_for_status()

        except httpx.RequestError as e:
            console.print(f'[bold red]Network error fetching groupid: {e}[/bold red]')
            return False
        except httpx.HTTPStatusError as e:
            console.print(f'[bold red]HTTP error when fetching groupid: Status {e.response.status_code}[/bold red]')
            return False

        try:
            data: dict[str, Any] = response.json()
        except Exception as e:
            console.print(f'[bold red]Error decoding JSON from groupid response: {e}[/bold red]')
            return False

        if data.get('status') == 200 and 'response' in data and 'ID' in data['response']:
            GPW.group_id = str(data["response"]["ID"])
            return True
        return False

    async def get_additional_data(self, meta: dict[str, Any]) -> dict[str, Any]:
        poster_url = ""
        while True:
            poster_url_raw = await asyncio.to_thread(cli_ui.ask_string, f"{self.tracker}: Enter the poster image URL (must be from one of {', '.join(self.approved_image_hosts)}): \n")
            poster_url = (poster_url_raw or "").strip()
            if any(host in poster_url for host in self.approved_image_hosts):
                break
            else:
                console.print("[red]Invalid host. Please use a URL from the allowed hosts.[/red]")

        data = {
            "data_source": "tmdb",
            "identifier": meta["tmdb_id"],
            "desc": self.tmdb_data.get("overview", ""),
            "image": poster_url,
            "maindesc": meta.get("overview", ""),
            "name": meta.get("title"),
            "releasetype": self._get_movie_type(meta),
            "subname": self.get_title(meta),
            "tags": await self.get_tags(meta),
            "year": meta.get("year"),
        }
        data.update(await self._get_artist_data(meta))

        return data

    async def _get_artist_data(self, meta: dict[str, Any]) -> dict[str, str]:
        directors = meta.get('imdb_info', {}).get('directors', [])
        directors_id = meta.get('imdb_info', {}).get('directors_id', [])

        if directors and directors_id:
            imdb_id = directors_id[0]
            english_name = directors[0]
            chinese_name = ''
        else:
            console.print(f'{self.tracker}: This movie is not registered in the {self.tracker} database, please enter the details of 1 director')
            imdb_id_raw = await asyncio.to_thread(cli_ui.ask_string, 'Enter Director IMDb ID (e.g., nm0000138): ')
            imdb_id = (imdb_id_raw or "").strip()
            english_name_raw = await asyncio.to_thread(cli_ui.ask_string, 'Enter Director English name: ')
            english_name = (english_name_raw or "").strip()
            chinese_name_raw = await asyncio.to_thread(cli_ui.ask_string, 'Enter Director Chinese name (optional, press Enter to skip): ')
            chinese_name = (chinese_name_raw or "").strip()

        post_data = {
            'artist_ids[]': imdb_id,
            'artists[]': english_name,
            'artists_sub[]': chinese_name,
            'importance[]': '1'
        }

        return post_data

    def _get_movie_type(self, meta: dict[str, Any]) -> str:
        movie_type = ''
        imdb_info = meta.get('imdb_info', {})
        if imdb_info:
            imdbType = imdb_info.get('type', 'movie').lower()
            if imdbType in ("movie", "tv movie", 'tvmovie', 'video'):
                runtime = int(imdb_info.get('runtime', '60'))
                movie_type = '1' if runtime >= 45 or runtime == 0 else '2'  # Feature Film/Short Film

        return movie_type

    def get_source(self, meta: dict[str, Any]) -> str:
        source_type = str(meta.get("type", "")).lower()

        if source_type == 'disc':
            is_disc = str(meta.get("is_disc", "")).upper()
            if is_disc == 'BDMV':
                return 'Blu-ray'
            elif is_disc in ('HDDVD', 'DVD'):
                return 'DVD'
            else:
                return 'Other'

        keyword_map = {
            'webdl': 'WEB',
            'webrip': 'WEB',
            'web': 'WEB',
            'remux': 'Blu-ray',
            'encode': 'Blu-ray',
            'bdrip': 'Blu-ray',
            'brrip': 'Blu-ray',
            'hdtv': 'HDTV',
            'sdtv': 'TV',
            'dvdrip': 'DVD',
            'hd-dvd': 'HD-DVD',
            'dvdscr': 'DVD',
            'pdtv': 'TV',
            'uhdtv': 'HDTV',
            'vhs': 'VHS',
            'tvrip': 'TVRip',
        }

        return keyword_map.get(source_type, 'Other')

    def get_processing(self, meta: dict[str, Any]) -> str:
        type_map = {
            'ENCODE': 'Encode',
            'REMUX': 'Remux',
            'DIY': 'DIY',
            'UNTOUCHED': 'Untouched'
        }
        release_type = str(meta.get("type", "")).strip().upper()
        return type_map.get(release_type, 'Untouched')

    def get_media_flags(self, meta: dict[str, Any]) -> dict[str, str]:
        audio = str(meta.get('audio', '')).lower()
        hdr = str(meta.get('hdr', ''))
        bit_depth = str(meta.get('bit_depth', ''))
        channels = str(meta.get('channels', ''))

        flags: dict[str, str] = {}

        # audio flags
        if 'atmos' in audio:
            flags['dolby_atmos'] = 'on'

        if 'dts:x' in audio:
            flags['dts_x'] = 'on'

        if channels == '5.1':
            flags['audio_51'] = 'on'

        if channels == '7.1':
            flags['audio_71'] = 'on'

        # video flags
        if not hdr.strip() and bit_depth == '10':
            flags['10_bit'] = 'on'

        if 'DV' in hdr:
            flags['dolby_vision'] = 'on'

            if 'HDR' in hdr:
                flags['hdr10plus' if 'HDR10+' in hdr else 'hdr10'] = 'on'

        return flags

    def get_resolution(self, meta: dict[str, Any]) -> str:
        resolution = str(meta.get("resolution", "")).lower()
        source = str(meta.get("source", "")).upper()

        if source in ["NTSC", "PAL"]:
            return source.upper()
        if resolution.lower() in ["480p", "576p", "720p", "1080i", "1080p", "2160p"]:
            return resolution.lower()
        else:
            return "Other"

    async def fetch_data(self, meta: dict[str, Any], _disctype: str) -> dict[str, Any]:
        await self.load_localized_data(meta)
        remaster_title = self.get_remaster_title(meta)
        codec = self.get_codec(meta)
        container = self.get_container(meta)

        data: dict[str, Any] = {}

        if not GPW.group_id:
            console.print(f'{self.tracker}: This movie is not registered in the database, please enter additional information.')
            data.update(await self.get_additional_data(meta))

        data.update(
            {
                "codec_other": meta.get("video_codec", "") if codec == "Other" else "",
                "codec": codec,
                "container_other": meta.get("container", "") if container == "Other" else "",
                "container": container,
                "groupid": GPW.group_id if GPW.group_id else "",
                "mediainfo[]": await self.get_media_info(meta),
                "movie_edition_information": "on" if remaster_title else "",
                "processing_other": self.get_processing_other(meta) if meta.get("type") == "DISC" else "",
                "processing": self.get_processing(meta),
                "release_desc": await self.get_release_desc(meta),
                "remaster_custom_title": "",
                "remaster_title": remaster_title,
                "remaster_year": "",
                "resolution_height": "",
                "resolution_width": "",
                "resolution": self.get_resolution(meta),
                "source_other": "",
                "source": self.get_source(meta),
                "submit": "true",
                "subtitle_type": ("2" if meta.get("hardcoded_subs", False) else "1" if meta.get("subtitle_languages", []) else "3"),
                "subtitles[]": await self.get_subtitle(meta),
            }
        )

        if await self.get_ch_dubs(meta):
            data.update({
                'chinese_dubbed': 'on'
            })

        if meta.get('sfx_subtitles', False):
            data.update({
                'special_effects_subtitles': 'on'
            })

        if meta.get('scene', False):
            data.update({
                'scene': 'on'
            })

        if meta.get('personalrelease', False):
            data.update({
                'self_rip': 'on'
            })

        data.update(self.get_media_flags(meta))

        return data

    async def upload(self, meta: dict[str, Any], disctype: str) -> bool:
        await self.common.create_torrent_for_upload(meta, self.tracker, self.source_flag)
        data = await self.fetch_data(meta, disctype)

        if not meta.get('debug', False):
            response_data = ''
            torrent_id = ''
            upload_url = f'{self.base_url}/api.php?api_key={self.api_key}&action=upload'
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

            async with aiofiles.open(torrent_path, 'rb') as torrent_file:
                torrent_bytes = await torrent_file.read()
            files = {'file_input': (f'{self.tracker}.placeholder.torrent', torrent_bytes, 'application/x-bittorrent')}

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(url=upload_url, files=files, data=data)
                    try:
                        response_data = response.json()
                    except Exception as e:
                        console.print(f"{self.tracker}: Failed to decode JSON response: {e}")
                        content_type = response.headers.get("Content-Type", "")
                        if "text/html" in content_type or "<!DOCTYPE html>" in response.text:
                            failure_path = await self.common.save_html_file(meta, self.tracker, response.text, "Failed_Upload")
                            console.print(f"{self.tracker}: HTML response saved to {failure_path}")
                        else:
                            truncated_text = (response.text[:500] + "...") if len(response.text) > 500 else response.text
                            console.print(f"{self.tracker}: Unexpected Response Text: {truncated_text}")
                        return False

                    torrent_id = str(response_data['response']['torrent_id'])
                    meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id
                    meta['tracker_status'][self.tracker]['status_message'] = 'Torrent uploaded successfully.'
                    await self.common.create_torrent_ready_to_seed(meta, self.tracker, self.source_flag, self.announce, self.torrent_url + torrent_id)
                    return True

            except httpx.TimeoutException:
                meta['tracker_status'][self.tracker]['status_message'] = 'data error: Request timed out after 10 seconds'
                return False
            except httpx.RequestError as e:
                meta['tracker_status'][self.tracker]['status_message'] = f'data error: Unable to upload. Error: {e}.\nResponse: {response_data}'
                return False
            except Exception as e:
                meta['tracker_status'][self.tracker]['status_message'] = f'data error: It may have uploaded, go check. Error: {e}.\nResponse: {response_data}'
                return False

        else:
            console.print("[cyan]GPW Request Data:")
            console.print(Redaction.redact_private_info(data))
            meta['tracker_status'][self.tracker]['status_message'] = 'Debug mode enabled, not uploading.'
            await self.common.create_torrent_for_upload(meta, f"{self.tracker}" + "_DEBUG", f"{self.tracker}" + "_DEBUG", announce_url="https://fake.tracker")
            return True
