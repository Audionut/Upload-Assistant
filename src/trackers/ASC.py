# -*- coding: utf-8 -*-
import os
import re
import requests
import cli_ui
from datetime import datetime
from src.exceptions import UploadException
from bs4 import BeautifulSoup
from src.console import console
from .COMMON import COMMON


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

    def get_season_and_episode(self, meta):
        if meta.get('category') == 'TV':
            season = meta.get('season')
            episode = meta.get('episode')

            if meta.get('tv_pack') == 1 and season:
                return f"{season}", None
            elif meta.get('tv_pack') == 0 and season and episode:
                return f"{season}", f"{episode}"
        return None, None

    def get_title(self, meta):
        og_name = meta.get('title')
        ptbr_name = None
        try:
            for aka in meta.get('imdb_info', {}).get('akas', []):
                if aka.get('country') == 'Brazil':
                    ptbr_name = aka.get('title')
                    break
        except (TypeError, AttributeError):
            ptbr_name = None

        nome_base = og_name
        if ptbr_name and ptbr_name.lower() != og_name.lower():
            nome_base = f"{ptbr_name} ({og_name})"

        season, episode = self.get_season_and_episode(meta)
        season_episode_str = ""
        if season and not episode:
            season_episode_str = f" - {season}"
        elif season and episode:
            season_episode_str = f" - {season}{episode}"

        return f"{nome_base}{season_episode_str}"

    def get_cat_id(self, meta):
        if meta.get('anime'):
            if meta.get('category') == 'MOVIE':
                return '116'  # Categoria Anime (Filme)
            elif meta.get('category') == 'TV':
                return '118'  # Categoria Anime (Série)
        return None  # Retorna None se não for uma categoria de anime específica

    def get_subtitles(self, meta):
        subtitle_languages = []
        pt_variants = ["pt", "portuguese", "português", "pt-br"]

        disc_type = meta.get('is_disc')
        if not disc_type and meta.get('discs'):
            disc_type = meta['discs'][0].get('type')

        if disc_type == 'BDMV':
            try:
                bdinfo_subs = meta.get('bdinfo', {}).get('subtitles', [])
                for sub in bdinfo_subs:
                    lang = sub.get('language', '') if isinstance(sub, dict) else sub
                    subtitle_languages.append(lang.lower())
            except Exception:
                console.print("[bold yellow]Aviso: Falha ao ler dados de legenda do BDInfo.[/bold yellow]")

        elif disc_type == 'DVD':
            try:
                for disc in meta.get('discs', []):
                    if 'ifo_mi' in disc:
                        ifo_text = disc['ifo_mi']
                        matches = re.findall(r'Text #\d+.*?Language\s*:\s*(.*?)\n', ifo_text, re.DOTALL)

                        for lang in matches:
                            subtitle_languages.append(lang.strip().lower())

            except Exception as e:
                console.print(f"[bold yellow]Aviso: Falha ao ler dados de legenda do IFO do DVD: {e}[/bold yellow]")

        else:
            try:
                tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
                for track in tracks:
                    if track.get('@type') == 'Text':
                        subtitle_languages.append(track.get('Language', '').lower())
            except (AttributeError, TypeError):
                console.print("[bold yellow]Aviso: Falha ao ler dados de legenda do MediaInfo.[/bold yellow]")

        if any(any(variant in lang for variant in pt_variants) for lang in subtitle_languages):
            return '1'  # Legenda Embutida

        console.print("[cyan]Nenhuma legenda embutida em Português foi detectada.[/cyan]")
        if cli_ui.ask_yes_no("Este upload inclui um arquivo de legenda SEPARADO (.srt, .sub) em Português?", default=False):
            console.print("[green]Opção 'Legenda Separada' selecionada pelo usuário.[/green]")
            return '2'  # Legenda Separada

        console.print("[green]Opção 'Sem Legenda' selecionada.[/green]")
        return '0'  # Sem Legenda

    def get_res_id(self, meta):
        if meta.get('is_disc') == 'BDMV':
            res_map = {'2160p': ('3840', '2160'), '1080p': ('1920', '1080'), '1080i': ('1920', '1080'), '720p': ('1280', '720')}
            return res_map.get(meta.get('resolution'))

        video_track = next((t for t in meta.get('mediainfo', {}).get('media', {}).get('track', []) if t.get('@type') == 'Video'), None)
        if video_track:
            return video_track.get('Width'), video_track.get('Height')
        return None, None

    def get_type_id(self, meta):
        qualidade_map_disc = {"BD25": "40", "BD50": "41", "BD66": "42", "BD100": "43"}
        qualidade_map_files = {"ENCODE": "9", "REMUX": "39", "WEBDL": "23", "WEBRIP": "38", "BDRIP": "8", "DVDR": "10"}
        qualidade_map_dvd = {"DVD5": "45", "DVD9": "46"}

        if meta.get('type') == 'DISC':
            if meta.get('is_disc') == 'DVD':
                dvd_size = meta.get('dvd_size')
                type_id = qualidade_map_dvd.get(dvd_size)
                if type_id:
                    return type_id

            disctype = meta.get('disctype')
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
            return qualidade_map_files.get(meta.get('type'), "0")

    def get_dubs(self, meta):
        audio_tracks_raw = []
        pt_variants = ["pt", "portuguese", "português", "pt-br"]

        disc_type = meta.get('is_disc')
        if not disc_type and meta.get('discs'):
            disc_type = meta['discs'][0].get('type')

        if disc_type == 'BDMV' and meta.get('bdinfo', {}).get('audio'):
            audio_tracks_raw = meta['bdinfo']['audio']

        elif disc_type == 'DVD':
            try:
                for disc in meta.get('discs', []):
                    if 'ifo_mi' in disc:
                        ifo_text = disc['ifo_mi']
                        matches = re.findall(r'Audio(?: #\d+)?.*?Language\s*:\s*(.*?)\n', ifo_text, re.DOTALL)

                        for lang in matches:
                            audio_tracks_raw.append({'language': lang.strip().lower()})
            except Exception as e:
                console.print(f"[bold yellow]Aviso: Falha ao ler dados de áudio do IFO do DVD: {e}[/bold yellow]")

        elif meta.get('mediainfo'):
            tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
            audio_tracks_raw = [{'language': t.get('Language')} for t in tracks if t.get('@type') == 'Audio']

        has_pt = any(any(v in track.get('language', '').lower() for v in pt_variants) for track in audio_tracks_raw)
        other_langs_count = sum(1 for t in audio_tracks_raw if not any(v in t.get('language', '').lower() for v in pt_variants))
        is_original_pt = any(v in meta.get('original_language', '').lower() for v in pt_variants)

        if has_pt:
            if is_original_pt:
                return "4"  # Nacional
            elif other_langs_count > 0:
                return "2"  # Dual-Audio
            return "3"  # Dublado
        return "1"  # Legendado

    def get_container(self, meta):
        if meta.get('is_disc') == "BDMV":
            return "5"
        elif meta.get('is_disc') == "DVD":
            return "15"

        try:
            general_track = next(t for t in meta.get('mediainfo', {}).get('media', {}).get('track', []) if t.get('@type') == 'General')
            file_extension = general_track.get('FileExtension', '').lower()
            if file_extension == 'mkv':
                return '6'
            elif file_extension == 'mp4':
                return '8'
        except (StopIteration, AttributeError, TypeError):
            return None
        return None

    def get_audio_codec(self, meta):
        audio_type = (meta.get('audio') or '').upper()

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

        return "20"  # Outros

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

    async def get_auto_description(self, meta):
        url_gerador_desc = f"{self.base_url}/search.php"
        payload = {
            'imdb': meta.get('imdb_info', {}).get('imdbID', ''),
            'layout': self.layout
        }

        try:
            await self._load_cookies(meta)

            response = self.session.post(url_gerador_desc, data=payload, timeout=20)
            response.raise_for_status()

            json_data = response.json()
            auto_description = await self.build_description(json_data, meta)

            return auto_description.strip()

        except Exception as e:
            console.print(f"[bold red]Ocorreu um erro no processo de descrição automática: {e}[/bold red]")

    async def build_description(self, json_data, meta):
        fileinfo_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/{'BD_SUMMARY_00.txt' if meta.get('is_disc') == 'BDMV' else 'MEDIAINFO_CLEANPATH.txt'}"
        with open(fileinfo_path, 'r', encoding='utf-8') as f:
            fileinfo_dump = f.read()

        asc_data = json_data.get('ASC')
        if not asc_data:
            console.print("[yellow]Alerta:[/yellow] O ASC não conseguiu gerar uma descrição com base no código IMDb.")
            console.print("[yellow]Alerta:[/yellow] Usando informações do arquivo como descrição.")
            return f"\n[left][font=Courier New]{fileinfo_dump}[/font][/left]"

        def format_image(url):
            return f"[img]{url}[/img]" if url else ""

        def format_date(date_str):
            if not date_str or date_str == 'N/A':
                return 'N/A'
            for fmt in ('%Y-%m-%d', '%d %b %Y'):
                try:
                    return datetime.strptime(date_str, fmt).strftime('%d/%m/%Y')
                except (ValueError, TypeError):
                    continue
            return date_str

        def append_section(parts, barrinha_key, content):
            if content:
                barrinha_url = barrinhas.get(barrinha_key)
                if barrinha_url:
                    parts.append(f"\n{format_image(barrinha_url)}")
                parts.append(f"\n{content}\n")

        def build_cast_section(cast_list):
            if not cast_list:
                return ""

            cast_parts = []
            for ator in cast_list[:10]:
                profile_url = f"https://image.tmdb.org/t/p/w45{ator.get('profile_path')}" if ator.get('profile_path') else "https://i.imgur.com/eCCCtFA.png"
                tmdb_url = f"https://www.themoviedb.org/person/{ator.get('id')}?language=pt-BR"
                cast_parts.append(f"[url={tmdb_url}]{format_image(profile_url)}[/url]\n[size=2][b]({ator.get('name', '')}) como {ator.get('character', '')}[/b][/size]\n")
            return "".join(cast_parts)

        def build_ratings_section(ratings_list, imdb_id):
            if not ratings_list:
                return ""

            ratings_map = {
                "Internet Movie Database": "https://i.postimg.cc/Pr8Gv4RQ/IMDB.png",
                "Rotten Tomatoes": "https://i.postimg.cc/rppL76qC/rotten.png",
                "Metacritic": "https://i.postimg.cc/SKkH5pNg/Metacritic45x45.png"
            }
            ratings_parts = []
            for rating in ratings_list:
                source = rating.get('Source')
                value = rating.get('Value', '').strip()
                img_url = ratings_map.get(source)

                if not img_url:
                    continue

                if source == "Internet Movie Database" and imdb_id:
                    ratings_parts.append(f"[url=https://www.imdb.com/title/{imdb_id}]{format_image(img_url)}[/url] - [b]{value}[/b]")
                else:
                    ratings_parts.append(f"{format_image(img_url)} - [b]{value}[/b]")

            return "\n".join(ratings_parts)

        tmdb_tv_data = None
        if meta.get('category', '').lower() == 'tv' and meta.get('tmdb') and self.config['DEFAULT'].get('tmdb_api'):
            url = f"https://api.themoviedb.org/3/tv/{meta['tmdb']}?api_key={self.config['DEFAULT']['tmdb_api']}&language=pt-BR"
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    tmdb_tv_data = response.json()
            except requests.exceptions.RequestException as e:
                print(f"Ocorreu um erro ao fazer a requisição para o TMDB: {e}")

        tipo_media = asc_data.get('Type', 'movie')
        imdb_id = asc_data.get('imdbID', '')
        barrinhas = {key: value for key, value in asc_data.items() if key.startswith('BARRINHA_')}

        description_parts = ["[center]"]

        # Custom top bars
        for i in range(1, 4):
            description_parts.append(format_image(barrinhas.get(f'BARRINHA_CUSTOM_T_{i}')))

        # Common data
        if tipo_media == 'movie':
            description_parts.append(f"\n{format_image(barrinhas.get('BARRINHA_APRESENTA'))}\n")
            description_parts.append(f"[size=3]{asc_data.get('Title', 'N/A')}[/size]\n")

            append_section(description_parts, 'BARRINHA_CAPA', format_image(asc_data.get('poster_path')))
            append_section(description_parts, 'BARRINHA_SINOPSE', asc_data.get('overview'))

            # Technical Sheet
            ficha_content = "\n".join([
                f"Tempo: {asc_data.get('Runtime', 'N/A')}",
                f"Produtora: {asc_data.get('Production', 'N/A')}",
                f"País de Origem: {asc_data.get('Country', 'N/A')}",
                f"Gêneros: {asc_data.get('Genre', 'N/A')}",
                f"Data de Lançamento: {format_date(asc_data.get('Released', 'N/A'))}",
                (f"Site: [url={asc_data.get('Website')}]Clique aqui[/url]" if asc_data.get('Website') != 'N/A' else "")
            ])
            append_section(description_parts, 'BARRINHA_FICHA_TECNICA', ficha_content)

        elif tipo_media in ['series', 'episode']:
            description_parts.append(f"\n{format_image(barrinhas.get('BARRINHA_APRESENTA'))}")
            description_parts.append(f"\n{format_image(asc_data.get('poster_path'))}\n")

            append_section(description_parts, 'BARRINHA_CAPA', format_image(asc_data.get('still_path')))
            append_section(description_parts, 'BARRINHA_SINOPSE', asc_data.get('overview'))

            # Technical Sheet (TV)
            generos = asc_data.get('Genre', 'N/A')
            if tmdb_tv_data and tmdb_tv_data.get('genres'):
                generos = ', '.join([g['name'] for g in tmdb_tv_data.get('genres', [])])

            ficha_content = "\n".join(filter(None, [
                f"País de Origem: {asc_data.get('Country', 'N/A')}",
                f"Gêneros: {generos}",
                (f"Site: [url={asc_data.get('Website')}]Clique aqui[/url]" if asc_data.get('Website') != 'N/A' else None)
            ]))
            append_section(description_parts, 'BARRINHA_FICHA_TECNICA', ficha_content)

            # Production Companies (TV)
            if tmdb_tv_data and tmdb_tv_data.get('production_companies'):
                prod_parts = ["[size=4][b]Produtoras[/b][/size]"]
                for p in tmdb_tv_data['production_companies']:
                    logo = format_image(f"https://image.tmdb.org/t/p/w45{p['logo_path']}") if p.get('logo_path') else ''
                    prod_parts.append(f"{logo}[size=2] - [b]{p.get('name', '')}[/b][/size]" if logo else f"[size=2][b]{p.get('name', '')}[/b][/size]")
                description_parts.append("\n" + "\n".join(prod_parts) + "\n")

        # Cast
        cast_content = build_cast_section(asc_data.get('cast'))
        append_section(description_parts, 'BARRINHA_ELENCO', cast_content)

        # Seasons
        if tipo_media == 'series' and tmdb_tv_data and tmdb_tv_data.get('seasons'):
            seasons_content = []
            for temp in tmdb_tv_data['seasons']:
                nome_temporada = temp.get('name', f"Temporada {temp.get('season_number')}").strip()
                poster_temp = format_image(f"https://image.tmdb.org/t/p/w185{temp.get('poster_path')}") if temp.get('poster_path') else ''
                overview_temp = f"\n\nSinopse:\n{temp.get('overview')}" if temp.get('overview') else ''

                inner_content = "\n".join([
                    f"Data: {format_date(temp.get('air_date'))}",
                    f"Episódios: {temp.get('episode_count')}",
                    poster_temp,
                    overview_temp
                ])
                seasons_content.append(f"\n[spoiler={nome_temporada}]{inner_content}\n[/spoiler]")
            append_section(description_parts, 'BARRINHA_EPISODIOS', "".join(seasons_content))

        # Ratings
        ratings_content = build_ratings_section(asc_data.get('Ratings'), imdb_id)
        barrinha_criticas_key = 'BARRINHA_INFORMACOES' if tipo_media == 'movie' and 'BARRINHA_INFORMACOES' in barrinhas else 'BARRINHA_CRITICAS'
        append_section(description_parts, barrinha_criticas_key, ratings_content)

        # Custom bottom bars
        for i in range(1, 4):
            description_parts.append(format_image(barrinhas.get(f'BARRINHA_CUSTOM_B_{i}')))

        description_parts.append(f"\n[spoiler=Informações do Arquivo]\n[left][font=Courier New]{fileinfo_dump}[/font][/left][/spoiler]\n")
        description_parts.append("[/center]")

        return "".join(filter(None, description_parts))

    async def prepare_form_data(self, meta):
        try:
            data = {'takeupload': 'yes', 'tresd': 2, 'layout': self.layout}

            asc_data = None
            if meta.get('imdb_id'):
                url_gerador_desc = f"{self.base_url}/search.php"
                payload = {'imdb': meta.get('imdb_info', {}).get('imdbID', ''), 'layout': self.layout}
                try:
                    await self._load_cookies(meta)
                    response = self.session.post(url_gerador_desc, data=payload, timeout=20)
                    response.raise_for_status()
                    asc_data = response.json().get('ASC')
                except Exception:
                    asc_data = None

            # Description
            tracker_description = await self.build_description({'ASC': asc_data}, meta)

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
            poster_path = asc_data.get('poster_path') if asc_data else None
            if not poster_path:
                poster_path = meta.get('poster')
            if poster_path:
                data['capa'] = poster_path

            # Title
            # The site database is incompatible with non-ASCII characters in the title
            def is_safe_ascii(text):
                if not text:
                    return False
                return bool(re.match(r'^[ -~]+$', text))

            title_from_asc = asc_data.get('Title') if asc_data else None

            if is_safe_ascii(title_from_asc):
                nome_base = title_from_asc

                if meta.get('category') == 'TV':
                    season, episode = self.get_season_and_episode(meta)
                    season_episode_str = ""
                    if season:
                        season_episode_str = f" - {season}{episode or ''}"
                    data['name'] = f"{nome_base}{season_episode_str}"
                else:
                    data['name'] = nome_base
            else:
                data['name'] = self.get_title(meta)

            # Year
            ano = asc_data.get('Year') if asc_data and asc_data.get('Year') else meta.get('year')
            if ano:
                data['ano'] = ano

            # Genre
            genre = asc_data.get('Genre') if asc_data and asc_data.get('Genre') else meta.get('genres')
            if genre:
                data['genre'] = genre

            # File information
            data['legenda'] = self.get_subtitles(meta)
            data['qualidade'] = self.get_type_id(meta)
            data['audio'] = self.get_dubs(meta)
            data['extencao'] = self.get_container(meta)
            data['codecaudio'] = self.get_audio_codec(meta)
            data['codecvideo'] = self.get_video_codec(meta)

            # IMDb
            if meta.get('imdb_id'):
                data['imdb'] = meta.get('imdb_info', {}).get('imdbID', '')

            # Trailer
            if meta.get('youtube'):
                data['tube'] = meta.get('youtube')

            # Resolution
            largura, altura = self.get_res_id(meta)
            if largura:
                data['largura'] = largura
            if altura:
                data['altura'] = altura

            # Languages
            lang_map = {"en": "1", "fr": "2", "de": "3", "it": "4", "ja": "5", "es": "6", "ru": "7", "pt": "8", "zh": "10", "da": "12", "sv": "13", "fi": "14", "bg": "15", "no": "16", "nl": "17", "pl": "19", "ko": "20", "th": "21", "hi": "23", "tr": "25"}

            if meta.get('anime'):
                if '3' in data['audio'] or '2' in data['audio']:
                    data['lang'] = "8"
                else:
                    data['lang'] = lang_map.get(meta.get('original_language', '').lower(), "11")

                idioma_map = {"de": "3", "zh": "9", "ko": "11", "es": "1", "en": "4", "ja": "8", "pt": "5", "ru": "2"}
                data['idioma'] = idioma_map.get(meta.get('original_language', '').lower(), "6")
                data['type'] = self.get_cat_id(meta)
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
        await COMMON(config=self.config).edit_torrent(meta, self.tracker, self.source_flag)
        await self._load_cookies(meta)

        data = await self.prepare_form_data(meta)
        if data is None:
            raise UploadException("Falha ao preparar os dados do formulário.", 'red')

        if meta.get('debug', False):
            console.print("[yellow]MODO DEBUG ATIVADO. Upload não será realizado.[/yellow]")
            console.print("[cyan]Dados do formulário:[/cyan]", data)
            return

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        if not os.path.exists(torrent_path):
            console.print(f"[bold red]CRÍTICO: Arquivo torrent não encontrado: {torrent_path}[/bold red]")
            return

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
        elif meta.get('category') == 'MOVIE':
            return f"{self.base_url}/enviar-filme.php"
        else:
            return f"{self.base_url}/enviar-series.php"

    async def successful_upload(self, response_text, meta):
        try:
            soup = BeautifulSoup(response_text, 'html.parser')
            details_link_tag = soup.find('a', href=lambda href: href and "torrents-details.php?id=" in href)

            relative_url = details_link_tag['href']
            torrent_url = f"{self.base_url}/{relative_url}"
            announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
            meta['tracker_status'][self.tracker]['status_message'] = torrent_url

            await COMMON(config=self.config).add_tracker_torrent(meta, self.tracker, self.source_flag, announce_url, torrent_url)

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
        console.print(f"[cyan]Buscando duplicados em:[/cyan] {search_url}")

        try:
            await self._load_cookies(meta)
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
                    name, year, resolution, disk_type, video_codec, audio_codec = meta.get('title'), "N/A", "N/A", "N/A", "N/A", "N/A"
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
        if meta.get('anime'):
            search_name = self.get_title(meta)
            search_query = search_name.replace(' ', '+')
            search_url = f"{self.base_url}/torrents-search.php?search={search_query}"

        elif meta.get('category') == 'TV':
            imdb_id = meta.get('imdb_info', {}).get('imdbID')

            if imdb_id:
                season, episode = self.get_season_and_episode(meta)
                search_param = ""
                if season and not episode:
                    search_param = f"{season}"
                elif season and episode:
                    search_param = f"{season}{episode}"

                search_url = f"{self.base_url}/busca-series.php?search={search_param}&imdb={imdb_id}"
            else:
                search_name = self.get_title(meta)
                search_query = search_name.replace(' ', '+')
                search_url = f"{self.base_url}/torrents-search.php?search={search_query}"

        else:
            imdb_id = meta.get('imdb_info', {}).get('imdbID')
            if not imdb_id:
                return []
            search_url = f"{self.base_url}/busca-filmes.php?search=&imdb={imdb_id}"

        return await self.get_dupes(search_url, meta)

    async def validate_credentials(self, meta):
        await self._load_cookies(meta)

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

    async def _load_cookies(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/ASC.txt")
        if os.path.exists(cookie_file):
            self.session.cookies.update(await self.parseCookieFile(cookie_file))
        else:
            console.print(f"[bold red]Arquivo de cookie para o {self.tracker} não encontrado: {cookie_file}[/bold red]")
            return False
