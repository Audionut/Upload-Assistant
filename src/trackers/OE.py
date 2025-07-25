# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import platform
import re
import os
import httpx
from src.bbcode import BBCODE
from src.trackers.COMMON import COMMON
from src.console import console
from src.rehostimages import check_hosts
from src.languages import process_desc_language, has_english_language


class OE():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """
    def __init__(self, config):
        self.config = config
        self.tracker = 'OE'
        self.source_flag = 'OE'
        self.search_url = 'https://onlyencodes.cc/api/torrents/filter'
        self.upload_url = 'https://onlyencodes.cc/api/torrents/upload'
        self.torrent_url = 'https://onlyencodes.cc/torrents/'
        self.id_url = 'https://onlyencodes.cc/api/torrents/'
        self.signature = "\n[center][url=https://github.com/Audionut/Upload-Assistant]Created by Audionut's Upload Assistant[/url][/center]"
        self.banned_groups = [
            '0neshot', '3LT0N', '4K4U', '4yEo', '$andra', '[Oj]', 'AFG', 'AkihitoSubs', 'AniHLS', 'Anime Time',
            'AnimeRG', 'AniURL', 'AOC', 'AR', 'AROMA', 'ASW', 'aXXo', 'BakedFish', 'BiTOR', 'BRrip', 'bonkai',
            'Cleo', 'CM8', 'C4K', 'CrEwSaDe', 'core', 'd3g', 'DDR', 'DE3PM', 'DeadFish', 'DeeJayAhmed', 'DNL', 'ELiTE',
            'EMBER', 'eSc', 'EVO', 'EZTV', 'FaNGDiNG0', 'FGT', 'fenix', 'FUM', 'FRDS', 'FROZEN', 'GalaxyTV',
            'GalaxyRG', 'GalaxyRG265', 'GERMini', 'Grym', 'GrymLegacy', 'HAiKU', 'HD2DVD', 'HDTime', 'Hi10',
            'HiQVE', 'ION10', 'iPlanet', 'JacobSwaggedUp', 'JIVE', 'Judas', 'KiNGDOM', 'LAMA', 'Leffe', 'LiGaS',
            'LOAD', 'LycanHD', 'MeGusta', 'MezRips', 'mHD', 'Mr.Deadpool', 'mSD', 'NemDiggers', 'neoHEVC', 'NeXus',
            'nHD', 'nikt0', 'nSD', 'NhaNc3', 'NOIVTC', 'pahe.in', 'PlaySD', 'playXD', 'PRODJi', 'ProRes',
            'project-gxs', 'PSA', 'QaS', 'Ranger', 'RAPiDCOWS', 'RARBG', 'Raze', 'RCDiVX', 'RDN', 'Reaktor',
            'REsuRRecTioN', 'RMTeam', 'ROBOTS', 'rubix', 'SANTi', 'SHUTTERSHIT', 'SpaceFish', 'SPASM', 'SSA',
            'TBS', 'Telly', 'Tenrai-Sensei', 'TERMiNAL', 'TGx', 'TM', 'topaz', 'TSP', 'TSPxL', 'URANiME', 'UTR',
            'VipapkSudios', 'ViSION', 'WAF', 'Wardevil', 'x0r', 'xRed', 'XS', 'YakuboEncodes', 'YIFY', 'YTS',
            'YuiSubs', 'ZKBL', 'ZmN', 'ZMNT'
        ]
        pass

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
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
        await self.edit_desc(meta, self.tracker, self.signature)
        should_skip = meta['tracker_status'][self.tracker].get('skip_upload', False)
        if should_skip:
            meta['tracker_status'][self.tracker]['status_message'] = "data error: oe_no_language"
            return
        cat_id = await self.get_cat_id(meta['category'])
        if meta.get('type') == "DVDRIP":
            meta['type'] = "ENCODE"
        type_id = await self.get_type_id(meta['type'], meta.get('video_codec', 'N/A'))
        resolution_id = await self.get_res_id(meta['resolution'])
        oe_name = await self.edit_name(meta)
        region_id = await common.unit3d_region_ids(meta.get('region'))
        distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
        if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False):
            anon = 0
        else:
            anon = 1
        if meta['bdinfo'] is not None:
            mi_dump = None
            bd_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()
            bd_dump = None
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        open_torrent = open(torrent_file_path, 'rb')
        files = {'torrent': open_torrent}
        data = {
            'name': oe_name,
            'description': desc,
            'mediainfo': mi_dump,
            'bdinfo': bd_dump,
            'category_id': cat_id,
            'type_id': type_id,
            'resolution_id': resolution_id,
            'tmdb': meta['tmdb'],
            'imdb': meta['imdb'],
            'mal': meta['mal_id'],
            'igdb': 0,
            'anonymous': anon,
            'stream': meta['stream'],
            'sd': meta['sd'],
            'keywords': meta['keywords'],
            'personal_release': int(meta.get('personalrelease', False)),
            'internal': 0,
            'featured': 0,
            'free': 0,
            'doubleup': 0,
            'sticky': 0,
        }
        # Internal
        if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
            if meta['tag'] != "" and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                data['internal'] = 1
        if meta.get('freeleech', 0) != 0:
            data['free'] = meta.get('freeleech', 0)
        if region_id != 0:
            data['region_id'] = region_id
        if distributor_id != 0:
            data['distributor_id'] = distributor_id

        if meta.get('category') == "TV":
            data['season_number'] = meta.get('season_int', '0')
            data['episode_number'] = meta.get('episode_int', '0')
            data['tvdb'] = meta['tvdb_id']
        elif meta.get('category') == "MOVIE":
            data['tvdb'] = 0
        headers = {
            'User-Agent': f'Upload Assistant/2.2 ({platform.system()} {platform.release()})'
        }
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip()
        }

        if meta['debug'] is False:
            response = requests.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
            try:
                meta['tracker_status'][self.tracker]['status_message'] = response.json()
                # adding torrent link to comment of torrent file
                t_id = response.json()['data'].split(".")[1].split("/")[3]
                meta['tracker_status'][self.tracker]['torrent_id'] = t_id
                await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS'][self.tracker].get('announce_url'), "https://onlyencodes.cc/torrents/" + t_id)
            except Exception:
                console.print("It may have uploaded, go check")
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()

    async def edit_name(self, meta):
        oe_name = meta.get('name')
        resolution = meta.get('resolution')
        video_encode = meta.get('video_encode')
        name_type = meta.get('type', "")
        tag_lower = meta['tag'].lower()
        invalid_tags = ["nogrp", "nogroup", "unknown", "-unk-"]
        imdb_name = meta.get('imdb_info', {}).get('title', "")
        title = meta.get('title', "")
        oe_name = oe_name.replace(f"{title}", imdb_name, 1)
        year = str(meta.get('year', ""))
        imdb_year = str(meta.get('imdb_info', {}).get('year', ""))
        scale = "DS4K" if "DS4K" in meta['uuid'].upper() else "RM4K" if "RM4K" in meta['uuid'].upper() else ""
        if not meta.get('category') == "TV":
            oe_name = oe_name.replace(f"{year}", imdb_year, 1)

        if name_type == "DVDRIP":
            if meta.get('category') == "MOVIE":
                oe_name = oe_name.replace(f"{meta['source']}{meta['video_encode']}", f"{resolution}", 1)
                oe_name = oe_name.replace((meta['audio']), f"{meta['audio']}{video_encode}", 1)
            else:
                oe_name = oe_name.replace(f"{meta['source']}", f"{resolution}", 1)
                oe_name = oe_name.replace(f"{meta['video_codec']}", f"{meta['audio']} {meta['video_codec']}", 1)

        if not meta.get('audio_languages'):
            await process_desc_language(meta, desc=None, tracker=self.tracker)
        elif meta.get('audio_languages'):
            audio_languages = meta['audio_languages'][0].upper()
            if audio_languages and not await has_english_language(audio_languages) and not meta.get('is_disc') == "BDMV":
                oe_name = oe_name.replace(meta['resolution'], f"{audio_languages} {meta['resolution']}", 1)

        if name_type in ["ENCODE", "WEBDL", "WEBRIP"] and scale != "":
            oe_name = oe_name.replace(f"{resolution}", f"{scale}", 1)

        if meta['tag'] == "" or any(invalid_tag in tag_lower for invalid_tag in invalid_tags):
            for invalid_tag in invalid_tags:
                oe_name = re.sub(f"-{invalid_tag}", "", oe_name, flags=re.IGNORECASE)
            oe_name = f"{oe_name}-NOGRP"

        return oe_name

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    async def get_type_id(self, type, video_codec):
        type_id = {
            'DISC': '19',
            'REMUX': '20',
            'WEBDL': '21',
        }.get(type, '0')
        if type == "WEBRIP":
            if video_codec == "HEVC":
                # x265 Encode
                type_id = '10'
            if video_codec == 'AV1':
                # AV1 Encode
                type_id = '14'
            if video_codec == 'AVC':
                # x264 Encode
                type_id = '15'
        if type == "ENCODE":
            if video_codec == "HEVC":
                # x265 Encode
                type_id = '10'
            if video_codec == 'AV1':
                # AV1 Encode
                type_id = '14'
            if video_codec == 'AVC':
                # x264 Encode
                type_id = '15'
        return type_id

    async def get_res_id(self, resolution):
        resolution_id = {
            '8640p': '10',
            '4320p': '1',
            '2160p': '2',
            '1440p': '3',
            '1080p': '3',
            '1080i': '4',
            '720p': '5',
            '576p': '6',
            '576i': '7',
            '480p': '8',
            '480i': '9'
        }.get(resolution, '10')
        return resolution_id

    async def edit_desc(self, meta, tracker, signature, comparison=False, desc_header=""):
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding='utf8').read()

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]DESCRIPTION.txt", 'w', encoding='utf8') as descfile:
            if desc_header != "":
                descfile.write(desc_header)

            await process_desc_language(meta, descfile, tracker=self.tracker)

            bbcode = BBCODE()
            if meta.get('discs', []) != []:
                discs = meta['discs']
                if discs[0]['type'] == "DVD":
                    descfile.write(f"[spoiler=VOB MediaInfo][code]{discs[0]['vob_mi']}[/code][/spoiler]\n\n")
                if len(discs) >= 2:
                    for each in discs[1:]:
                        if each['type'] == "BDMV":
                            descfile.write(f"[spoiler={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/spoiler]\n\n")
                        elif each['type'] == "DVD":
                            descfile.write(f"{each['name']}:\n")
                            descfile.write(f"[spoiler={os.path.basename(each['vob'])}][code][{each['vob_mi']}[/code][/spoiler] [spoiler={os.path.basename(each['ifo'])}][code][{each['ifo_mi']}[/code][/spoiler]\n\n")
                        elif each['type'] == "HDDVD":
                            descfile.write(f"{each['name']}:\n")
                            descfile.write(f"[spoiler={os.path.basename(each['largest_evo'])}][code][{each['evo_mi']}[/code][/spoiler]\n\n")

            desc = base
            desc = bbcode.convert_pre_to_code(desc)
            desc = bbcode.convert_hide_to_spoiler(desc)
            desc = bbcode.convert_comparison_to_collapse(desc, 1000)

            desc = desc.replace('[img]', '[img=300]')
            descfile.write(desc)
            if f'{self.tracker}_images_key' in meta:
                images = meta[f'{self.tracker}_images_key']
            else:
                images = meta['image_list']
            if len(images) > 0:
                descfile.write("[center]")
                for each in range(len(images[:int(meta['screens'])])):
                    web_url = images[each]['web_url']
                    raw_url = images[each]['raw_url']
                    descfile.write(f"[url={web_url}][img=350]{raw_url}[/img][/url]")
                descfile.write("[/center]")

            if signature is not None:
                descfile.write(signature)
        return

    async def search_existing(self, meta, disctype):
        disallowed_keywords = {'XXX', 'softcore', 'concert'}
        if any(keyword.lower() in disallowed_keywords for keyword in map(str.lower, meta['keywords'])):
            if not meta['unattended']:
                console.print('[bold red]Erotic not allowed at OE.')
            meta['skipping'] = "OE"
            return

        if not meta['is_disc'] == "BDMV":
            if not meta.get('audio_languages') or not meta.get('subtitle_languages'):
                await process_desc_language(meta, desc=None, tracker=self.tracker)
            if not await has_english_language(meta.get('audio_languages')) and not await has_english_language(meta.get('subtitle_languages')):
                if not meta['unattended']:
                    console.print('[bold red]OE requires at least one English audio or subtitle track.')
                meta['skipping'] = "OE"
                return

        dupes = []
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdbId': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta['category']),
            'types[]': await self.get_type_id(meta['type'], meta.get('video_codec', 'N/A')),
            'resolutions[]': await self.get_res_id(meta['resolution']),
            'name': ""
        }
        if meta['category'] == 'TV':
            params['name'] = f"{meta.get('season', '')}"
        if meta.get('edition', "") != "":
            params['name'] + meta['edition']
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=self.search_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    for each in data['data']:
                        attributes = each['attributes']
                        result = {
                            'name': attributes['name'],
                            'size': attributes['size']
                        }
                        dupes.append(result)
                else:
                    console.print(f"[bold red]Failed to search torrents. HTTP Status: {response.status_code}")
        except httpx.TimeoutException:
            console.print("[bold red]Request timed out after 5 seconds")
        except httpx.RequestError as e:
            console.print(f"[bold red]Unable to search for existing torrents: {e}")
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}")
            await asyncio.sleep(5)

        return dupes
