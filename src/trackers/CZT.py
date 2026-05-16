# Upload Assistant — CZTeam (czteam.me) tracker plugin
#
# CZTeam is BTSource/NVTracker-lineage, same family as FileList. Login + upload
# go through the regular user-facing endpoints (login.php → takelogin.php,
# upload.php → takeupload.php) using session cookies and a per-form CSRF token.
import asyncio
import os
import re
from typing import Any, Optional, cast
from urllib.parse import urljoin

import aiofiles
import cli_ui
import httpx
from bs4 import BeautifulSoup

from src.console import console
from src.cookie_auth import CookieValidator
from src.exceptions import *  # noqa F403
from src.trackers.COMMON import COMMON


class CZT:

    def __init__(self, config: dict[str, Any]) -> None:
        self.config: dict[str, Any] = config
        self.tracker = 'CZT'
        self.source_flag = 'CzT'
        tracker_cfg = config['TRACKERS'][self.tracker]
        self.username: str = str(tracker_cfg.get('username', '')).strip()
        self.password: str = str(tracker_cfg.get('password', '')).strip()
        self.totp: str = str(tracker_cfg.get('totp', '')).strip()
        self.base_url: str = str(tracker_cfg.get('base_url', 'https://czteam.me')).rstrip('/')
        self.anon: bool = self._is_true(tracker_cfg.get('anon', False))
        self.banned_groups: list[str] = []
        self.cookie_validator = CookieValidator(config)

    @staticmethod
    def _is_true(value: Any) -> bool:
        return str(value).strip().lower() in {"true", "1", "yes"}

    # CZTeam category ids (see `categories` table)
    async def get_category_id(self, meta: dict[str, Any]) -> int:
        has_ro_audio, has_ro_sub = self._detect_ro_tracks(meta)
        ro = has_ro_audio or has_ro_sub

        if meta.get('anime', False) is True:
            return 23  # Anime

        if meta['category'] == 'MOVIE':
            if meta.get('is_disc') == 'BDMV':
                return 36 if ro else 29  # Full BluRay-RO / Movies/HD
            if meta.get('is_disc') == 'DVD':
                return 28 if ro else 20  # Movies/DVD-RO / Movies/DVD-R
            if str(meta.get('type', '')).upper() in {'WEBDL', 'WEBRIP', 'HDTV', 'ENCODE', 'REMUX'}:
                if meta.get('resolution') in ('720p', '1080p', '2160p'):
                    return 33 if ro else 29  # Movies/HDTV-RO / Movies/HD
            # SD / XviD bucket
            if str(meta.get('video_codec', '')).lower() in {'xvid', 'divx'} or meta.get('sd', 0) == 1:
                return 19  # Movies/XviD
            return 29  # default HD

        if meta['category'] == 'TV':
            if meta.get('resolution') in ('720p', '1080p', '2160p'):
                return 34 if ro else 5  # TvEps/HD-RO / TvEps/HD
            return 7  # TvEps

        return 29

    @staticmethod
    def _meta_resolution(meta: dict[str, Any]) -> str:
        allowed = {'480p', '576p', '720p', '1080p', '2160p'}
        r = str(meta.get('resolution', '')).lower()
        return r if r in allowed else ''

    @staticmethod
    def _meta_codec(meta: dict[str, Any]) -> str:
        vc = str(meta.get('video_codec', '')).upper().replace(' ', '')
        mapping = {
            'H264': 'H.264', 'AVC': 'H.264', 'X264': 'x264',
            'H265': 'H.265', 'HEVC': 'H.265', 'X265': 'x265',
            'XVID': 'XviD', 'AV1': 'AV1',
        }
        return mapping.get(vc, '')

    @staticmethod
    def _meta_container(meta: dict[str, Any]) -> str:
        allowed = {'MKV', 'AVI', 'MP4', 'TS', 'ISO'}
        c = str(meta.get('container', '')).upper()
        return c if c in allowed else ''

    @staticmethod
    def _meta_source(meta: dict[str, Any]) -> str:
        t = str(meta.get('type', '')).upper()
        mapping = {
            'DISC': 'BluRay', 'REMUX': 'BluRay', 'ENCODE': 'BluRay',
            'WEBDL': 'WEB-DL', 'WEBRIP': 'WEBRip',
            'HDTV': 'HDTV', 'DVDRIP': 'DVDRip',
        }
        if meta.get('is_disc') == 'BDMV':
            return 'BluRay'
        if meta.get('is_disc') == 'DVD':
            return 'DVD'
        return mapping.get(t, '')

    @staticmethod
    def _detect_ro_tracks(meta: dict[str, Any]) -> tuple[bool, bool]:
        has_ro_audio = has_ro_sub = False
        mi = meta.get('mediainfo')
        if isinstance(mi, dict):
            media = mi.get('media') if isinstance(mi.get('media'), dict) else {}
            tracks = media.get('track') if isinstance(media, dict) else None
            if isinstance(tracks, list):
                for track in tracks:
                    if not isinstance(track, dict):
                        continue
                    lang = str(track.get('Language', '')).lower()
                    if track.get('@type') == 'Text' and lang in ('ro', 'rum', 'ron', 'romanian'):
                        has_ro_sub = True
                    if track.get('@type') == 'Audio' and lang in ('ro', 'rum', 'ron', 'romanian'):
                        has_ro_audio = True
        bdinfo = meta.get('bdinfo')
        if isinstance(bdinfo, dict):
            subs = bdinfo.get('subtitles')
            if isinstance(subs, list) and 'Romanian' in subs:
                has_ro_sub = True
            audio_tracks = bdinfo.get('audio')
            if isinstance(audio_tracks, list):
                for a in audio_tracks:
                    if isinstance(a, dict) and a.get('language') == 'Romanian':
                        has_ro_audio = True
                        break
        return has_ro_audio, has_ro_sub

    @staticmethod
    def _extract_csrf(html: str) -> Optional[str]:
        soup = BeautifulSoup(html, 'html.parser')
        tag = soup.find('input', {'name': 'csrf_token'})
        if tag is None:
            return None
        value = tag.get('value')
        return value if isinstance(value, str) else None

    def _cookie_paths(self, meta: dict[str, Any]) -> tuple[str, str]:
        base = meta['base_dir']
        return (
            os.path.abspath(f"{base}/data/cookies/CZT.json"),
            os.path.abspath(f"{base}/data/cookies/CZT.pkl"),
        )

    def _load_cookie_dict(self, cookiefile_json: str, _cookiefile_pkl: str) -> dict[str, str]:
        if os.path.exists(cookiefile_json):
            raw = self.cookie_validator._load_cookies_dict_secure(cookiefile_json)  # pyright: ignore[reportPrivateUsage]
            return {name: str(data.get('value', '')) for name, data in raw.items()}
        return {}

    async def validate_credentials(self, meta: dict[str, Any]) -> bool:
        cookiefile_json, cookiefile_pkl = self._cookie_paths(meta)
        if not os.path.exists(cookiefile_json):
            await self.login(cookiefile_json)
        ok = await self.validate_cookies(meta, cookiefile_json)
        if not ok:
            console.print('[red]CZT: cookie validation failed. The site may be down, the account locked, or rate-limited.')
            try:
                retry = cli_ui.ask_yes_no("Log in again and create a new session?")
            except Exception:
                retry = False
            if retry:
                if os.path.exists(cookiefile_json):
                    os.remove(cookiefile_json)
                await self.login(cookiefile_json)
                ok = await self.validate_cookies(meta, cookiefile_json)
        return ok

    async def validate_cookies(self, meta: dict[str, Any], _cookiefile: str) -> bool:
        cookiefile_json, cookiefile_pkl = self._cookie_paths(meta)
        cookies = self._load_cookie_dict(cookiefile_json, cookiefile_pkl)
        if not cookies:
            return False
        async with httpx.AsyncClient(cookies=cookies, timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(f'{self.base_url}/index.php')
        if meta.get('debug'):
            console.print(resp.url)
        # logout.php link is rendered in the header for every authenticated page
        return 'logout.php' in resp.text or 'Logout' in resp.text

    async def login(self, cookiefile: str) -> None:
        login_url = f'{self.base_url}/login.php'
        takelogin_url = f'{self.base_url}/takelogin.php'
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(login_url)
            token = self._extract_csrf(r.text)
            if not token:
                raise LoginException('CZT: unable to locate csrf_token on login page.')  # noqa F405
            data: dict[str, str] = {
                'csrf_token': token,
                'username': self.username,
                'password': self.password,
                'returnto': '/index.php',
            }
            if self.totp:
                data['totp'] = self.totp
            await client.post(takelogin_url, data=data)
            await asyncio.sleep(0.5)
            check = await client.get(f'{self.base_url}/index.php')
            if 'logout.php' in check.text or 'Logout' in check.text:
                console.print('[green]CZT: logged in successfully.')
                self.cookie_validator._save_cookies_secure(client.cookies.jar, cookiefile)  # pyright: ignore[reportPrivateUsage]
            else:
                console.print('[bold red]CZT: login failed (check username/password, totp, or rate-limit).')

    async def search_existing(self, meta: dict[str, Any], _disctype: str) -> list[str]:
        dupes: list[str] = []
        cookiefile_json, cookiefile_pkl = self._cookie_paths(meta)
        cookies = self._load_cookie_dict(cookiefile_json, cookiefile_pkl)
        imdb_id_value = str(meta.get('imdb_id', '0'))
        if imdb_id_value.isdigit() and int(imdb_id_value) != 0:
            params: dict[str, Any] = {'search': f"tt{int(imdb_id_value):07d}"}
        else:
            params = {'search': meta.get('title', '')}
        try:
            async with httpx.AsyncClient(cookies=cookies, timeout=15.0) as client:
                resp = await client.get(f'{self.base_url}/browse.php', params=params)
            if resp.status_code != 200:
                console.print(f"[bold red]CZT: search returned HTTP {resp.status_code}")
                return dupes
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if isinstance(href, str) and re.match(r'details\.php\?id=\d+', href):
                    title = a.get('title') or a.get_text(strip=True)
                    if title:
                        dupes.append(str(title))
        except httpx.RequestError as e:
            console.print(f"[bold red]CZT search error: {e}")
        return dupes

    async def upload(self, meta: dict[str, Any], _disctype: str) -> bool:
        common = COMMON(config=self.config)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag)

        cookiefile_json, cookiefile_pkl = self._cookie_paths(meta)
        cookies = self._load_cookie_dict(cookiefile_json, cookiefile_pkl)

        # MediaInfo paste (descr field on CZTeam holds MediaInfo)
        if meta.get('bdinfo') is not None:
            mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt"
        else:
            mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
        async with aiofiles.open(mi_path, encoding='utf-8') as f:
            mi_dump = await f.read()

        # Free-form body (user_descr — BBCode); reuse UA's generated description
        desc_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt"
        user_descr = ''
        if os.path.exists(desc_path):
            async with aiofiles.open(desc_path, encoding='utf-8') as f:
                user_descr = (await f.read()).strip()

        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        async with aiofiles.open(torrent_path, 'rb') as f:
            torrent_bytes = await f.read()

        torrent_name = str(meta.get('name', '')).strip().replace(' ', '.')
        cat_id = await self.get_category_id(meta)

        files = {'file': (f"{torrent_name}.torrent", torrent_bytes, 'application/x-bittorrent')}
        data: dict[str, str] = {
            'name': torrent_name,
            'type': str(cat_id),
            'descr': mi_dump,
            'user_descr': user_descr,
            'resolution': self._meta_resolution(meta),
            'codec': self._meta_codec(meta),
            'container': self._meta_container(meta),
            'source': self._meta_source(meta),
            # url is the IMDB URL; takeupload.php extracts the tt-id from it
            'url': f"https://www.imdb.com/title/tt{int(meta['imdb_id']):07d}/" if str(meta.get('imdb_id', '0')).isdigit() and int(meta.get('imdb_id', 0)) != 0 else '',
            'poster': '',
            'tube': '',
            'genre': '',
            'ripnfo': '0',
            'stripasciiart': '0',
        }

        if meta.get('debug'):
            console.print(f"{self.base_url}/takeupload.php")
            scrubbed = {k: ('<binary>' if k == 'file' else (v[:120] + '…') if isinstance(v, str) and len(v) > 120 else v) for k, v in data.items()}
            console.print(scrubbed)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
            await common.create_torrent_for_upload(meta, f"{self.tracker}_DEBUG", f"{self.tracker}_DEBUG", announce_url="https://fake.tracker")
            return True

        upload_form_url = f'{self.base_url}/upload.php'
        takeupload_url = f'{self.base_url}/takeupload.php'
        async with httpx.AsyncClient(cookies=cookies, timeout=120.0, follow_redirects=True) as client:
            # Re-fetch the upload form to mint a fresh csrf_token
            form_resp = await client.get(upload_form_url)
            token = self._extract_csrf(form_resp.text)
            if not token:
                console.print('[bold red]CZT: could not extract csrf_token from upload.php (session expired?).')
                return False
            data['csrf_token'] = token
            up = await client.post(takeupload_url, data=data, files=files)

        # Word boundary on "details" so the header's userdetails.php link
        # doesn't false-match the upload result.
        m = re.search(r'(?<![a-z])details\.php\?id=(\d+)', up.text)
        if m:
            torrent_id = m.group(1)
            details_url = urljoin(f'{self.base_url}/', f'details.php?id={torrent_id}')
            meta['tracker_status'][self.tracker]['status_message'] = details_url
            await self.download_new_torrent(cookies, torrent_id, torrent_path)
            return True

        # Server-rendered error path: takeupload.php's abort() echoes
        # <p style="color:red">$msg</p> — surface that to the user.
        err = re.search(r'<p style="color:red">(.*?)</p>', up.text, flags=re.DOTALL)
        reason = err.group(1).strip() if err else f"unexpected response (HTTP {up.status_code})"
        console.print(f"[bold red]CZT upload failed: {reason}")
        if meta.get('debug'):
            console.print(up.text[:2000])
        raise UploadException(f"Upload to CZT failed: {reason}", 'red')  # noqa F405

    async def download_new_torrent(self, cookies: dict[str, str], torrent_id: str, torrent_path: str) -> None:
        # CZTeam's download.php accepts ?torrent=<id> (legacy form) or the
        # /download/<id>/<name>.torrent rewrite path. The ?id= shape returns
        # "Invalid id". The query-string form is the simplest for cross-seed.
        url = f'{self.base_url}/download.php?torrent={torrent_id}'
        async with httpx.AsyncClient(cookies=cookies, timeout=30.0, follow_redirects=True) as client:
            r = await client.get(url)
        if r.status_code == 200 and r.content[:1] == b'd':
            async with aiofiles.open(torrent_path, 'wb') as f:
                await f.write(r.content)
        else:
            console.print(f"[red]CZT: failed to download replacement .torrent (HTTP {r.status_code})")
