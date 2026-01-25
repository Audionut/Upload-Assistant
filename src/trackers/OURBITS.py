# -*- coding: utf-8 -*-
# Upload Assistant — OURBITS Tracker Class
from __future__ import annotations

from bs4 import BeautifulSoup
import asyncio
import os
import re
import shlex
from typing import Any
import httpx

from src.trackers.COMMON import COMMON
from src.exceptions import *  # noqa E403
from src.console import console


class OURBITS:

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.tracker = 'OURBITS'
        self.source_flag = 'OURBITS'
        self.passkey = str(config['TRACKERS'].get('OURBITS', {}).get('passkey', '')).strip()
        self.announce_url = str(
            config['TRACKERS'].get('OURBITS', {}).get('announce_url', 'https://ourbits.club/announce.php')
        ).strip()
        self.meta_script = str(config['TRACKERS'].get('OURBITS', {}).get('meta_script', '')).strip()
        self.meta_timeout = int(config['TRACKERS'].get('OURBITS', {}).get('meta_timeout', 30))
        self.signature = None
        self.banned_groups = [""]

    async def validate_credentials(self, meta: dict[str, Any]) -> bool:
        vcookie = await self.validate_cookies(meta)
        return True if vcookie is True else False

    async def validate_cookies(self, meta: dict[str, Any]) -> bool:
        common = COMMON(config=self.config)
        url = "https://ourbits.club"
        cookiefile = f"{meta['base_dir']}/data/cookies/OURBITS.txt"
        if not os.path.exists(cookiefile):
            return False
        cookies = await common.parseCookieFile(cookiefile)
        try:
            async with httpx.AsyncClient(cookies=cookies, timeout=10.0) as client:
                resp = await client.get(url)
                return True if "logout.php" in resp.text else False
        except Exception:
            return False

    async def search_existing(self, meta: dict[str, Any], _disctype: str) -> list[str]:
        dupes = []
        common = COMMON(config=self.config)
        cookiefile = f"{meta['base_dir']}/data/cookies/OURBITS.txt"
        if not os.path.exists(cookiefile):
            return []
        cookies = await common.parseCookieFile(cookiefile)
        imdb_id_raw = str(meta.get('imdb_id', '0')).replace('tt', '').strip()
        imdb = f"tt{imdb_id_raw.zfill(7)}" if imdb_id_raw.isdigit() and int(imdb_id_raw) != 0 else ""
        if not imdb:
            return []
        search_url = f"https://ourbits.club/torrents.php?incldead=0&spstate=0&inclbookmarked=0&search={imdb}&search_area=4&search_mode=0"
        try:
            async with httpx.AsyncClient(cookies=cookies, timeout=15.0) as client:
                r = await client.get(search_url)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, 'lxml')
                    rows = soup.select('table.torrents > tr:has(table.torrentname)')
                    for row in rows:
                        text = row.select_one('a[href^="details.php?id="]')
                        if text and text.attrs.get('title'):
                            dupes.append(text.attrs.get('title'))
        except Exception:
            pass
        return dupes

    async def get_type_category_id(self, meta: dict[str, Any]) -> int:
        cat_id = 401
        if str(meta.get('3D', '')).upper() == '3D':
            cat_id = 402

        if meta.get('category') == 'TV':
            cat_id = 405 if meta.get('tv_pack') else 412

        genres_value = meta.get("genres", "")
        keywords_value = meta.get("keywords", "")
        if isinstance(genres_value, list):
            genres = ' '.join(genres_value).lower()
        else:
            genres = str(genres_value).lower()
        if isinstance(keywords_value, list):
            keywords = ' '.join(keywords_value).lower()
        else:
            keywords = str(keywords_value).lower()

        if 'documentary' in genres or 'documentary' in keywords:
            cat_id = 410
        if 'animation' in genres or 'animation' in keywords:
            cat_id = 411
        if 'concert' in genres or 'concert' in keywords:
            cat_id = 419
        if 'sport' in genres or 'sport' in keywords:
            cat_id = 415
        return cat_id

    async def get_medium_sel(self, meta: dict[str, Any]) -> int:
        if meta.get('is_disc', '') == "BDMV":
            return 12 if meta.get('resolution') == '2160p' else 1
        if meta.get('is_disc', '') == "HD DVD":
            return 1
        medium_map = {
            "HDTV": 5,
            "UHDTV": 13,
            "WEBDL": 9,
            "WEBRIP": 7,
            "ENCODE": 7,
            "REMUX": 7,
            "DVDR": 2,
            "CD": 8,
        }
        return medium_map.get(meta.get('type', ''), 7)

    async def get_codec_sel(self, meta: dict[str, Any]) -> int:
        codecmap = {
            "AVC": 12,
            "H.264": 12,
            "x264": 12,
            "HEVC": 14,
            "H.265": 14,
            "x265": 14,
            "MPEG-2": 15,
            "VC-1": 16,
            "Xvid": 17,
            "AV1": 19,
        }
        searchcodec = meta.get('video_codec', meta.get('video_encode'))
        return codecmap.get(searchcodec, 18)

    async def get_audiocodec_sel(self, meta: dict[str, Any]) -> int:
        audio = meta.get('audio', '')
        if "Atmos" in audio:
            return 14
        if "DTS:X" in audio:
            return 21
        if "DTS-HD" in audio:
            return 1
        if "TrueHD" in audio or "True HD" in audio:
            return 2
        if "DTS" in audio:
            return 4
        if "LPCM" in audio:
            return 5
        if "FLAC" in audio:
            return 13
        if "APE" in audio:
            return 12
        if "AAC" in audio:
            return 7
        if "AC3" in audio or "DD" in audio:
            return 6
        if "WAV" in audio:
            return 11
        if "OPUS" in audio or "Opus" in audio:
            return 33
        if "MP3" in audio or "MP2" in audio or "MPEG" in audio:
            return 32
        return 4

    async def get_standard_sel(self, meta: dict[str, Any]) -> int:
        res_map = {'2160p': 5, '1080p': 1, '1080i': 2, '720p': 3, 'SD': 4}
        return res_map.get(meta.get('resolution'), 1)

    async def get_processing_sel(self, meta: dict[str, Any]) -> int:
        region = str(meta.get('region') or meta.get('country') or '').lower()
        if any(key in region for key in ("china", "chinese", "cn", "chn", "mainland")):
            return 1
        if any(key in region for key in ("hong kong", "hongkong", "hk", "taiwan", "tw")):
            return 3
        if any(key in region for key in ("japan", "jp")):
            return 4
        if any(key in region for key in ("korea", "kr")):
            return 5
        if any(key in region for key in ("us", "usa", "united states", "uk", "europe", "eu", "france", "germany", "italy", "spain")):
            return 2
        return 6

    async def get_external_meta(self, meta: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {"bbcode": "", "trans_title": [], "douban_url": ""}
        if not self.meta_script:
            return result
        imdb_id = str(meta.get('imdb_id', '')).strip()
        arg = f"tt{imdb_id.replace('tt', '').zfill(7)}" if imdb_id and imdb_id != '0' else meta.get("douban_url")
        if not arg:
            return result
        try:
            cmdline = shlex.split(self.meta_script) + [str(arg).strip()]
            proc = await asyncio.create_subprocess_exec(*cmdline, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.meta_timeout)
            output = stdout.decode('utf-8').strip()
            if output:
                result["bbcode"] = output
                m = re.search(r'^[ \t]*◎译　　名[ \t　]+(.+)$', output, flags=re.M)
                if m:
                    result["trans_title"] = [p.strip() for p in re.split(r'\s*/\s*', m.group(1).strip()) if p.strip()]
                douban_match = re.search(r"https?://(?:movie\.)?douban\.com/subject/\d+/?", output)
                if douban_match:
                    result["douban_url"] = douban_match.group(0)
        except Exception:
            pass
        return result

    async def edit_desc(self, meta: dict[str, Any]) -> None:
        out_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        with open(out_path, 'w', encoding='utf-8') as descfile:
            ext_meta = await self.get_external_meta(meta)
            meta['ptgen'] = ext_meta
            if ext_meta.get("bbcode"):
                descfile.write(ext_meta["bbcode"] + "\n\n")
            if meta.get('discs'):
                for each in meta['discs']:
                    content = each['summary'] if each['type'] == "BDMV" else f"{each['vob_mi']}\n{each['ifo_mi']}"
                    descfile.write(f"[quote]{content}[/quote]\n\n")
            else:
                mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
                if os.path.exists(mi_path):
                    with open(mi_path, 'r', encoding='utf-8') as f:
                        descfile.write(f"[quote]{f.read()}[/quote]\n")
            for img in meta.get('image_list', [])[:int(meta.get('screens', 5))]:
                descfile.write(f"[url={img['web_url']}][img]{img['img_url']}[/img][/url]")

    async def _has_chinese_audio(self, meta: dict[str, Any]) -> bool:
        chinese_languages = {
            'chinese', 'mandarin', 'cantonese', 'zh', 'zho', 'chi', 'cmn', 'yue', 'putonghua', 'guoyu', '国语', '普通话'
        }
        audio_languages = meta.get('audio_languages', [])
        if isinstance(audio_languages, list):
            for lang in audio_languages:
                if str(lang).lower() in chinese_languages:
                    return True
        return False

    async def _has_chinese_subs(self, meta: dict[str, Any]) -> bool:
        if meta.get('is_disc') == 'BDMV':
            subtitles = meta.get('bdinfo', {}).get('subtitles', [])
            return "Chinese" in str(subtitles)
        chinese_languages = {
            'chinese', 'mandarin', 'cantonese', 'zh', 'zho', 'chi', 'cmn', 'yue', 'putonghua', 'guoyu', '国语', '普通话'
        }
        subtitle_languages = meta.get('subtitle_languages', [])
        if isinstance(subtitle_languages, list):
            for lang in subtitle_languages:
                if str(lang).lower() in chinese_languages:
                    return True
        return False

    async def get_tags(self, meta: dict[str, Any]) -> list[str]:
        tags = []
        if meta.get('dolby_vision'):
            tags.append('db')
        if meta.get('hdr10_plus'):
            tags.append('hdrp')
        if meta.get('hlg'):
            tags.append('hlg')
        hdr = str(meta.get('hdr', '')).lower()
        if hdr and hdr != "none":
            tags.append('hdr')
        if await self._has_chinese_audio(meta):
            tags.append('gy')
        if await self._has_chinese_subs(meta):
            tags.append('zz')
        if meta.get('diy') or "DIY" in str(meta.get('edition', '')):
            tags.append('diy')
        return tags

    async def upload(self, meta: dict[str, Any], disctype: str) -> bool:
        common = COMMON(config=self.config)
        announce_url = self.announce_url or "https://ourbits.club/announce.php"
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag, announce_url=announce_url)
        desc_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        if not os.path.exists(desc_file):
            await self.edit_desc(meta)

        ext_meta = meta.get('ptgen', await self.get_external_meta(meta))
        small_descr = ' / '.join(ext_meta.get("trans_title", [])) if ext_meta.get("trans_title") else meta.get('title', '')
        raw_id = str(meta.get('imdb_id', '0')).replace('tt', '').strip()
        imdb_url = f"http://www.imdb.com/title/tt{raw_id.zfill(7)}/" if (raw_id.isdigit() and int(raw_id) != 0) else ""
        douban_url = str(meta.get('douban_url', '')).strip() or str(ext_meta.get("douban_url", "")).strip()
        external_url = imdb_url or douban_url

        data: dict[str, Any] = {
            "name": meta['name'].replace('PQ10', 'HDR'),
            "small_descr": small_descr,
            "descr": open(desc_file, 'r', encoding='utf-8').read(),
            "type": await self.get_type_category_id(meta),
            "medium_sel": await self.get_medium_sel(meta),
            "codec_sel": await self.get_codec_sel(meta),
            "audiocodec_sel": await self.get_audiocodec_sel(meta),
            "standard_sel": await self.get_standard_sel(meta),
            "processing_sel": await self.get_processing_sel(meta),
            "team_sel": 0,
            "uplver": 'yes' if (meta.get('anon') != 0 or self.config['TRACKERS'].get(self.tracker, {}).get('anon', False)) else 'no',
            "url": external_url,
        }
        tag_values = await self.get_tags(meta)
        if tag_values:
            data["tags[]"] = tag_values
        if meta.get('personalrelease'):
            data["pr"] = "yes"

        cookiefile = f"{meta['base_dir']}/data/cookies/OURBITS.txt"
        cookies = await common.parseCookieFile(cookiefile)
        async with httpx.AsyncClient(cookies=cookies, timeout=60.0, follow_redirects=True) as client:
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
            with open(torrent_path, 'rb') as f:
                torrent_bytes = f.read()
                files = {
                    "file": ("upload.torrent", torrent_bytes, "application/x-bittorrent"),
                    "torrentfile": ("upload.torrent", torrent_bytes, "application/x-bittorrent"),
                }
                resp = await client.post("https://ourbits.club/takeupload.php", data=data, files=files)

                success_match = None
                if "details.php?id=" in str(resp.url):
                    success_match = re.search(r"id=(\d+)", str(resp.url))
                if not success_match and "details.php?id=" in resp.text:
                    success_match = re.search(r"details\.php\?id=(\d+)", resp.text)

                if success_match:
                    new_id = success_match.group(1)
                    console.print(f"[green]Uploaded to OURBITS! [yellow]https://ourbits.club/details.php?id={new_id}[/yellow][/green]")
                    if "tracker_status" not in meta:
                        meta["tracker_status"] = {}
                    meta["tracker_status"][self.tracker] = {"upload": True, "torrent_id": new_id, "status_message": "Success"}
                    await self.download_new_torrent(new_id, torrent_path, meta)
                    return True

                if "该种子已存在" in resp.text:
                    existing_link = re.search(r'https://ourbits\.club/details\.php\?id=\d+', resp.text)
                    link_str = existing_link.group(0) if existing_link else "未知链接"
                    console.print(f"[bold red]错误：该种子已在 OURBITS 存在！[/bold red]")
                    console.print(f"[red]已有种子链接: [yellow]{link_str}[/yellow][/red]")
                    return False

                error_log = f"{meta['base_dir']}/tmp/OURBITS_ERROR.html"
                with open(error_log, 'w', encoding='utf-8') as ef:
                    ef.write(resp.text)
                console.print(f"[red]上传失败，详情见: {error_log}[/red]")
                return False

    async def download_new_torrent(self, id: str, torrent_path: str, meta: dict[str, Any]) -> None:
        url = f"https://ourbits.club/download.php?id={id}&passkey={self.passkey}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url)
            if r.status_code == 200:
                with open(torrent_path, "wb") as f:
                    f.write(r.content)
                try:
                    from src.clients import Clients
                    client_inst = Clients(config=self.config)
                    await client_inst.add_to_client(meta, self.tracker)
                except Exception as e:
                    console.print(f"[red]Push to client failed: {e}[/red]")
