# -*- coding: utf-8 -*-
import asyncio
import httpx
import os
import re
import requests
from .COMMON import COMMON
from bs4 import BeautifulSoup
from datetime import datetime
from pymediainfo import MediaInfo
from src.console import console
from src.exceptions import UploadException
from src.languages import process_desc_language


class ASC(COMMON):
    def __init__(self, config):
        super().__init__(config)
        self.tracker = 'ASC'
        self.source_flag = 'ASC'
        self.banned_groups = [""]
        self.base_url = "https://cliente.amigos-share.club"
        self.layout = self.config['TRACKERS'][self.tracker].get('custom_layout', '2')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        })
        self.signature = "[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"

    def assign_media_properties(self, meta):
        self.imdb_id = meta['imdb_info']['imdbID']
        self.tmdb_id = meta['tmdb']
        self.category = meta['category']
        self.season = meta.get('season', '')
        self.episode = meta.get('episode', '')

    async def get_title(self, meta):
        self.assign_media_properties(meta)
        tmdb_ptbr_data = await self.main_tmdb_data(meta)
        name = meta['title']
        base_name = name

        if self.category == 'TV':
            tv_title_ptbr = tmdb_ptbr_data['name']
            if tv_title_ptbr and tv_title_ptbr.lower() != name.lower():
                base_name = f"{tv_title_ptbr} ({name})"

            return f"{base_name} - {self.season}{self.episode}"

        else:
            movie_title_ptbr = tmdb_ptbr_data['title']
            if movie_title_ptbr and movie_title_ptbr.lower() != name.lower():
                base_name = f"{movie_title_ptbr} ({name})"

            return f"{base_name}"

    async def _determine_language_properties(self, meta):
        subtitled = '1'
        dual_audio = '2'
        dubbed = '3'
        original_dub = '4'

        no_subs = '0'
        embedded_subs = '1'

        if not meta.get('audio_languages') or not meta.get('subtitle_languages'):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        portuguese_languages = ['Portuguese', 'Português']
        audio_languages = set(meta.get('audio_languages', []))
        has_pt_subtitle = any(lang in meta.get('subtitle_languages', []) for lang in portuguese_languages)
        has_pt_audio = any(lang in meta.get('audio_languages', []) for lang in portuguese_languages)
        is_pt_original_language = meta.get('original_language', '') == 'pt'

        if not has_pt_audio and not has_pt_subtitle:
            if not meta.get('unattended'):
                console.print('[bold red]ASC requer pelo menos uma faixa de áudio ou legenda em português.[/bold red]')
            meta['skipping'] = "ASC"
            return None, None

        subtitle = embedded_subs if has_pt_subtitle else no_subs

        audio = None
        if has_pt_audio:
            if is_pt_original_language:
                audio = original_dub
            elif len(audio_languages) > 1:
                audio = dual_audio
            else:
                audio = dubbed
        elif has_pt_subtitle:
            audio = subtitled

        return subtitle, audio

    def get_res_id(self, meta):
        if meta['is_disc'] == 'BDMV':
            res_map = {'2160p': ('3840', '2160'), '1080p': ('1920', '1080'), '1080i': ('1920', '1080'), '720p': ('1280', '720')}
            return res_map[meta['resolution']]

        video_track = next((t for t in meta['mediainfo']['media']['track'] if t['@type'] == 'Video'), None)
        if video_track:
            return video_track['Width'], video_track['Height']
        return None, None

    def get_type_id(self, meta):
        qualidade_map_disc = {"BD25": "40", "BD50": "41", "BD66": "42", "BD100": "43"}
        qualidade_map_files = {"ENCODE": "9", "REMUX": "39", "WEBDL": "23", "WEBRIP": "38", "BDRIP": "8", "DVDRIP": "3"}
        qualidade_map_dvd = {"DVD5": "45", "DVD9": "46"}

        if meta['type'] == 'DISC':
            if meta['is_disc'] == 'DVD':
                dvd_size = meta['dvd_size']
                type_id = qualidade_map_dvd[dvd_size]
                if type_id:
                    return type_id

            disctype = meta['disctype']
            if disctype in qualidade_map_disc:
                return qualidade_map_disc[disctype]

            bdinfo_size_gib = meta.get('bdinfo', {}).get('size')
            if bdinfo_size_gib:
                size_bytes = bdinfo_size_gib * 1_073_741_824
                if size_bytes > 66_000_000_000:
                    return "43"  # BD100
                elif size_bytes > 50_000_000_000:
                    return "42"  # BD66
                elif size_bytes > 25_000_000_000:
                    return "41"  # BD50
                else:
                    return "40"  # BD25
        else:
            return qualidade_map_files.get(meta['type'], "0")

    def get_container(self, meta):
        if meta['is_disc'] == "BDMV":
            return "5"
        elif meta['is_disc'] == "DVD":
            return "15"

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

    def get_audio_codec(self, meta):
        audio_type = (meta['audio'] or '').upper()

        codec_map = {
            "ATMOS": "43",
            "DTS:X": "25",
            "DTS-HD MA": "24",
            "DTS-HD": "23",
            "TRUEHD": "29",
            "DD+": "26",
            "DD": "11",
            "DTS": "12",
            "FLAC": "13",
            "LPCM": "21",
            "PCM": "28",
            "AAC": "10",
            "OPUS": "27",
            "MPEG": "17"
        }

        for key, code in codec_map.items():
            if key in audio_type:
                return code

        return "20"

    def get_video_codec(self, meta):
        codec_video_map = {
            "MPEG-4": "31", "AV1": "29", "AVC": "30", "DivX": "9",
            "H264": "17", "H265": "18", "HEVC": "27", "M4V": "20",
            "MPEG-1": "10", "MPEG-2": "11", "RMVB": "12", "VC-1": "21",
            "VP6": "22", "VP9": "23", "WMV": "13", "XviD": "15"
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

        codec_id = codec_video_map.get(codec_video, "16")

        is_hdr = bool(meta.get('hdr'))

        if is_hdr:
            if codec_video in ("HEVC", "H265"):
                return "28"
            if codec_video in ("AVC", "H264"):
                return "32"

        return codec_id

    async def fetch_tmdb_data(self, endpoint):
        tmdb_api = self.config['DEFAULT']['tmdb_api']

        url = f"https://api.themoviedb.org/3/{endpoint}?api_key={tmdb_api}&language=pt-BR&append_to_response=credits,videos"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()
                else:
                    return None
        except httpx.RequestError:
            return None

    async def main_tmdb_data(self, meta):
        self.assign_media_properties(meta)
        if not self.category or not self.tmdb_id:
            return None

        endpoint = f"{self.category.lower()}/{self.tmdb_id}"
        return await self.fetch_tmdb_data(endpoint)

    async def season_tmdb_data(self, meta):
        season = meta.get('season_int')
        if not self.tmdb_id or season is None:
            return None

        endpoint = f"tv/{self.tmdb_id}/season/{season}"
        return await self.fetch_tmdb_data(endpoint)

    async def episode_tmdb_data(self, meta):
        season = meta.get('season_int')
        episode = meta.get('episode_int')
        if not self.tmdb_id or season is None or episode is None:
            return None

        endpoint = f"tv/{self.tmdb_id}/season/{season}/episode/{episode}"
        return await self.fetch_tmdb_data(endpoint)

    def format_image(self, url):
        return f"[img]{url}[/img]" if url else ""

    def format_date(self, date_str):
        if not date_str or date_str == 'N/A':
            return 'N/A'
        for fmt in ('%Y-%m-%d', '%d %b %Y'):
            try:
                return datetime.strptime(str(date_str), fmt).strftime('%d/%m/%Y')
            except (ValueError, TypeError):
                continue
        return str(date_str)

    def get_file_info(self, meta):
        if meta.get('is_disc') != 'BDMV':
            video_file = meta['filelist'][0]
            template_path = os.path.abspath(f"{meta['base_dir']}/data/templates/MEDIAINFO.txt")
            if os.path.exists(template_path):
                mi_output = MediaInfo.parse(
                    video_file,
                    output="STRING",
                    full=False,
                    mediainfo_options={"inform": f"file://{template_path}"}
                )
                return str(mi_output).replace('\r', '')
        else:
            summary_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if os.path.exists(summary_path):
                with open(summary_path, 'r', encoding='utf-8') as f:
                    return f.read()
        return None

    async def fetch_layout_data(self, meta):
        url = f"{self.base_url}/search.php"

        async def _fetch(payload):
            try:
                await self.load_cookies(meta)
                response = self.session.post(url, data=payload, timeout=20)
                response.raise_for_status()
                return response.json().get('ASC')
            except Exception:
                return None

        primary_payload = {'imdb': self.imdb_id, 'layout': self.layout}
        if layout_data := await _fetch(primary_payload):
            return layout_data

        # Fallback to a known movie if primary fetch fails
        fallback_payload = {'imdb': 'tt0013442', 'layout': self.layout}
        return await _fetch(fallback_payload)

    def build_ratings_bbcode(self, ratings_list):
        if not ratings_list:
            return ""

        ratings_map = {
            "Internet Movie Database": "[img]https://i.postimg.cc/Pr8Gv4RQ/IMDB.png[/img]",
            "Rotten Tomatoes": "[img]https://i.postimg.cc/rppL76qC/rotten.png[/img]",
            "Metacritic": "[img]https://i.postimg.cc/SKkH5pNg/Metacritic45x45.png[/img]",
            "TMDb": "[img]https://i.postimg.cc/T13yyzyY/tmdb.png[/img]"
        }
        parts = []
        for rating in ratings_list:
            source = rating.get('Source')
            value = rating.get('Value', '').strip()
            img_tag = ratings_map.get(source)
            if not img_tag:
                continue

            if source == "Internet Movie Database":
                parts.append(f"\n[url=https://www.imdb.com/title/{self.imdb_id}]{img_tag}[/url]\n[b]{value}[/b]\n")
            elif source == "TMDb":
                parts.append(f"[url=https://www.themoviedb.org/{self.category.lower()}/{self.tmdb_id}]{img_tag}[/url]\n[b]{value}[/b]\n")
            else:
                parts.append(f"{img_tag}\n[b]{value}[/b]\n")
        return "\n".join(parts)

    def build_cast_bbcode(self, cast_list):
        if not cast_list:
            return ""

        parts = []
        for person in cast_list[:10]:
            profile_path = person.get('profile_path')
            profile_url = f"https://image.tmdb.org/t/p/w45{profile_path}" if profile_path else "https://i.imgur.com/eCCCtFA.png"
            tmdb_url = f"https://www.themoviedb.org/person/{person.get('id')}?language=pt-BR"
            img_tag = self.format_image(profile_url)
            character_info = f"({person.get('name', '')}) como {person.get('character', '')}"
            parts.append(f"[url={tmdb_url}]{img_tag}[/url]\n[size=2][b]{character_info}[/b][/size]\n")
        return "".join(parts)

    async def build_description(self, json_data, meta):
        main_tmdb, season_tmdb, episode_tmdb, user_layout = await asyncio.gather(
            self.main_tmdb_data(meta),
            self.season_tmdb_data(meta),
            self.episode_tmdb_data(meta),
            self.fetch_layout_data(meta)
        )
        fileinfo_dump = await asyncio.to_thread(self.get_file_info, meta)

        if not user_layout:
            return "[center]Erro: Não foi possível carregar o layout da descrição.[/center]"

        layout_image = {k: v for k, v in user_layout.items() if k.startswith('BARRINHA_')}
        description_parts = ["[center]"]

        def append_section(key: str, content: str):
            if content and (img := layout_image.get(key)):
                description_parts.append(f"\n{self.format_image(img)}")
                description_parts.append(f"\n{content}\n")

        # Title
        for i in range(1, 4):
            description_parts.append(self.format_image(layout_image.get(f'BARRINHA_CUSTOM_T_{i}')))
        description_parts.append(f"\n{self.format_image(layout_image.get('BARRINHA_APRESENTA'))}\n")
        description_parts.append(f"\n[size=3]{await self.get_title(meta)}[/size]\n")

        # Poster
        poster_path = (season_tmdb or {}).get('poster_path') or (main_tmdb or {}).get('poster_path') or meta.get('tmdb_poster')
        self.poster = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ""
        append_section('BARRINHA_CAPA', self.format_image(self.poster))

        # Overview
        overview = (season_tmdb or {}).get('overview') or (main_tmdb or {}).get('overview')
        append_section('BARRINHA_SINOPSE', overview)

        # Episode
        if self.category == 'TV' and episode_tmdb:
            episode_name = episode_tmdb.get('name')
            episode_overview = episode_tmdb.get('overview')
            still_path = episode_tmdb.get('still_path')

            if episode_name and episode_overview and still_path:
                still_url = f"https://image.tmdb.org/t/p/w300{still_path}"
                description_parts.append(f"\n[size=4][b]Episódio:[/b] {episode_name}[/size]\n")
                description_parts.append(f"\n{self.format_image(still_url)}\n\n{episode_overview}\n")

        # Technical Sheet
        if main_tmdb:
            runtime = (episode_tmdb or {}).get('runtime') or main_tmdb.get('runtime') or meta.get('runtime')
            formatted_runtime = None
            if runtime:
                h, m = divmod(runtime, 60)
                formatted_runtime = f"{h} hora{'s' if h > 1 else ''} e {m:02d} minutos" if h > 0 else f"{m:02d} minutos"

            release_date = (episode_tmdb or {}).get('air_date') or (season_tmdb or {}).get('air_date') if self.category != 'MOVIE' else main_tmdb.get('release_date')

            sheet_items = [
                f"Duração: {formatted_runtime}" if formatted_runtime else None,
                f"País de Origem: {', '.join(c['name'] for c in main_tmdb.get('production_countries', []))}" if main_tmdb.get('production_countries') else None,
                f"Gêneros: {', '.join(g['name'] for g in main_tmdb.get('genres', []))}" if main_tmdb.get('genres') else None,
                f"Data de Lançamento: {self.format_date(release_date)}" if release_date else None,
                f"Site: [url={main_tmdb.get('homepage')}]Clique aqui[/url]" if main_tmdb.get('homepage') else None
            ]
            append_section('BARRINHA_FICHA_TECNICA', "\n".join(filter(None, sheet_items)))

        # Production Companies
        if main_tmdb and main_tmdb.get('production_companies'):
            prod_parts = ["[size=4][b]Produtoras[/b][/size]"]
            for p in main_tmdb.get('production_companies', []):
                logo_path = p.get('logo_path')
                logo = self.format_image(f"https://image.tmdb.org/t/p/w45{logo_path}") if logo_path else ''

                prod_parts.append(f"{logo}[size=2] - [b]{p.get('name', '')}[/b][/size]" if logo else f"[size=2][b]{p.get('name', '')}[/b][/size]")
            description_parts.append("\n" + "\n".join(prod_parts) + "\n")

        # Cast
        if self.category == 'MOVIE':
            cast_data = ((main_tmdb or {}).get('credits') or {}).get('cast', [])
        elif meta.get('tv_pack'):
            cast_data = ((season_tmdb or {}).get('credits') or {}).get('cast', [])
        else:
            cast_data = ((episode_tmdb or {}).get('credits') or {}).get('cast', [])
        append_section('BARRINHA_ELENCO', self.build_cast_bbcode(cast_data))

        # Seasons
        if self.category == 'TV' and main_tmdb and main_tmdb.get('seasons'):
            seasons_content = []
            for seasons in main_tmdb.get('seasons', []):
                season_name = seasons.get('name', f"Temporada {seasons.get('season_number')}").strip()
                poster_temp = self.format_image(f"https://image.tmdb.org/t/p/w185{seasons.get('poster_path')}") if seasons.get('poster_path') else ''
                overview_temp = f"\n\nSinopse:\n{seasons.get('overview')}" if seasons.get('overview') else ''

                inner_content_parts = []
                air_date = seasons.get('air_date')
                if air_date:
                    inner_content_parts.append(f"Data: {self.format_date(air_date)}")

                episode_count = seasons.get('episode_count')
                if episode_count is not None:
                    inner_content_parts.append(f"Episódios: {episode_count}")

                inner_content_parts.append(poster_temp)
                inner_content_parts.append(overview_temp)

                inner_content = "\n".join(inner_content_parts)
                seasons_content.append(f"\n[spoiler={season_name}]{inner_content}[/spoiler]\n")
            append_section('BARRINHA_EPISODIOS', "".join(seasons_content))

        # Ratings
        ratings_list = user_layout.get('Ratings', [])
        if not ratings_list:
            if imdb_rating := meta.get('imdb_info', {}).get('rating'):
                ratings_list.append({'Source': 'Internet Movie Database', 'Value': f'{imdb_rating}/10'})
        if main_tmdb and (tmdb_rating := main_tmdb.get('vote_average')):
            if not any(r.get('Source') == 'TMDb' for r in ratings_list):
                ratings_list.append({'Source': 'TMDb', 'Value': f'{tmdb_rating:.1f}/10'})

        criticas_key = 'BARRINHA_INFORMACOES' if self.category == 'MOVIE' and 'BARRINHA_INFORMACOES' in layout_image else 'BARRINHA_CRITICAS'
        append_section(criticas_key, self.build_ratings_bbcode(ratings_list))

        # MediaInfo/BDinfo
        if fileinfo_dump:
            description_parts.append(f"\n[spoiler=Informações do Arquivo]\n[left][font=Courier New]{fileinfo_dump}[/font][/left][/spoiler]\n")

        # Custom Bar
        for i in range(1, 4):
            description_parts.append(self.format_image(layout_image.get(f'BARRINHA_CUSTOM_B_{i}')))
        description_parts.append("[/center]")

        return "".join(filter(None, description_parts))

    async def prepare_form_data(self, meta):
        self.assign_media_properties(meta)
        main_tmdb = await self.main_tmdb_data(meta)

        try:
            data = {'takeupload': 'yes', 'layout': self.layout}

            subtitle_value, audio_value = await self._determine_language_properties(meta)
            if subtitle_value is None and audio_value is None:
                return None

            # Description
            json_data = {}
            tracker_description = await self.build_description(json_data, meta)

            base_desc = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
            asc_desc = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
            external_desc_content = ""
            if os.path.exists(base_desc):
                with open(base_desc, 'r', encoding='utf-8') as f:
                    external_desc_content = f.read().strip()
                    desc = external_desc_content
                    desc = desc.replace("[user]", "").replace("[/user]", "")
                    desc = desc.replace("[align=left]", "").replace("[/align]", "")
                    desc = desc.replace("[align=right]", "").replace("[/align]", "")
                    desc = desc.replace("[alert]", "").replace("[/alert]", "")
                    desc = desc.replace("[note]", "").replace("[/note]", "")
                    desc = desc.replace("[h1]", "[u][b]").replace("[/h1]", "[/b][/u]")
                    desc = desc.replace("[h2]", "[u][b]").replace("[/h2]", "[/b][/u]")
                    desc = desc.replace("[h3]", "[u][b]").replace("[/h3]", "[/b][/u]")
                    desc = re.sub(r"(\[img=\d+)]", "[img]", desc, flags=re.IGNORECASE)

            final_desc_parts = [
                tracker_description,
                desc,
                self.signature
            ]

            data['descr'] = "\n\n".join(filter(None, final_desc_parts)).strip()

            with open(asc_desc, 'w', encoding='utf-8') as f:
                f.write(data['descr'])

            # Poster
            data['capa'] = self.poster

            # Title
            data['name'] = await self.get_title(meta)

            # Year
            data['ano'] = str(meta['year'])

            # Genre
            data['genre'] = (', '.join(g['name'] for g in main_tmdb.get('genres', []))) or meta.get('genre', 'Gênero desconhecido')

            # File information
            data['legenda'] = subtitle_value
            data['audio'] = audio_value
            data['qualidade'] = self.get_type_id(meta)
            data['extencao'] = self.get_container(meta)
            data['codecaudio'] = self.get_audio_codec(meta)
            data['codecvideo'] = self.get_video_codec(meta)

            # IMDb
            data['imdb'] = self.imdb_id

            # Trailer
            video_results = main_tmdb.get('videos', {}).get('results', [])
            youtube_code = video_results[-1].get('key', '') if video_results else ''
            if youtube_code:
                data['tube'] = f"http://www.youtube.com/watch?v={youtube_code}"
            else:
                data['tube'] = meta.get('youtube') or ''

            # Resolution
            width, hight = self.get_res_id(meta)
            data['largura'] = width
            data['altura'] = hight

            # Languages
            lang_map = {
                "en": "1", "fr": "2", "de": "3", "it": "4", "ja": "5",
                "es": "6", "ru": "7", "pt": "8", "zh": "10", "da": "12",
                "sv": "13", "fi": "14", "bg": "15", "no": "16", "nl": "17",
                "pl": "19", "ko": "20", "th": "21", "hi": "23", "tr": "25"
            }

            # 3D
            data['tresd'] = '1' if meta.get('3d') else '2'

            if meta.get('anime'):
                if '3' in data['audio'] or '2' in data['audio']:
                    data['lang'] = "8"
                else:
                    data['lang'] = lang_map.get(meta.get('original_language', '').lower(), "11")

                idioma_map = {"de": "3", "zh": "9", "ko": "11", "es": "1", "en": "4", "ja": "8", "pt": "5", "ru": "2"}
                data['idioma'] = idioma_map.get(meta.get('original_language', '').lower(), "6")

                if self.category == 'MOVIE':
                    data['type'] = '116'
                elif self.category == 'TV':
                    data['type'] = '118'

            else:
                data['lang'] = lang_map.get(meta.get('original_language', '').lower(), "11")

            # Screenshots
            for i, img in enumerate(meta.get('image_list', [])[:4]):
                data[f'screens{i+1}'] = img.get('raw_url')

            return data
        except Exception as e:
            console.print(f"[bold red]A preparação dos dados para o upload falhou: {e}[/bold red]")
            raise

    async def upload(self, meta, disctype):
        await self.edit_torrent(meta, self.tracker, self.source_flag)
        await self.load_cookies(meta)

        data = await self.prepare_form_data(meta)

        if meta.get('debug', False):
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
            return

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

        upload_url = self.get_upload_url(meta)

        with open(torrent_path, 'rb') as torrent_file:
            files = {'torrent': (f"{self.tracker}.{meta.get('infohash', '')}.placeholder.torrent", torrent_file, "application/x-bittorrent")}
            response = self.session.post(upload_url, data=data, files=files, timeout=60)

        if "foi enviado com sucesso" in response.text:
            await self.successful_upload(response.text, meta)
        else:
            self.failed_upload(response, meta)

    def get_upload_url(self, meta):
        if meta.get('anime'):
            return f"{self.base_url}/enviar-anime.php"
        elif self.category == 'MOVIE':
            return f"{self.base_url}/enviar-filme.php"
        else:
            return f"{self.base_url}/enviar-series.php"

    async def successful_upload(self, response_text, meta):
        try:
            soup = BeautifulSoup(response_text, 'html.parser')
            details_link_tag = soup.find('a', href=lambda href: href and "torrents-details.php?id=" in href)

            relative_url = details_link_tag['href']
            torrent_url = f"{self.base_url}/{relative_url}"
            announce_url = self.config['TRACKERS'][self.tracker]['announce_url']
            meta['tracker_status'][self.tracker]['status_message'] = torrent_url

            await self.add_tracker_torrent(meta, self.tracker, self.source_flag, announce_url, torrent_url)

            should_approve = await self.get_approval(meta)
            if should_approve:
                await self.auto_approval(relative_url)

        except Exception as e:
            console.print(f"[bold red]Ocorreu um erro no pós-processamento do upload: {e}[/bold red]")

    async def auto_approval(self, relative_url):
        try:
            torrent_id = relative_url.split('id=')[-1]
            approval_url = f"{self.base_url}/uploader_app.php?id={torrent_id}"
            approval_response = self.session.get(approval_url, timeout=30)
            approval_response.raise_for_status()
        except Exception as e:
            console.print(f"[bold red]Erro durante a tentativa de aprovação automática: {e}[/bold red]")

    def failed_upload(self, response, meta):
        response_save_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
        with open(response_save_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        console.print("[bold red]Falha no upload para o ASC. A resposta do servidor não indicou sucesso.[/bold red]")
        console.print(f"[yellow]A resposta foi salva em: {response_save_path}[/yellow]")
        raise UploadException("Falha no upload para o ASC: resposta inesperada do servidor.", 'red')

    async def get_dupes(self, search_url, meta):
        dupes = []

        try:
            await self.load_cookies(meta)
            response = self.session.get(search_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            releases = soup.find_all('li', class_='list-group-item dark-gray')
        except Exception as e:
            console.print(f"[bold red]Falha ao acessar a página de busca do ASC: {e}[/bold red]")
            return dupes

        if not releases:
            return dupes

        for release in releases:
            try:
                badges = release.find_all('span', class_='badge')
                disc_types = ['BD25', 'BD50', 'BD66', 'BD100', 'DVD5', 'DVD9']
                is_disc = any(badge.text.strip().upper() in disc_types for badge in badges)

                if is_disc:
                    name, year, resolution, disk_type, video_codec, audio_codec = meta['title'], "N/A", "N/A", "N/A", "N/A", "N/A"
                    video_codec_terms = ['MPEG-4', 'AV1', 'AVC', 'H264', 'H265', 'HEVC', 'MPEG-1', 'MPEG-2', 'VC-1', 'VP6', 'VP9']
                    audio_codec_terms = ['DTS', 'AC3', 'DDP', 'E-AC-3', 'TRUEHD', 'ATMOS', 'LPCM', 'AAC', 'FLAC']

                    for badge in badges:
                        badge_text = badge.text.strip()
                        badge_text_upper = badge_text.upper()

                        if badge_text.isdigit() and len(badge_text) == 4:
                            year = badge_text
                        elif badge_text_upper in ['4K', '2160P', '1080P', '720P', '480P']:
                            resolution = "2160p" if badge_text_upper == '4K' else badge_text
                        elif any(term in badge_text_upper for term in video_codec_terms):
                            video_codec = badge_text
                        elif any(term in badge_text_upper for term in audio_codec_terms):
                            audio_codec = badge_text
                        elif any(term in badge_text_upper for term in disc_types):
                            disk_type = badge_text

                    dupe_string = f"{name} {year} {resolution} {disk_type} {video_codec} {audio_codec}"
                    dupes.append(dupe_string)
                else:
                    details_link_tag = release.find('a', href=lambda href: href and "torrents-details.php?id=" in href)
                    if not details_link_tag:
                        continue

                    torrent_id = details_link_tag['href'].split('id=')[-1]
                    file_page_url = f"{self.base_url}/torrents-arquivos.php?id={torrent_id}"
                    file_page_response = self.session.get(file_page_url, timeout=15)
                    file_page_response.raise_for_status()
                    file_page_soup = BeautifulSoup(file_page_response.text, 'html.parser')

                    file_li_tag = file_page_soup.find('li', class_='list-group-item')
                    if file_li_tag and file_li_tag.contents:
                        filename = file_li_tag.contents[0].strip()
                        dupes.append(filename)

            except Exception as e:
                console.print(f"[bold red]Falha ao processar um release da lista: {e}[/bold red]")
                continue
        return dupes

    async def search_existing(self, meta, disctype):
        self.assign_media_properties(meta)
        if meta.get('anime'):
            search_name = await self.get_title(meta)
            search_query = search_name.replace(' ', '+')
            search_url = f"{self.base_url}/torrents-search.php?search={search_query}"

        if self.category == 'MOVIE':
            search_url = f"{self.base_url}/busca-filmes.php?search=&imdb={self.imdb_id}"

        if self.category == 'TV':
            search_url = f"{self.base_url}/busca-series.php?search={self.season}{self.episode}&imdb={self.imdb_id}"

        return await self.get_dupes(search_url, meta)

    async def validate_credentials(self, meta):
        await self.load_cookies(meta)

        try:
            test_url = f"{self.base_url}/gerador.php"

            response = self.session.get(test_url, timeout=10, allow_redirects=False)

            if response.status_code == 200 and 'gerador.php' in response.url:
                return True
            else:
                console.print(f"[bold red]Falha na validação das credenciais do {self.tracker}. O cookie pode estar expirado.[/bold red]")
                return False
        except Exception as e:
            console.print(f"[bold red]Erro ao validar credenciais do {self.tracker}: {e}[/bold red]")
            return False

    async def get_approval(self, meta):
        uploader = self.config['TRACKERS'][self.tracker].get('uploader_status', False)
        if not uploader:
            return False

        modq = meta.get('modq', False) or meta.get('mq', False)
        if modq:
            return False, "Enviando para a fila de moderação."

        return True

    async def load_cookies(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/ASC.txt")
        if os.path.exists(cookie_file):
            self.session.cookies.update(await self.parseCookieFile(cookie_file))
        else:
            console.print(f"[bold red]Arquivo de cookie para o {self.tracker} não encontrado: {cookie_file}[/bold red]")
            return False
