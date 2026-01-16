# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import glob
import json
import os
import re
from pathlib import Path
from typing import Any, Optional, Union, cast
from urllib.parse import urlparse

import httpx
import requests
from bs4 import BeautifulSoup
from unidecode import unidecode

from src.console import console
from src.cookie_auth import CookieValidator
from src.exceptions import *  # noqa E403
from src.trackers.COMMON import COMMON

Meta = dict[str, Any]
Config = dict[str, Any]


class PTER:

    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.tracker = 'PTER'
        self.source_flag = 'PTER'
        self.passkey = str(config['TRACKERS']['PTER'].get('passkey', '')).strip()
        self.username = str(config['TRACKERS']['PTER'].get('username', '')).strip()
        self.password = str(config['TRACKERS']['PTER'].get('password', '')).strip()
        self.rehost_images = bool(config['TRACKERS']['PTER'].get('img_rehost', False))
        self.ptgen_api = str(config['TRACKERS']['PTER'].get('ptgen_api', '')).strip()

        self.ptgen_retry = 3
        self.signature: Optional[str] = None
        self.banned_groups: list[str] = [""]

        self.cookie_validator = CookieValidator(config)

    def _extract_auth_token(self, text: str, pattern: str) -> str:
        match = re.search(pattern, text)
        if match is None:
            raise LoginException("Unable to locate auth token for Pterimg.")  # noqa: F405
        return match.group(1)

    async def validate_credentials(self, meta: Meta) -> bool:
        vcookie = await self.validate_cookies(meta)
        if vcookie is not True:
            console.print('[red]Failed to validate cookies. Please confirm that the site is up and your passkey is valid.')
            return False
        return True

    async def validate_cookies(self, meta: Meta) -> bool:
        common = COMMON(config=self.config)
        url = "https://pterclub.com"
        cookiefile = f"{meta['base_dir']}/data/cookies/PTER.txt"
        if os.path.exists(cookiefile):
            with requests.Session() as session:
                cookies = await common.parseCookieFile(cookiefile)
                cast(Any, session.cookies).update(cookies)
                resp = session.get(url=url, timeout=30)

                return resp.text.find('''<a href="#" data-url="logout.php" id="logout-confirm">''') != -1
        else:
            console.print("[bold red]Missing Cookie File. (data/cookies/PTER.txt)")
            return False

    async def search_existing(self, meta: Meta, disctype: str) -> Union[list[str], bool]:
        dupes: list[str] = []
        common = COMMON(config=self.config)
        cookiefile = f"{meta['base_dir']}/data/cookies/PTER.txt"
        if not os.path.exists(cookiefile):
            console.print("[bold red]Missing Cookie File. (data/cookies/PTER.txt)")
            return False
        cookies = await common.parseCookieFile(cookiefile)
        imdb_id = int(meta.get('imdb_id', 0) or 0)
        imdb = f"tt{meta.get('imdb', '')}" if imdb_id != 0 else ""
        source = await self.get_type_medium_id(meta)
        search_url = f"https://pterclub.com/torrents.php?search={imdb}&incldead=0&search_mode=0&source{source}=1"

        try:
            async with httpx.AsyncClient(cookies=cookies, timeout=10.0) as client:
                response = await client.get(search_url)

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'lxml')
                    rows = soup.select('table.torrents > tr:has(table.torrentname)')
                    for row in rows:
                        text = row.select_one('a[href^="details.php?id="]')
                        if text is not None:
                            release_value = text.attrs.get('title', '')
                            release = str(release_value)
                            if release:
                                dupes.append(release)
                else:
                    console.print(f"[bold red]HTTP request failed. Status: {response.status_code}")

        except httpx.TimeoutException:
            console.print("[bold red]Request timed out while searching for existing torrents.")
        except httpx.RequestError as e:
            console.print(f"[bold red]An error occurred while making the request: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            console.print_exception()

        return dupes

    async def get_type_category_id(self, meta: Meta) -> str:
        cat_id = "EXIT"
        category = str(meta.get('category', ''))

        if category == 'MOVIE':
            cat_id = '401'

        if category == 'TV':
            cat_id = '404'
        genres_value = meta.get("genres", "")
        genres = ', '.join(cast(list[str], genres_value)) if isinstance(genres_value, list) else str(genres_value)
        keywords_value = meta.get("keywords", "")
        keywords = ', '.join(cast(list[str], keywords_value)) if isinstance(keywords_value, list) else str(keywords_value)
        if 'documentary' in genres.lower() or 'documentary' in keywords.lower():
            cat_id = '402'

        if 'animation' in genres.lower() or 'animation' in keywords.lower():
            cat_id = '403'

        return cat_id

    async def get_area_id(self, meta: Meta) -> int:

        area_id = 8
        area_map = {  # To do
            "中国大陆": 1, "中国香港": 2, "中国台湾": 3, "美国": 4, "日本": 6, "韩国": 5,
            "印度": 7, "法国": 4, "意大利": 4, "德国": 4, "西班牙": 4, "葡萄牙": 4,
            "英国": 4, "阿根廷": 8, "澳大利亚": 4, "比利时": 4,
            "巴西": 8, "加拿大": 4, "瑞士": 4, "智利": 8,
        }
        ptgen = cast(dict[str, Any], meta.get('ptgen', {}))
        regions_value = ptgen.get("region", [])
        regions = cast(list[str], regions_value) if isinstance(regions_value, list) else []
        for area in area_map:
            if area in regions:
                return area_map[area]
        return area_id

    async def get_type_medium_id(self, meta: Meta) -> str:
        medium_id = "EXIT"
        # 1 = UHD Discs
        if meta.get('is_disc', '') in ("BDMV", "HD DVD"):
            medium_id = '1' if meta['resolution'] == '2160p' else '2'  # BD Discs

        if meta.get('is_disc', '') == "DVD":
            medium_id = '7'

        # 4 = HDTV
        if meta.get('type', '') == "HDTV":
            medium_id = '4'

        # 6 = Encode
        if meta.get('type', '') in ("ENCODE", "WEBRIP"):
            medium_id = '6'

        # 3 = Remux
        if meta.get('type', '') == "REMUX":
            medium_id = '3'

        # 5 = WEB-DL
        if meta.get('type', '') == "WEBDL":
            medium_id = '5'

        return medium_id

    async def edit_desc(self, meta: Meta) -> None:
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", encoding='utf-8') as base_file:
            base = base_file.read()
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as descfile:
            from src.bbcode import BBCODE
            from src.trackers.COMMON import COMMON
            common = COMMON(config=self.config)

            if int(meta.get('imdb_id', 0) or 0) != 0:
                ptgen = await common.ptgen(meta, self.ptgen_api, self.ptgen_retry)
                if ptgen.strip() != '':
                    descfile.write(ptgen)

            bbcode = BBCODE()
            if meta.get('discs', []) != []:
                discs = cast(list[dict[str, Any]], meta.get('discs', []))
                for each in discs:
                    if each['type'] == "BDMV":
                        descfile.write(f"[hide=BDInfo]{each['summary']}[/hide]\n")
                        descfile.write("\n")
                        pass
                    if each['type'] == "DVD":
                        descfile.write(f"{each['name']}:\n")
                        descfile.write(f"[hide=mediainfo][{each['vob_mi']}[/hide] [hide=mediainfo][{each['ifo_mi']}[/hide]\n")
                        descfile.write("\n")
            else:
                with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", encoding='utf-8') as mi_file:
                    mi = mi_file.read()
                descfile.write(f"[hide=mediainfo]{mi}[/hide]")
                descfile.write("\n")
            desc = base
            desc = bbcode.convert_code_to_quote(desc)
            desc = bbcode.convert_spoiler_to_hide(desc)
            desc = bbcode.convert_comparison_to_centered(desc, 1000)
            desc = desc.replace('[img]', '[img]')
            desc = re.sub(r"(\[img=\d+)]", "[img]", desc, flags=re.IGNORECASE)
            descfile.write(desc)

            if self.rehost_images is True:
                console.print("[green]Rehosting Images...")
                images = await self.pterimg_upload(meta)
                if len(images) > 0:
                    descfile.write("[center]")
                    for each in range(len(images[:int(meta['screens'])])):
                        web_url = images[each]['web_url']
                        img_url = images[each]['img_url']
                        descfile.write(f"[url={web_url}][img]{img_url}[/img][/url]")
                    descfile.write("[/center]")
            else:
                images = cast(list[dict[str, Any]], meta.get('image_list', []))
                if len(images) > 0:
                    descfile.write("[center]")
                    for each in range(len(images[:int(meta['screens'])])):
                        web_url = images[each]['web_url']
                        img_url = images[each]['img_url']
                        descfile.write(f"[url={web_url}][img]{img_url}[/img][/url]")
                    descfile.write("[/center]")

            if self.signature is not None:
                descfile.write("\n\n")
                descfile.write(self.signature)
            descfile.close()

    async def get_auth_token(self, meta: Meta) -> str:
        if not os.path.exists(f"{meta['base_dir']}/data/cookies"):
            Path(f"{meta['base_dir']}/data/cookies").mkdir(parents=True, exist_ok=True)
        cookiefile = f"{meta['base_dir']}/data/cookies/Pterimg.json"
        with requests.Session() as session:
            loggedIn = False
            r: Optional[requests.Response] = None
            if os.path.exists(cookiefile):
                self.cookie_validator._load_cookies_secure(session, cookiefile, self.tracker)  # pyright: ignore[reportPrivateUsage]
                r = session.get("https://s3.pterclub.com", timeout=30)
                loggedIn = await self.validate_login(r)
            else:
                console.print("[yellow]Pterimg Cookies not found. Creating new session.")
            if loggedIn is True:
                if r is None:
                    raise LoginException("Failed to refresh Pterimg session.")  # noqa: F405
                auth_token = self._extract_auth_token(r.text, r'auth_token.*?"(\w+)"')
            else:
                data = {
                    'login-subject': self.username,
                    'password': self.password,
                    'keep-login': 1
                }
                r = session.get("https://s3.pterclub.com", timeout=30)
                data['auth_token'] = self._extract_auth_token(r.text, r'auth_token.*?"(\w+)"')
                loginresponse = session.post(url='https://s3.pterclub.com/login', data=data, timeout=30)
                if not loginresponse.ok:
                    raise LoginException("Failed to login to Pterimg. ")  # noqa #F405
                auth_token = self._extract_auth_token(loginresponse.text, r'auth_token = *?"(\w+)"')
                self.cookie_validator._save_cookies_secure(session.cookies, cookiefile)  # pyright: ignore[reportPrivateUsage]

        return auth_token

    async def validate_login(self, response: requests.Response) -> bool:
        loggedIn = response.text.find('''<a href="https://s3.pterclub.com/logout/?''') != -1
        return loggedIn

    async def pterimg_upload(self, meta: Meta) -> list[dict[str, str]]:
        images = glob.glob(f"{meta['base_dir']}/tmp/{meta['uuid']}/{meta['filename']}-*.png")
        url = 'https://s3.pterclub.com'
        image_list: list[dict[str, str]] = []
        data: dict[str, Any] = {
            'type': 'file',
            'action': 'upload',
            'nsfw': 0,
            'auth_token': await self.get_auth_token(meta)
        }
        cookiefile = f"{meta['base_dir']}/data/cookies/Pterimg.json"
        with requests.Session() as session:
            if os.path.exists(cookiefile):
                self.cookie_validator._load_cookies_secure(session, cookiefile, self.tracker)  # pyright: ignore[reportPrivateUsage]
                for image_path in images:
                    with open(image_path, 'rb') as f:
                        files = {'source': f}
                        req = session.post(f'{url}/json', data=data, files=files, timeout=60)

                        res: Any = None
                        try:
                            res = req.json()
                        except json.decoder.JSONDecodeError:
                            res = None

                        message = None
                        if isinstance(res, dict):
                            res_dict = cast(dict[str, Any], res)
                            error = cast(dict[str, Any], res_dict.get('error', {}))
                            message = error.get('message')
                        if not message:
                            message = (req.reason or '').strip() or (req.text or '').strip()

                        if not req.ok:
                            if message in ('重复上传', 'Duplicated upload'):
                                continue
                            raise Exception(f'HTTP {req.status_code}, reason: {message}')

                        if not isinstance(res, dict):
                            raise ValueError('Unexpected response payload while uploading to Pterimg.')
                        res_dict = cast(dict[str, Any], res)
                        image_data = res_dict.get('image')
                        if not isinstance(image_data, dict):
                            raise ValueError('Missing image data in Pterimg response.')
                        image_data_dict = cast(dict[str, Any], image_data)
                        image_url = image_data_dict.get('url')
                        if not isinstance(image_url, str):
                            raise ValueError('Missing image url in Pterimg response.')
                        image_dict = {
                            'web_url': image_url,
                            'img_url': image_url,
                        }
                        image_list.append(image_dict)
        return image_list

    async def edit_name(self, meta: Meta) -> str:
        pter_name = str(meta.get('name', ''))

        remove_list = ['Dubbed', 'Dual-Audio']
        for each in remove_list:
            pter_name = pter_name.replace(each, '')

        pter_name = pter_name.replace(str(meta.get("aka", '')), '')
        pter_name = pter_name.replace('PQ10', 'HDR')

        if meta.get('type') == 'WEBDL' and meta.get('has_encode_settings', False) is True:
            pter_name = pter_name.replace('H.264', 'x264')

        return pter_name

    async def is_zhongzi(self, meta: Meta) -> Optional[str]:
        if meta.get('is_disc', '') != 'BDMV':
            mi = cast(dict[str, Any], meta.get('mediainfo', {}))
            media = cast(dict[str, Any], mi.get('media', {}))
            tracks = cast(list[dict[str, Any]], media.get('track', []))
            for track in tracks:
                if track['@type'] == "Text":
                    language = track.get('Language')
                    if language == "zh":
                        return 'yes'
        else:
            bdinfo = cast(dict[str, Any], meta.get('bdinfo', {}))
            subtitles = cast(list[str], bdinfo.get('subtitles', []))
            for language in subtitles:
                if language == "Chinese":
                    return 'yes'
        return None

    async def upload(self, meta: Meta, disctype: str) -> bool:

        common = COMMON(config=self.config)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag)

        desc_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        if not os.path.exists(desc_file):
            await self.edit_desc(meta)

        anon = 'no' if meta.get('anon') == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False) else 'yes'

        pter_name = await self.edit_name(meta)

        mi_path = (
            f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if meta['bdinfo'] is not None
            else f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"
        )
        with open(mi_path, encoding='utf-8') as mi_dump:
            _ = mi_dump.read()
        with open(desc_file, encoding='utf-8') as desc_handle:
            pter_desc = desc_handle.read()
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"

        with open(torrent_path, 'rb') as torrentFile:
            filelist = cast(list[Any], meta.get('filelist', []))
            if len(filelist) == 1:
                torrentFileName = unidecode(os.path.basename(str(meta.get('video', ''))).replace(' ', '.'))
            else:
                torrentFileName = unidecode(os.path.basename(str(meta.get('path', ''))).replace(' ', '.'))
            files = {
                'file': (f"{torrentFileName}.torrent", torrentFile, "application/x-bittorent"),
            }

            # use chinese small_descr
            ptgen = cast(dict[str, Any], meta.get('ptgen', {}))
            trans_title = cast(list[str], ptgen.get("trans_title", []))
            genres = cast(list[str], ptgen.get("genre", []))
            if trans_title != ['']:
                small_descr = ''
                for title_ in trans_title:
                    small_descr += f'{title_} / '
                genre_value = genres[0] if genres else ''
                small_descr += "| 类别:" + genre_value
                small_descr = small_descr.replace('/ |', '|')
            else:
                small_descr = str(meta.get('title', ''))
            data: dict[str, Any] = {
                "name": pter_name,
                "small_descr": small_descr,
                "descr": pter_desc,
                "type": await self.get_type_category_id(meta),
                "source_sel": await self.get_type_medium_id(meta),
                "team_sel": await self.get_area_id(meta),
                "uplver": anon,
                "zhongzi": await self.is_zhongzi(meta)
            }

            if meta.get('personalrelease', False) is True:
                data["pr"] = "yes"

            url = "https://pterclub.com/takeupload.php"

            # Submit
            if meta.get('debug'):
                console.print(url)
                console.print(data)
                meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
                await common.create_torrent_for_upload(meta, f"{self.tracker}" + "_DEBUG", f"{self.tracker}" + "_DEBUG", announce_url="https://fake.tracker")
                return True  # Debug mode - simulated success
            else:
                cookiefile = f"{meta['base_dir']}/data/cookies/PTER.txt"
                if os.path.exists(cookiefile):
                    with requests.Session() as session:
                        cookies = await common.parseCookieFile(cookiefile)
                        cast(Any, session.cookies).update(cookies)
                        up = session.post(url=url, data=data, files=files, timeout=30)

                        if up.url.startswith("https://pterclub.com/details.php?id="):
                            console.print(f"[green]Uploaded to: [yellow]{up.url.replace('&uploaded=1', '')}[/yellow][/green]")
                            id_match = re.search(r"(id=)(\d+)", urlparse(up.url).query)
                            if id_match is None:
                                raise UploadException("Upload succeeded but torrent id was not present in the redirect URL.", 'red')  # noqa: F405
                            torrent_id = id_match.group(2)
                            await self.download_new_torrent(torrent_id, torrent_path)
                            meta['tracker_status'][self.tracker]['status_message'] = up.url.replace('&uploaded=1', '')
                            meta['tracker_status'][self.tracker]['torrent_id'] = torrent_id
                            return True
                        else:
                            console.print(data)
                            console.print("\n\n")
                            raise UploadException(f"Upload to Pter Failed: result URL {up.url} ({up.status_code}) was not expected", 'red')  # noqa #F405
        return False

    async def download_new_torrent(self, id: str, torrent_path: str) -> None:
        download_url = f"https://pterclub.com/download.php?id={id}&passkey={self.passkey}"
        r = requests.get(url=download_url, timeout=30)
        if r.status_code == 200:
            with open(torrent_path, "wb") as tor:
                tor.write(r.content)
        else:
            console.print("[red]There was an issue downloading the new .torrent from pter")
            console.print(r.text)
