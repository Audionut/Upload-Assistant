# -*- coding: utf-8 -*-
# Upload Assistant — HDSKY Tracker Class
from bs4 import BeautifulSoup
import asyncio
import os
import re
import shlex
import httpx
from src.trackers.COMMON import COMMON
from src.exceptions import *  # noqa E403
from src.console import console


class HDSKY:

    def __init__(self, config):
        self.config = config
        self.tracker = 'HDSKY'
        self.source_flag = 'HDSKY'
        self.passkey = str(config['TRACKERS'].get('HDSKY', {}).get('passkey', '')).strip()
        self.meta_script = str(config['TRACKERS'].get('HDSKY', {}).get('meta_script', '')).strip()
        self.meta_timeout = int(config['TRACKERS'].get('HDSKY', {}).get('meta_timeout', 30))
        self.signature = None
        self.banned_groups = [""]

    async def validate_credentials(self, meta):
        vcookie = await self.validate_cookies(meta)
        return True if vcookie is True else False

    async def validate_cookies(self, meta):
        common = COMMON(config=self.config)
        url = "https://hdsky.me"
        cookiefile = f"{meta['base_dir']}/data/cookies/HDSKY.txt"
        if not os.path.exists(cookiefile):
            return False
        cookies = await common.parseCookieFile(cookiefile)
        try:
            async with httpx.AsyncClient(cookies=cookies, timeout=10.0) as client:
                resp = await client.get(url)
                return True if "logout.php" in resp.text else False
        except Exception:
            return False

    async def search_existing(self, meta, _disctype):
        dupes = []
        common = COMMON(config=self.config)
        cookiefile = f"{meta['base_dir']}/data/cookies/HDSKY.txt"
        if not os.path.exists(cookiefile):
            return []
        cookies = await common.parseCookieFile(cookiefile)
        imdb_id_raw = str(meta.get('imdb_id', '0')).replace('tt', '').strip()
        imdb = f"tt{imdb_id_raw.zfill(7)}" if imdb_id_raw.isdigit() and int(imdb_id_raw) != 0 else ""
        if not imdb:
            return []
        search_url = f"https://hdsky.me/torrents.php?incldead=0&spstate=0&inclbookmarked=0&search={imdb}&search_area=4&search_mode=0"
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

    async def get_type_category_id(self, meta):
        cat_id = 401
        category = meta.get('category')
        if category == 'TV':
            cat_id = 411 if meta.get('tv_pack') else 402

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
            cat_id = 404
        if 'animation' in genres or 'animation' in keywords:
            cat_id = 405
        return cat_id

    async def get_medium_sel(self, meta):
        if meta.get('is_disc', '') == "BDMV":
            return 13 if meta['resolution'] == '2160p' else 1
        if meta.get('is_disc', '') == "HD DVD":
            return 2
        medium_map = {
            "HDTV": 5,
            "REMUX": 3,
            "WEBDL": 11,
            "WEBRIP": 7,
            "ENCODE": 7,
            "DVDR": 6,
            "CD": 8,
        }
        return medium_map.get(meta.get('type', ''), 7)

    async def get_codec_sel(self, meta):
        codecmap = {
            "AVC": 1,
            "H.264": 1,
            "x264": 10,
            "HEVC": 12,
            "H.265": 13,
            "x265": 13,
            "MPEG-2": 4,
            "VC-1": 2,
            "Xvid": 3,
            "VP9": 17,
            "AV1": 16,
            "ProRes": 15,
        }
        searchcodec = meta.get('video_codec', meta.get('video_encode'))
        return codecmap.get(searchcodec, 11)

    async def get_audiocodec_sel(self, meta):
        audio = meta.get('audio', '')
        if "DTS:X" in audio:
            return 16
        if "Atmos" in audio and ("TrueHD" in audio or "True HD" in audio):
            return 17
        if "Atmos" in audio and ("DDP" in audio or "E-AC3" in audio or "EAC3" in audio):
            return 21
        if "TrueHD" in audio or "True HD" in audio:
            return 11
        if "DTS-HD MA" in audio or "DTS-HD.MA" in audio:
            return 10
        if "DTS-HD HR" in audio:
            return 14
        if "DTS-HD" in audio:
            return 10
        if "DTS" in audio:
            return 3
        if "LPCM" in audio:
            return 13
        if "PCM" in audio:
            return 19
        if "FLAC" in audio:
            return 1
        if "APE" in audio:
            return 2
        if "MP3" in audio:
            return 4
        if "OGG" in audio:
            return 5
        if "AAC" in audio:
            return 6
        if "AC3" in audio or "DD" in audio:
            return 12
        if "WAV" in audio:
            return 15
        if "DSD" in audio:
            return 18
        if "Opus" in audio:
            return 22
        if "E-AC3" in audio or "EAC3" in audio or "DDP" in audio:
            return 20
        if "ALAC" in audio:
            return 23
        return 7

    async def get_standard_sel(self, meta):
        res_map = {'4320p': 6, '2160p': 5, '1080p': 1, '1080i': 2, '720p': 3, 'SD': 4}
        return res_map.get(meta.get('resolution'), 1)

    async def get_external_meta(self, meta):
        result = {"bbcode": "", "trans_title": []}
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
        except Exception:
            pass
        return result

    async def edit_desc(self, meta):
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

    async def get_option_sel(self, meta):
        options = []
        hdr = str(meta.get('hdr', '')).lower()
        if meta.get('dolby_vision'):
            options.append('15')
        if meta.get('hlg'):
            options.append('16')
        if meta.get('hdr10_plus'):
            options.append('17')
        if hdr and hdr != "none":
            options.append('9')
        if meta.get('atmos'):
            options.append('21')
        if meta.get('dts_x'):
            options.append('23')
        return options

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag)
        desc_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        if not os.path.exists(desc_file):
            await self.edit_desc(meta)

        ext_meta = meta.get('ptgen', await self.get_external_meta(meta))
        small_descr = ' / '.join(ext_meta.get("trans_title", [])) if ext_meta.get("trans_title") else meta.get('title', '')
        raw_id = str(meta.get('imdb_id', '0')).replace('tt', '').strip()
        imdb_url = f"http://www.imdb.com/title/tt{raw_id.zfill(7)}/" if (raw_id.isdigit() and int(raw_id) != 0) else ""
        douban_url = str(meta.get('douban_url', '')).strip()

        data = {
            "name": meta['name'].replace('PQ10', 'HDR'),
            "small_descr": small_descr,
            "descr": open(desc_file, 'r', encoding='utf-8').read(),
            "type": await self.get_type_category_id(meta),
            "medium_sel": await self.get_medium_sel(meta),
            "codec_sel": await self.get_codec_sel(meta),
            "audiocodec_sel": await self.get_audiocodec_sel(meta),
            "standard_sel": await self.get_standard_sel(meta),
            "team_sel": 0,
            "uplver": 'yes' if (meta.get('anon') != 0 or self.config['TRACKERS'].get(self.tracker, {}).get('anon', False)) else 'no',
            "url": imdb_url,
            "url_douban": douban_url,
        }
        option_sel = await self.get_option_sel(meta)
        if option_sel:
            data["option_sel[]"] = option_sel
        if meta.get('personalrelease'):
            data["pr"] = "yes"

        cookiefile = f"{meta['base_dir']}/data/cookies/HDSKY.txt"
        cookies = await common.parseCookieFile(cookiefile)
        async with httpx.AsyncClient(cookies=cookies, timeout=60.0, follow_redirects=True) as client:
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
            with open(torrent_path, 'rb') as f:
                torrent_bytes = f.read()
                files = {
                    "file": ("upload.torrent", torrent_bytes, "application/x-bittorrent"),
                    "torrentfile": ("upload.torrent", torrent_bytes, "application/x-bittorrent"),
                }
                resp = await client.post("https://hdsky.me/takeupload.php", data=data, files=files)

                success_match = None
                if "details.php?id=" in str(resp.url):
                    success_match = re.search(r"id=(\d+)", str(resp.url))
                if not success_match and "details.php?id=" in resp.text:
                    success_match = re.search(r"details\.php\?id=(\d+)", resp.text)

                if success_match:
                    new_id = success_match.group(1)
                    console.print(f"[green]Uploaded to HDSKY! [yellow]https://hdsky.me/details.php?id={new_id}[/yellow][/green]")
                    if "tracker_status" not in meta:
                        meta["tracker_status"] = {}
                    meta["tracker_status"][self.tracker] = {"upload": True, "torrent_id": new_id, "status_message": "Success"}
                    await self.download_new_torrent(new_id, torrent_path, meta)
                    return True

                if "该种子已存在" in resp.text:
                    existing_link = re.search(r'https://hdsky\.me/details\.php\?id=\d+', resp.text)
                    link_str = existing_link.group(0) if existing_link else "未知链接"
                    console.print(f"[bold red]错误：该种子已在 HDSKY 存在！[/bold red]")
                    console.print(f"[red]已有种子链接: [yellow]{link_str}[/yellow][/red]")
                    return False

                error_log = f"{meta['base_dir']}/tmp/HDSKY_ERROR.html"
                with open(error_log, 'w', encoding='utf-8') as ef:
                    ef.write(resp.text)
                console.print(f"[red]上传失败，详情见: {error_log}[/red]")
                return False

    async def download_new_torrent(self, id, torrent_path, meta):
        url = f"https://hdsky.me/download.php?id={id}&passkey={self.passkey}"
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
