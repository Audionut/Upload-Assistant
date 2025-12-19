# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import aiofiles
import httpx
import json
import os
import re
import unicodedata
from bs4 import BeautifulSoup
from src.bbcode import BBCODE
from src.console import console
from src.get_desc import DescriptionBuilder
from src.languages import process_desc_language
from src.rehostimages import check_hosts
from src.tmdb import get_tmdb_localized_data
from src.trackers.COMMON import COMMON
from typing import Dict


class GPW():
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'GPW'
        self.source_flag = 'GreatPosterWall'
        self.base_url = 'https://greatposterwall.com'
        self.torrent_url = f'{self.base_url}/torrents.php?torrentid='
        self.announce = self.config['TRACKERS'][self.tracker]['announce_url']
        self.api_key = self.config['TRACKERS'][self.tracker]['api_key']
        self.auth_token = None
        self.banned_groups = [
            'ALT', 'aXXo', 'BATWEB', 'BlackTV', 'BitsTV', 'BMDRu', 'BRrip', 'CM8', 'CrEwSaDe', 'CTFOH', 'CTRLHD',
            'DDHDTV', 'DNL', 'DreamHD', 'ENTHD', 'FaNGDiNG0', 'FGT', 'FRDS', 'HD2DVD', 'HDTime',
            'HDT', 'Huawei', 'GPTHD', 'ION10', 'iPlanet', 'KiNGDOM', 'Leffe', 'Mp4Ba', 'mHD', 'MiniHD', 'mSD', 'MOMOWEB',
            'nHD', 'nikt0', 'NSBC', 'nSD', 'NhaNc3', 'NukeHD', 'OFT', 'PRODJi', 'RARBG', 'RDN', 'SANTi', 'SeeHD', 'SeeWEB',
            'SM737', 'SonyHD', 'STUTTERSHIT', 'TAGWEB', 'ViSION', 'VXT', 'WAF', 'x0r', 'Xiaomi', 'YIFY',
            ['EVO', 'web-dl Only']
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

    async def load_cookies(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        if not os.path.exists(cookie_file):
            return False

        return await self.common.parseCookieFile(cookie_file)

    async def load_localized_data(self, meta):
        localized_data_file = f'{meta["base_dir"]}/tmp/{meta["uuid"]}/tmdb_localized_data.json'
        main_ch_data = {}
        data = {}

        if os.path.isfile(localized_data_file):
            try:
                async with aiofiles.open(localized_data_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)
            except json.JSONDecodeError:
                print(f'Warning: Could not decode JSON from {localized_data_file}')
                data = {}
            except Exception as e:
                print(f'Error reading file {localized_data_file}: {e}')
                data = {}

        main_ch_data = data.get('zh-cn', {}).get('main')

        if not main_ch_data:
            main_ch_data = await get_tmdb_localized_data(
                meta,
                data_type='main',
                language='zh-cn',
                append_to_response='credits'
            )

        self.tmdb_data = main_ch_data

        return

    async def get_container(self, meta):
        container = meta.get('container', '')
        if container == 'm2ts':
            return container
        elif container == 'vob':
            return 'VOB IFO'
        elif container in ['avi', 'mpg', 'mp4', 'mkv']:
            return container.upper()

        return 'Other'

    async def get_subtitle(self, meta):
        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        found_language_strings = meta.get('subtitle_languages', [])

        if found_language_strings:
            return [lang.lower() for lang in found_language_strings]
        else:
            return []

    async def get_ch_dubs(self, meta):
        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        found_language_strings = meta.get('audio_languages', [])

        chinese_languages = {'mandarin', 'chinese', 'zh', 'zh-cn', 'zh-hans', 'zh-hant', 'putonghua', '国语', '普通话'}
        for lang in found_language_strings:
            if lang.strip().lower() in chinese_languages:
                return True
        return False

    async def get_codec(self, meta):
        video_encode = meta.get('video_encode', '').strip().lower()
        codec_final = meta.get('video_codec', '').strip().lower()

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

    async def get_audio_codec(self, meta):
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

    async def get_title(self, meta):
        title = self.tmdb_data.get('name') or self.tmdb_data.get('title') or ''

        return title if title and title != meta.get('title') else ''

    async def check_image_hosts(self, meta):
        # Rule: 2.2.1. Screenshots: They have to be saved at kshare.club, pixhost.to, ptpimg.me, img.pterclub.com, yes.ilikeshots.club, imgbox.com, s3.pterclub.com
        await check_hosts(meta, self.tracker, url_host_mapping=self.url_host_mapping, img_host_index=1, approved_image_hosts=self.approved_image_hosts)
        return

    async def get_release_desc(self, meta):
        builder = DescriptionBuilder(self.config)
        desc_parts = []

        # Custom Header
        desc_parts.append(await builder.get_custom_header(self.tracker))

        # Logo
        logo, logo_size = await builder.get_logo_section(meta, self.tracker)
        if logo and logo_size:
            desc_parts.append(f'[center][img={logo_size}]{logo}[/img][/center]')

        # NFO
        if meta.get('description_nfo_content', ''):
            desc_parts.append(f"[pre]{meta.get('description_nfo_content')}[/pre]")

        # User description
        desc_parts.append(await builder.get_user_description(meta))

        # Screenshot Header
        desc_parts.append(await builder.screenshot_header(self.tracker))

        # Screenshots
        if f'{self.tracker}_images_key' in meta:
            images = meta[f'{self.tracker}_images_key']
        else:
            images = meta['image_list']
        if images:
            screenshots_block = ''
            for image in images:
                screenshots_block += f"[img]{image['raw_url']}[/img]\n"
            desc_parts.append('[center]\n' + screenshots_block + '[/center]')

        # Tonemapped Header
        desc_parts.append(await builder.get_tonemapped_header(meta, self.tracker))

        # Signature
        desc_parts.append(f"[align=right][url=https://github.com/Audionut/Upload-Assistant][size=1]{meta['ua_signature']}[/size][/url][/align]")

        description = '\n\n'.join(part for part in desc_parts if part.strip())

        bbcode = BBCODE()
        description = bbcode.remove_sup(description)
        description = bbcode.remove_sub(description)
        description = bbcode.convert_to_align(description)
        description = bbcode.remove_list(description)
        description = bbcode.remove_extra_lines(description)

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as description_file:
            await description_file.write(description)

        return description

    async def get_trailer(self, meta):
        video_results = self.tmdb_data.get('videos', {}).get('results', [])

        youtube = ''

        if video_results:
            youtube = video_results[-1].get('key', '')

        if not youtube:
            meta_trailer = meta.get('youtube', '')
            if meta_trailer:
                youtube = meta_trailer.replace('https://www.youtube.com/watch?v=', '').replace('/', '')

        return youtube

    async def get_tags(self, meta):
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
            tags = await self.common.async_input(prompt=f'Enter the genres (in {self.tracker} format): ')

        return tags

    async def search_existing(self, meta, disctype):
        if meta['category'] != 'MOVIE':
            console.print(f'{self.tracker}: Only feature films, short films, and live performances are permitted on {self.tracker}')
            meta['skipping'] = f'{self.tracker}'
            return

        group_id = await self.get_groupid(meta)
        if not group_id:
            return []

        imdb = meta.get("imdb_info", {}).get("imdbID")

        cookies = await self.load_cookies(meta)
        if not cookies:
            search_url = f'{self.base_url}/api.php?api_key={self.api_key}&action=torrent&imdbID={imdb}'
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(search_url)
                    response.raise_for_status()
                    data = response.json()

                    if data.get('status') == 200 and 'response' in data:
                        results = []
                        for item in data['response']:
                            name = item.get('Name', '')
                            year = item.get('Year', '')
                            resolution = item.get('Resolution', '')
                            source = item.get('Source', '')
                            processing = item.get('Processing', '')
                            remaster = item.get('RemasterTitle', '')
                            codec = item.get('Codec', '')

                            formatted = f'{name} {year} {resolution} {source} {processing} {remaster} {codec}'.strip()
                            formatted = re.sub(r'\s{2,}', ' ', formatted)
                            results.append(formatted)
                        return results
                    else:
                        return []
            except Exception as e:
                print(f'An unexpected error occurred while processing the search: {e}')
            return []

        else:
            search_url = f'{self.base_url}/torrents.php?groupname={imdb.upper()}'  # using TT in imdb returns the search page instead of redirecting to the group page
            found_items = []

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
                        if not title_link or not title_link.get('data-tooltip'):
                            continue

                        name = title_link['data-tooltip']

                        size_cell = torrent_row.find('td', class_='TableTorrent-cellStatSize')
                        size = size_cell.get_text(strip=True) if size_cell else None

                        match = re.search(r'torrentid=(\d+)', title_link['href'])
                        torrent_link = f'{self.torrent_url}{match.group(1)}' if match else None

                        dupe_entry = {
                            'name': name,
                            'size': size,
                            'link': torrent_link
                        }

                        found_items.append(dupe_entry)

                    if found_items:
                        await self.get_slots(meta, client, group_id)

                    return found_items

            except httpx.HTTPError as e:
                print(f'An HTTP error occurred: {e}')
                return []
            except Exception as e:
                print(f'An unexpected error occurred while processing the search: {e}')
                return []

    async def get_slots(self, meta, client, group_id):
        url = f'{self.base_url}/torrents.php?id={group_id}'

        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            print(f'Error on request: {e.response.status_code} - {e.response.reason_phrase}')
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
                slot_type_tag = row.find('td', class_='TableTorrent-cellEmptySlotNote').find('i')
                if slot_type_tag:
                    resolution = slot_type_tag.get_text(strip=True).replace('empty slots:', '').strip()

            slot_names = []

            i_tags = row.find_all('i')
            for tag in i_tags:
                text = tag.get_text(strip=True)
                if 'empty slots:' not in text:
                    slot_names.append(text)

            span_tags = row.find_all('span', class_='tooltipstered')
            for tag in span_tags:
                slot_names.append(tag.find('i').get_text(strip=True))

            final_slots_list = sorted(list(set(slot_names)))
            formatted_slots = [f'- {slot}' for slot in final_slots_list]
            final_slots = '\n'.join(formatted_slots)

            if final_slots:
                final_slots = final_slots.replace('Slot', '').replace('Empty slots:', '').strip()
                if resolution == meta.get('resolution'):
                    console.print(f'\n[green]Available Slots for[/green] {resolution}:')
                    console.print(f'{final_slots}\n')

    async def get_media_info(self, meta):
        info_file_path = ''
        if meta.get('is_disc') == 'BDMV':
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/BD_SUMMARY_00.txt"
        else:
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MEDIAINFO_CLEANPATH.txt"

        if os.path.exists(info_file_path):
            try:
                with open(info_file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                console.print(f'[bold red]Error reading info file at {info_file_path}: {e}[/bold red]')
                return ''
        else:
            console.print(f'[bold red]Info file not found: {info_file_path}[/bold red]')
            return ''

    async def get_edition(self, meta):
        edition_str = meta.get('edition', '').lower()
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

    async def get_processing_other(self, meta):
        if meta.get('type') == 'DISC':
            is_disc_type = meta.get('is_disc')

            if is_disc_type == 'BDMV':
                disctype = meta.get('disctype')
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
                dvd_size = meta.get('dvd_size')
                if dvd_size in ['DVD9', 'DVD5']:
                    return dvd_size
                return 'DVD9'

    async def get_screens(self, meta):
        screenshot_urls = [
            image.get('raw_url')
            for image in meta.get('image_list', [])
            if image.get('raw_url')
        ]

        return screenshot_urls

    async def get_credits(self, meta):
        director = (meta.get('imdb_info', {}).get('directors') or []) + (meta.get('tmdb_directors') or [])
        if director:
            unique_names = list(dict.fromkeys(director))[:5]
            return ', '.join(unique_names)
        else:
            return 'N/A'

    async def get_remaster_title(self, meta):
        found_tags = []

        def add_tag(tag_id):
            if tag_id and tag_id not in found_tags:
                found_tags.append(tag_id)

        # Collections
        distributor = meta.get('distributor', '').upper()
        if distributor in ('WARNER ARCHIVE', 'WARNER ARCHIVE COLLECTION', 'WAC'):
            add_tag('warner_archive_collection')
        elif distributor in ('CRITERION', 'CRITERION COLLECTION', 'CC'):
            add_tag('the_criterion_collection')
        elif distributor in ('MASTERS OF CINEMA', 'MOC'):
            add_tag('masters_of_cinema')

        # Editions
        edition = meta.get('edition', '').lower()
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
            return '', ''

        remaster_title_show = ' / '.join(found_tags)

        return remaster_title_show

    async def get_groupid(self, meta):
        search_url = f"{self.base_url}/api.php?api_key={self.api_key}&action=torrent&req=group&imdbID={meta.get('imdb_info', {}).get('imdbID')}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(search_url)
                response.raise_for_status()

        except httpx.RequestError as e:
            console.print(f'[bold red]Network error fetching groupid: {e}[/bold red]')
            return None
        except httpx.HTTPStatusError as e:
            console.print(f'[bold red]HTTP error when fetching groupid: Status {e.response.status_code}[/bold red]')
            return None

        try:
            data = response.json()
        except Exception as e:
            console.print(f'[bold red]Error decoding JSON from groupid response: {e}[/bold red]')
            return None

        if data.get('status') == 200 and 'response' in data and 'ID' in data['response']:
            return str(data['response']['ID'])
        return None

    async def get_additional_data(self, meta):
        poster_url = ''
        while True:
            poster_url = await self.common.async_input(prompt=f"{self.tracker}: Enter the poster image URL (must be from one of {', '.join(self.approved_image_hosts)}): \n")
            if any(host in poster_url for host in self.approved_image_hosts):
                break
            else:
                console.print('[red]Invalid host. Please use a URL from the allowed hosts.[/red]')

        data = {
            'desc': self.tmdb_data.get('overview', ''),
            'image': poster_url,
            'imdb': meta.get('imdb_info', {}).get('imdbID'),
            'maindesc': meta.get('overview', ''),
            'name': meta.get('title'),
            'releasetype': self._get_movie_type(meta),
            'subname': await self.get_title(meta),
            'tags': await self.get_tags(meta),
            'year': meta.get('year'),
        }
        data.update(await self._get_artist_data(meta))

        return data

    async def _get_artist_data(self, meta) -> Dict[str, str]:
        directors = meta.get('imdb_info', {}).get('directors', [])
        directors_id = meta.get('imdb_info', {}).get('directors_id', [])

        if directors and directors_id:
            imdb_id = directors_id[0]
            english_name = directors[0]
            chinese_name = ''
        else:
            console.print(f'{self.tracker}: This movie is not registered in the {self.tracker} database, please enter the details of 1 director')
            imdb_id = await self.common.async_input(prompt='Enter Director IMDb ID (e.g., nm0000138): ')
            english_name = await self.common.async_input(prompt='Enter Director English name: ')
            chinese_name = await self.common.async_input(prompt='Enter Director Chinese name (optional, press Enter to skip): ')

        post_data = {
            'artist_ids[]': imdb_id,
            'artists[]': english_name,
            'artists_sub[]': chinese_name,
            'importance[]': '1'
        }

        return post_data

    def _get_movie_type(self, meta):
        movie_type = ''
        imdb_info = meta.get('imdb_info', {})
        if imdb_info:
            imdbType = imdb_info.get('type', 'movie').lower()
            if imdbType in ("movie", "tv movie", 'tvmovie', 'video'):
                if int(imdb_info.get('runtime', '60')) >= 45 or int(imdb_info.get('runtime', '60')) == 0:
                    movie_type = '1'  # Feature Film
                else:
                    movie_type = '2'  # Short Film

        return movie_type

    async def get_source(self, meta):
        source_type = meta.get('type', '').lower()

        if source_type == 'disc':
            is_disc = meta.get('is_disc', '').upper()
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

    async def get_processing(self, meta):
        type_map = {
            'ENCODE': 'Encode',
            'REMUX': 'Remux',
            'DIY': 'DIY',
            'UNTOUCHED': 'Untouched'
        }
        release_type = meta.get('type', '').strip().upper()
        return type_map.get(release_type, 'Untouched')

    def get_media_flags(self, meta):
        audio = meta.get('audio', '').lower()
        hdr = meta.get('hdr', '')
        bit_depth = meta.get('bit_depth', '')
        channels = meta.get('channels', '')

        flags = {}

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

    async def fetch_data(self, meta, disctype):
        await self.load_localized_data(meta)
        remaster_title = await self.get_remaster_title(meta)
        codec = await self.get_codec(meta)
        container = await self.get_container(meta)
        groupid = await self.get_groupid(meta)

        data = {}

        if not groupid:
            console.print(f'{self.tracker}: This movie is not registered in the database, please enter additional information.')
            data.update(await self.get_additional_data(meta))

        data.update({
            'codec_other': meta.get('video_codec', '') if codec == 'Other' else '',
            'codec': codec,
            'container_other': meta.get('container', '') if container == 'Other' else '',
            'container': container,
            'groupid': groupid if groupid else '',
            'mediainfo[]': await self.get_media_info(meta),
            'movie_edition_information': 'on' if remaster_title else '',
            'processing_other': await self.get_processing_other(meta) if meta.get('type') == 'DISC' else '',
            'processing': await self.get_processing(meta),
            'release_desc': await self.get_release_desc(meta),
            'remaster_custom_title': '',
            'remaster_title': remaster_title,
            'remaster_year': '',
            'resolution_height': '',
            'resolution_width': '',
            'resolution': meta.get('resolution'),
            'source_other': '',
            'source': await self.get_source(meta),
            'submit': 'true',
            'subtitle_type': ('2' if meta.get('hardcoded-subs', False) else '1' if meta.get('subtitle_languages', []) else '3'),
            'subtitles[]': await self.get_subtitle(meta),
        })

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

    async def upload(self, meta, disctype):
        await self.common.edit_torrent(meta, self.tracker, self.source_flag)
        data = await self.fetch_data(meta, disctype)
        status_message = ''

        if not meta.get('debug', False):
            response_data = ''
            torrent_id = ''
            upload_url = f'{self.base_url}/api.php?api_key={self.api_key}&action=upload'
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

            with open(torrent_path, 'rb') as torrent_file:
                files = {'file_input': (f'{self.tracker}.placeholder.torrent', torrent_file, 'application/x-bittorrent')}

                try:
                    async with httpx.AsyncClient(timeout=30) as client:
                        response = await client.post(url=upload_url, files=files, data=data)
                        response_data = response.json()

                        torrent_id = str(response_data['response']['torrent_id'])
                        meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id
                        status_message = 'Torrent uploaded successfully.'

                except httpx.TimeoutException:
                    meta['tracker_status'][self.tracker]['status_message'] = 'data error: Request timed out after 10 seconds'
                except httpx.RequestError as e:
                    meta['tracker_status'][self.tracker]['status_message'] = f'data error: Unable to upload. Error: {e}.\nResponse: {response_data}'
                except Exception as e:
                    meta['tracker_status'][self.tracker]['status_message'] = f'data error: It may have uploaded, go check. Error: {e}.\nResponse: {response_data}'
                    return

            await self.common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.announce, self.torrent_url + torrent_id)

        else:
            console.print(data)
            status_message = 'Debug mode enabled, not uploading.'

        meta['tracker_status'][self.tracker]['status_message'] = status_message
