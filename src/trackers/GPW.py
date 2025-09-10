# -*- coding: utf-8 -*-
import asyncio
import httpx
import json
import os
import platform
import re
import unicodedata
from bs4 import BeautifulSoup
from src.console import console
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
        self.banned_groups = ['']
        self.source_flag = 'GreatPosterWall'
        self.base_url = 'https://greatposterwall.com'
        self.torrent_url = 'https://greatposterwall.com/torrents.php?torrentid='
        self.announce = self.config['TRACKERS'][self.tracker]['announce_url']
        self.auth_token = None
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f"Audionut's Upload Assistant ({platform.system()} {platform.release()})"
        }, timeout=60.0)
        self.signature = "[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"

    async def load_cookies(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        if not os.path.exists(cookie_file):
            console.print(f'[bold red]Cookie file for {self.tracker} not found: {cookie_file}[/bold red]')
            return False

        self.session.cookies = await self.common.parseCookieFile(cookie_file)

    async def validate_credentials(self, meta):
        await self.load_cookies(meta)
        try:
            upload_page_url = f'{self.base_url}/upload.php'
            response = await self.session.get(upload_page_url, timeout=30.0)
            response.raise_for_status()

            if 'login.php' in str(response.url):
                console.print(f'[bold red]{self.tracker} validation failed. Cookie appears to be expired (redirected to login).[/bold red]')
                return False

            auth_match = re.search(r'name="auth" value="([^"]+)"', response.text)

            user_link = re.search(r'user\.php\?id=(\d+)', response.text)
            if user_link:
                self.user_id = user_link.group(1)
            else:
                self.user_id = ''

            if not auth_match:
                console.print(f'[bold red]{self.tracker} validation failed. Auth token not found.[/bold red]')
                console.print('[yellow]The site structure may have changed or login failed silently.[/yellow]')

                failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                with open(failure_path, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                console.print(f'[yellow]The server response was saved to {failure_path} for analysis.[/yellow]')
                return False

            self.auth_token = auth_match.group(1)
            return True

        except httpx.TimeoutException:
            console.print(f'[bold red]Error in {self.tracker}: Timeout while trying to validate credentials.[/bold red]')
            return False
        except httpx.HTTPStatusError as e:
            console.print(f'[bold red]HTTP error validating credentials for {self.tracker}: Status {e.response.status_code}.[/bold red]')
            return False
        except httpx.RequestError as e:
            console.print(f'[bold red]Network error validating credentials for {self.tracker}: {e.__class__.__name__}.[/bold red]')
            return False

    def load_localized_data(self, meta):
        localized_data_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/tmdb_localized_data.json"

        if os.path.isfile(localized_data_file):
            with open(localized_data_file, "r", encoding="utf-8") as f:
                self.tmdb_data = json.load(f)
        else:
            self.tmdb_data = {}

    async def ch_tmdb_data(self, meta):
        brazil_data_in_meta = self.tmdb_data.get('zh-cn', {}).get('main')
        if brazil_data_in_meta:
            return brazil_data_in_meta

        data = await get_tmdb_localized_data(meta, data_type='main', language='zh-cn', append_to_response='credits')
        self.load_localized_data(meta)

        return data

    async def get_container(self, meta):
        container = None
        if meta['is_disc'] == 'BDMV':
            container = 'm2ts'
        elif meta['is_disc'] == 'DVD':
            container = 'VOB IFO'
        else:
            ext = os.path.splitext(meta['filelist'][0])[1]
            containermap = {
                '.mkv': 'MKV',
                '.mp4': 'MP4'
            }
            container = containermap.get(ext, 'Outro')
        return container

    async def get_subtitle(self, meta):
        if not meta.get('subtitle_languages'):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        found_language_strings = meta.get('subtitle_languages', [])

        if found_language_strings:
            return [lang.lower() for lang in found_language_strings]
        else:
            return []

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
        tmdb_data = await self.ch_tmdb_data(meta)

        title = tmdb_data.get('name') or tmdb_data.get('title') or ''

        return title if title and title != meta.get('title') else ''

    async def get_release_desc(self, meta):
        description = []

        base_desc = ''
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        if os.path.exists(base_desc_path):
            with open(base_desc_path, 'r', encoding='utf-8') as f:
                base_desc = f.read()
                if base_desc:
                    description.append(base_desc)

        # Screenshots
        # Rule: 2.2.1. Screenshots: They have to be saved at kshare.club, pixhost.to, ptpimg.me, img.pterclub.com, yes.ilikeshots.club, imgbox.com, s3.pterclub.com
        approved_image_hosts = ['kshare', 'pixhost', 'ptpimg', 'pterclub', 'ilikeshots', 'imgbox']
        url_host_mapping = {
            'kshare.club': 'kshare',
            'pixhost.to': 'pixhost',
            'imgbox.com': 'imgbox',
            'ptpimg.me': 'ptpimg',
            'img.pterclub.com': 'pterclub',
            'yes.ilikeshots.club': 'ilikeshots',
        }
        await check_hosts(meta, self.tracker, url_host_mapping=url_host_mapping, img_host_index=1, approved_image_hosts=approved_image_hosts)

        if f'{self.tracker}_images_key' in meta:
            images = meta[f'{self.tracker}_images_key']
        else:
            images = meta['image_list']
        if images:
            screenshots_block = '[center]\n'
            for i, image in enumerate(images, start=1):
                img_url = image['img_url']
                web_url = image['web_url']
                screenshots_block += f'[url={web_url}][img=350]{img_url}[/img][/url] '
                if i % 2 == 0:
                    screenshots_block += '\n'
            screenshots_block += '\n[/center]'
            description.append(screenshots_block)

        custom_description_header = self.config['DEFAULT'].get('custom_description_header', '')
        if custom_description_header:
            description.append(custom_description_header + '\n')

        if self.signature:
            description.append(self.signature)

        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        with open(final_desc_path, 'w', encoding='utf-8') as descfile:
            from src.bbcode import BBCODE
            bbcode = BBCODE()
            desc = '\n\n'.join(filter(None, description))
            desc = desc.replace('[sup]', '').replace('[/sup]', '')
            desc = desc.replace('[sub]', '').replace('[/sub]', '')
            desc = bbcode.remove_spoiler(desc)
            desc = bbcode.convert_code_to_quote(desc)
            desc = re.sub(r'\[(right|center|left)\]', lambda m: f"[align={m.group(1)}]", desc)
            desc = re.sub(r'\[/(right|center|left)\]', "[/align]", desc)
            final_description = re.sub(r'\n{3,}', '\n\n', desc)
            descfile.write(final_description)

        return final_description

    async def get_trailer(self, meta):
        tmdb_data = await self.ch_tmdb_data(meta)
        video_results = tmdb_data.get('videos', {}).get('results', [])

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
        # Handle if genres is a string like "War, History, Thriller"
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
            tags = await asyncio.to_thread(input, f'Enter the genres (in {self.tracker} format): ')

        return tags

    async def search_existing(self, meta, disctype):
        group_id = await self.get_groupid(meta)
        if not group_id:
            return []

        search_url = f'{self.base_url}/torrents.php?id={group_id}'
        found_items = []
        upload_resolution = meta.get('resolution')

        try:
            response = await self.session.get(search_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            torrent_table = soup.find('table', id='torrent_details')
            if not torrent_table:
                return []

            for torrent_row in torrent_table.find_all('tr', id=re.compile(r'^torrent\d+$')):
                title_link = torrent_row.find('a', class_='TableTorrent-titleTitle')
                if not title_link:
                    continue

                description_text = ' '.join(title_link.get_text(strip=True).split())

                if upload_resolution and upload_resolution not in description_text:
                    continue

                torrent_id = torrent_row.get('id', '').replace('torrent', '')

                filelist_url = f'{self.base_url}/torrents.php?action=filelist&torrentid={torrent_id}'
                filelist_response = await self.session.get(filelist_url)
                filelist_response.raise_for_status()
                filelist_soup = BeautifulSoup(filelist_response.text, 'html.parser')

                is_existing_torrent_a_disc = any(keyword in description_text.lower() for keyword in ['bd25', 'bd50', 'bd66', 'bd100', 'dvd5', 'dvd9', 'm2ts'])

                if is_existing_torrent_a_disc:
                    root_folder_item = filelist_soup.find('li', class_='TorrentDetailfileListItem-fileListItem', variant='root')
                    if root_folder_item:
                        folder_name_tag = root_folder_item.find('a', class_='TorrentDetailfileList-fileName')
                        if folder_name_tag:
                            folder_name = folder_name_tag.get_text(strip=True)
                            found_items.append(folder_name)
                else:
                    file_table = filelist_soup.find('table', class_='filelist_table')
                    if not file_table:
                        file_list_container = filelist_soup.find('div', class_='TorrentDetail-row is-fileList is-block')
                        if file_list_container:
                            for file_item in file_list_container.find_all('div', class_='TorrentDetailfileList-fileName'):
                                filename = file_item.get_text(strip=True)
                                if filename:
                                    found_items.append(filename)
                                    break
                    else:
                        for row in file_table.find_all('tr'):
                            if 'colhead' not in row.get('class', []):
                                cell = row.find('td')
                                if cell:
                                    filename = cell.get_text(strip=True)
                                    if filename:
                                        found_items.append(filename)
                                        break

        except Exception as e:
            print(f'Ocorreu um erro inesperado ao processar a busca: {e}')
            return []

        return found_items

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
        REMMASTER_TAGS = {
            # Collections
            'masters_of_cinema': 'Masters of Cinema',
            'the_criterion_collection': 'The Criterion Collection',
            'warner_archive_collection': 'Warner Archive Collection',
            # Editions
            'director_s_cut': "Director's Cut",
            'extended_edition': 'Extended Edition',
            'rifftrax': 'Rifftrax',
            'theatrical_cut': 'Theatrical Cut',
            'uncut': 'Uncut',
            'unrated': 'Unrated',
            # Features
            '2d_3d_edition': '2D/3D Edition',
            '3d_anaglyph': '3D Anaglyph',
            '3d_full_sbs': '3D Full SBS',
            '3d_half_ou': '3D Half OU',
            '3d_half_sbs': '3D Half SBS',
            '2_disc_set': '2-Disc Set',
            '2_in_1': '2in1',
            '4k_restoration': '4K Restoration',
            '4k_remaster': '4K Remaster',
            'remaster': 'Remaster',
            'extras': 'Extras',
            'with_commentary': 'With Commentary',
            # Other
            'dual_audio': 'Dual Audio',
            'english_dub': 'English Dub',
        }

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

        display_titles = [REMMASTER_TAGS.get(tag, tag) for tag in found_tags]
        remaster_title = ' / '.join(display_titles)

        return remaster_title, remaster_title_show

    async def get_groupid(self, meta):
        url = f'{self.base_url}/upload.php'
        params = {
            'action': 'movie_info',
            'imdbid': meta.get('imdb_info', {}).get('imdbID')
        }

        try:
            response = await self.session.get(url, params=params)
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

        if data.get('status', '') == 'success':
            return False
        elif data.get('error', {}).get('Dupe') is True:
            groupid = data.get('error', {}).get('GroupID')
            return str(groupid)

        return None

    async def get_additional_data(self, meta):
        tmdb_data = await self.ch_tmdb_data(meta)
        data = {
            'desc': tmdb_data.get('overview', ''),
            'image': meta.get('poster'),
            'imdb': meta.get('imdb_info', {}).get('imdbID'),
            'maindesc': meta.get('overview', ''),
            'name': meta.get('title'),
            'releasetype': self._get_movie_type(meta),
            'subname': await self.get_title(meta),
            'tags': await self.get_tags(meta),
            'year': meta.get('year'),
        }
        data.update(self._get_artist_data(meta))

        return data

    def _get_artist_data(self, meta) -> Dict[str, str]:
        console.print('--- This film is not registered, please enter details of 1 artist ---')

        imdb_id = input('Enter IMDb ID (e.g., nm0000138): ')
        english_name = input('Enter English name: ')
        chinese_name = input('Enter Chinese name (optional, press Enter to skip): ')

        roles = {
            '1': 'Director',
            '2': 'Writer',
            '3': 'Producer',
            '4': 'Composer',
            '5': 'Cinematographer',
            '6': 'Actor'
        }

        console.print('\nSelect the artist\'s role:')
        for key, value in roles.items():
            console.print(f'  {key}: {value}')

        importance_choice = ''
        while importance_choice not in roles:
            importance_choice = input('Enter the number for the role (1-6): ')
            if importance_choice not in roles:
                console.print('Invalid selection. Please choose a number between 1 and 6.')

        post_data = {
            'artist_ids[]': imdb_id,
            'artists[]': english_name,
            'artists_sub[]': chinese_name,
            'importance[]': importance_choice
        }

        return post_data

    def _get_movie_type(self, meta):
        movie_type = ''
        imdb_info = meta.get('imdb_info', {})
        if imdb_info:
            imdbType = imdb_info.get('type', 'movie').lower()
            if imdbType in ("movie", "tv movie", 'tvmovie'):
                if int(imdb_info.get('runtime', '60')) >= 45 or int(imdb_info.get('runtime', '60')) == 0:
                    movie_type = "Feature Film"
                else:
                    movie_type = "Short Film"

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

    async def fetch_data(self, meta, disctype):
        self.load_localized_data(meta)
        await self.validate_credentials(meta)
        remaster_title, remaster_title_show = await self.get_remaster_title(meta)
        codec = await self.get_codec(meta)
        groupid = await self.get_groupid(meta)

        data = {}

        if not groupid:
            data.update(await self.get_additional_data(meta))

        data.update({
            'audio_51': 'on' if meta.get('channels', '') == '5.1' else 'off',
            'audio_71': 'on' if meta.get('channels', '') == '7.1' else 'off',
            'auth': self.auth_token,
            'codec_other': meta.get('video_codec', '') if codec == 'Other' else '',
            'codec': codec,
            'container': await self.get_container(meta),
            'groupid': groupid if groupid else '',
            'mediainfo[]': await self.get_media_info(meta),
            'movie_edition_information': 'on' if remaster_title else 'off',
            'processing_other': await self.get_processing_other(meta) if meta.get('type') == 'DISC' else '',
            'processing': await self.get_processing(meta),
            'release_desc': await self.get_release_desc(meta),
            'remaster_custom_title': '',
            'remaster_title_show': remaster_title_show,
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

        if 'atmos' in meta.get('audio', '').lower():
            data.update({
                'dolby_atmos': 'on',
            })

        return data

    async def upload(self, meta, disctype):
        await self.load_cookies(meta)
        await self.common.edit_torrent(meta, self.tracker, self.source_flag)
        data = await self.fetch_data(meta, disctype)
        status_message = ''

        if not meta.get('debug', False):
            torrent_id = ''
            upload_url = f'{self.base_url}/upload.php'
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

            with open(torrent_path, 'rb') as torrent_file:
                files = {'file_input': (f'{self.tracker}.placeholder.torrent', torrent_file, 'application/x-bittorrent')}

                response = await self.session.post(upload_url, data=data, files=files, timeout=120)

                # Try to find the torrent id from the response HTML
                match = re.search(r'torrentid=(\d+)', response.text)
                if match:
                    torrent_id = match.group(1)
                    status_message = 'Uploaded successfully.'
                    meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id

                else:
                    status_message = 'It may have uploaded, go check '
                    response_save_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                    with open(response_save_path, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    console.print(f'Upload failed, HTML response was saved to: {response_save_path}')
                    meta['skipping'] = f'{self.tracker}'
                    return

            await self.common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.announce, self.torrent_url + torrent_id)

        else:
            console.print(data)
            status_message = 'Debug mode enabled, not uploading.'

        meta['tracker_status'][self.tracker]['status_message'] = status_message
