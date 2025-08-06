# -*- coding: utf-8 -*-
import os
import re
import requests
import asyncio
import hashlib
import bencodepy
from .COMMON import COMMON
from bs4 import BeautifulSoup
from http.cookiejar import MozillaCookieJar
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

            self.lang_map[lang_name.lower()] = lang_id

            if code3:
                self.lang_map[code3.lower()] = lang_id

            if code2:
                self.lang_map[code2.lower()] = lang_id

    def assign_media_properties(self, meta):
        self.imdb_id = meta['imdb_info']['imdbID']
        self.tmdb_id = meta['tmdb']
        self.category = meta['category']
        self.season = meta.get('season', '')
        self.episode = meta.get('episode', '')

    def get_resolution(self, meta):
        resolution = ''
        if not meta.get('is_disc') == 'BDMV':
            video_mi = meta['mediainfo']['media']['track'][1]
            resolution = f"{video_mi['Width']}x{video_mi['Height']}"

        return resolution

    async def validate_credentials(self, meta):
        cookie_file = os.path.abspath(f"{meta['base_dir']}/data/cookies/{self.tracker}.txt")
        if not os.path.exists(cookie_file):
            console.print(f"[bold red]Cookie file for {self.tracker} not found: {cookie_file}[/bold red]")
            return False

        try:
            jar = MozillaCookieJar(cookie_file)
            jar.load(ignore_discard=True, ignore_expires=True)
            self.session.cookies = jar
        except Exception as e:
            console.print(f"[bold red]Error loading cookie file. Please check if the format is correct. Error:{e}[/bold red]")
            return False

        try:
            upload_page_url = f"{self.base_url}/upload"
            response = self.session.get(upload_page_url, timeout=10, allow_redirects=True)

            if 'login' in str(response.url):
                console.print(f"[bold red]{self.tracker} validation failed. The cookie appears to be expired or invalid.[/bold red]")
                return False

            auth_match = re.search(r'name="_token" content="([^"]+)"', response.text)

            if auth_match:
                self.auth_token = auth_match.group(1)
                return True
            else:
                console.print(f"[bold red]{self.tracker} validation failed. Could not find 'auth' token on upload page.[/bold red]")
                console.print("[yellow]This can happen if the site structure has changed or if the login failed silently..[/yellow]")
                with open(f"{self.tracker}_auth_failure_{meta['uuid']}.html", "w", encoding="utf-8") as f:
                    f.write(response.text)
                console.print(f"[yellow]The server response was saved to '{self.tracker}_auth_failure_{meta['uuid']}.html' for analysis.[/yellow]")
                return False

        except Exception as e:
            console.print(f"[bold red]Error validating credentials for {self.tracker}: {e}[/bold red]")
            return False

    def get_rip_type(self, meta):
        source_type = meta.get('type')

        keyword_map = {
            'bdrip': '1',
            'encode': '2',
            'disc': '3',
            'hdrip': '6',
            'hdtv': '7',
            'webdl': '12',
            'webrip': '13',
            'remux': '14',
        }

        return keyword_map.get(source_type.lower())

    def get_video_quality(self, meta):
        resolution = meta.get('resolution')

        keyword_map = {
            '1080i': '7',
            '1080p': '3',
            '2160p': '6',
            '4320p': '8',
            '720p': '2',
        }

        return keyword_map.get(resolution)

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
        if self.category == 'TV':
            category_path = 'tv'
            search_category = 'tv-shows'

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
                console.print(f"Media code is {self.media_code}")  # delete after finished
            else:
                console.print(f"No code found for {self.imdb_id} in {search_url}")

        except Exception as e:
            console.print(f"[bold red]Error trying to fetch media code for tracker {self.tracker}: {e}[/bold red]")

        return bool(self.media_code)

    async def upload(self, meta, disctype):
        lang_info = await self.get_lang(meta)
        if not await self.get_media_code(meta):
            raise UploadException('no media code')  # improve message

        await self.validate_credentials(meta)
        self.assign_media_properties(meta)

        type_id = ''
        if self.category == 'MOVIE':
            type_id = '1'
        if self.category == 'TV':
            type_id = '2'

        final_message = ""

        data1 = {
            '_token': self.auth_token,
            'type_id': type_id,
            'movie_id': self.media_code,
            'media_info': await self.get_file_info(meta),
        }

        data2 = {
            '_token': self.auth_token,
            'torrent_id': '',
            'type_id': type_id,
            'file_name': meta.get('name'),
            'anon_upload': '',
            'description': '',  # Couldn't find a way to properly handle the description while following the rules
            'qqfile': '',  # I'm not sure what this does, it doesn't seem necessary
            'screenshots[]': '684049',  # placeholder, add img hosting later
            'rip_type_id': self.get_rip_type(meta),
            'video_quality_id': self.get_video_quality(meta),
            'video_resolution': self.get_resolution(meta),
            'movie_id': self.media_code,
            'languages[]': lang_info.get('languages[]'),
            'subtitles[]': lang_info.get('subtitles[]'),
            'media_info': await self.get_file_info(meta),
            }

        anon = not (meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False))
        if anon:
            data2.update({
                'anon_upload': '1'
            })

        if not meta.get('debug', False):
            try:
                await COMMON(config=self.config).edit_torrent(meta, self.tracker, self.source_flag)
                upload_url_step1 = f"{self.base_url}/upload/{self.category.lower()}"
                torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

                with open(torrent_path, 'rb') as torrent_file:
                    files = {'torrent_file': (os.path.basename(torrent_path), torrent_file, 'application/x-bittorrent')}
                    response1 = self.session.post(upload_url_step1, data=data1, files=files, timeout=120, allow_redirects=False)

                if response1.status_code == 302 and 'Location' in response1.headers:
                    await asyncio.sleep(5)
                    redirect_url = response1.headers['Location']

                    match = re.search(r'/(\d+)$', redirect_url)
                    if not match:
                        raise UploadException(f"Could not extract 'task_id' from redirect URL:{redirect_url}")

                    task_id = match.group(1)

                    with open(torrent_path, "rb") as f:
                        torrent_data = bencodepy.decode(f.read())
                        info = bencodepy.encode(torrent_data[b'info'])
                        new_info_hash = hashlib.sha1(info).hexdigest()

                    data2.update({
                        'info_hash': new_info_hash,
                        'task_id': task_id,
                    })
                    upload_url_step2 = redirect_url
                    response2 = self.session.post(upload_url_step2, data=data2, timeout=120)

                    if response2.status_code in [200, 302]:
                        announce_url = self.config['TRACKERS'][self.tracker].get('announce_url')
                        await COMMON(config=self.config).add_tracker_torrent(meta, self.tracker, self.source_flag, announce_url, upload_url_step2)
                        final_message = f"[bold green]{meta['name']} was successfully sent to {self.tracker}[/bold green]"  # change to print the torrent url later
                    else:
                        failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload_Step2.html"
                        with open(failure_path, "w", encoding="utf-8") as f:
                            f.write(response2.text)
                        final_message = f"""[bold red]Step 2 of upload failed to {self.tracker}. Status: {response2.status_code}, URL: {response2.url}[/bold red].
                                            [yellow]The HTML response was saved to '{failure_path}' for analysis.[/yellow]"""
                else:
                    failure_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]FailedUpload_Step1.html"
                    with open(failure_path, "w", encoding="utf-8") as f:
                        f.write(response1.text)
                    final_message = f"""[bold red]Step 1 of upload failed to {self.tracker}. Status: {response1.status_code}, URL: {response1.url}[/bold red].
                                        [yellow]The HTML response was saved to '{failure_path}' for analysis.[/yellow]"""

            except requests.exceptions.RequestException as e:
                final_message = f"[bold red]Connection error while uploading to {self.tracker}: {e}[/bold red]"
            except UploadException as e:
                final_message = f"[bold red]Upload error: {e}[/bold red]"
            except Exception as e:
                final_message = f"[bold red]An unexpected error occurred while uploading to {self.tracker}: {e}[/bold red]"

        else:
            console.print(data1)
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
