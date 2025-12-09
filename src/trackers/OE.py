# Upload Assistant © 2025 Audionut — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
import aiofiles
import os
import re
from src.bbcode import BBCODE
from src.console import console
from src.languages import process_desc_language, has_english_language
from src.rehostimages import check_hosts
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class OE(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='OE')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'OE'
        self.source_flag = 'OE'
        self.base_url = 'https://onlyencodes.cc'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = [
            '0neshot', '3LT0N', '4K4U', '4yEo', '$andra', '[Oj]', 'AFG', 'AkihitoSubs', 'Alcaide_Kira', 'AniHLS', 'Anime Time',
            'AnimeRG', 'AniURL', 'AOC', 'AR', 'AROMA', 'ASW', 'aXXo', 'BakedFish', 'BiTOR', 'BRrip', 'bonkai',
            'Cleo', 'CM8', 'C4K', 'CrEwSaDe', 'core', 'd3g', 'DDR', 'DE3PM', 'DeadFish', 'DeeJayAhmed', 'DNL', 'ELiTE',
            'EMBER', 'eSc', 'EVO', 'EZTV', 'FaNGDiNG0', 'FGT', 'fenix', 'FUM', 'FRDS', 'FROZEN', 'GalaxyTV',
            'GalaxyRG', 'GalaxyRG265', 'GERMini', 'Grym', 'GrymLegacy', 'HAiKU', 'HD2DVD', 'HDTime', 'Hi10',
            'HiQVE', 'ION10', 'iPlanet', 'iVy', 'JacobSwaggedUp', 'JIVE', 'Judas', 'KiNGDOM', 'LAMA', 'Leffe', 'LiGaS',
            'LOAD', 'LycanHD', 'MeGusta', 'MezRips', 'mHD', 'Mr.Deadpool', 'mSD', 'NemDiggers', 'neoHEVC', 'NeXus',
            'nHD', 'nikt0', 'nSD', 'NhaNc3', 'NOIVTC', 'pahe.in', 'PlaySD', 'playXD', 'PRODJi', 'ProRes',
            'project-gxs', 'PSA', 'QaS', 'Ranger', 'RAPiDCOWS', 'RARBG', 'Raze', 'RCDiVX', 'RDN', 'Reaktor',
            'REsuRRecTioN', 'RMTeam', 'ROBOTS', 'rubix', 'SANTi', 'SHUTTERSHIT', 'SM737', 'SpaceFish', 'SPASM', 'SSA',
            'TBS', 'Telly', 'Tenrai-Sensei', 'TERMiNAL', 'TGx', 'TM', 'topaz', 'ToVaR', 'TSP', 'TSPxL', 'UnKn0wn', 'URANiME', 'UTR',
            'VipapkSudios', 'ViSION', 'WAF', 'Wardevil', 'x0r', 'xRed', 'XS', 'YakuboEncodes', 'YAWNTiC', 'YAWNiX', 'YIFY', 'YTS',
            'YuiSubs', 'ZKBL', 'ZmN', 'ZMNT'
        ]
        pass

    async def get_additional_checks(self, meta):
        genres = f"{meta.get('keywords', '')} {meta.get('combined_genres', '')}"
        adult_keywords = ['xxx', 'erotic', 'porn', 'adult', 'orgy']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', genres, re.IGNORECASE) for keyword in adult_keywords):
            if not meta['unattended']:
                console.print('[bold red]Erotic not allowed at OE.')
            return False

        if not meta['is_disc'] == "BDMV":
            if not await self.common.check_language_requirements(
                meta, self.tracker, languages_to_check=["english"], check_audio=True, check_subtitle=True
            ):
                return False

        return True

    async def check_image_hosts(self, meta):
        approved_image_hosts = ['ptpimg', 'imgbox', 'imgbb', 'onlyimage', 'ptscreens', "passtheimage"]
        url_host_mapping = {
            "ibb.co": "imgbb",
            "ptpimg.me": "ptpimg",
            "imgbox.com": "imgbox",
            "onlyimage.org": "onlyimage",
            "imagebam.com": "bam",
            "ptscreens.com": "ptscreens",
            "img.passtheima.ge": "passtheimage",
        }

        await check_hosts(meta, self.tracker, url_host_mapping=url_host_mapping, img_host_index=1, approved_image_hosts=approved_image_hosts)
        return

    async def get_description(self, meta):
        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding='utf8') as f:
            base = await f.read()

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf8') as descfile:
            await process_desc_language(meta, descfile, tracker=self.tracker)

            bbcode = BBCODE()
            if meta.get('discs', []) != []:
                discs = meta['discs']
                if discs[0]['type'] == "DVD":
                    await descfile.write(f"[spoiler=VOB MediaInfo][code]{discs[0]['vob_mi']}[/code][/spoiler]\n\n")
                if len(discs) >= 2:
                    for each in discs[1:]:
                        if each['type'] == "BDMV":
                            await descfile.write(f"[spoiler={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/spoiler]\n\n")
                        elif each['type'] == "DVD":
                            await descfile.write(f"{each['name']}:\n")
                            await descfile.write(f"[spoiler={os.path.basename(each['vob'])}][code][{each['vob_mi']}[/code][/spoiler] [spoiler={os.path.basename(each['ifo'])}][code][{each['ifo_mi']}[/code][/spoiler]\n\n")
                        elif each['type'] == "HDDVD":
                            await descfile.write(f"{each['name']}:\n")
                            await descfile.write(f"[spoiler={os.path.basename(each['largest_evo'])}][code][{each['evo_mi']}[/code][/spoiler]\n\n")

            desc = base
            desc = bbcode.convert_pre_to_code(desc)
            desc = bbcode.convert_hide_to_spoiler(desc)
            desc = bbcode.convert_comparison_to_collapse(desc, 1000)
            try:
                if meta.get('tonemapped', False) and self.config['DEFAULT'].get('tonemapped_header', None):
                    tonemapped_header = self.config['DEFAULT'].get('tonemapped_header')
                    desc = desc + tonemapped_header
                    desc = desc + "\n\n"
            except Exception as e:
                console.print(f"[yellow]Warning: Error setting tonemapped header: {str(e)}[/yellow]")
            desc = desc.replace('[img]', '[img=300]')
            await descfile.write(desc)
            if f'{self.tracker}_images_key' in meta:
                images = meta[f'{self.tracker}_images_key']
            else:
                images = meta['image_list']
            if len(images) > 0:
                await descfile.write("[center]")
                for each in range(len(images[:int(meta['screens'])])):
                    web_url = images[each]['web_url']
                    raw_url = images[each]['raw_url']
                    await descfile.write(f"[url={web_url}][img=350]{raw_url}[/img][/url]")
                await descfile.write("[/center]")

            await descfile.write(f"\n[right][url=https://github.com/Audionut/Upload-Assistant][size=4]{meta['ua_signature']}[/size][/url][/right]")

        async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8') as f:
            desc = await f.read()

        return {'description': desc}

    async def get_name(self, meta):
        oe_name = meta.get('name')
        resolution = meta.get('resolution')
        video_encode = meta.get('video_encode')
        name_type = meta.get('type', "")
        source = meta.get('source', "")
        audio = meta.get('audio', "")
        video_codec = meta.get('video_codec', "")

        imdb_name = meta.get('imdb_info', {}).get('title', "")
        imdb_year = str(meta.get('imdb_info', {}).get('year', ""))
        imdb_aka = meta.get('imdb_info', {}).get('aka', "")
        year = str(meta.get('year', ""))
        aka = meta.get('aka', "")
        if imdb_name and imdb_name.strip():
            if aka:
                oe_name = oe_name.replace(f"{aka} ", "", 1)
            oe_name = oe_name.replace(f"{meta['title']}", imdb_name, 1)

            if imdb_aka and imdb_aka.strip() and imdb_aka != imdb_name and not meta.get('no_aka', False):
                oe_name = oe_name.replace(f"{imdb_name}", f"{imdb_name} AKA {imdb_aka}", 1)

        if not meta.get('category') == "TV" and imdb_year and imdb_year.strip() and year and year.strip() and imdb_year != year:
            oe_name = oe_name.replace(f"{year}", imdb_year, 1)

        if name_type == "DVDRIP":
            if meta.get('category') == "MOVIE":
                oe_name = oe_name.replace(f"{source}{video_encode}", f"{resolution}", 1)
                oe_name = oe_name.replace((audio), f"{audio}{video_encode}", 1)
            else:
                oe_name = oe_name.replace(f"{source}", f"{resolution}", 1)
                oe_name = oe_name.replace(f"{video_codec}", f"{audio} {video_codec}", 1)

        if not meta.get('audio_languages'):
            await process_desc_language(meta, desc=None, tracker=self.tracker)
        elif meta.get('audio_languages'):
            audio_languages = meta['audio_languages']
            if audio_languages and not await has_english_language(audio_languages) and not meta.get('is_disc') == "BDMV":
                foreign_lang = meta['audio_languages'][0].upper()
                oe_name = oe_name.replace(f"{resolution}", f"{foreign_lang} {resolution}", 1)

        scale = "DS4K" if "DS4K" in meta['uuid'].upper() else "RM4K" if "RM4K" in meta['uuid'].upper() else ""
        if name_type in ["ENCODE", "WEBDL", "WEBRIP"] and scale != "":
            oe_name = oe_name.replace(f"{resolution}", f"{scale}", 1)

        tag_lower = meta['tag'].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]
        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                oe_name = re.sub(f"-{invalid_tag}", "", oe_name, flags=re.IGNORECASE)
            oe_name = f"{oe_name}-NOGRP"

        return {'name': oe_name}

    async def get_type_id(self, meta):
        video_codec = meta.get('video_codec', 'N/A')

        meta_type = meta['type']
        if meta_type == "DVDRIP":
            meta_type = "ENCODE"

        type_id = {
            'DISC': '19',
            'REMUX': '20',
            'WEBDL': '21',
        }.get(meta_type, '0')
        if meta_type == "WEBRIP":
            if video_codec == "HEVC":
                # x265 Encode
                type_id = '10'
            if video_codec == 'AV1':
                # AV1 Encode
                type_id = '14'
            if video_codec == 'AVC':
                # x264 Encode
                type_id = '15'
        if meta_type == "ENCODE":
            if video_codec == "HEVC":
                # x265 Encode
                type_id = '10'
            if video_codec == 'AV1':
                # AV1 Encode
                type_id = '14'
            if video_codec == 'AVC':
                # x264 Encode
                type_id = '15'
        return {'type_id': type_id}
