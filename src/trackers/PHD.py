# -*- coding: utf-8 -*-
import httpx
import langcodes
import os
import re
import requests
import unicodedata
from .COMMON import COMMON
from bs4 import BeautifulSoup
from http.cookiejar import MozillaCookieJar
from langcodes.tag_parser import LanguageTagError
from src.console import console
from src.exceptions import UploadException
from src.languages import process_desc_language


class PHD(COMMON):
    def __init__(self, config):
        super().__init__(config)
        self.tracker = "PHD"
        self.source_flag = "PrivateHD"
        self.banned_groups = [""]
        self.base_url = "https://privatehd.to"
        self.auth_token = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        })
        self.signature = ""

        self.all_lang_map = {
            ("Abkhazian", "abk", "ab"): '1',
            ("Afar", "aar", "aa"): '2',
            ("Afrikaans", "afr", "af"): '3',
            ("Akan", "aka", "ak"): '4',
            ("Albanian", "sqi", "sq"): '5',
            ("Amharic", "amh", "am"): '6',
            ("Arabic", "ara", "ar"): '7',
            ("Aragonese", "arg", "an"): '8',
            ("Armenian", "hye", "hy"): '9',
            ("Assamese", "asm", "as"): '10',
            ("Avaric", "ava", "av"): '11',
            ("Avestan", "ave", "ae"): '12',
            ("Aymara", "aym", "ay"): '13',
            ("Azerbaijani", "aze", "az"): '14',
            ("Bambara", "bam", "bm"): '15',
            ("Bashkir", "bak", "ba"): '16',
            ("Basque", "eus", "eu"): '17',
            ("Belarusian", "bel", "be"): '18',
            ("Bengali", "ben", "bn"): '19',
            ("Bihari languages", "bih", "bh"): '20',
            ("Bislama", "bis", "bi"): '21',
            ("Bokmål, Norwegian", "nob", "nb"): '22',
            ("Bosnian", "bos", "bs"): '23',
            ("Brazilian Portuguese", "por", "pt"): '187',
            ("Breton", "bre", "br"): '24',
            ("Bulgarian", "bul", "bg"): '25',
            ("Burmese", "mya", "my"): '26',
            ("Cantonese", "yue", "zh"): '27',
            ("Catalan", "cat", "ca"): '28',
            ("Central Khmer", "khm", "km"): '29',
            ("Chamorro", "cha", "ch"): '30',
            ("Chechen", "che", "ce"): '31',
            ("Chichewa", "nya", "ny"): '32',
            ("Chinese", "zho", "zh"): '33',
            ("Church Slavic", "chu", "cu"): '34',
            ("Chuvash", "chv", "cv"): '35',
            ("Cornish", "cor", "kw"): '36',
            ("Corsican", "cos", "co"): '37',
            ("Cree", "cre", "cr"): '38',
            ("Croatian", "hrv", "hr"): '39',
            ("Czech", "ces", "cs"): '40',
            ("Danish", "dan", "da"): '41',
            ("Dhivehi", "div", "dv"): '42',
            ("Dutch", "nld", "nl"): '43',
            ("Dzongkha", "dzo", "dz"): '44',
            ("English", "eng", "en"): '45',
            ("Esperanto", "epo", "eo"): '46',
            ("Estonian", "est", "et"): '47',
            ("Ewe", "ewe", "ee"): '48',
            ("Faroese", "fao", "fo"): '49',
            ("Fijian", "fij", "fj"): '50',
            ("Filipino", "fil", "fil"): '189',
            ("Finnish", "fin", "fi"): '51',
            ("French", "fra", "fr"): '52',
            ("Fulah", "ful", "ff"): '53',
            ("Gaelic", "gla", "gd"): '54',
            ("Galician", "glg", "gl"): '55',
            ("Ganda", "lug", "lg"): '56',
            ("Georgian", "kat", "ka"): '57',
            ("German", "deu", "de"): '58',
            ("Greek", "ell", "el"): '59',
            ("Guarani", "grn", "gn"): '60',
            ("Gujarati", "guj", "gu"): '61',
            ("Haitian", "hat", "ht"): '62',
            ("Hausa", "hau", "ha"): '63',
            ("Hebrew", "heb", "he"): '64',
            ("Herero", "her", "hz"): '65',
            ("Hindi", "hin", "hi"): '66',
            ("Hiri Motu", "hmo", "ho"): '67',
            ("Hungarian", "hun", "hu"): '68',
            ("Icelandic", "isl", "is"): '69',
            ("Ido", "ido", "io"): '70',
            ("Igbo", "ibo", "ig"): '71',
            ("Indonesian", "ind", "id"): '72',
            ("Interlingua", "ina", "ia"): '73',
            ("Interlingue", "ile", "ie"): '74',
            ("Inuktitut", "iku", "iu"): '75',
            ("Inupiaq", "ipk", "ik"): '76',
            ("Irish", "gle", "ga"): '77',
            ("Italian", "ita", "it"): '78',
            ("Japanese", "jpn", "ja"): '79',
            ("Javanese", "jav", "jv"): '80',
            ("Kalaallisut", "kal", "kl"): '81',
            ("Kannada", "kan", "kn"): '82',
            ("Kanuri", "kau", "kr"): '83',
            ("Kashmiri", "kas", "ks"): '84',
            ("Kazakh", "kaz", "kk"): '85',
            ("Kikuyu", "kik", "ki"): '86',
            ("Kinyarwanda", "kin", "rw"): '87',
            ("Kirghiz", "kir", "ky"): '88',
            ("Komi", "kom", "kv"): '89',
            ("Kongo", "kon", "kg"): '90',
            ("Korean", "kor", "ko"): '91',
            ("Kuanyama", "kua", "kj"): '92',
            ("Kurdish", "kur", "ku"): '93',
            ("Lao", "lao", "lo"): '94',
            ("Latin", "lat", "la"): '95',
            ("Latvian", "lav", "lv"): '96',
            ("Limburgan", "lim", "li"): '97',
            ("Lingala", "lin", "ln"): '98',
            ("Lithuanian", "lit", "lt"): '99',
            ("Luba-Katanga", "lub", "lu"): '100',
            ("Luxembourgish", "ltz", "lb"): '101',
            ("Macedonian", "mkd", "mk"): '102',
            ("Malagasy", "mlg", "mg"): '103',
            ("Malay", "msa", "ms"): '104',
            ("Malayalam", "mal", "ml"): '105',
            ("Maltese", "mlt", "mt"): '106',
            ("Mandarin", "cmn", "zh"): '107',
            ("Manx", "glv", "gv"): '108',
            ("Maori", "mri", "mi"): '109',
            ("Marathi", "mar", "mr"): '110',
            ("Marshallese", "mah", "mh"): '111',
            ("Mongolian", "mon", "mn"): '112',
            ("Mooré", "mos", "mos"): '188',
            ("Nauru", "nau", "na"): '113',
            ("Navajo", "nav", "nv"): '114',
            ("Ndebele, North", "nde", "nd"): '115',
            ("Ndebele, South", "nbl", "nr"): '116',
            ("Ndonga", "ndo", "ng"): '117',
            ("Nepali", "nep", "ne"): '118',
            ("Northern Sami", "sme", "se"): '119',
            ("Norwegian", "nor", "no"): '120',
            ("Norwegian Nynorsk", "nno", "nn"): '121',
            ("Occitan (post 1500)", "oci", "oc"): '122',
            ("Ojibwa", "oji", "oj"): '123',
            ("Oriya", "ori", "or"): '124',
            ("Oromo", "orm", "om"): '125',
            ("Ossetian", "oss", "os"): '126',
            ("Pali", "pli", "pi"): '127',
            ("Panjabi", "pan", "pa"): '128',
            ("Persian", "fas", "fa"): '129',
            ("Polish", "pol", "pl"): '130',
            ("Portuguese", "por", "pt"): '131',
            ("Pushto", "pus", "ps"): '132',
            ("Quechua", "que", "qu"): '133',
            ("Romanian", "ron", "ro"): '134',
            ("Romansh", "roh", "rm"): '135',
            ("Rundi", "run", "rn"): '136',
            ("Russian", "rus", "ru"): '137',
            ("Samoan", "smo", "sm"): '138',
            ("Sango", "sag", "sg"): '139',
            ("Sanskrit", "san", "sa"): '140',
            ("Sardinian", "srd", "sc"): '141',
            ("Serbian", "srp", "sr"): '142',
            ("Shona", "sna", "sn"): '143',
            ("Sichuan Yi", "iii", "ii"): '144',
            ("Sindhi", "snd", "sd"): '145',
            ("Sinhala", "sin", "si"): '146',
            ("Slovak", "slk", "sk"): '147',
            ("Slovenian", "slv", "sl"): '148',
            ("Somali", "som", "so"): '149',
            ("Sotho, Southern", "sot", "st"): '150',
            ("Spanish", "spa", "es"): '151',
            ("Sundanese", "sun", "su"): '152',
            ("Swahili", "swa", "sw"): '153',
            ("Swati", "ssw", "ss"): '154',
            ("Swedish", "swe", "sv"): '155',
            ("Tagalog", "tgl", "tl"): '156',
            ("Tahitian", "tah", "ty"): '157',
            ("Tajik", "tgk", "tg"): '158',
            ("Tamil", "tam", "ta"): '159',
            ("Tatar", "tat", "tt"): '160',
            ("Telugu", "tel", "te"): '161',
            ("Thai", "tha", "th"): '162',
            ("Tibetan", "bod", "bo"): '163',
            ("Tigrinya", "tir", "ti"): '164',
            ("Tongan", "ton", "to"): '165',
            ("Tsonga", "tso", "ts"): '166',
            ("Tswana", "tsn", "tn"): '167',
            ("Turkish", "tur", "tr"): '168',
            ("Turkmen", "tuk", "tk"): '169',
            ("Twi", "twi", "tw"): '170',
            ("Uighur", "uig", "ug"): '171',
            ("Ukrainian", "ukr", "uk"): '172',
            ("Urdu", "urd", "ur"): '173',
            ("Uzbek", "uzb", "uz"): '174',
            ("Venda", "ven", "ve"): '175',
            ("Vietnamese", "vie", "vi"): '176',
            ("Volapük", "vol", "vo"): '177',
            ("Walloon", "wln", "wa"): '178',
            ("Welsh", "cym", "cy"): '179',
            ("Western Frisian", "fry", "fy"): '180',
            ("Wolof", "wol", "wo"): '181',
            ("Xhosa", "xho", "xh"): '182',
            ("Yiddish", "yid", "yi"): '183',
            ("Yoruba", "yor", "yo"): '184',
            ("Zhuang", "zha", "za"): '185',
            ("Zulu", "zul", "zu"): '186',
        }
        self.lang_map = {}
        for key_tuple, lang_id in self.all_lang_map.items():
            lang_name, code3, code2 = key_tuple

            # Adiciona o nome completo do idioma em minúsculas como chave
            self.lang_map[lang_name.lower()] = lang_id

            # Adiciona o código de 3 letras como chave
            if code3:
                self.lang_map[code3.lower()] = lang_id

            # Adiciona o código de 2 letras como chave
            if code2:
                self.lang_map[code2.lower()] = lang_id

    def assign_media_properties(self, meta):
        self.imdb_id = meta['imdb_info']['imdbID']
        self.tmdb_id = meta['tmdb']
        self.category = meta['category']
        self.season = meta.get('season', '')
        self.episode = meta.get('episode', '')

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
            upload_page_url = f"{self.base_url}/upload"
            response = self.session.get(upload_page_url, timeout=10, allow_redirects=True)

            if 'login' in str(response.url):
                console.print(f"[bold red]Falha na validação do {self.tracker}. O cookie parece estar expirado ou é inválido.[/bold red]")
                return False

            auth_match = re.search(r'name="_token" content="([^"]+)"', response.text)

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

    async def search_existing(self, meta, disctype):
        await self.validate_credentials(meta)
        return []

    async def get_media_code(self, meta):
        self.assign_media_properties(meta)
        await self.validate_credentials(meta)
        self.media_code = ''

        if self.category == 'MOVIE':
            category_path = 'movie'
            search_category = 'movies'
        elif self.category == 'TV':
            category_path = 'tv'
            search_category = 'tv-shows'
        else:
            console.print(f"[bold red]Categoria desconhecida: {self.category}[/bold red]")
            return None

        search_url = f"https://privatehd.to/{search_category}?search=&imdb={self.imdb_id}"

        try:
            response = self.session.get(search_url, timeout=20)
            response.raise_for_status()

            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')

            media_link = soup.find('a', href=re.compile(rf'/{category_path}/\d+'))

            if media_link:
                href = media_link.get('href')
                match = re.search(rf'/{category_path}/(\d+)-', href)
                self.media_code = match.group(1) if match else None
                console.print(f"Media code is {self.media_code}")
            else:
                console.print(f"No code found for {self.imdb_id} in {search_url}")

        except Exception as e:
            console.print(f"[bold red]Error trying to fetch media code for tracker {self.tracker}: {e}[/bold red]")

        return bool(self.media_code)

    async def upload(self, meta, disctype):
        lang_info = await self.get_lang(meta)
        if await self.get_media_code(meta):
            pass
        else:
            raise UploadException('no media code')

        await self.validate_credentials(meta)
        self.assign_media_properties(meta)

        if self.category == 'MOVIE':
            type_id = '1'
        if self.category == 'TV':
            type_id = '2'

        data1 = {}

        data1.update({
            '_token': self.auth_token,
            'type_id': type_id,
            'movie_id': self.media_code,
            'media_info': await self.get_file_info(meta),
        })

        if not meta.get('debug', False):
            await COMMON(config=self.config).edit_torrent(meta, self.tracker, self.source_flag)
            upload_url = f"{self.base_url}/upload/{self.category.lower()}"

            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
            with open(torrent_path, 'rb') as torrent_file:
                files = {'torrent_file': (os.path.basename(torrent_path), torrent_file, 'application/x-bittorrent')}

                try:
                    response = self.session.post(upload_url, data=data1, files=files, timeout=120)

                    if response.status_code == 302:
                        announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
                        await COMMON(config=self.config).add_tracker_torrent(meta, self.tracker, announce_url)

                except requests.exceptions.RequestException as e:
                    final_message = f"[bold red]Erro de conexão ao fazer upload para {self.tracker}: {e}[/bold red]"

        data2 = {}
        data2.update({
            '_token': self.auth_token,
            'info_hash': meta['infohash'],
            'torrent_id': '',  # empty
            'type_id': type_id,
            'task_id': '',
            'file_name': meta['name'],
            'anon_upload': '',
            'description': '',
            'qqfile': '',  # empty
            'screenshots[]': '',
            'rip_type_id': '3',
            'video_quality_id': '3',
            'video_resolution': '',  # can be empty it seems
            'movie_id': self.media_code,
            'languages[]': lang_info.get('languages[]'),  # audio languages
            'subtitles[]': lang_info.get('subtitles[]'),  # subtitles languages
            'media_info': await self.get_file_info(meta),
        })

        if not meta.get('debug', False):
            await COMMON(config=self.config).edit_torrent(meta, self.tracker, self.source_flag)
            upload_url = ''

            try:
                response = self.session.post(upload_url, data=data2, timeout=120)

                if response.status_code == 302:
                    announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
                    await COMMON(config=self.config).add_tracker_torrent(meta, self.tracker, announce_url)

                else:
                    failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload.html"
                    with open(failure_path, "w", encoding="utf-8") as f:
                        f.write(response.text)
                    final_message = f"""[bold red]Falha no upload para {self.tracker}. Status: {response.status_code}, URL: {response.url}[/bold red].
                                        [yellow]A resposta HTML foi salva em '{failure_path}' para análise.[/yellow]"""

            except requests.exceptions.RequestException as e:
                final_message = f"[bold red]Erro de conexão ao fazer upload para {self.tracker}: {e}[/bold red]"

        if meta.get('debug', False):
            console.print(data2)
            final_message = 'Debug mode enabled, not uploading.'

        meta['tracker_status'][self.tracker]['status_message'] = final_message

    async def get_file_info(self, meta):
        info_file_path = ""
        if meta.get('is_disc') == 'BDMV':
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/BD_SUMMARY_00.txt"
        else:
            info_file_path = f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MEDIAINFO_CLEANPATH.txt"

        if os.path.exists(info_file_path):
            with open(info_file_path, 'r', encoding='utf-8') as f:
                return f.read()

    async def get_lang(self, meta):
        if not meta.get('subtitle_languages') or meta.get('audio_languages'):
            await process_desc_language(meta, desc=None, tracker=self.tracker)

        found_subs_strings = meta.get('subtitle_languages', [])
        subtitle_ids = set()
        for lang_str in found_subs_strings:
            target_id = self.lang_map.get(lang_str.lower())
            if target_id:
                subtitle_ids.add(target_id)
        final_subtitle_ids = sorted(list(subtitle_ids))

        found_audio_strings = meta.get('audio_languages', [])
        audio_ids = set()
        for lang_str in found_audio_strings:
            target_id = self.lang_map.get(lang_str.lower())
            if target_id:
                audio_ids.add(target_id)
        final_audio_ids = sorted(list(audio_ids))

        return {
            'subtitles[]': final_subtitle_ids,
            'languages[]': final_audio_ids
        }

    async def edit_desc(self, meta):
        base_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        final_desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

        base_desc = ""
        if os.path.exists(base_desc_path):
            with open(base_desc_path, 'r', encoding='utf-8') as f:
                base_desc = f.read()

        description_parts = []

        description_parts.append(base_desc)

        custom_description_header = self.config['DEFAULT'].get('custom_description_header', '')
        if custom_description_header:
            description_parts.append(custom_description_header + "\n")

        if self.signature:
            description_parts.append(self.signature)

        with open(final_desc_path, 'w', encoding='utf-8') as descfile:
            final_description = "\n".join(filter(None, description_parts))
            descfile.write(final_description)

    def get_resolution(self, meta):
        width, height = "", ""

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
            'resolucaow': width,
            'resolucaoh': height
        }

    async def data_prep(self, meta, disctype):
        await self.validate_credentials(meta)
        await self.edit_desc(meta)

        desc_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"

        data = {
            'submit': 'true',
            'auth': self.auth_token,
        }

        # Common data MOVIE/TV
        if self.category in ('MOVIE', 'TV'):
            data.update({
            })

        # Anon
        anon = not (meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False))
        if anon:
            data['anonymous'] = '1'

        return data