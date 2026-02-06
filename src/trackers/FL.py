# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import glob
import os
import pickle  # nosec B403 - legacy cookie migration
import re
from typing import Any, Optional, cast

import aiofiles
import cli_ui
import httpx
from bs4 import BeautifulSoup
from unidecode import unidecode

from src.console import console
from src.cookie_auth import CookieValidator
from src.exceptions import *  # noqa F403
from src.trackers.COMMON import COMMON, get_process_executor


def _download_fl_torrent_worker(cookies: dict[str, str], torrent_id: str, torrent_path: str) -> None:
    download_url = f"https://filelist.io/download.php?id={torrent_id}"
    os.makedirs(os.path.dirname(torrent_path), exist_ok=True)
    with httpx.Client(cookies=cookies, timeout=30.0) as client:
        response = client.get(url=download_url)
    if response.status_code != 200:
        raise ValueError("There was an issue downloading the new .torrent from FL")
    with open(torrent_path, "wb") as tor:
        tor.write(response.content)


class FL:

    def __init__(self, config: dict[str, Any]) -> None:
        self.config: dict[str, Any] = config
        self.tracker = 'FL'
        self.source_flag = 'FL'
        tracker_cfg = config['TRACKERS'][self.tracker]
        self.username: str = str(tracker_cfg.get('username', '')).strip()
        self.password: str = str(tracker_cfg.get('password', '')).strip()
        fltools_raw = tracker_cfg.get('fltools', {})
        self.fltools: dict[str, Any] = cast(dict[str, Any], fltools_raw) if isinstance(fltools_raw, dict) else {}
        uploader_name_raw = tracker_cfg.get('uploader_name')
        self.uploader_name: Optional[str] = str(uploader_name_raw) if uploader_name_raw else None
        self.signature: Optional[str] = None
        self.banned_groups = [""]

        self.cookie_validator = CookieValidator(config)

    def get_category_id(self, meta: dict[str, Any]) -> int:
        _has_ro_audio, has_ro_sub = self.get_ro_tracks(meta)
        cat_id = 4
        # 25 = 3D Movie
        if meta['category'] == 'MOVIE':
            # 4 = Movie HD
            cat_id = 4
            if meta['is_disc'] == "BDMV" or meta['type'] == "REMUX":
                # 20 = BluRay
                cat_id = 20
                if meta['resolution'] == '2160p':
                    # 26 = 4k Movie - BluRay
                    cat_id = 26
            elif meta['resolution'] == '2160p':
                # 6 = 4k Movie
                cat_id = 6
            elif meta.get('sd', 0) == 1:
                # 1 = Movie SD
                cat_id = 1
            if has_ro_sub and meta.get('sd', 0) == 0 and meta['resolution'] != '2160p':
                # 19 = Movie + RO
                cat_id = 19

        if meta['category'] == 'TV':
            # 21 = TV HD
            cat_id = 21
            if meta['resolution'] == '2160p':
                # 27 = TV 4k
                cat_id = 27
            elif meta.get('sd', 0) == 1:
                # 23 = TV SD
                cat_id = 23

        if meta['is_disc'] == "DVD":
            # 2 = DVD
            cat_id = 2
            if has_ro_sub:
                # 3 = DVD + RO
                cat_id = 3

        if meta.get('anime', False) is True:
            # 24 = Anime
            cat_id = 24
        return cat_id

    def edit_name(self, meta: dict[str, Any]) -> str:
        fl_name = str(meta.get('name', ''))
        hdr = str(meta.get('hdr', ''))
        audio = str(meta.get('audio', ''))
        if 'DV' in hdr:
            fl_name = fl_name.replace(' DV ', ' DoVi ')
        if meta.get('type') in ('WEBDL', 'WEBRIP', 'ENCODE'):
            fl_name = fl_name.replace(audio, audio.replace(' ', '', 1))
        fl_name = fl_name.replace(str(meta.get('aka', '')), '')
        imdb_info = meta.get('imdb_info')
        if isinstance(imdb_info, dict):
            imdb_info_dict = cast(dict[str, Any], imdb_info)
            title = str(meta.get('title', ''))
            imdb_aka = str(imdb_info_dict.get('aka', ''))
            if imdb_aka:
                fl_name = fl_name.replace(title, imdb_aka)
            meta_year = str(meta.get('year', '')).strip()
            imdb_year = str(imdb_info_dict.get('year', meta.get('year', '')))
            if meta_year and meta.get('year') != imdb_info_dict.get('year', meta.get('year')):
                fl_name = fl_name.replace(meta_year, imdb_year)
        if 'DD+' in audio and 'DDP' in str(meta.get('uuid', '')):
            fl_name = fl_name.replace('DD+', 'DDP')
        if 'Atmos' in audio and 'Atmos' not in str(meta.get('uuid', '')):
            fl_name = fl_name.replace('Atmos', '')

        fl_name = fl_name.replace('BluRay REMUX', 'Remux').replace('BluRay Remux', 'Remux').replace('Bluray Remux', 'Remux')
        fl_name = fl_name.replace('PQ10', 'HDR').replace('HDR10+', 'HDR')
        fl_name = fl_name.replace('DoVi HDR HEVC', 'HEVC DoVi HDR').replace('HDR HEVC', 'HEVC HDR').replace('DoVi HEVC', 'HEVC DoVi')
        fl_name = fl_name.replace('DTS7.1', 'DTS').replace('DTS5.1', 'DTS').replace('DTS2.0', 'DTS').replace('DTS1.0', 'DTS')
        fl_name = fl_name.replace('Dubbed', '').replace('Dual-Audio', '')
        fl_name = ' '.join(fl_name.split())
        fl_name = re.sub(r"[^0-9a-zA-ZÀ-ÿ. &+'\-\[\]]+", "", fl_name)
        fl_name = fl_name.replace(' ', '.').replace('..', '.')
        return fl_name

    def _is_true(self, value: Any) -> bool:
        return str(value).strip().lower() in {"true", "1", "yes"}

    def _load_cookie_dict(self, cookiefile_json: str, cookiefile_pkl: str) -> dict[str, str]:
        if os.path.exists(cookiefile_json):
            raw_cookies = self.cookie_validator._load_cookies_dict_secure(cookiefile_json)  # pyright: ignore[reportPrivateUsage]
            return {name: str(data.get('value', '')) for name, data in raw_cookies.items()}

        if os.path.exists(cookiefile_pkl):
            try:
                with open(cookiefile_pkl, 'rb') as f:
                    session_cookies = pickle.load(f)  # nosec B301 - legacy migration only
                self.cookie_validator._save_cookies_secure(session_cookies, cookiefile_json)  # pyright: ignore[reportPrivateUsage]
                return {cookie.name: cookie.value for cookie in session_cookies}
            except Exception as e:
                console.print(f"[red]Failed to migrate legacy cookies: {e}[/red]")

        return {}

    async def upload(self, meta: dict[str, Any], _disctype: str, _torrent_bytes: Any = None) -> bool:
        common = COMMON(config=self.config)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag, torrent_bytes=_torrent_bytes)
        await self.edit_desc(meta)
        fl_name = self.edit_name(meta)
        cat_id = self.get_category_id(meta)
        has_ro_audio, _has_ro_sub = self.get_ro_tracks(meta)

        # Confirm the correct naming order for FL
        cli_ui.info(f"Filelist name: {fl_name}")
        if meta.get('unattended', False) is False:
            fl_confirm = cli_ui.ask_yes_no("Correct?", default=False)
            if fl_confirm is not True:
                fl_name_manually = cli_ui.ask_string("Please enter a proper name", default="")
                if fl_name_manually == "":
                    console.print('No proper name given')
                    console.print("Aborting...")
                    return False
                else:
                    fl_name = fl_name_manually

        # Torrent File Naming
        # Note: Don't Edit .torrent filename after creation, SubsPlease anime releases (because of their weird naming) are an exception
        if meta.get('anime', True) is True and meta.get('tag', '') == '-SubsPlease':
            torrentFileName = str(fl_name)
        else:
            if meta.get('isdir', False) is False:
                torrent_uuid = str(meta.get('uuid', ''))
                torrentFileName = os.path.splitext(torrent_uuid)[0]
            else:
                torrentFileName = str(meta.get('uuid', ''))

        # Download new .torrent from site
        desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        async with aiofiles.open(desc_path, newline='', encoding='utf-8') as desc_file:
            fl_desc = await desc_file.read()
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        mi_path = (
            f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
            if meta['bdinfo'] is not None
            else f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
        )
        async with aiofiles.open(mi_path, encoding='utf-8') as mi_file:
            mi_dump = await mi_file.read()
        async with aiofiles.open(torrent_path, 'rb') as torrent_file:
            torrent_bytes = await torrent_file.read()
        torrentFileName = unidecode(str(torrentFileName))
        files = {
            'file': (f"{torrentFileName}.torrent", torrent_bytes, "application/x-bittorent")
        }
        data = {
            'name': fl_name,
            'type': cat_id,
            'descr': fl_desc.strip(),
            'nfo': mi_dump
        }

        imdb_id_value = str(meta.get('imdb_id', '0'))
        if imdb_id_value.isdigit() and int(imdb_id_value) != 0:
            data['imdbid'] = meta.get('imdb')
            imdb_info = meta.get('imdb_info')
            imdb_info_dict = cast(dict[str, Any], imdb_info) if isinstance(imdb_info, dict) else {}
            data['description'] = imdb_info_dict.get('genres', '')
        if self.uploader_name not in ("", None) and not self._is_true(self.config['TRACKERS'][self.tracker].get('anon', "False")):
            data['epenis'] = self.uploader_name
        if has_ro_audio:
            data['materialro'] = 'on'
        if meta['is_disc'] == "BDMV" or meta['type'] == "REMUX":
            data['freeleech'] = 'on'
        if int(meta.get('tv_pack', '0')) != 0:
            data['freeleech'] = 'on'
        if int(meta.get('freeleech', '0')) != 0:
            data['freeleech'] = 'on'

        url = "https://filelist.io/takeupload.php"
        # Submit
        if meta['debug']:
            console.print(url)
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
            await common.create_torrent_for_upload(
                meta,
                f"{self.tracker}" + "_DEBUG",
                f"{self.tracker}" + "_DEBUG",
                announce_url="https://fake.tracker",
                torrent_bytes=_torrent_bytes,
            )
            return True  # Debug mode - simulated success
        else:
            cookiefile_json = os.path.abspath(f"{meta['base_dir']}/data/cookies/FL.json")
            cookiefile_pkl = os.path.abspath(f"{meta['base_dir']}/data/cookies/FL.pkl")
            cookies = self._load_cookie_dict(cookiefile_json, cookiefile_pkl)
            async with httpx.AsyncClient(cookies=cookies, timeout=60.0, follow_redirects=True) as client:
                up = await client.post(url=url, data=data, files=files)

            # Match url to verify successful upload
            match = re.match(r".*?filelist\.io/details\.php\?id=(\d+)&uploaded=(\d+)", str(up.url))
            if match:
                meta['tracker_status'][self.tracker]['status_message'] = match.group(0)
                torrent_id = match.group(1)
                await self.download_new_torrent(cookies, torrent_id, torrent_path)
                return True
            else:
                console.print(data)
                console.print("\n\n")
                console.print(up.text)
                raise UploadException(f"Upload to FL Failed: result URL {up.url} ({up.status_code}) was not expected", 'red')  # noqa F405

    async def search_existing(self, meta: dict[str, Any], _disctype: str) -> list[str]:
        dupes: list[str] = []
        cookiefile_json = os.path.abspath(f"{meta['base_dir']}/data/cookies/FL.json")
        cookiefile_pkl = os.path.abspath(f"{meta['base_dir']}/data/cookies/FL.pkl")
        cookies = self._load_cookie_dict(cookiefile_json, cookiefile_pkl)

        search_url = "https://filelist.io/browse.php"

        imdb_id_value = str(meta.get('imdb_id', '0'))
        if imdb_id_value.isdigit() and int(imdb_id_value) != 0:
            params = {
                'search': meta['imdb'],
                'cat': self.get_category_id(meta),
                'searchin': '3'
            }
        else:
            params = {
                'search': meta['title'],
                'cat': self.get_category_id(meta),
                'searchin': '0'
            }

        try:
            async with httpx.AsyncClient(cookies=cookies, timeout=10.0) as client:
                response = await client.get(search_url, params=params)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    find = soup.find_all('a', href=True)
                    for each in find:
                        href_attr = each.get('href')
                        title_attr = each.get('title')
                        if (
                            isinstance(href_attr, str)
                            and href_attr.startswith('details.php?id=')
                            and '&' not in href_attr
                            and isinstance(title_attr, str)
                        ):
                            dupes.append(title_attr)
                else:
                    console.print(f"[bold red]Failed to search torrents. HTTP Status: {response.status_code}")
                await asyncio.sleep(0.5)

        except httpx.TimeoutException:
            console.print("[bold red]Request timed out while searching for existing torrents.")
        except httpx.RequestError as e:
            console.print(f"[bold red]An error occurred while making the request: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            await asyncio.sleep(0.5)

        return dupes

    async def validate_credentials(self, meta: dict[str, Any]) -> bool:
        cookiefile_json = os.path.abspath(f"{meta['base_dir']}/data/cookies/FL.json")
        cookiefile_pkl = os.path.abspath(f"{meta['base_dir']}/data/cookies/FL.pkl")

        if os.path.exists(cookiefile_json):
            cookiefile = cookiefile_json
        elif os.path.exists(cookiefile_pkl):
            cookiefile = cookiefile_pkl
        else:
            cookiefile = cookiefile_json  # Default to JSON for new saves

        if not os.path.exists(cookiefile):
            await self.login(cookiefile)
        vcookie = await self.validate_cookies(meta, cookiefile)
        if vcookie is not True:
            console.print('[red]Failed to validate cookies. Please confirm that the site is up and your passkey is valid.')
            recreate = cli_ui.ask_yes_no("Log in again and create new session?")
            if recreate is True:
                if os.path.exists(cookiefile):
                    os.remove(cookiefile)
                await self.login(cookiefile)
                vcookie = await self.validate_cookies(meta, cookiefile)
                return vcookie
            else:
                return False
        return True

    async def validate_cookies(self, meta: dict[str, Any], _cookiefile: str) -> bool:
        url = "https://filelist.io/index.php"
        cookiefile_json = os.path.abspath(f"{meta['base_dir']}/data/cookies/FL.json")
        cookiefile_pkl = os.path.abspath(f"{meta['base_dir']}/data/cookies/FL.pkl")
        cookies = self._load_cookie_dict(cookiefile_json, cookiefile_pkl)
        if cookies:
            async with httpx.AsyncClient(cookies=cookies, timeout=30.0) as client:
                resp = await client.get(url=url)
            if meta['debug']:
                console.print(resp.url)
            return resp.text.find("Logout") != -1
        return False

    async def login(self, cookiefile: str) -> None:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get("https://filelist.io/login.php")
            await asyncio.sleep(0.5)
            soup = BeautifulSoup(r.text, 'html.parser')
            validator_input = soup.find('input', {'name': 'validator'})
            if validator_input is None:
                raise LoginException('Unable to locate validator input on FL login page.')  # noqa: F405
            validator_value = validator_input.get('value')
            if not isinstance(validator_value, str):
                raise LoginException('Validator input missing value attribute on FL login page.')  # noqa: F405
            validator = validator_value
            data = {
                'validator': validator,
                'username': self.username,
                'password': self.password,
                'unlock': '1',
            }
            await client.post('https://filelist.io/takelogin.php', data=data)
            await asyncio.sleep(0.5)
            index = 'https://filelist.io/index.php'
            response = await client.get(index)
            if response.text.find("Logout") != -1:
                console.print('[green]Successfully logged into FL')
                self.cookie_validator._save_cookies_secure(client.cookies.jar, cookiefile)  # pyright: ignore[reportPrivateUsage]
            else:
                console.print('[bold red]Something went wrong while trying to log into FL')
                await asyncio.sleep(1)
                console.print(response.url)

    async def download_new_torrent(self, cookies: dict[str, str], id: str, torrent_path: str) -> None:
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                get_process_executor(),
                _download_fl_torrent_worker,
                cookies,
                id,
                torrent_path,
            )
        except Exception as e:
            console.print("[red]There was an issue downloading the new .torrent from FL")
            console.print(str(e))

    async def edit_desc(self, meta: dict[str, Any]) -> None:
        base_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        async with aiofiles.open(base_path, encoding='utf-8') as base_file:
            base = await base_file.read()
        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', newline='', encoding='utf-8') as descfile:
            from src.bbcode import BBCODE
            bbcode = BBCODE()

            desc = base
            desc = bbcode.remove_spoiler(desc)
            desc = bbcode.convert_code_to_quote(desc)
            desc = bbcode.convert_comparison_to_centered(desc, 900)
            desc = desc.replace('[img]', '[img]').replace('[/img]', '[/img]')
            desc = re.sub(r"(\[img=\d+)]", "[img]", desc, flags=re.IGNORECASE)
            if meta['is_disc'] != 'BDMV':
                url = "https://up.img4k.net/api/description"
                mediainfo_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
                async with aiofiles.open(mediainfo_path, encoding='utf-8') as mi_file:
                    data = {
                        'mediainfo': await mi_file.read(),
                    }
                if int(meta['imdb_id']) != 0:
                    data['imdbURL'] = f"tt{meta['imdb_id']}"
                screen_glob = [os.path.basename(f) for f in glob.glob(os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"{meta['filename']}-*.png"))]
                files: list[tuple[str, tuple[str, bytes, str]]] = []
                for screen in screen_glob:
                    screen_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/{screen}"
                    async with aiofiles.open(screen_path, 'rb') as image_file:
                        image_bytes = await image_file.read()
                    files.append(('images', (os.path.basename(screen), image_bytes, 'image/png')))
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, data=data, files=files, auth=(self.fltools['user'], self.fltools['pass']))
                final_desc = response.text.replace('\r\n', '\n')
            else:
                # BD Description Generator
                bd_summary_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_EXT.txt"
                async with aiofiles.open(bd_summary_path, encoding='utf-8') as bd_file:
                    final_desc = await bd_file.read()
                if final_desc.strip() != "":  # Use BD_SUMMARY_EXT and bbcode format it
                    final_desc = final_desc.replace('[/pre][/quote]', f'[/pre][/quote]\n\n{desc}\n', 1)
                    final_desc = final_desc.replace('DISC INFO:', '[pre][quote=BD_Info][b][color=#FF0000]DISC INFO:[/color][/b]').replace('PLAYLIST REPORT:', '[b][color=#FF0000]PLAYLIST REPORT:[/color][/b]').replace('VIDEO:', '[b][color=#FF0000]VIDEO:[/color][/b]').replace('AUDIO:', '[b][color=#FF0000]AUDIO:[/color][/b]').replace('SUBTITLES:', '[b][color=#FF0000]SUBTITLES:[/color][/b]')
                    final_desc += "[/pre][/quote]\n"  # Closed bbcode tags
                    # Upload screens and append to the end of the description
                    url = "https://up.img4k.net/api/description"
                    screen_glob = [os.path.basename(f) for f in glob.glob(os.path.join(f"{meta['base_dir']}/tmp/{meta['uuid']}", f"{meta['filename']}-*.png"))]
                    files: list[tuple[str, tuple[str, bytes, str]]] = []
                    for screen in screen_glob:
                        screen_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/{screen}"
                        async with aiofiles.open(screen_path, 'rb') as image_file:
                            image_bytes = await image_file.read()
                        files.append(('images', (os.path.basename(screen), image_bytes, 'image/png')))
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(url, files=files, auth=(self.fltools['user'], self.fltools['pass']))
                    final_desc += response.text.replace('\r\n', '\n')
            await descfile.write(final_desc)

            if self.signature is not None:
                await descfile.write(self.signature)

    def get_ro_tracks(self, meta: dict[str, Any]) -> tuple[bool, bool]:
        has_ro_audio = has_ro_sub = False
        if meta.get('is_disc', '') != 'BDMV':
            mi = meta.get('mediainfo')
            if isinstance(mi, dict):
                mi_dict = cast(dict[str, Any], mi)
                media = mi_dict.get('media')
                if isinstance(media, dict):
                    media_dict = cast(dict[str, Any], media)
                    tracks = media_dict.get('track')
                    if isinstance(tracks, list):
                        tracks_list = cast(list[Any], tracks)
                        for track in tracks_list:
                            if not isinstance(track, dict):
                                continue
                            track_dict = cast(dict[str, Any], track)
                            if track_dict.get('@type') == "Text" and track_dict.get('Language') == "ro":
                                has_ro_sub = True
                            if track_dict.get('@type') == "Audio" and track_dict.get('Audio') == 'ro':
                                has_ro_audio = True
        else:
            bdinfo = meta.get('bdinfo')
            if isinstance(bdinfo, dict):
                bdinfo_dict = cast(dict[str, Any], bdinfo)
                subtitles = bdinfo_dict.get('subtitles')
                if isinstance(subtitles, list) and "Romanian" in subtitles:
                    has_ro_sub = True
                audio_tracks = bdinfo_dict.get('audio')
                if isinstance(audio_tracks, list):
                    audio_tracks_list = cast(list[Any], audio_tracks)
                    for audio_track in audio_tracks_list:
                        if isinstance(audio_track, dict):
                            audio_track_dict = cast(dict[str, Any], audio_track)
                        else:
                            continue
                        if audio_track_dict.get('language') == 'Romanian':
                            has_ro_audio = True
                            break
        return has_ro_audio, has_ro_sub
