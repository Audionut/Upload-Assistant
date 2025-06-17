# -*- coding: utf-8 -*-
import os
import re
import requests
from bs4 import BeautifulSoup
from http.cookiejar import MozillaCookieJar
from src.console import console
from .COMMON import COMMON


class BT(COMMON):
    def __init__(self, config):
        super().__init__(config)
        self.tracker = "BT"
        self.banned_groups = [""]
        self.source_flag = "BT"
        self.base_url = "https://brasiltracker.org"
        self.auth_token = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        })
        self.signature = "[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"

        target_site_ids = {
            'danish': '10', 'swedish': '11', 'norwegian': '12', 'romanian': '13',
            'chinese': '14', 'finnish': '15', 'italian': '16', 'polish': '17',
            'turkish': '18', 'korean': '19', 'thai': '20', 'arabic': '22',
            'croatian': '23', 'hungarian': '24', 'vietnamese': '25', 'greek': '26',
            'icelandic': '28', 'bulgarian': '29', 'english': '3', 'czech': '30',
            'serbian': '31', 'ukrainian': '34', 'latvian': '37', 'estonian': '38',
            'lithuanian': '39', 'spanish': '4', 'hebrew': '40', 'hindi': '41',
            'slovak': '42', 'slovenian': '43', 'indonesian': '47',
            'português': '49',
            'french': '5', 'german': '6', 'russian': '7', 'japanese': '8', 'dutch': '9',
            'english - forçada': '50', 'persian': '52'
        }

        source_alias_map = {
            ("Arabic", "ara", "ar"): "arabic",
            ("Brazilian Portuguese", "Brazilian", "Portuguese-BR", 'pt-br', 'pt-BR', "Portuguese", "por", "pt", "pt-PT", "Português Brasileiro", "Português"): "português",
            ("Bulgarian", "bul", "bg"): "bulgarian",
            ("Chinese", "chi", "zh", "Chinese (Simplified)", "Chinese (Traditional)", 'cmn-Hant', 'cmn-Hans', 'yue-Hant', 'yue-Hans'): "chinese",
            ("Croatian", "hrv", "hr", "scr"): "croatian",
            ("Czech", "cze", "cz", "cs"): "czech",
            ("Danish", "dan", "da"): "danish",
            ("Dutch", "dut", "nl"): "dutch",
            ("English", "eng", "en", "en-US", "en-GB", "English (CC)", "English - SDH"): "english",
            ("English - Forced", "English (Forced)", "en (Forced)", "en-US (Forced)"): "english - forçada",
            ("Estonian", "est", "et"): "estonian",
            ("Finnish", "fin", "fi"): "finnish",
            ("French", "fre", "fr", "fr-FR", "fr-CA"): "french",
            ("German", "ger", "de"): "german",
            ("Greek", "gre", "el"): "greek",
            ("Hebrew", "heb", "he"): "hebrew",
            ("Hindi", "hin", "hi"): "hindi",
            ("Hungarian", "hun", "hu"): "hungarian",
            ("Icelandic", "ice", "is"): "icelandic",
            ("Indonesian", "ind", "id"): "indonesian",
            ("Italian", "ita", "it"): "italian",
            ("Japanese", "jpn", "ja"): "japanese",
            ("Korean", "kor", "ko"): "korean",
            ("Latvian", "lav", "lv"): "latvian",
            ("Lithuanian", "lit", "lt"): "lithuanian",
            ("Norwegian", "nor", "no"): "norwegian",
            ("Persian", "fa", "far"): "persian",
            ("Polish", "pol", "pl"): "polish",
            ("Romanian", "rum", "ro"): "romanian",
            ("Russian", "rus", "ru"): "russian",
            ("Serbian", "srp", "sr", "scc"): "serbian",
            ("Slovak", "slo", "sk"): "slovak",
            ("Slovenian", "slv", "sl"): "slovenian",
            ("Spanish", "spa", "es", "es-ES", "es-419"): "spanish",
            ("Swedish", "swe", "sv"): "swedish",
            ("Thai", "tha", "th"): "thai",
            ("Turkish", "tur", "tr"): "turkish",
            ("Ukrainian", "ukr", "uk"): "ukrainian",
            ("Vietnamese", "vie", "vi"): "vietnamese",
        }

        self.ultimate_lang_map = {}
        for aliases_tuple, canonical_name in source_alias_map.items():
            if canonical_name in target_site_ids:
                correct_id = target_site_ids[canonical_name]
                for alias in aliases_tuple:
                    self.ultimate_lang_map[alias.lower()] = correct_id

    async def search_existing(self, meta, disctype):
        imdb_id = meta.get('imdb_info', {}).get('imdbID', '')
        if not imdb_id:
            console.print("[yellow]Aviso: Nenhum IMDb ID fornecido, não é possível buscar por duplicatas.[/yellow]")
            return []

        is_current_upload_a_tv_pack = meta.get('tv_pack') == 1

        search_url = f"{self.base_url}/torrents.php?searchstr={imdb_id}"

        found_items = []
        try:
            response = self.session.get(search_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            torrent_table = soup.find('table', id='torrent_table')
            if not torrent_table:
                return []

            group_links = set()
            for group_row in torrent_table.find_all('tr'):
                link = group_row.find('a', href=re.compile(r'torrents\.php\?id=\d+'))
                if link and 'torrentid' not in link.get('href', ''):
                    group_links.add(link['href'])

            if not group_links:
                return []

            for group_link in group_links:
                group_url = f"{self.base_url}/{group_link}"
                group_response = self.session.get(group_url)
                group_response.raise_for_status()
                group_soup = BeautifulSoup(group_response.text, 'html.parser')

                for torrent_row in group_soup.find_all('tr', id=re.compile(r'^torrent\d+$')):
                    desc_link = torrent_row.find('a', onclick=re.compile(r'gtoggle'))
                    if not desc_link:
                        continue
                    description_text = " ".join(desc_link.get_text(strip=True).split())

                    torrent_id = torrent_row.get('id', '').replace('torrent', '')
                    file_div = group_soup.find('div', id=f'files_{torrent_id}')
                    if not file_div:
                        continue

                    is_existing_torrent_a_disc = any(keyword in description_text.lower() for keyword in ['bd25', 'bd50', 'bd66', 'bd100', 'dvd5', 'dvd9', 'm2ts'])

                    if is_existing_torrent_a_disc or is_current_upload_a_tv_pack:
                        path_div = file_div.find('div', class_='filelist_path')
                        if path_div:
                            folder_name = path_div.get_text(strip=True).strip('/')
                            if folder_name:
                                found_items.append(folder_name)
                    else:
                        file_table = file_div.find('table', class_='filelist_table')
                        if file_table:
                            for row in file_table.find_all('tr'):
                                if 'colhead_dark' not in row.get('class', []):
                                    cell = row.find('td')
                                    if cell:
                                        filename = cell.get_text(strip=True)
                                        if filename:
                                            found_items.append(filename)
                                            break

        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Ocorreu um erro de rede ao buscar por duplicatas: {e}[/bold red]")
            return []
        except Exception as e:
            console.print(f"[bold red]Ocorreu um erro inesperado ao processar a busca: {e}[/bold red]")
            return []

        return found_items

    async def validate_credentials(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        if not os.path.exists(cookie_file):
            console.print(f"[bold red]Arquivo de cookie para o {self.tracker} não encontrado: {cookie_file}[/bold red]")
            return False

        try:
            jar = MozillaCookieJar(cookie_file)
            jar.load(ignore_discard=True, ignore_expires=True)
            self.session.cookies = jar
        except Exception as e:
            console.print(f"[bold red]Erro ao carregar o arquivo de cookie. Verifique se o formato está correto. Erro: {e}[/bold red]")
            return False

        try:
            upload_page_url = f"{self.base_url}/upload.php"
            response = self.session.get(upload_page_url, timeout=10, allow_redirects=True)

            if 'login.php' in str(response.url):
                console.print(f"[bold red]Falha na validação do {self.tracker}. O cookie parece estar expirado ou é inválido.[/bold red]")
                return False

            auth_match = re.search(r'name="auth" value="([^"]+)"', response.text)

            if auth_match:
                self.auth_token = auth_match.group(1)
                return True
            else:
                console.print(f"[bold red]Falha na validação do {self.tracker}. Não foi possível encontrar o token 'auth' na página de upload.[/bold red]")
                console.print("[yellow]Isso pode acontecer se a estrutura do site mudou ou se o login falhou silenciosamente.[/yellow]")
                with open(f"{self.tracker}_auth_failure_{meta['uuid']}.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                console.print(f"[yellow]A resposta do servidor foi salva em '{self.tracker}_auth_failure_{meta['uuid']}.html' para análise.[/yellow]")
                return False

        except Exception as e:
            console.print(f"[bold red]Erro ao validar credenciais do {self.tracker}: {e}[/bold red]")
            return False

    def get_type(self, meta):
        if meta.get('anime', False):
            return '5'

        if meta.get('category') == 'TV' or meta.get('season') is not None:
            return '1'

        if 'Documentary' in meta.get('genres', ''):
            return '7'

        if meta.get('category') == 'MOVIE':
            return '0'

        return '0'

    def get_details(self, meta):
        details = {
            'imdb_input': '',
            'nota_imdb': '',
            'year': '',
            'diretor': '',
            'duracao': '',
            'idioma_ori': '',
            'youtube': ''
        }

        details['imdb_input'] = meta.get('imdb_info', {}).get('imdbID', '')

        if 'imdb_info' in meta and 'rating' in meta['imdb_info']:
            details['nota_imdb'] = str(meta['imdb_info']['rating'])

        details['year'] = str(meta.get('year', ''))

        if 'tmdb_directors' in meta:
            unique_directors = list(set(meta['tmdb_directors']))
            details['diretor'] = ", ".join(unique_directors)

        details['duracao'] = str(meta.get('runtime', ''))

        details['idioma_ori'] = meta.get('original_language', '')

        youtube_url = meta.get('youtube', '')
        if youtube_url:
            match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', youtube_url)
            if match:
                details['youtube'] = match.group(1)
            else:
                try:
                    details['youtube'] = youtube_url.split('/')[-1]
                except:
                    details['youtube'] = ''

        return details

    def get_name(self, meta):
        names = {
            'title': '',
            'title_br': ''
        }

        names['title'] = meta.get('title', '')

        if 'imdb_info' in meta and 'akas' in meta['imdb_info']:
            for aka in meta['imdb_info']['akas']:
                if aka.get('country') == 'Brazil':
                    names['title_br'] = aka.get('title', '')
                    break

        if not names['title_br']:
            pass

        return names

    def get_file_info(self, meta):
        info_file_path = ""
        if meta.get('is_disc') == 'BDMV':
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/BD_SUMMARY_00.txt"
        else:
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MEDIAINFO_CLEANPATH.txt"

        if os.path.exists(info_file_path):
            try:
                with open(info_file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                console.print(f"[bold red]Erro ao ler o arquivo de info em '{info_file_path}': {e}[/bold red]")
                return ""
        else:
            console.print(f"[bold red]Arquivo de info não encontrado: {info_file_path}[/bold red]")
            return ""

    def get_format(self, meta):
        if meta.get('is_disc') == "BDMV":
            return "M2TS"

        try:
            general_track = next(t for t in meta.get('mediainfo', {}).get('media', {}).get('track', []) if t.get('@type') == 'General')
            file_extension = general_track.get('FileExtension', '').lower()
            if file_extension == 'mkv':
                return 'MKV'
            elif file_extension == 'mp4':
                return 'MP4'
            elif file_extension == 'vob':
                return 'VOB'
            else:
                return "Outros"
        except (StopIteration, AttributeError, TypeError):
            return None
        return None

    def get_audio(self, meta):
        audio_tracks_raw = []
        pt_variants = ["pt", "portuguese", "português", "pt-br"]

        if meta.get('is_disc') == 'BDMV' and meta.get('bdinfo', {}).get('audio'):
            audio_tracks_raw = meta['bdinfo']['audio']
        elif meta.get('mediainfo'):
            tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
            audio_tracks_raw = [{'language': t.get('Language')} for t in tracks if t.get('@type') == 'Audio']

        has_pt = any(any(v in track.get('language', '').lower() for v in pt_variants) for track in audio_tracks_raw)
        other_langs_count = sum(1 for t in audio_tracks_raw if not any(v in t.get('language', '').lower() for v in pt_variants))
        is_original_pt = any(v in meta.get('original_language', '').lower() for v in pt_variants)

        if has_pt:
            if is_original_pt:
                return "Nacional"
            elif other_langs_count > 0:
                return "Dual Audio"
            return "Dublado"
        return "Legendado"

    def get_video_codec(self, meta):
        video_encode = meta.get('video_encode', '').strip().lower()
        codec_final = meta.get('video_codec', '')
        is_hdr = bool(meta.get('hdr'))

        encode_map = {
            'x265': 'x265',
            'h.265': 'H.265',
            'x264': 'x264',
            'h.264': 'H.264',
            'vp9': 'VP9',
            'xvid': 'XviD',
        }

        for key, value in encode_map.items():
            if key in video_encode:
                if value in ['x265', 'H.265'] and is_hdr:
                    return f"{value} HDR"
                return value

        # Use 'video_codec' if 'video_encode' is not present
        codec_lower = codec_final.lower()

        codec_map = {
            'hevc': 'x265',
            'avc': 'x264',
            'mpeg-2': 'MPEG-2',
            'vc-1': 'VC-1',
        }

        for key, value in codec_map.items():
            if key in codec_lower:
                return f"{value} HDR" if value == 'x265' and is_hdr else value

        return codec_final if codec_final else "Outro"

    def get_audio_codec(self, meta):
        priority_order = [
            "DTS-X", "E-AC-3 JOC", "TrueHD", "DTS-HD", "PCM", "FLAC", "DTS-ES",
            "DTS", "E-AC-3", "AC3", "AAC", "Opus", "Vorbis", "MP3", "MP2"
        ]

        codec_map = {
            "DTS-X": ["DTS:X"],
            "E-AC-3 JOC": ["DD+ 5.1 Atmos", "DD+ 7.1 Atmos"],
            "TrueHD": ["TrueHD"],
            "DTS-HD": ["DTS-HD"],
            "PCM": ["LPCM"],
            "FLAC": ["FLAC"],
            "DTS-ES": ["DTS-ES"],
            "DTS": ["DTS"],
            "E-AC-3": ["DD+"],
            "AC3": ["DD"],
            "AAC": ["AAC"],
            "Opus": ["Opus"],
            "Vorbis": ["VORBIS"],
            "MP2": ["MP2"],
            "MP3": ["MP3"]
        }

        audio_description = meta.get('audio')

        if not audio_description or not isinstance(audio_description, str):
            return "Outro"

        for codec_name in priority_order:
            search_terms = codec_map.get(codec_name, [])

            for term in search_terms:
                if term in audio_description:
                    return codec_name

        return "Outro"

    def get_subtitles(self, meta):
        found_language_strings = set()

        if meta.get('is_disc') == 'BDMV' and 'bdinfo' in meta and isinstance(meta['bdinfo'].get('subtitles'), list):
            for sub_lang in meta['bdinfo']['subtitles']:
                if sub_lang and isinstance(sub_lang, str):
                    found_language_strings.add(sub_lang.strip())

        else:
            try:
                raw_tracks = meta.get('mediainfo', {}).get('media', {}).get('track')

                tracks = []
                if raw_tracks:
                    if isinstance(raw_tracks, list):
                        tracks = raw_tracks
                    else:
                        tracks = [raw_tracks]

                text_tracks = [t for t in tracks if t and t.get('@type') == 'Text']
                for track in text_tracks:
                    if track.get('Language'):
                        found_language_strings.add(track.get('Language').strip())
                    if track.get('Title'):
                        found_language_strings.add(track.get('Title').strip())
            except (AttributeError, TypeError):
                pass

        subtitle_ids = set()
        for lang_str in found_language_strings:
            if lang_str:
                target_id = self.ultimate_lang_map.get(lang_str.lower())
                if target_id:
                    subtitle_ids.add(target_id)

        legenda_value = "Sim" if '49' in subtitle_ids else "Nao"
        final_subtitle_ids = sorted(list(subtitle_ids))
        if not final_subtitle_ids:
            final_subtitle_ids.append('44')

        return {
            'legenda': legenda_value,
            'subtitles[]': final_subtitle_ids
        }

    def get_edition(self, meta):
        edition_str = meta.get('edition', '').lower()
        if not edition_str:
            return ""

        edition_map = {
            "director's cut": "Director's Cut",
            "theatrical": "Theatrical Cut",
            "extended": "Extended",
            "uncut": "Uncut",
            "unrated": "Unrated",
            "imax": "IMAX",
            "noir": "Noir",
            "remastered": "Remastered",
        }

        for keyword, label in edition_map.items():
            if keyword in edition_str:
                return label

        return ""
        
    def get_bitrate(self, meta):
        if meta.get('type') == 'DISC':
            is_disc_type = meta.get('is_disc')

            if is_disc_type == 'BDMV':
                disctype = meta.get('disctype')
                if disctype in ["BD100", "BD66", "BD50", "BD25"]:
                    return disctype

                try:
                    size_in_gb = meta['torrent_comments'][0]['size'] / (10**9)
                except (KeyError, IndexError, TypeError):
                    size_in_gb = 0

                if size_in_gb > 66:
                    return "BD100"
                elif size_in_gb > 50:
                    return "BD66"
                elif size_in_gb > 25:
                    return "BD50"
                else:
                    return "BD25"

            elif is_disc_type == 'DVD':
                disctype = meta.get('disctype')
                if disctype in ["DVD9", "DVD5"]:
                    return disctype
                return "DVD9"

        source_type = meta.get('type')

        if not source_type or not isinstance(source_type, str):
            return "Outro"

        keyword_map = {
            'remux': 'Remux',
            'webdl': 'WEB-DL',
            'webrip': 'WEBRip',
            'web': 'WEB',
            'encode': 'Encode',
            'bdrip': 'BDRip',
            'brrip': 'BRRip',
            'blu-ray': 'Blu-ray',
            'bluray': 'Blu-ray',
            'hdtv': 'HDTV',
            'pdtv': 'PDTV',
            'sdtv': 'SDTV',
            'dvdrip': 'DVDRip',
            'dvdscr': 'DVDScr',
            'hd-dvd': 'HD-DVD',
            'hdrip': 'HDRip',
            'hdtc': 'HDTC',
            'hd-tc': 'HDTC',
            'tc': 'TC',
            'tvrip': 'TVRip',
            'vhsrip': 'VHSRip'
        }

        return keyword_map.get(source_type.lower(), "Outro")

    def get_screens(self, meta):
        screenshot_urls = [
            image.get('raw_url')
            for image in meta.get('image_list', [])
            if image.get('raw_url')
        ]

        return screenshot_urls

    async def edit_desc(self, meta):
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

        base_desc = ""
        if os.path.exists(base_desc_path):
            with open(base_desc_path, 'r', encoding='utf-8') as f:
                base_desc = f.read()

        description_parts = []

        # Adiciona nota sobre a fonte para WEBDLs
        if meta.get('type') == 'WEBDL' and meta.get('service_longname', ''):
            source_note = f"[center][quote]Este lançamento tem como fonte o serviço {meta['service_longname']}[/quote][/center]"
            description_parts.append(source_note)

        description_parts.append(base_desc)

        if self.signature:
            description_parts.append(self.signature)

        with open(final_desc_path, 'w', encoding='utf-8') as descfile:
            final_description = "\n\n".join(filter(None, description_parts))
            descfile.write(final_description)

    def get_3d(self, meta):
        if meta.get('3D'):
            return "Sim"
        else:
            return "Nao"

    def get_resolution(self, meta):
        width, height = "", ""

        if meta.get('is_disc'):
            resolution_str = meta.get('resolution', '')
            try:
                height_num = int(resolution_str.lower().replace('p', ''))
                height = str(height_num)

                width_num = round((16 / 9) * height_num)
                width = str(width_num)
            except (ValueError, TypeError):
                pass

        else:
            try:
                tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])
                video_track = next((t for t in tracks if t.get('@type') == 'Video'), None)
                if video_track:
                    width = video_track.get('Width', '')
                    height = video_track.get('Height', '')
            except (AttributeError, TypeError):
                pass

        return {
            'resolucao_1': width,
            'resolucao_2': height
        }

    def get_tv_info(self, meta):
        tv_info = {
            'tipo': '',
            'temporada': '',
            'temporada_e': '',
            'episodio': ''
        }

        season_num = meta.get('season') or ""
        episode_num = meta.get('episode') or ""

        if episode_num:
            tv_info['tipo'] = 'ep_individual'
            tv_info['temporada_e'] = season_num
            tv_info['episodio'] = episode_num
        elif season_num:
            tv_info['tipo'] = 'completa'
            tv_info['temporada'] = season_num

        return tv_info

    async def _fetch_tracker_data(self, imdb_id, category_id):
        if category_id == '5':
            return None

        if not imdb_id or not category_id:
            return None

        api_url = f"{self.base_url}/ajax.php"
        params = {
            'action': 'upload_imdb',
            'id': imdb_id,
            'cat': category_id
        }

        try:
            response = self.session.get(api_url, params=params, timeout=15)
            response.raise_for_status()

            json_response = response.json()
            if json_response and not json_response.get("error"):
                return json_response
            else:
                error_msg = json_response.get("error", "Erro desconhecido na resposta da API.")
                console.print(f"[bold yellow]Aviso: A API do tracker retornou um erro: {error_msg}[/bold yellow]")
                return None
        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Erro de rede ao buscar dados do tracker: {e}[/bold red]")
            return None
        except ValueError:
            console.print("[bold red]Erro: Não foi possível decodificar a resposta JSON da API do tracker.[/bold red]")
            return None

    async def upload(self, meta, disctype):

        if not await self.validate_credentials(meta):
            console.print(f"[bold red]Upload para {self.tracker} abortado.[/bold red]")
            return

        await COMMON(config=self.config).edit_torrent(meta, self.tracker, self.source_flag)
        await self.edit_desc(meta)
        imdb_id = meta.get('imdb_info', {}).get('imdbID', '')
        category_type = self.get_type(meta)
        if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False):
            anon = 0
        else:
            anon = 1
        tracker_data = await self._fetch_tracker_data(imdb_id, category_type)

        data = {
            'submit': 'true',
            'auth': self.auth_token,
            'type': category_type,
            'imdb_input': imdb_id,
            'adulto': '0',
        }

        if anon == 1:
            data['anonymous'] = '1'

        if tracker_data:
            data['title'] = tracker_data.get('titulo', '')
            data['title_br'] = tracker_data.get('titulo_br', '')
            data['nota_imdb'] = tracker_data.get('nota', '')
            data['year'] = tracker_data.get('ano', '')
            data['diretor'] = tracker_data.get('diretor', '')
            data['idioma_ori'] = tracker_data.get('idioma', '')
            data['sinopse'] = tracker_data.get('sinopse', '')
            data['tags'] = tracker_data.get('generos', '')
            duracao_str = tracker_data.get('duracao') or ''
            data['duracao'] = tracker_data.get('duracao', '')

            if tracker_data.get('capa'):
                data['image'] = f"https://image.tmdb.org/t/p/w500{tracker_data.get('capa')}"
            else:
                 data['image'] = ''

        else:
            details = self.get_details(meta)
            names = self.get_name(meta)
            data.update({
                'title': names.get('title', ''),
                'title_br': names.get('title_br', ''),
                'nota_imdb': details.get('nota_imdb', ''),
                'year': details.get('year', ''),
                'diretor': details.get('diretor', ''),
                'idioma_ori': details.get('idioma_ori', ''),
                'sinopse': meta.get('imdb_info', {}).get('plot', 'Nenhuma sinopse disponível.'),
                'duracao': f"{details.get('duracao', '')} min" if details.get('duracao') else '',
                'tags': meta.get('genres', '').replace(', ', ',').replace(' ', '.').lower(),
                'image': meta.get('image_list', [{}])[0].get('raw_url', '')
            })

        tv_info = self.get_tv_info(meta)
        resolution = self.get_resolution(meta)
        subtitles_info = self.get_subtitles(meta)
        bt_desc = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

        data.update({
            'mediainfo': self.get_file_info(meta),
            'format': self.get_format(meta),
            'audio': self.get_audio(meta),
            'video_c': self.get_video_codec(meta),
            'audio_c': self.get_audio_codec(meta),
            'legenda': subtitles_info.get('legenda', 'Nao'),
            '3d': self.get_3d(meta),
            'resolucao_1': resolution['resolucao_1'],
            'resolucao_2': resolution['resolucao_2'],
            'bitrate': self.get_bitrate(meta),
            'screen[]': self.get_screens(meta),
            'desc': '',
            'especificas': bt_desc,
        })
        if 'subtitles[]' in subtitles_info: data['subtitles[]'] = subtitles_info['subtitles[]']

        if category_type in ['1', '5']:
            data['ntorrent'] = meta.get('name')

            tipo_serie = tv_info.get('tipo')
            if tipo_serie:
                data['tipo'] = tipo_serie
                if tipo_serie == 'completa':
                    data['temporada'] = tv_info.get('temporada', '')
                elif tipo_serie == 'ep_individual':
                    data['temporada_e'] = tv_info.get('temporada_e', '')
                    data['episodio'] = tv_info.get('episodio', '')

            if category_type == '5':
                duracao_min = 0
                try:
                    duracao_apenas_numeros = re.search(r'\d+', data.get('duracao', '0'))
                    if duracao_apenas_numeros:
                        duracao_min = int(duracao_apenas_numeros.group(0))
                except (ValueError, TypeError):
                    pass

                data.update({
                    'releasedate': data.get('year', ''), 'rating': data.get('nota_imdb', ''),
                    'horas': str(duracao_min // 60), 'minutos': str(duracao_min % 60)
                })
        else:
            data['versao'] = self.get_edition(meta)

        if meta.get('debug', False):
            console.print("[yellow]MODO DEBUG ATIVADO. O upload não será realizado.[/yellow]")
            import pprint
            if tracker_data:
                pprint.pprint(tracker_data)
            pprint.pprint(data)
            return

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        if not os.path.exists(torrent_path):
            return

        upload_url = f"{self.base_url}/upload.php"
        with open(torrent_path, 'rb') as torrent_file:
            files = {'file_input': (f"{self.tracker}_placeholder.torrent", torrent_file, "application/x-bittorrent")}

            try:
                response = self.session.post(upload_url, data=data, files=files, timeout=60)

                if response.status_code == 200 and 'torrents.php?id=' in str(response.url):
                    final_url = str(response.url)
                    console.print(f"[bold green]Upload para '{self.tracker}' bem-sucedido! Redirecionado para: {final_url}[/bold green]")

                    id_match = re.search(r'id=(\d+)', final_url)

                    if id_match:
                        torrent_id = id_match.group(1)
                        details_url = f"{self.base_url}/torrents.php?id={torrent_id}"

                        announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
                        await COMMON(config=self.config).add_tracker_torrent(meta, self.tracker, self.source_flag, announce_url, details_url)
                    else:
                        console.print(f"[bold yellow]Redirecionamento para a página do torrent ocorreu, mas não foi possível extrair o ID da URL: {final_url}[/bold yellow]")

                else:
                    console.print(f"[bold red]Falha no upload para {self.tracker}. Status: {response.status_code}, URL: {response.url}[/bold red]")
                    failure_path = f"{self.tracker}_upload_failure_{meta['uuid']}.html"
                    with open(failure_path, "w", encoding="utf-8") as f:
                        f.write(response.text)
                    console.print(f"[yellow]A resposta HTML foi salva em '{failure_path}' para análise.[/yellow]")

            except requests.exceptions.RequestException as e:
                console.print(f"[bold red]Erro de conexão ao fazer upload para {self.tracker}: {e}[/bold red]")
