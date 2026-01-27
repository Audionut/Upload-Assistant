# -*- coding: utf-8 -*-
# Upload Assistant — OURBITS Tracker Class
from __future__ import annotations

import os
import re
import shlex
import asyncio
from typing import Any

import httpx
from bs4 import BeautifulSoup

from src.trackers.COMMON import COMMON
from src.exceptions import * # noqa E403
from src.console import console


class OURBITS:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.tracker = 'OURBITS'
        self.source_flag = 'OURBITS'
        self.passkey = str(config['TRACKERS'].get('OURBITS', {}).get('passkey', '')).strip()
        self.torrent_url = "https://ourbits.club/details.php?id="
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
        combined = f"{str(meta.get('genres', '')).lower()} {str(meta.get('keywords', '')).lower()}"
        if 'documentary' in combined: cat_id = 410
        elif 'animation' in combined or 'anime' in combined: cat_id = 411
        elif 'concert' in combined: cat_id = 419
        elif 'sport' in combined: cat_id = 415
        return cat_id

    async def get_medium_sel(self, meta: dict[str, Any]) -> int:
        if meta.get('is_disc', '') == "BDMV":
            return 12 if meta.get('resolution') == '2160p' else 1
        medium_map = {"HDTV": 5, "UHDTV": 13, "WEBDL": 9, "WEBRIP": 7, "ENCODE": 7, "REMUX": 7, "DVDR": 2, "CD": 8}
        return medium_map.get(meta.get('type', ''), 7)

    async def get_codec_sel(self, meta: dict[str, Any]) -> int:
        codecmap = {"AVC": 12, "H.264": 12, "x264": 12, "HEVC": 14, "H.265": 14, "x265": 14, "MPEG-2": 15, "VC-1": 16, "Xvid": 17, "AV1": 19}
        searchcodec = meta.get('video_codec', meta.get('video_encode'))
        return codecmap.get(searchcodec, 18)

    async def get_audiocodec_sel(self, meta: dict[str, Any]) -> int:
        audio = str(meta.get('audio', ''))
        if "Atmos" in audio: return 14
        if "DTS:X" in audio: return 21
        if "DTS-HD" in audio: return 1
        if any(x in audio for x in ["TrueHD", "True HD"]): return 2
        if "DTS" in audio: return 4
        if "LPCM" in audio: return 5
        if "FLAC" in audio: return 13
        if "AAC" in audio: return 7
        if any(x in audio for x in ["AC3", "DD"]): return 6
        return 4

    async def get_standard_sel(self, meta: dict[str, Any]) -> int:
        res_map = {'2160p': 5, '1080p': 1, '1080i': 2, '720p': 3, 'SD': 4}
        return res_map.get(meta.get('resolution'), 1)

    async def get_processing_sel(self, meta: dict[str, Any]) -> int:
        EURO_US_LIST = [
            '阿尔巴尼亚', '爱尔兰', '爱沙尼亚', '安道尔', '奥地利', '白俄罗斯', '保加利亚',
            '北马其顿', '比利时', '冰岛', '波黑', '波兰', '丹麦', '德国', '法国',
            '梵蒂冈', '芬兰', '荷兰', '黑山', '捷克', '克罗地亚', '拉脱维亚', '立陶宛',
            '列支敦士登', '卢森堡', '罗马尼亚', '马耳他', '摩尔多瓦', '摩纳哥', '挪威',
            '葡萄牙', '瑞典', '瑞士', '塞尔维亚', '塞浦路斯', '圣马力诺', '斯洛伐克',
            '斯洛文尼亚', '乌克兰', '西班牙', '希腊', '匈牙利', '意大利', '英国',
            '安提瓜和巴布达', '巴巴多斯', '巴哈马', '巴拿马', '伯利兹', '多米尼加', '多米尼克',
            '格林纳达', '哥斯达黎加', '古巴', '海地', '洪都拉斯', '加拿大', '美国', '墨西哥',
            '尼加拉瓜', '萨尔瓦多', '圣基茨和尼维斯', '圣卢西亚', '圣文森特和格林纳丁斯',
            '特立尼达和多巴哥', '危地马拉', '牙买加', '阿根廷', '巴拉圭', '巴西', '秘鲁',
            '玻利维亚', '厄瓜多尔', '哥伦比亚', '圭亚那', '苏里南', '委内瑞拉', '乌拉圭',
            '智利', '捷克斯洛伐克','澳大利亚','西德','新西兰'
        ]
        sources = [str(meta.get('region', '')), str(meta.get('country', '')), str(meta.get('ptgen', {}).get('region', '')), str(meta.get('ptgen', {}).get('country', '')), str(meta.get('ptgen', {}).get('bbcode', ''))]
        search_pool = "|".join(sources)
        for country in EURO_US_LIST:
            if country in search_pool: return 2
        pool_lower = search_pool.lower()
        if any(x in pool_lower for x in ['usa', 'united states', 'uk', 'gb', 'france', 'germany', 'canada', 'europe']): return 2
        if any(x in pool_lower for x in ['china', '大陆', '中国', 'mainland', 'chn']): return 1
        if any(x in pool_lower for x in ['hong kong', 'taiwan', 'macau', '香港', '台湾', 'hk', 'tw']): return 3
        if any(x in pool_lower for x in ['japan', '日本', 'jp']): return 4
        if any(x in pool_lower for x in ['korea', '韩国', 'kr']): return 5
        return 6

    async def get_external_meta(self, meta: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {"bbcode": "", "trans_title": [], "douban_url": ""}
        if not self.meta_script: return result
        imdb_id = str(meta.get('imdb_id', '')).strip()
        arg = f"tt{imdb_id.replace('tt', '').zfill(7)}" if imdb_id and imdb_id != '0' else meta.get("douban_url")
        if not arg: return result
        try:
            cmdline = shlex.split(self.meta_script) + [str(arg).strip()]
            proc = await asyncio.create_subprocess_exec(*cmdline, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.meta_timeout)
            output = stdout.decode('utf-8').strip()
            if output:
                result["bbcode"] = output
                m = re.search(r'^[ \t]*◎译　　名[ \t　]+(.+)$', output, flags=re.M)
                if m: result["trans_title"] = [p.strip() for p in re.split(r'\s*/\s*', m.group(1).strip()) if p.strip()]
                douban_match = re.search(r"https?://(?:movie\.)?douban\.com/subject/\d+/?", output)
                if douban_match: result["douban_url"] = douban_match.group(0)
        except Exception: pass
        return result

    async def edit_desc(self, meta: dict[str, Any]) -> None:
        out_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        ext_meta = await self.get_external_meta(meta)
        meta['ptgen'] = ext_meta
        with open(out_path, 'w', encoding='utf-8') as descfile:
            if ext_meta.get("bbcode"): descfile.write(ext_meta["bbcode"] + "\n\n")
            if meta.get('discs'):
                for each in meta['discs']:
                    content = each['summary'] if each['type'] == "BDMV" else f"{each['vob_mi']}\n{each['ifo_mi']}"
                    descfile.write(f"[quote]{content}[/quote]\n\n")
            else:
                mi_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt"
                if os.path.exists(mi_path):
                    with open(mi_path, 'r', encoding='utf-8') as f: descfile.write(f"[quote]{f.read()}[/quote]\n")
            for img in meta.get('image_list', [])[:int(meta.get('screens', 5))]:
                descfile.write(f"[url={img['web_url']}][img]{img['img_url']}[/img][/url]")

    async def _has_chinese_audio(self, meta: dict[str, Any]) -> bool:
        chinese_langs = {'chinese', 'mandarin', 'cantonese', 'zh', 'zho', 'chi', 'cmn', 'yue', 'putonghua', 'guoyu', '国语', '普通话'}
        audio_languages = meta.get('audio_languages', [])
        return any(str(lang).lower() in chinese_langs for lang in audio_languages) if isinstance(audio_languages, list) else False

    async def _has_chinese_subs(self, meta: dict[str, Any]) -> bool:
        chinese_langs = {'chinese', 'mandarin', 'cantonese', 'zh', 'zho', 'chi', 'cmn', 'yue', 'putonghua', 'guoyu', '国语', '普通话'}
        subtitle_languages = meta.get('subtitle_languages', [])
        return any(str(lang).lower() in chinese_langs for lang in subtitle_languages) if isinstance(subtitle_languages, list) else False

    async def get_tags(self, meta: dict[str, Any]) -> list[str]:
        tags = []
        if meta.get('dolby_vision'): tags.append('db')
        if meta.get('hdr10_plus'): tags.append('hdrp')
        if meta.get('hlg'): tags.append('hlg')
        if str(meta.get('hdr', '')).lower() not in ["none", ""]: tags.append('hdr')
        if await self._has_chinese_audio(meta): tags.append('gy')
        if await self._has_chinese_subs(meta): tags.append('zz')
        return tags

    async def upload(self, meta: dict[str, Any], disctype: str) -> bool:
        common = COMMON(config=self.config)
        await common.create_torrent_for_upload(meta, self.tracker, self.source_flag, announce_url=self.announce_url)
        await self.edit_desc(meta)
        
        desc_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt"
        ext_meta = meta.get('ptgen', {})
        small_descr = ' / '.join(ext_meta.get("trans_title", [])) if ext_meta.get("trans_title") else meta.get('title', '')
        raw_id = str(meta.get('imdb_id', '0')).replace('tt', '').strip()
        imdb_url = f"http://www.imdb.com/title/tt{raw_id.zfill(7)}/" if (raw_id.isdigit() and int(raw_id) != 0) else ""

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
            "url": imdb_url or str(ext_meta.get("douban_url", "")),
        }
        tag_values = await self.get_tags(meta)
        if tag_values: data["tags[]"] = tag_values

        cookiefile = f"{meta['base_dir']}/data/cookies/OURBITS.txt"
        cookies = await common.parseCookieFile(cookiefile)
        
        # 统一初始化状态字典
        if "tracker_status" not in meta: meta["tracker_status"] = {}

        async with httpx.AsyncClient(cookies=cookies, timeout=60.0, follow_redirects=True) as client:
            torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
            with open(torrent_path, 'rb') as f:
                torrent_bytes = f.read()
                files = {"file": ("upload.torrent", torrent_bytes, "application/x-bittorrent"), "torrentfile": ("upload.torrent", torrent_bytes, "application/x-bittorrent")}
                resp = await client.post("https://ourbits.club/takeupload.php", data=data, files=files)
                
                resp_text = resp.text
                resp_url = str(resp.url)
                soup = BeautifulSoup(resp_text, 'lxml')

                # --- 1. 重复识别逻辑 ---
                if "该种子已存在" in resp_text:
                    stdmsg = soup.find('td', id='stdmsg')
                    dupe_id = ""
                    if stdmsg:
                        dupe_link = stdmsg.find('a', href=re.compile(r"details\.php\?id=\d+"))
                        if dupe_link:
                            dupe_id = re.search(r"id=(\d+)", dupe_link['href']).group(1)
                    
                    if dupe_id:
                        console.print(f"[bold red]错误：该种子已在 OURBITS 存在！[/bold red]")
                        console.print(f"[red]种子链接: [yellow]https://ourbits.club/details.php?id={dupe_id}[/yellow][/red]")
                        
                        # 重要：更新 meta 状态并返回 True（假装成功以阻止外部报错）
                        meta["tracker_status"][self.tracker] = {"upload": False, "success": True, "status_message": "Duplicate", "torrent_id": dupe_id}
                        return True 

                # --- 2. 成功上传逻辑 ---
                success_pattern = r"details\.php\?id=(\d+)(?!.*userdetails)"
                success_match = re.search(success_pattern, resp_url) or (re.search(success_pattern, resp_text) if "stdmsg" not in resp_text else None)
                
                if success_match and success_match.group(1) != "52027":
                    new_id = success_match.group(1)
                    
                    meta["tracker_status"][self.tracker] = {"upload": True, "success": True, "torrent_id": new_id, "status_message": "Success"}
                    await self.download_new_torrent(new_id, torrent_path, meta)
                    return True
                
                # --- 3. 真正失败 ---
                console.print(f"[red]上传失败，详情见 tmp/OURBITS_ERROR.html[/red]")
                with open(f"{meta['base_dir']}/tmp/OURBITS_ERROR.html", 'w', encoding='utf-8') as ef: ef.write(resp_text)
                meta["tracker_status"][self.tracker] = {"upload": False, "success": False, "status_message": "Failed"}
                return False

    async def download_new_torrent(self, id: str, torrent_path: str, meta: dict[str, Any]) -> None:
        url = f"https://ourbits.club/download.php?id={id}&passkey={self.passkey}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url)
            if r.status_code == 200:
                with open(torrent_path, "wb") as f: f.write(r.content)
                try:
                    from src.clients import Clients
                    client_inst = Clients(config=self.config)
                    await client_inst.add_to_client(meta, self.tracker)
                except Exception: pass
