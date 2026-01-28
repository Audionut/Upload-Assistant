import os
import httpx
import json
import re
from bs4 import BeautifulSoup
import bencodepy
import cli_ui
import subprocess
import shlex
import asyncio

from src.trackers.COMMON import COMMON


class SSD(COMMON):
    
    def __init__(self, config):
        super().__init__(config)
        self.config = config
        self.tracker = 'SSD'
        self.source_flag = 'SSD'
        
        tracker_config = self.config['TRACKERS'].get(self.tracker, {})
        self.cookie_file = tracker_config.get('cookie')
        self.anon = tracker_config.get('anon', True)
        self.offer = tracker_config.get('offer', True)
        self.passkey = tracker_config.get('passkey')
        self.meta_script = str(tracker_config.get('meta_script', '')).strip()
        self.meta_timeout = int(tracker_config.get('meta_timeout', 30))
        self.upload_url = 'https://springsunday.net/takeupload.php'
        self.torrent_url = 'https://springsunday.net/details.php?id='
        self.banned_groups = []

        self.imdb_id_with_prefix = None
        self.douban_url = ""
        
        self.session = httpx.AsyncClient()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'})

        self.medium_map = {'Blu-ray': '1', 'Remux': '4', 'BDRip': '6', 'WEB-DL': '7', 'WEBRip': '8', 'HDTV': '5', 'Other': '99'}
        self.codec_map = {'H.265': '1', 'HEVC': '1', 'x265': '1', 'H.264': '2', 'AVC': '2', 'x264': '2', 'VC-1': '3', 'MPEG-2': '4', 'AV1': '5', 'Other': '99'}
        self.audiocodec_map = {'DTS:X': '1', 'DTS-HD': '1', 'TrueHD': '2', 'LPCM': '6', 'FLAC': '7', 'DDP': '11', 'E-AC-3': '11', 'EAC3': '11', 'DD+': '11', 'DTS': '3', 'AC-3': '4', 'AC3': '4', 'DD': '4', 'AAC': '5', 'APE': '8', 'WAV': '9', 'MP3': '10', 'OPUS': '12', 'Other': '99'}
        self.resolution_map = {'2160p': '1', '1080p': '2', '1080i': '3', '720p': '4', 'SD': '5', 'Other': '99'}
        self.category_map = {'MOVIE': '501', 'TV_SERIES': '502', 'DOCS': '503', 'TV_SHOWS': '505', 'SPORTS': '506', 'MV': '507', 'MUSIC': '508', 'AUDIO': '510', 'OTHER': '509'}

    def _log(self, meta, message):
        if meta.get('debug', False):
            print(message)

    async def edit_torrent(self, meta, tracker, source_flag):
        edited_torrent_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'], f"[{tracker}].torrent")
        decoded_torrent = None
        user_input_path = meta.get('path')
        if user_input_path:
            qbt_client = None
            try:
                from qbittorrentapi import Client
                client_config = self.config.get('TORRENT_CLIENTS', {}).get('qbittorrent', {})
                qbt_url, qbt_port, qbt_user, qbt_pass = (client_config.get(k) for k in ['qbit_url', 'qbit_port', 'qbit_user', 'qbit_pass'])
                if all([qbt_url, qbt_port, qbt_user, qbt_pass]):
                    qbt_client = Client(host=f"{qbt_url}:{qbt_port}", username=qbt_user, password=qbt_pass)
                    qbt_client.auth_log_in()
                    target_name = os.path.basename(os.path.normpath(user_input_path))
                    for torrent in qbt_client.torrents_info():
                        if torrent.name == target_name:
                            content_path_in_qb = os.path.join(torrent.save_path, torrent.name)
                            if os.path.normpath(content_path_in_qb) == os.path.normpath(user_input_path):
                                self._log(meta, f"[{self.tracker}] ✅ 在 qb 中找到完美匹配的种子，正在导出...")
                                torrent_content = qbt_client.torrents_export(torrent_hash=torrent.hash)
                                decoded_torrent = bencodepy.decode(torrent_content)
                                break
            except Exception as e:
                self._log(meta, f"[{self.tracker}] 在 qb 中查找种子时出错: {e}")
            finally:
                if qbt_client and qbt_client.is_logged_in:
                    qbt_client.auth_log_out()
        if not decoded_torrent:
            self._log(meta, f"[{self.tracker}] 未在 qb 中找到匹配种子，回退到使用 BASE.torrent。")
            base_torrent_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'], 'BASE.torrent')
            if not os.path.exists(base_torrent_path):
                self._log(meta, f"[{self.tracker}] ❌ 错误：BASE.torrent 文件也不存在，无法编辑。")
                return False
            with open(base_torrent_path, 'rb') as f:
                decoded_torrent = bencodepy.decode(f.read())
        announce_url = 'https://on.springsunday.net/announce.php'
        decoded_torrent[b'announce'] = announce_url.encode('utf-8')
        if source_flag: decoded_torrent[b'source'] = source_flag.encode('utf-8')
        if b'info' in decoded_torrent: decoded_torrent[b'info'][b'private'] = 1
        with open(edited_torrent_path, 'wb') as f:
            f.write(bencodepy.encode(decoded_torrent))
        return True

    async def _get_douban_link_from_imdb(self, imdb_id_with_prefix):
        search_url = f"https://search.douban.com/movie/subject_search?search_text={imdb_id_with_prefix}"
        try:
            response = await self.session.get(search_url, timeout=10)
            response.raise_for_status()
            pattern = re.compile(r'window\.__DATA__ = (\{.*?\});', re.DOTALL)
            match = pattern.search(response.text)
            if not match: return None
            data = json.loads(match.group(1))
            if data.get('items') and len(data['items']) > 0:
                douban_link = data['items'][0].get('url')
                if douban_link:
                    return douban_link
            return None
        except Exception:
            return None

    async def get_external_meta(self, meta):
        result = {"bbcode": "", "trans_title": [], "douban_url": ""}
        if not self.meta_script:
            return result
        imdb_id = str(meta.get('imdb_id', '')).strip()
        arg = f"tt{imdb_id.replace('tt', '').zfill(7)}" if imdb_id and imdb_id != '0' else meta.get("douban_url")
        if not arg:
            return result
        try:
            cmdline = shlex.split(self.meta_script) + [str(arg).strip()]
            proc = await asyncio.create_subprocess_exec(
                *cmdline,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self.meta_timeout)
            output = stdout.decode('utf-8').strip()
            if output:
                result["bbcode"] = output
                m = re.search(r'^[ \t]*◎译　　名[ \t　]+(.+)$', output, flags=re.M)
                if m:
                    result["trans_title"] = [
                        p.strip()
                        for p in re.split(r'\s*/\s*', m.group(1).strip())
                        if p.strip()
                    ]
                douban_match = re.search(r"https?://(?:movie\.)?douban\.com/subject/\d+/?", output)
                if douban_match:
                    result["douban_url"] = douban_match.group(0)
        except Exception:
            pass
        return result

    async def _resolve_douban_link(self, meta):
        self.douban_url = ""
        douban_link, is_manual_mode = "", False
        if meta.get('category') == 'TV' and re.search(r'[Ss]0*([2-9]|[1-9][0-9])', meta.get('name', '')):
            is_manual_mode, season_num = True, re.search(r'[Ss](\d+)', meta.get('name', '')).group(1)
            cli_ui.info_section(f"[{self.tracker}] 非第一季剧集手动干预")
            cli_ui.info(f"检测到季数为 S{int(season_num):02}。为确保准确性，请手动提供豆瓣链接。")
            douban_link = cli_ui.ask_string("请输入正确的豆瓣链接:", default="").strip()

        if not is_manual_mode:
            ext_meta = await self.get_external_meta(meta)
            if ext_meta.get("douban_url"):
                self.douban_url = ext_meta["douban_url"]
                meta['ptgen'] = ext_meta
                douban_link = self.douban_url
            else:
                douban_link = await self._get_douban_link_from_imdb(self.imdb_id_with_prefix)

        if not douban_link:
            if not is_manual_mode:
                cli_ui.info_section(f"[{self.tracker}] 豆瓣链接自动获取失败")
                cli_ui.info(f"未能通过 IMDb ID '{self.imdb_id_with_prefix}' 自动找到豆瓣链接。")
            douban_link = cli_ui.ask_string("请手动输入正确的豆瓣链接 (或直接按回车跳过):", default="").strip()

        if douban_link:
            self.douban_url = douban_link
        return bool(douban_link)

    def _split_region_candidates(self, regions):
        if not regions:
            return []
        if isinstance(regions, str):
            parts = re.split(r"[/,|，、;；]", regions)
            return [part.strip() for part in parts if part.strip()]
        return [str(part).strip() for part in regions if str(part).strip()]

    def _get_genres(self, meta):
        genres = meta.get('genres')
        if not genres:
            genres = meta.get('imdb_info', {}).get('genres')
        if not genres:
            return []
        if isinstance(genres, list):
            return [str(item).strip() for item in genres if str(item).strip()]
        if isinstance(genres, str):
            parts = re.split(r"[/,|，、;；]", genres)
            return [part.strip() for part in parts if part.strip()]
        return []

    def _has_genre(self, genres, targets):
        lowered = {str(g).lower() for g in genres}
        for target in targets:
            if str(target).lower() in lowered:
                return True
        return False

    def _get_region_id_from_meta(self, meta=None):
        EUROPE_AMERICA_OCEANIA_SET = {'阿尔巴尼亚', '爱尔兰', '爱沙尼亚', '安道尔', '奥地利', '白俄罗斯', '保加利亚', '北马其顿', '比利时', '冰岛', '波黑', '波兰', '丹麦', '德国', '法国', '梵蒂冈', '芬兰', '荷兰', '黑山', '捷克', '克罗地亚', '拉脱维亚', '立陶宛', '列支敦士登', '卢森堡', '罗马尼亚', '马耳他', '摩尔多瓦', '摩纳哥', '挪威', '葡萄牙', '瑞典', '瑞士', '塞尔维亚', '塞浦路斯', '圣马力诺', '斯洛伐克', '斯洛文尼亚', '乌克兰', '西班牙', '希腊', '匈牙利', '意大利', '英国', '安提瓜和巴布达', '巴巴多斯', '巴哈马', '巴拿马', '伯利兹', '多米尼加', '多米尼克', '格林纳达', '哥斯达黎加', '古巴', '海地', '洪都拉斯', '加拿大', '美国', '墨西哥', '尼加拉瓜', '萨尔瓦多', '圣基茨和尼维斯', '圣卢西亚', '圣文森特和格林纳丁斯', '特立尼达和多巴哥', '危地马拉', '牙买加', '阿根廷', '巴拉圭', '巴西', '秘鲁', '玻利维亚', '厄瓜多尔', '哥伦比亚', '圭亚那', '苏里南', '委内瑞拉', '乌拉圭', '智利', '捷克斯洛伐克', '澳大利亚', '西德', '新西兰'}
        CHINA_MAINLAND = {'中国大陆', '中国内地', '大陆', '内地', '中国'}
        CHINA_HK = {'中国香港', '香港'}
        CHINA_TW = {'中国台湾', '台湾'}
        JAPAN = {'日本', 'Japan'}
        KOREA = {'韩国', 'Korea', 'South Korea'}
        INDIA = {'印度', 'India'}
        RUSSIA = {'俄罗斯', '苏联', 'Russia', 'USSR'}
        THAILAND = {'泰国', 'Thailand'}
        REGION_CODE_MAP = {
            'CHN': '1',
            'HKG': '2',
            'TWN': '3',
            'JPN': '5',
            'KOR': '6',
            'IND': '7',
            'RUS': '8',
            'THA': '9',
            'USA': '4',
            'GBR': '4',
            'EUR': '4',
            'AUS': '4',
            'CAN': '4',
        }
        movie_regions = []
        if meta:
            meta_regions = [
                meta.get('region'),
                meta.get('country'),
                meta.get('imdb_info', {}).get('country'),
                meta.get('imdb_info', {}).get('country_list'),
                meta.get('ptgen', {}).get('region'),
                meta.get('ptgen', {}).get('country'),
            ]
            for meta_region in meta_regions:
                movie_regions.extend(self._split_region_candidates(meta_region))
        western_keywords = {
            'albania', 'ireland', 'estonia', 'andorra', 'austria', 'belarus', 'bulgaria', 'north macedonia',
            'macedonia', 'belgium', 'iceland', 'bosnia', 'poland', 'denmark', 'germany', 'france', 'vatican',
            'finland', 'netherlands', 'montenegro', 'czech', 'croatia', 'latvia', 'lithuania', 'liechtenstein',
            'luxembourg', 'romania', 'malta', 'moldova', 'monaco', 'norway', 'portugal', 'sweden', 'switzerland',
            'serbia', 'cyprus', 'san marino', 'slovakia', 'slovenia', 'ukraine', 'spain', 'greece', 'hungary',
            'italy', 'united kingdom', 'uk', 'britain', 'england', 'scotland', 'wales', 'antigua', 'barbados',
            'bahamas', 'panama', 'belize', 'dominican', 'grenada', 'costa rica', 'cuba', 'haiti', 'honduras',
            'canada', 'united states', 'usa', 'mexico', 'nicaragua', 'el salvador', 'saint kitts', 'saint lucia',
            'saint vincent', 'trinidad', 'guatemala', 'jamaica', 'argentina', 'paraguay', 'brazil', 'peru',
            'bolivia', 'ecuador', 'colombia', 'guyana', 'suriname', 'venezuela', 'uruguay', 'chile',
            'czechoslovakia', 'australia', 'west germany', 'new zealand',
        }
        for region in movie_regions:
            region = region.strip()
            if not region:
                continue
            upper_region = region.upper()
            if upper_region in REGION_CODE_MAP:
                return REGION_CODE_MAP[upper_region]
            if region in EUROPE_AMERICA_OCEANIA_SET:
                return '4'
            lower_region = region.lower()
            if any(keyword in lower_region for keyword in western_keywords):
                return '4'
            if region in CHINA_HK:
                return '2'
            if region in CHINA_MAINLAND:
                return '1'
            if region in CHINA_TW:
                return '3'
            if region in JAPAN:
                return '5'
            if region in KOREA:
                return '6'
            if region in INDIA:
                return '7'
            if region in RUSSIA:
                return '8'
            if region in THAILAND:
                return '9'
        return '99'

    def _get_small_descr(self, meta):
        ext_meta = meta.get('ptgen', {}) if isinstance(meta.get('ptgen', {}), dict) else {}
        trans_titles = ext_meta.get('trans_title', [])
        if isinstance(trans_titles, str):
            trans_titles = [trans_titles]
        trans_titles = [t.strip() for t in trans_titles if str(t).strip()]
        if trans_titles:
            return " / ".join(trans_titles)
        return str(meta.get('title') or meta.get('name', '')).strip()
        
    def _get_year_from_meta(self, meta):
        year_value = meta.get('year') or meta.get('imdb_info', {}).get('year')
        return str(year_value) if year_value else ""

    def _get_category_id(self, meta):
        genres = self._get_genres(meta)
        if self._has_genre(genres, {"真人秀", "Reality"}):
            return self.category_map.get('TV_SHOWS')
        if self._has_genre(genres, {"纪录片", "Documentary"}):
            return self.category_map.get('DOCS')
        main_category = meta.get('category')
        if main_category == 'MOVIE': return self.category_map.get('MOVIE')
        if main_category == 'TV': return self.category_map.get('TV_SERIES')
        return self.category_map.get('OTHER')

    def _get_medium_id(self, name):
        name = name.upper()
        if 'BLURAY' in name and ('X264' in name or 'X265' in name): return self.medium_map.get('BDRip')
        if 'WEB-DL' in name: return self.medium_map.get('WEB-DL')
        if 'REMUX' in name: return self.medium_map.get('Remux')
        if 'BLU-RAY' in name or 'BLURAY' in name: return self.medium_map.get('Blu-ray')
        if 'WEBRIP' in name: return self.medium_map.get('WEBRip')
        if 'HDTV' in name: return self.medium_map.get('HDTV')
        return self.medium_map.get('Other')

    def _get_codec_id(self, name):
        name = name.upper()
        if 'H.265' in name or 'X265' in name or 'HEVC' in name: return self.codec_map.get('H.265')
        if 'H.264' in name or 'X264' in name or 'AVC' in name: return self.codec_map.get('H.264')
        if 'VC-1' in name:return self.codec_map.get('VC-1')
        if 'MPEG-2' in name:return self.codec_map.get('MPEG-2')
        if 'AV1' in name:return self.codec_map.get('AV1')
        return self.codec_map.get('Other')

    def _get_audiocodec_id(self, name):
        name = name.upper()
        for key, value in self.audiocodec_map.items():
            if key.upper() in name: return value
        return self.audiocodec_map.get('Other')
        
    def _get_resolution_id(self, name):
        if '2160p' in name: return self.resolution_map.get('2160p')
        if '1080p' in name: return self.resolution_map.get('1080p')
        if '1080i' in name: return self.resolution_map.get('1080i')
        if '720p' in name: return self.resolution_map.get('720p')
        return self.resolution_map.get('Other')
    
    def _is_pack(self, meta):
        return meta.get('category') == 'TV'

    def _has_chinese_subtitle(self, meta):
        if meta.get('is_disc') == 'BDMV':
            for lang in meta.get('bdinfo', {}).get('subtitles', []):
                if 'Chinese' in lang: return True
        for track in meta.get('mediainfo', {}).get('media', {}).get('track', []):
            if track.get('@type') == 'Text' and any(ch in track.get('Language', '') for ch in ['Chinese', 'zh-Hant', 'zh-Hans', 'zh', 'yue-Hant']):
                return True
        return False

    def _get_media_bdinfo(self, meta):
        tmp_folder = os.path.join(meta['base_dir'], 'tmp', meta['uuid'])
        path_to_read = os.path.join(tmp_folder, 'BD_SUMMARY_00.txt')
        if not os.path.exists(path_to_read):
            path_to_read = os.path.join(tmp_folder, 'MEDIAINFO.txt')
        content = ""
        if os.path.exists(path_to_read):
            try:
                with open(path_to_read, 'r', encoding='utf-8') as f: content = f.read()
            except Exception: pass
        content = re.sub(r'\[code\]', '[quote]', content, flags=re.IGNORECASE)
        content = re.sub(r'\[/code\]', '[/quote]', content, flags=re.IGNORECASE)
        return content.strip()

    def _get_final_description(self, meta):
        parts = []
        
        tag = meta.get('tag', '').lstrip('-')
        declaration_map = {"HHWEB": "[b][quote][img=100x50]https://img1.pixhost.to/images/9789/656115101_hh.png[/img]\n[color=#f29d38]HHClub[/color]官组作品，[color=#f29d38]感谢[/color]原制作者发布。[/quote][/b]",
                           "CHDWEB": "[b][quote][img=100x50]https://img1.pixhost.to/images/9788/656111976_chdbits.png[/img]\n[i][color=red]CHD[/color]Bits[/i]官组作品，[i][color=red]感谢[/color][/i] 原制作者发布！[/quote][/b]",
                           "CHDBits": "[b][quote][img=100x50]https://img1.pixhost.to/images/9788/656111976_chdbits.png[/img]\n[i][color=red]CHD[/color]Bits[/i]官组作品，[i][color=red]感谢[/color][/i] 原制作者发布！[/quote][/b]",
                           "ADWeb": "[b][quote][img=144x34]https://img1.pixhost.to/images/9788/656113858_aud.png[/img]\n[b]Audiences[/b]官组作品，[color=#ffa32d]感谢[/color]原制作者发布！[/quote][/b]",
                           "MTeam": "[b][quote][img=120x37]https://img1.pixhost.to/images/9788/656113860_mt.png[/img]\n[color=orange]MTeam[/color]官组作品，[color=orange]感谢[/color]原制作者发布！[/quote][/b]"}
        if tag in declaration_map:
             parts.append(declaration_map[tag])

        if not meta.get('scene', False):
            description_file_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'], 'DESCRIPTION.txt')
            if os.path.exists(description_file_path):
                try:
                    with open(description_file_path, 'r', encoding='utf-8') as f: 
                        content = f.read()
                    content = re.sub(r'\[code\]', '[quote]', content, flags=re.IGNORECASE)
                    content = re.sub(r'\[/code\]', '[/quote]', content, flags=re.IGNORECASE)
                    if content.strip():
                        parts.append(content.strip())
                except Exception as e: 
                    self._log(meta, f"[{self.tracker}] 读取 DESCRIPTION.txt 文件时出错: {e}")
        
        return "\n\n".join(parts)

    async def _add_to_qbittorrent(self, meta, torrent_id, upload_limit_kib=-1):
        if not self.passkey:
            self._log(meta, f"[{self.tracker}] ❌ 错误：未在 config.py 的 SSD 配置中找到 'passkey'。")
            return
        download_link = f"https://springsunday.net/download.php?id={torrent_id}&passkey={self.passkey}&https=1"
        try:
            from qbittorrentapi import Client
        except ImportError:
            self._log(meta, f"[{self.tracker}] ❌ 错误：缺少 'qbittorrent-api' 库。")
            return
        client_config = self.config.get('TORRENT_CLIENTS', {}).get('qbittorrent', {})
        if not client_config:
            self._log(meta, f"[{self.tracker}] ❌ 错误：在 config.py 中未找到名为 'qbittorrent' 的客户端配置。")
            return
        qbt_url, qbt_port, qbt_user, qbt_pass = (client_config.get(k) for k in ['qbit_url', 'qbit_port', 'qbit_user', 'qbit_pass'])
        if not all([qbt_url, qbt_port, qbt_user, qbt_pass]):
            self._log(meta, f"[{self.tracker}] ❌ 错误：qBittorrent 客户端配置不完整。")
            return
        try:
            qbt_client = Client(host=f"{qbt_url}:{qbt_port}", username=qbt_user, password=qbt_pass)
            qbt_client.auth_log_in()
        except Exception as e:
            self._log(meta, f"[{self.tracker}] ❌ 连接到 qBittorrent 失败: {e}")
            return
        try:
            user_input_path = meta.get('path')
            if not user_input_path: qbt_client.auth_log_out(); return
            save_path = os.path.dirname(os.path.normpath(user_input_path))
            if not save_path: save_path = "/"
            if not os.path.isdir(save_path): qbt_client.auth_log_out(); return
            result = qbt_client.torrents_add(urls=download_link, save_path=save_path, skip_checking=True, is_paused=False, upload_limit=upload_limit_kib * 1024)
            if result == "Ok.":
                self._log(meta, f"[{self.tracker}] ✅ 种子已成功添加到 qBittorrent。")
            else:
                self._log(meta, f"[{self.tracker}] ❌ 添加到 qBittorrent 失败，客户端返回: {result}")
        except Exception as e:
            self._log(meta, f"[{self.tracker}] ❌ 添加种子到 qBittorrent 时发生错误: {e}")
        finally: qbt_client.auth_log_out()

    async def validate_credentials(self, meta):
        if not await self.validate_cookies(meta): return False
        return True

    async def validate_cookies(self, meta):
        cookie_str = await self._load_cookie_header(meta)
        if not cookie_str:
            return False
        try:
            response = await self.session.get("https://springsunday.net/upload.php", timeout=10, follow_redirects=False)
            return response.status_code == 200
        except httpx.RequestError: return False

    async def _load_cookie_header(self, meta):
        if not self.cookie_file or not os.path.exists(self.cookie_file):
            return ""
        try:
            with open(self.cookie_file, 'r', encoding='utf-8') as f:
                cookie_str = f.read().strip()
            if not cookie_str:
                return ""
            if "\t" in cookie_str or cookie_str.startswith("# Netscape"):
                common = COMMON(config=self.config)
                cookies = await common.parseCookieFile(self.cookie_file)
                cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
            self.session.cookies.update({
                k.strip(): v.strip()
                for k, v in (p.split('=', 1) for p in cookie_str.split(';') if '=' in p)
            })
            return cookie_str
        except Exception:
            return ""

    async def search_existing(self, meta, _disctype):
        dupes = []
        if not self.cookie_file or not os.path.exists(self.cookie_file):
            return []
        imdb_id_raw = str(meta.get('imdb_id', '0')).replace('tt', '').strip()
        imdb = f"tt{imdb_id_raw.zfill(7)}" if imdb_id_raw.isdigit() and int(imdb_id_raw) != 0 else ""
        if not imdb:
            return []
        search_url = f"https://springsunday.net/torrents.php?search={imdb}&search_area=4&search_mode=0"
        cookie_str = await self._load_cookie_header(meta)
        if not cookie_str:
            return []
        try:
            headers = {"Cookie": cookie_str}
            response = await self.session.get(search_url, headers=headers, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')
                rows = soup.select('table.torrents > tr:has(table.torrentname)')
                for row in rows:
                    text = row.select_one('a[href^="details.php?id="]')
                    if text and text.attrs.get('title'):
                        dupes.append(text.attrs.get('title'))
        except Exception:
            pass
        return dupes
    
    def edit_name(self, meta):
        base_name = meta.get('name', '').replace(' ', '.')
        edited_name = re.sub(r'DD\+', 'DDP', base_name, flags=re.IGNORECASE)
        category = meta.get('category')
        if category == 'TV':
            year_from_meta = self._get_year_from_meta(meta)
            if year_from_meta:
                season_pattern = re.compile(r'(S\d{2})', re.IGNORECASE)
                new_name = season_pattern.sub(fr'\g<1>.{year_from_meta}', edited_name, count=1)
                if new_name != edited_name: edited_name = new_name
        elif category == 'MOVIE':
            imdb_year = str(meta.get('imdb_info', {}).get('year', ""))
            if imdb_year:
                year_pattern = re.compile(r'\b\d{4}\b')
                if year_pattern.search(edited_name):
                    edited_name = year_pattern.sub(imdb_year, edited_name, count=1)
                else:
                    name_notag = meta.get('name_notag', '').replace(' ', '.')
                    name_notag = re.sub(r'DD\+', 'DDP', name_notag, flags=re.IGNORECASE)
                    tech_info = edited_name.replace(name_notag, '', 1).strip('.')
                    edited_name = f"{name_notag}.{imdb_year}.{tech_info}"
        edited_name = re.sub(r'\.{2,}', '.', edited_name)
        if meta.get('debug', False):
            return f"[请勿审核].{edited_name}"
        return edited_name

    async def upload(self, meta, disctype):
        self._log(meta, f"[{self.tracker}] 开始处理上传任务...")
        if not self.cookie_file or not os.path.exists(self.cookie_file):
            meta['tracker_status'][self.tracker] = {
                'status': 'failed',
                'reason': "Cookie file not configured or missing",
            }
            return False
        
        imdb_id_num = meta.get('imdb_id')
        if not imdb_id_num:
            meta['tracker_status'][self.tracker] = {'status': 'failed', 'reason': "IMDb ID not found"}
            return False
        
        self.imdb_id_with_prefix = f"tt{str(imdb_id_num).zfill(7)}"
        
        if not await self._resolve_douban_link(meta):
            meta['tracker_status'][self.tracker] = {'status': 'failed', 'reason': "豆瓣链接获取失败，上传任务中止。"}
            return False

        douban_link = self.douban_url

        if not await self.edit_torrent(meta, self.tracker, self.source_flag):
            meta['tracker_status'][self.tracker] = {'status': 'failed', 'reason': "Failed to edit torrent"}
            return False
            
        ssd_name = self.edit_name(meta)
        poster_url = ""
        final_description = self._get_final_description(meta)

        data = {
            'name': ssd_name, 
            'small_descr': self._get_small_descr(meta),
            'url': douban_link or f"https://www.imdb.com/title/{self.imdb_id_with_prefix}/",
            'url_vimages': '\n'.join([img['raw_url'] for img in meta.get('image_list', [])]),
            'url_poster': poster_url,
            'Media_BDInfo': self._get_media_bdinfo(meta), 
            'descr': final_description,
            'type': self._get_category_id(meta), 
            'source_sel': self._get_region_id_from_meta(meta),
            'medium_sel': self._get_medium_id(ssd_name), 
            'codec_sel': self._get_codec_id(ssd_name),
            'audiocodec_sel': self._get_audiocodec_id(ssd_name), 
            'standard_sel': self._get_resolution_id(ssd_name),
            'uplver': 'yes' if self.anon else 'no', 
            'offer': 'yes' if self.offer else 'no',
        }
        if 'Blu-ray' in ssd_name and meta.get('is_disc') == 'BDMV': data['untouched'] = '1'
        if self._is_pack(meta): data['pack'] = '1'
        if self._has_genre(self._get_genres(meta), {"动画", "Animation"}): data['animation'] = '1'
        if self._has_chinese_subtitle(meta): data['subtitlezh'] = '1'
        
        hdr_string = meta.get('hdr', '').upper()
        if 'DV' in hdr_string: data['dovi'] = '1'
        if 'HDR10+' in hdr_string: data['hdr10plus'] = '1'
        elif 'HDR' in hdr_string: data['hdr10'] = '1'
        
        final_torrent_path = os.path.join(meta['base_dir'], 'tmp', meta['uuid'], f"[{self.tracker}].torrent")
        if not os.path.exists(final_torrent_path):
            meta['tracker_status'][self.tracker] = {'status': 'failed', 'reason': "Torrent file not created after edit"}
            return False
            
        try:
            cookie_str = await self._load_cookie_header(meta)
            if not cookie_str:
                meta['tracker_status'][self.tracker] = {'status': 'failed', 'reason': "Cookie file empty or invalid"}
                return False
            command = ["curl", "--silent", "--output", "/dev/null", "--write-out", "%{redirect_url}", self.upload_url]
            command.extend(["-H", f"Cookie: {cookie_str}"])
            command.extend(["-H", f"User-Agent: {self.session.headers.get('User-Agent')}"])
            for key, value in data.items():
                command.extend(["--form-string", f"{key}={str(value) if value is not None else ''}"])
            command.extend(["--form", f"file=@{final_torrent_path}"])
            
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            final_url = result.stdout.strip()
            
            if result.returncode == 0 and 'details.php?id=' in final_url:
                if meta.get('debug', False):
                    self._log(meta, f"[{self.tracker}] ✅ 上传成功！")
                    self._log(meta, f"[{self.tracker}] 种子详情页: {final_url}")
                torrent_id = re.search(r'id=(\d+)', final_url).group(1) if re.search(r'id=(\d+)', final_url) else None
                meta['tracker_status'][self.tracker] = {
                    'status': 'success',
                    'status_message': 'Upload successful',
                    'torrent_url': final_url,
                    'torrent_id': torrent_id,
                }
                
                if meta.get('debug', False):
                    self._log(meta, f"[{self.tracker}] 🚧 DEBUG模式：跳过将种子添加到 qBittorrent 的步骤。")
                elif torrent_id:
                    upload_limit_kib = 112640 
                    await self._add_to_qbittorrent(meta, torrent_id, upload_limit_kib)
                return True
            else:
                self._log(meta, f"[{self.tracker}] ❌ 上传失败。")
                meta['tracker_status'][self.tracker] = {
                    'status': 'failed',
                    'status_message': 'Upload failed',
                    'reason': f"curl failed with exit code {result.returncode}",
                }
                return False
        except Exception as e:
            error_message = f"执行 curl 命令时发生 Python 错误: {e}"
            self._log(meta, f"[{self.tracker}] ❌ {error_message}")
            meta['tracker_status'][self.tracker] = {
                'status': 'failed',
                'status_message': 'Upload failed',
                'reason': error_message,
            }
            return False
