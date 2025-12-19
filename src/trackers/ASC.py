# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import aiofiles
import asyncio
import json
import httpx
import os
import platform
import re
from bs4 import BeautifulSoup
from datetime import datetime
from pymediainfo import MediaInfo
from src.console import console
from src.cookie_auth import CookieValidator, CookieAuthUploader
from src.languages import process_desc_language
from src.tmdb import get_tmdb_localized_data
from src.trackers.COMMON import COMMON


class ASC:
    def __init__(self, config):
        self.config = config
        self.common = COMMON(config)
        self.cookie_validator = CookieValidator(config)
        self.cookie_auth_uploader = CookieAuthUploader(config)
        self.tracker = 'ASC'
        self.source_flag = 'ASC'
        self.banned_groups = []
        self.base_url = 'https://cliente.amigos-share.club'
        self.torrent_url = 'https://cliente.amigos-share.club/torrents-details.php?id='
        self.requests_url = f'{self.base_url}/pedidos.php'
        self.layout = self.config['TRACKERS'][self.tracker].get('custom_layout', '2')
        self.session = httpx.AsyncClient(headers={
            'User-Agent': f'Upload Assistant ({platform.system()} {platform.release()})'
        }, timeout=60.0)

        self.language_map = {
            'bg': '15', 'da': '12',
            'de': '3', 'en': '1',
            'es': '6', 'fi': '14',
            'fr': '2', 'hi': '23',
            'it': '4', 'ja': '5',
            'ko': '20', 'nl': '17',
            'no': '16', 'pl': '19',
            'pt': '8', 'ru': '7',
            'sv': '13', 'th': '21',
            'tr': '25', 'zh': '10',
        }
        self.anime_language_map = {
            'de': '3', 'en': '4',
            'es': '1', 'ja': '8',
            'ko': '11', 'pt': '5',
            'ru': '2', 'zh': '9',
        }

    async def validate_credentials(self, meta):
        self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        return await self.cookie_validator.cookie_validation(
            meta=meta,
            tracker=self.tracker,
            test_url=f'{self.base_url}/gerador.php',
            error_text='Esqueceu sua senha',
        )

    async def load_localized_data(self, meta):
        localized_data_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/tmdb_localized_data.json"
        tmdb_data = {}
        self.main_tmdb_data = {}
        self.season_tmdb_data = {}
        self.episode_tmdb_data = {}

        try:
            async with aiofiles.open(localized_data_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                try:
                    tmdb_data = json.loads(content)
                except json.JSONDecodeError as e:
                    console.print(f"[red]Warning: JSON decode error in {localized_data_file}: {e}. Continuing with empty data.[/red]")
                    tmdb_data = {}
        except (FileNotFoundError, json.JSONDecodeError):
            pass

        local_results = {
            'main': tmdb_data.get('pt-BR', {}).get('main'),
            'season': tmdb_data.get('pt-BR', {}).get('season'),
            'episode': tmdb_data.get('pt-BR', {}).get('episode')
        }

        tasks_to_run = []

        if local_results['main']:
            self.main_tmdb_data = local_results['main']
        else:
            tasks_to_run.append(
                ('main', get_tmdb_localized_data(meta, data_type='main', language='pt-BR', append_to_response='credits,videos,content_ratings'))
            )

        if meta.get('category') == 'TV':
            if local_results['season']:
                self.season_tmdb_data = local_results['season']
            else:
                tasks_to_run.append(
                    ('season', get_tmdb_localized_data(meta, data_type='season', language='pt-BR', append_to_response=''))
                )

        if meta.get('category') == 'TV' and not meta.get('tv_pack', False):
            if local_results['episode']:
                self.episode_tmdb_data = local_results['episode']
            else:
                tasks_to_run.append(
                    ('episode', get_tmdb_localized_data(meta, data_type='episode', language='pt-BR', append_to_response=''))
                )

        if tasks_to_run:
            data_types, coroutines = zip(*tasks_to_run)

            try:
                api_results = await asyncio.gather(*coroutines)

                for data_type, result_data in zip(data_types, api_results, strict=True):
                    if result_data:  # Only assign if result_data is not None
                        if data_type == 'main':
                            self.main_tmdb_data = result_data
                        elif data_type == 'season':
                            self.season_tmdb_data = result_data
                        elif data_type == 'episode':
                            self.episode_tmdb_data = result_data
            except Exception as e:
                console.print(f"[red]Error loading TMDB data: {e}[/red]")
                # Ensure we have at least empty dicts to prevent KeyErrors
                if not self.main_tmdb_data:
                    self.main_tmdb_data = {}
                if not self.season_tmdb_data:
                    self.season_tmdb_data = {}
                if not self.episode_tmdb_data:
                    self.episode_tmdb_data = {}

    async def get_container(self, meta):
        if meta['is_disc'] == 'BDMV':
            return '5'
        elif meta['is_disc'] == 'DVD':
            return '15'

        try:
            general_track = next(t for t in meta['mediainfo']['media']['track'] if t['@type'] == 'General')
            file_extension = general_track.get('FileExtension', '').lower()
            if file_extension == 'mkv':
                return '6'
            elif file_extension == 'mp4':
                return '8'
        except (StopIteration, AttributeError, TypeError):
            return None
        return None

    async def get_type(self, meta):
        bd_disc_map = {'BD25': '40', 'BD50': '41', 'BD66': '42', 'BD100': '43'}
        standard_map = {'ENCODE': '9', 'REMUX': '39', 'WEBDL': '23', 'WEBRIP': '38', 'BDRIP': '8', 'DVDRIP': '3'}
        dvd_map = {'DVD5': '45', 'DVD9': '46'}

        if meta['type'] == 'DISC':
            if meta['is_disc'] == 'HDDVD':
                return 15

            if meta['is_disc'] == 'DVD':
                dvd_size = meta['dvd_size']
                type_id = dvd_map[dvd_size]
                if type_id:
                    return type_id

            disctype = meta['disctype']
            if disctype in bd_disc_map:
                return bd_disc_map[disctype]

            try:
                size_in_gb = meta['bdinfo']['size']
            except (KeyError, IndexError, TypeError):
                size_in_gb = 0

            if size_in_gb > 66:
                return '43'  # BD100
            elif size_in_gb > 50:
                return '42'  # BD66
            elif size_in_gb > 25:
                return '41'  # BD50
            else:
                return '40'  # BD25
        else:
            return standard_map.get(meta['type'], '0')

    async def get_languages(self, meta):
        if meta.get('anime'):
            if meta['category'] == 'MOVIE':
                type_ = '116'
            if meta['category'] == 'TV':
                type_ = '118'

            anime_language = self.anime_language_map.get(meta.get('original_language', '').lower(), '6')

            if await self.get_audio(meta) in ('2', '3', '4'):
                lang = '8'
            else:
                lang = self.language_map.get(meta.get('original_language', '').lower(), '11')

            return {
                'type': type_,
                'idioma': anime_language,
                'lang': lang
            }

    async def get_audio(self, meta):
        subtitles = '1'
        dual_audio = '2'
        dubbed = '3'
        national = '4'
        original = '7'

        portuguese_languages = {'portuguese', 'português', 'pt'}

        has_pt_subs = (await self.get_subtitle(meta)) == 'Embutida'

        audio_languages = {lang.lower() for lang in meta.get('audio_languages', [])}
        has_pt_audio = any(lang in portuguese_languages for lang in audio_languages)

        original_lang = meta.get('original_language', '').lower()
        is_original_pt = original_lang in portuguese_languages

        if has_pt_audio:
            if is_original_pt:
                return national
            elif len(audio_languages - portuguese_languages) > 0:
                return dual_audio
            else:
                return dubbed
        elif has_pt_subs:
            return subtitles
        else:
            return original

    async def get_subtitle(self, meta):
        portuguese_languages = {'portuguese', 'português', 'pt'}

        found_languages = {lang.lower() for lang in meta.get('subtitle_languages', [])}

        if any(lang in portuguese_languages for lang in found_languages):
            return 'Embutida'
        return 'S_legenda'

    async def get_resolution(self, meta):
        if meta.get('is_disc') == 'BDMV':
            resolution_str = meta.get('resolution', '')
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

        return {
            'width': width,
            'height': height
        }

    async def get_video_codec(self, meta):
        codec_video_map = {
            'MPEG-4': '31', 'AV1': '29', 'AVC': '30', 'DivX': '9',
            'H264': '17', 'H265': '18', 'HEVC': '27', 'M4V': '20',
            'MPEG-1': '10', 'MPEG-2': '11', 'RMVB': '12', 'VC-1': '21',
            'VP6': '22', 'VP9': '23', 'WMV': '13', 'XviD': '15'
        }

        codec_video = None
        video_encode_raw = meta.get('video_encode')

        if video_encode_raw and isinstance(video_encode_raw, str):
            video_encode_clean = video_encode_raw.strip().lower()
            if '264' in video_encode_clean:
                codec_video = 'H264'
            elif '265' in video_encode_clean:
                codec_video = 'HEVC'

        if not codec_video:
            codec_video = meta.get('video_codec')

        codec_id = codec_video_map.get(codec_video, '16')

        is_hdr = bool(meta.get('hdr'))

        if is_hdr:
            if codec_video in ('HEVC', 'H265'):
                return '28'
            if codec_video in ('AVC', 'H264'):
                return '32'

        return codec_id

    async def get_audio_codec(self, meta):
        audio_type = (meta['audio'] or '').upper()

        codec_map = {
            'ATMOS': '43',
            'DTS:X': '25',
            'DTS-HD MA': '24',
            'DTS-HD': '23',
            'TRUEHD': '29',
            'DD+': '26',
            'DD': '11',
            'DTS': '12',
            'FLAC': '13',
            'LPCM': '21',
            'PCM': '28',
            'AAC': '10',
            'OPUS': '27',
            'MPEG': '17'
        }

        for key, code in codec_map.items():
            if key in audio_type:
                return code

        return '20'

    async def get_title(self, meta):
        name = meta['title']
        base_name = name

        if meta['category'] == 'TV':
            tv_title_ptbr = self.main_tmdb_data.get('name')
            if tv_title_ptbr and tv_title_ptbr.lower() != name.lower():
                base_name = f"{tv_title_ptbr} ({name})"

            return f"{base_name} - {meta.get('season', '')}{meta.get('episode', '')}"

        else:
            movie_title_ptbr = self.main_tmdb_data.get('title')
            if movie_title_ptbr and movie_title_ptbr.lower() != name.lower():
                base_name = f"{movie_title_ptbr} ({name})"

            return f"{base_name}"

    async def build_description(self, meta):
        user_layout = await self.fetch_layout_data(meta)
        fileinfo_dump = await self.media_info(meta)

        if not user_layout:
            return '[center]Erro: Não foi possível carregar o layout da descrição.[/center]'

        layout_image = {k: v for k, v in user_layout.items() if k.startswith('BARRINHA_')}
        description_parts = ['[center]']

        async def append_section(key: str, content: str):
            if content and (img := layout_image.get(key)):
                description_parts.append(f'\n{await self.format_image(img)}')
                description_parts.append(f'\n{content}\n')

        # Title
        for i in range(1, 4):
            description_parts.append(await self.format_image(layout_image.get(f'BARRINHA_CUSTOM_T_{i}')))
        description_parts.append(f"\n{await self.format_image(layout_image.get('BARRINHA_APRESENTA'))}\n")
        description_parts.append(f"\n[size=3]{await self.get_title(meta)}[/size]\n")

        # Poster
        poster_path = (self.season_tmdb_data or {}).get('poster_path') or (self.main_tmdb_data or {}).get('poster_path') or meta.get('tmdb_poster')
        poster = f'https://image.tmdb.org/t/p/w500{poster_path}' if poster_path else ''
        await append_section('BARRINHA_CAPA', await self.format_image(poster))

        # Overview
        overview = (self.season_tmdb_data or {}).get('overview') or (self.main_tmdb_data or {}).get('overview')
        await append_section('BARRINHA_SINOPSE', overview)

        # Episode
        if meta['category'] == 'TV' and self.episode_tmdb_data:
            episode_name = self.episode_tmdb_data.get('name')
            episode_overview = self.episode_tmdb_data.get('overview')
            still_path = self.episode_tmdb_data.get('still_path')

            if episode_name and episode_overview and still_path:
                still_url = f'https://image.tmdb.org/t/p/w300{still_path}'
                description_parts.append(f'\n[size=4][b]Episódio:[/b] {episode_name}[/size]\n')
                description_parts.append(f'\n{await self.format_image(still_url)}\n\n{episode_overview}\n')

        # Technical Sheet
        if self.main_tmdb_data:
            runtime = (self.episode_tmdb_data or {}).get('runtime') or self.main_tmdb_data.get('runtime') or meta.get('runtime')
            formatted_runtime = None
            if runtime:
                h, m = divmod(runtime, 60)
                formatted_runtime = f"{h} hora{'s' if h > 1 else ''} e {m:02d} minutos" if h > 0 else f"{m:02d} minutos"

            release_date = (self.episode_tmdb_data or {}).get('air_date') or (self.season_tmdb_data or {}).get('air_date') if meta['category'] != 'MOVIE' else self.main_tmdb_data.get('release_date')

            sheet_items = [
                f'Duração: {formatted_runtime}' if formatted_runtime else None,
                f"País de Origem: {', '.join(c['name'] for c in self.main_tmdb_data.get('production_countries', []))}" if self.main_tmdb_data.get('production_countries') else None,
                f"Gêneros: {', '.join(g['name'] for g in self.main_tmdb_data.get('genres', []))}" if self.main_tmdb_data.get('genres') else None,
                f'Data de Lançamento: {await self.format_date(release_date)}' if release_date else None,
                f"Site: [url={self.main_tmdb_data.get('homepage')}]Clique aqui[/url]" if self.main_tmdb_data.get('homepage') else None
            ]
            await append_section('BARRINHA_FICHA_TECNICA', '\n'.join(filter(None, sheet_items)))

        # Production Companies
        if self.main_tmdb_data and self.main_tmdb_data.get('production_companies'):
            prod_parts = ['[size=4][b]Produtoras[/b][/size]']
            for p in self.main_tmdb_data.get('production_companies', []):
                logo_path = p.get('logo_path')
                logo = await self.format_image(f'https://image.tmdb.org/t/p/w45{logo_path}') if logo_path else ''

                prod_parts.append(f"{logo}[size=2] - [b]{p.get('name', '')}[/b][/size]" if logo else f"[size=2][b]{p.get('name', '')}[/b][/size]")
            description_parts.append('\n' + '\n'.join(prod_parts) + '\n')

        # Cast
        if meta['category'] == 'MOVIE':
            cast_data = ((self.main_tmdb_data or {}).get('credits') or {}).get('cast', [])
        elif meta.get('tv_pack'):
            cast_data = ((self.season_tmdb_data or {}).get('credits') or {}).get('cast', [])
        else:
            cast_data = ((self.episode_tmdb_data or {}).get('credits') or {}).get('cast', [])
        await append_section('BARRINHA_ELENCO', await self.build_cast_bbcode(cast_data))

        # Seasons
        if meta['category'] == 'TV' and self.main_tmdb_data and self.main_tmdb_data.get('seasons'):
            seasons_content = []
            for seasons in self.main_tmdb_data.get('seasons', []):
                season_name = seasons.get('name', f"Temporada {seasons.get('season_number')}").strip()
                poster_temp = await self.format_image(f"https://image.tmdb.org/t/p/w185{seasons.get('poster_path')}") if seasons.get('poster_path') else ''
                overview_temp = f"\n\nSinopse:\n{seasons.get('overview')}" if seasons.get('overview') else ''

                inner_content_parts = []
                air_date = seasons.get('air_date')
                if air_date:
                    inner_content_parts.append(f'Data: {await self.format_date(air_date)}')

                episode_count = seasons.get('episode_count')
                if episode_count is not None:
                    inner_content_parts.append(f'Episódios: {episode_count}')

                inner_content_parts.append(poster_temp)
                inner_content_parts.append(overview_temp)

                inner_content = '\n'.join(inner_content_parts)
                seasons_content.append(f'\n[spoiler={season_name}]{inner_content}[/spoiler]\n')
            await append_section('BARRINHA_EPISODIOS', ''.join(seasons_content))

        # Ratings
        ratings_list = user_layout.get('Ratings', [])
        if not ratings_list:
            if imdb_rating := meta.get('imdb_info', {}).get('rating'):
                ratings_list.append({'Source': 'Internet Movie Database', 'Value': f'{imdb_rating}/10'})
        if self.main_tmdb_data and (tmdb_rating := self.main_tmdb_data.get('vote_average')):
            if not any(r.get('Source') == 'TMDb' for r in ratings_list):
                ratings_list.append({'Source': 'TMDb', 'Value': f'{tmdb_rating:.1f}/10'})

        criticas_key = 'BARRINHA_INFORMACOES' if meta['category'] == 'MOVIE' and 'BARRINHA_INFORMACOES' in layout_image else 'BARRINHA_CRITICAS'
        await append_section(criticas_key, await self.build_ratings_bbcode(meta, ratings_list))

        # MediaInfo/BDinfo
        if fileinfo_dump:
            description_parts.append(f'\n[spoiler=Informações do Arquivo]\n[left][font=Courier New]{fileinfo_dump}[/font][/left][/spoiler]\n')

        # Custom Bar
        for i in range(1, 4):
            description_parts.append(await self.format_image(layout_image.get(f'BARRINHA_CUSTOM_B_{i}')))
        description_parts.append('[/center]')

        # External description
        desc = ''
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        if os.path.exists(base_desc_path):
            with open(base_desc_path, 'r', encoding='utf-8') as f:
                desc = f.read().strip()
                desc = desc.replace('[user]', '').replace('[/user]', '')
                desc = desc.replace('[align=left]', '').replace('[/align]', '')
                desc = desc.replace('[align=right]', '').replace('[/align]', '')
                desc = desc.replace('[alert]', '').replace('[/alert]', '')
                desc = desc.replace('[note]', '').replace('[/note]', '')
                desc = desc.replace('[h1]', '[u][b]').replace('[/h1]', '[/b][/u]')
                desc = desc.replace('[h2]', '[u][b]').replace('[/h2]', '[/b][/u]')
                desc = desc.replace('[h3]', '[u][b]').replace('[/h3]', '[/b][/u]')
                desc = re.sub(r'(\[img=\d+)]', '[img]', desc, flags=re.IGNORECASE)
                description_parts.append(desc)

        custom_description_header = self.config['DEFAULT'].get('custom_description_header', '')
        if custom_description_header:
            description_parts.append(custom_description_header + '\n')

        description_parts.append(f"[center][url=https://github.com/Audionut/Upload-Assistant]Upload realizado via {meta['ua_name']} {meta['current_version']}[/url][/center]")

        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        with open(final_desc_path, 'w', encoding='utf-8') as descfile:
            final_description = '\n'.join(filter(None, description_parts))
            descfile.write(final_description)

        return final_description

    async def get_trailer(self, meta):
        video_results = self.main_tmdb_data.get('videos', {}).get('results', [])
        youtube_code = video_results[-1].get('key', '') if video_results else ''
        if youtube_code:
            youtube = f'http://www.youtube.com/watch?v={youtube_code}'
        else:
            youtube = meta.get('youtube') or ''

        return youtube

    async def get_tags(self, meta):
        tags = ', '.join(
            g.get('name', '')
            for g in self.main_tmdb_data.get('genres', [])
            if isinstance(g.get('name'), str) and g.get('name').strip()
        )

        if not tags:
            tags = meta.get('genre') or await self.common.async_input(prompt=f'Digite os gêneros (no formato do {self.tracker}): ')

        return tags

    async def _fetch_file_info(self, torrent_id, torrent_link, size):
        '''
        Helper function to fetch file info for a single release in parallel.
        '''
        file_page_url = f'{self.base_url}/torrents-arquivos.php?id={torrent_id}'
        filename = 'N/A'

        try:
            file_page_response = await self.session.get(file_page_url, timeout=15)
            file_page_response.raise_for_status()
            file_page_soup = BeautifulSoup(file_page_response.text, 'html.parser')
            file_li_tag = file_page_soup.find('li', class_='list-group-item')

            if file_li_tag and file_li_tag.contents:
                filename = file_li_tag.contents[0].strip()

        except Exception as e:
            console.print(f'[bold red]Falha ao obter nome do arquivo para ID {torrent_id}: {e}[/bold red]')

        return {
            'name': filename,
            'size': size,
            'link': torrent_link
        }

    async def search_existing(self, meta, disctype):
        self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)

        found_items = []
        if meta.get('anime'):
            await self.load_localized_data(meta)
            search_name = await self.get_title(meta)
            search_query = search_name.replace(' ', '+')
            search_url = f'{self.base_url}/torrents-search.php?search={search_query}'

        elif meta['category'] == 'MOVIE':
            search_url = f"{self.base_url}/busca-filmes.php?search=&imdb={meta['imdb_info']['imdbID']}"

        elif meta['category'] == 'TV':
            search_url = f"{self.base_url}/busca-series.php?search={meta.get('season', '')}{meta.get('episode', '')}&imdb={meta['imdb_info']['imdbID']}"

        else:
            return found_items

        try:
            response = await self.session.get(search_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            releases = soup.find_all('li', class_='list-group-item dark-gray')
        except Exception as e:
            console.print(f'[bold red]Falha ao acessar a página de busca do ASC: {e}[/bold red]')
            return found_items

        if not releases:
            return found_items

        name_search_tasks = []

        for release in releases:
            details_link_tag = release.find('a', href=lambda href: href and 'torrents-details.php?id=' in href)
            torrent_link = details_link_tag.get('href', '') if details_link_tag else ''
            size_tag = release.find('span', text=lambda t: t and ('GB' in t.upper() or 'MB' in t.upper()), class_='badge-info')
            size = size_tag.get_text(strip=True).strip() if size_tag else ''

            try:
                badges = release.find_all('span', class_='badge')
                disc_types = ['BD25', 'BD50', 'BD66', 'BD100', 'DVD5', 'DVD9']
                is_disc = any(badge.text.strip().upper() in disc_types for badge in badges)

                if is_disc:
                    name, year, resolution, disk_type, video_codec, audio_codec = meta['title'], 'N/A', 'N/A', 'N/A', 'N/A', 'N/A'
                    video_codec_terms = ['MPEG-4', 'AV1', 'AVC', 'H264', 'H265', 'HEVC', 'MPEG-1', 'MPEG-2', 'VC-1', 'VP6', 'VP9']
                    audio_codec_terms = ['DTS', 'AC3', 'DDP', 'E-AC-3', 'TRUEHD', 'ATMOS', 'LPCM', 'AAC', 'FLAC']

                    for badge in badges:
                        badge_text = badge.text.strip()
                        badge_text_upper = badge_text.upper()

                        if badge_text.isdigit() and len(badge_text) == 4:
                            year = badge_text
                        elif badge_text_upper in ['4K', '2160P', '1080P', '720P', '480P']:
                            resolution = '2160p' if badge_text_upper == '4K' else badge_text
                        elif any(term in badge_text_upper for term in video_codec_terms):
                            video_codec = badge_text
                        elif any(term in badge_text_upper for term in audio_codec_terms):
                            audio_codec = badge_text
                        elif any(term in badge_text_upper for term in disc_types):
                            disk_type = badge_text

                    name = f'{name} {year} {resolution} {disk_type} {video_codec} {audio_codec}'
                    dupe_entry = {
                        'name': name,
                        'size': size,
                        'link': torrent_link
                    }

                    found_items.append(dupe_entry)

                else:
                    if not details_link_tag:
                        continue

                    torrent_id = details_link_tag['href'].split('id=')[-1]
                    name_search_tasks.append(self._fetch_file_info(torrent_id, torrent_link, size))

            except Exception as e:
                console.print(f'[bold red]Falha ao processar um release da lista: {e}[/bold red]')
                continue

        if name_search_tasks:
            parallel_results = await asyncio.gather(*name_search_tasks)
            found_items.extend(parallel_results)

        return found_items

    async def get_upload_url(self, meta):
        if meta.get('anime'):
            return f'{self.base_url}/enviar-anime.php'
        elif meta['category'] == 'MOVIE':
            return f'{self.base_url}/enviar-filme.php'
        else:
            return f'{self.base_url}/enviar-series.php'

    async def format_image(self, url):
        return f'[img]{url}[/img]' if url else ''

    async def format_date(self, date_str):
        if not date_str or date_str == 'N/A':
            return 'N/A'
        for fmt in ('%Y-%m-%d', '%d %b %Y'):
            try:
                return datetime.strptime(str(date_str), fmt).strftime('%d/%m/%Y')
            except (ValueError, TypeError):
                continue
        return str(date_str)

    async def media_info(self, meta):
        if meta.get('is_disc') == 'BDMV':
            summary_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if os.path.exists(summary_path):
                with open(summary_path, 'r', encoding='utf-8') as f:
                    return f.read()
        if not meta.get('is_disc'):
            video_file = meta['filelist'][0]
            template_path = os.path.abspath(f"{meta['base_dir']}/data/templates/MEDIAINFO.txt")
            if os.path.exists(template_path):
                mi_output = MediaInfo.parse(
                    video_file,
                    output='STRING',
                    full=False,
                    mediainfo_options={'inform': f'file://{template_path}'}
                )
                return str(mi_output).replace('\r', '')

        return None

    async def fetch_layout_data(self, meta):
        url = f'{self.base_url}/search.php'

        async def _fetch(payload):
            try:
                response = await self.session.post(url, data=payload, timeout=20)
                response.raise_for_status()
                return response.json().get('ASC')
            except Exception:
                return None

        primary_payload = {'imdb': meta['imdb_info']['imdbID'], 'layout': self.layout}
        layout_data = await _fetch(primary_payload)
        if layout_data:
            return layout_data

        # Fallback
        fallback_payload = {'imdb': 'tt0013442', 'layout': self.layout}
        return await _fetch(fallback_payload)

    async def build_ratings_bbcode(self, meta, ratings_list):
        if not ratings_list:
            return ''

        ratings_map = {
            'Internet Movie Database': '[img]https://i.postimg.cc/Pr8Gv4RQ/IMDB.png[/img]',
            'Rotten Tomatoes': '[img]https://i.postimg.cc/rppL76qC/rotten.png[/img]',
            'Metacritic': '[img]https://i.postimg.cc/SKkH5pNg/Metacritic45x45.png[/img]',
            'TMDb': '[img]https://i.postimg.cc/T13yyzyY/tmdb.png[/img]'
        }
        parts = []
        for rating in ratings_list:
            source = rating.get('Source')
            value = rating.get('Value', '').strip()
            img_tag = ratings_map.get(source)
            if not img_tag:
                continue

            if source == 'Internet Movie Database':
                parts.append(f"\n[url={meta.get('imdb_info', {}).get('imdb_url', '')}]{img_tag}[/url]\n[b]{value}[/b]\n")
            elif source == 'TMDb':
                parts.append(f"[url=https://www.themoviedb.org/{meta['category'].lower()}/{meta['tmdb']}]{img_tag}[/url]\n[b]{value}[/b]\n")
            else:
                parts.append(f"{img_tag}\n[b]{value}[/b]\n")
        return "\n".join(parts)

    async def build_cast_bbcode(self, cast_list):
        if not cast_list:
            return ''

        parts = []
        for person in cast_list[:10]:
            profile_path = person.get('profile_path')
            profile_url = f'https://image.tmdb.org/t/p/w45{profile_path}' if profile_path else 'https://i.imgur.com/eCCCtFA.png'
            tmdb_url = f"https://www.themoviedb.org/person/{person.get('id')}?language=pt-BR"
            img_tag = await self.format_image(profile_url)
            character_info = f"({person.get('name', '')}) como {person.get('character', '')}"
            parts.append(f'[url={tmdb_url}]{img_tag}[/url]\n[size=2][b]{character_info}[/b][/size]\n')
        return ''.join(parts)

    async def get_requests(self, meta):
        if not self.config['DEFAULT'].get('search_requests', False) and not meta.get('search_requests', False):
            return False
        else:
            self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
            try:
                category = meta['category']
                if meta.get('anime'):
                    if category == 'TV':
                        category = 118
                    if category == 'MOVIE':
                        category = 116
                else:
                    if category == 'TV':
                        category = 120
                    if category == 'MOVIE':
                        category = 119

                query = meta['title']
                search_url = f'{self.requests_url}?search={query}&category={category}'

                response = await self.session.get(search_url)
                response.raise_for_status()
                response_results_text = response.text

                soup = BeautifulSoup(response_results_text, 'html.parser')

                request_rows = soup.select('.table-responsive table tr')

                results = []
                for row in request_rows:
                    all_tds = row.find_all('td')
                    if not all_tds or len(all_tds) < 6:
                        continue

                    info_cell = all_tds[1]
                    link_element = info_cell.select_one('a[href*="pedidos.php?action=ver"]')
                    if not link_element:
                        continue

                    name = link_element.text.strip()
                    link = link_element.get('href')

                    reward_td = all_tds[4]
                    reward = reward_td.text.strip()

                    results.append({
                        'Name': name,
                        'Reward': reward,
                        'Link': link,
                    })

                if results:
                    message = f'\n{self.tracker}: [bold yellow]Seu upload pode atender o(s) seguinte(s) pedido(s), confira:[/bold yellow]\n\n'
                    for r in results:
                        message += f"[bold green]Nome:[/bold green] {r['Name']}\n"
                        message += f"[bold green]Recompensa:[/bold green] {r['Reward']}\n"
                        message += f"[bold green]Link:[/bold green] {self.base_url}/{r['Link']}\n\n"
                    console.print(message)

                return results

            except Exception as e:
                console.print(f'[bold red]Ocorreu um erro ao buscar pedido(s) no {self.tracker}: {e}[/bold red]')
                import traceback
                console.print(traceback.format_exc())
                return []

    async def get_data(self, meta):
        await self.load_localized_data(meta)
        if not meta.get('language_checked', False):
            await process_desc_language(meta, desc=None, tracker=self.tracker)
        resolution = await self.get_resolution(meta)

        data = {
            'ano': str(meta['year']),
            'audio': await self.get_audio(meta),
            'capa': f"https://image.tmdb.org/t/p/w500{self.main_tmdb_data.get('poster_path') or meta.get('tmdb_poster')}",
            'codecaudio': await self.get_audio_codec(meta),
            'codecvideo': await self.get_video_codec(meta),
            'descr': await self.build_description(meta),
            'extencao': await self.get_container(meta),
            'genre': await self.get_tags(meta),
            'imdb': meta['imdb_info']['imdbID'],
            'altura': resolution['height'],
            'largura': resolution['width'],
            'lang': self.language_map.get(meta.get('original_language', '').lower(), '11'),
            'layout': self.layout,
            'legenda': await self.get_subtitle(meta),
            'name': await self.get_title(meta),
            'qualidade': await self.get_type(meta),
            'takeupload': 'yes',
            'tresd': '1' if meta.get('3d') else '2',
            'tube': await self.get_trailer(meta),
        }

        if meta.get('anime'):
            anime_info = await self.get_languages(meta)
            data.update({
                'idioma': anime_info['idioma'],
                'lang': anime_info['lang'],
                'type': anime_info['type'],
            })

        # Screenshots
        for i, img in enumerate(meta.get('image_list', [])[:4]):
            data[f'screens{i+1}'] = img.get('raw_url')

        return data

    async def upload(self, meta, disctype):
        self.session.cookies = await self.cookie_validator.load_session_cookies(meta, self.tracker)
        data = await self.get_data(meta)
        upload_url = await self.get_upload_url(meta)

        await self.cookie_auth_uploader.handle_upload(
            meta=meta,
            tracker=self.tracker,
            source_flag=self.source_flag,
            torrent_url=self.torrent_url,
            data=data,
            torrent_field_name='torrent',
            upload_cookies=self.session.cookies,
            upload_url=upload_url,
            id_pattern=r'torrents-details\.php\?id=(\d+)',
            success_text="torrents-details.php?id=",
        )

        # Approval
        should_approve = await self.get_approval(meta)
        if should_approve:
            await self.auto_approval(meta)

        # Internal
        if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
            if meta['tag'] != '' and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                await self.set_internal_flag(meta)

        return

    async def auto_approval(self, meta):
        if meta.get('debug', False):
            console.print(
                f'{self.tracker}: Debug mode, skipping automatic approval.'
            )
        else:
            torrent_id = meta['tracker_status'][self.tracker]['torrent_id']
            try:
                approval_url = f'{self.base_url}/uploader_app.php?id={torrent_id}'
                approval_response = await self.session.get(approval_url, timeout=30)
                approval_response.raise_for_status()
            except Exception as e:
                console.print(f'{self.tracker}: [bold red]Error during automatic approval attempt: {e}[/bold red]')

    async def get_approval(self, meta):
        if not self.config['TRACKERS'][self.tracker].get('uploader_status', False):
            return False

        if meta.get('modq', False):
            console.print(f'{self.tracker}: Sending to the moderation queue.')
            return False

        return True

    async def set_internal_flag(self, meta):
        if meta.get('debug', False):
            console.print(
                f'{self.tracker}: [bold yellow]Debug mode, skipping setting internal flag.[/bold yellow]'
            )
        else:
            data = {
                'id': meta['tracker_status'][self.tracker]['torrent_id'],
                'internal': 'yes'
            }

            try:
                response = await self.session.post(
                    f"{self.base_url}/torrents-edit.php?action=doedit",
                    data=data
                )
                response.raise_for_status()

            except Exception as e:
                console.print(f'{self.tracker}: [bold red]Error setting internal flag: {e}[/bold red]')
                return
