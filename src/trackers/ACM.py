# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
# -*- coding: utf-8 -*-
# import discord
import aiofiles
import asyncio
import httpx
import os
import platform
import re

from src.bbcode import BBCODE
from src.console import console
from src.trackers.COMMON import COMMON
from src.trackers.UNIT3D import UNIT3D


class ACM(UNIT3D):
    def __init__(self, config):
        super().__init__(config, tracker_name='ACM')
        self.config = config
        self.common = COMMON(config)
        self.tracker = 'ACM'
        self.source_flag = 'AsianCinema'
        self.base_url = 'https://eiga.moi'
        self.id_url = f'{self.base_url}/api/torrents/'
        self.upload_url = f'{self.base_url}/api/torrents/upload'
        self.search_url = f'{self.base_url}/api/torrents/filter'
        self.torrent_url = f'{self.base_url}/torrents/'
        self.banned_groups = []
        pass

    async def get_type_id(self, meta):
        if meta['is_disc'] == "BDMV":
            bdinfo = meta['bdinfo']
            bd_sizes = [25, 50, 66, 100]
            bd_size = 100  # Default to largest size
            for each in bd_sizes:
                if bdinfo['size'] < each:
                    bd_size = each
                    break
            if meta['uhd'] == "UHD" and bd_size != 25:
                type_string = f"UHD {bd_size}"
            else:
                type_string = f"BD {bd_size}"
            # if type_id not in ['UHD 100', 'UHD 66', 'UHD 50', 'BD 50', 'BD 25']:
            #     type_id = "Other"
        elif meta['is_disc'] == "DVD":
            if "DVD5" in meta['dvd_size']:
                type_string = "DVD 5"
            elif "DVD9" in meta['dvd_size']:
                type_string = "DVD 9"
            else:
                type_string = "Other"
        else:
            if meta['type'] == "REMUX":
                if meta['uhd'] == "UHD":
                    type_string = "UHD REMUX"
                else:
                    type_string = "REMUX"
            else:
                type_string = meta['type']
            # else:
            #     acceptable_res = ["2160p", "1080p", "1080i", "720p", "576p", "576i", "540p", "480p", "Other"]
            #     if meta['resolution'] in acceptable_res:
            #         type_id = meta['resolution']
            #     else:
            #         type_id = "Other"

        type_id_map = {
            'UHD 100': '1',
            'UHD 66': '2',
            'UHD 50': '3',
            'UHD REMUX': '12',
            'BD 50': '4',
            'BD 25': '5',
            'DVD 5': '14',
            'REMUX': '7',
            'WEBDL': '9',
            'SDTV': '13',
            'DVD 9': '16',
            'HDTV': '17',
        }
        type_id = type_id_map.get(type_string, '0')

        return type_id

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    async def get_resolution_id(self, meta):
        resolution_id = {
            '2160p': '1',
            '1080p': '2',
            '1080i': '2',
            '720p': '3',
            '576p': '4',
            '576i': '4',
            '480p': '5',
            '480i': '5'
        }.get(meta['resolution'], '10')
        return resolution_id

    # ACM rejects uploads with more that 10 keywords
    async def get_keywords(self, meta):
        keywords = meta.get('keywords', '')
        if keywords != '':
            keywords_list = keywords.split(',')
            keywords_list = [keyword.strip() for keyword in keywords_list if " " not in keyword.strip()][:10]
            keywords = ', '.join(keywords_list)
        return keywords

    async def get_additional_files(self, meta):
        return {}

    def get_subtitles(self, meta):
        sub_lang_map = {
            ("Arabic", "ara", "ar"): 'Ara',
            ("Brazilian Portuguese", "Brazilian", "Portuguese-BR", 'pt-br'): 'Por-BR',
            ("Bulgarian", "bul", "bg"): 'Bul',
            ("Chinese", "chi", "zh", "Chinese (Simplified)", "Chinese (Traditional)"): 'Chi',
            ("Croatian", "hrv", "hr", "scr"): 'Cro',
            ("Czech", "cze", "cz", "cs"): 'Cze',
            ("Danish", "dan", "da"): 'Dan',
            ("Dutch", "dut", "nl"): 'Dut',
            ("English", "eng", "en", "English (CC)", "English - SDH"): 'Eng',
            ("English - Forced", "English (Forced)", "en (Forced)"): 'Eng',
            ("English Intertitles", "English (Intertitles)", "English - Intertitles", "en (Intertitles)"): 'Eng',
            ("Estonian", "est", "et"): 'Est',
            ("Finnish", "fin", "fi"): 'Fin',
            ("French", "fre", "fr"): 'Fre',
            ("German", "ger", "de"): 'Ger',
            ("Greek", "gre", "el"): 'Gre',
            ("Hebrew", "heb", "he"): 'Heb',
            ("Hindi" "hin", "hi"): 'Hin',
            ("Hungarian", "hun", "hu"): 'Hun',
            ("Icelandic", "ice", "is"): 'Ice',
            ("Indonesian", "ind", "id"): 'Ind',
            ("Italian", "ita", "it"): 'Ita',
            ("Japanese", "jpn", "ja"): 'Jpn',
            ("Korean", "kor", "ko"): 'Kor',
            ("Latvian", "lav", "lv"): 'Lav',
            ("Lithuanian", "lit", "lt"): 'Lit',
            ("Norwegian", "nor", "no"): 'Nor',
            ("Persian", "fa", "far"): 'Per',
            ("Polish", "pol", "pl"): 'Pol',
            ("Portuguese", "por", "pt"): 'Por',
            ("Romanian", "rum", "ro"): 'Rom',
            ("Russian", "rus", "ru"): 'Rus',
            ("Serbian", "srp", "sr", "scc"): 'Ser',
            ("Slovak", "slo", "sk"): 'Slo',
            ("Slovenian", "slv", "sl"): 'Slv',
            ("Spanish", "spa", "es"): 'Spa',
            ("Swedish", "swe", "sv"): 'Swe',
            ("Thai", "tha", "th"): 'Tha',
            ("Turkish", "tur", "tr"): 'Tur',
            ("Ukrainian", "ukr", "uk"): 'Ukr',
            ("Vietnamese", "vie", "vi"): 'Vie',
        }

        sub_langs = []
        if meta.get('is_disc', '') != 'BDMV':
            mi = meta['mediainfo']
            for track in mi['media']['track']:
                if track['@type'] == "Text":
                    language = track.get('Language')
                    if language == "en":
                        if track.get('Forced', "") == "Yes":
                            language = "en (Forced)"
                        title = track.get('Title', "")
                        if isinstance(title, str) and "intertitles" in title.lower():
                            language = "en (Intertitles)"
                    for lang, subID in sub_lang_map.items():
                        if language in lang and subID not in sub_langs:
                            sub_langs.append(subID)
        else:
            for language in meta['bdinfo']['subtitles']:
                for lang, subID in sub_lang_map.items():
                    if language in lang and subID not in sub_langs:
                        sub_langs.append(subID)

        # if sub_langs == []:
        #     sub_langs = [44] # No Subtitle
        return sub_langs

    def get_subs_tag(self, subs):
        if subs == []:
            return ' [No subs]'
        elif 'Eng' in subs:
            return ''
        elif len(subs) > 1:
            return ' [No Eng subs]'
        return f" [{subs[0]} subs only]"

    async def upload(self, meta, disctype):
        await self.common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'])
        type_id = await self.get_type_id(meta)
        resolution_id = await self.get_resolution_id(meta)
        desc = await self.get_description(meta)
        region_id = await self.common.unit3d_region_ids(meta.get('region'))
        distributor_id = await self.common.unit3d_distributor_ids(meta.get('distributor'))
        acm_name = await self.get_name(meta)
        if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False):
            anon = 0
        else:
            anon = 1

        if meta['bdinfo'] is not None:
            # bd_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
            mi_dump = None
            bd_dump = ""
            for each in meta['discs']:
                bd_dump = bd_dump + each['summary'].strip() + "\n\n"
        else:
            async with aiofiles.open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8') as f:
                mi_dump = await f.read()
            bd_dump = None
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        async with aiofiles.open(torrent_file_path, 'rb') as f:
            torrent_bytes = await f.read()
        files = {'torrent': ('torrent.torrent', torrent_bytes, 'application/x-bittorrent')}
        data = {
            'name': acm_name,
            'description': desc,
            'mediainfo': mi_dump,
            'bdinfo': bd_dump,
            'category_id': cat_id,
            'type_id': type_id,
            'resolution_id': resolution_id,
            'tmdb': meta['tmdb'],
            'imdb': meta['imdb'],
            'tvdb': meta['tvdb_id'],
            'mal': meta['mal_id'],
            'igdb': 0,
            'anonymous': anon,
            'stream': meta['stream'],
            'sd': meta['sd'],
            'keywords': await self.get_keywords(meta),
            'personal_release': int(meta.get('personalrelease', False)),
            'internal': 0,
            'featured': 0,
            'free': 0,
            'doubleup': 0,
            'sticky': 0,
        }
        if self.config['TRACKERS'][self.tracker].get('internal', False) is True:
            if meta['tag'] != "" and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                data['internal'] = 1
        if region_id != 0:
            data['region_id'] = region_id
        if distributor_id != 0:
            data['distributor_id'] = distributor_id
        if meta.get('category') == "TV":
            data['season_number'] = meta.get('season_int', '0')
            data['episode_number'] = meta.get('episode_int', '0')
        headers = {'User-Agent': f'{meta["ua_name"]} {meta.get("current_version", "")} ({platform.system()} {platform.release()})'}
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip()
        }

        if meta['debug'] is False:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
                try:
                    meta['tracker_status'][self.tracker]['status_message'] = response.json()
                    # adding torrent link to comment of torrent file
                    t_id = response.json()['data'].split('.')[1].split('/')[3]
                    meta['tracker_status'][self.tracker]['torrent_id'] = t_id
                    await self.common.add_tracker_torrent(
                        meta,
                        self.tracker,
                        self.source_flag,
                        self.announce_url,
                        self.torrent_url + t_id,
                        headers=headers,
                        params=params,
                        downurl=response.json()['data']
                    )
                except httpx.TimeoutException:
                    meta['tracker_status'][self.tracker]['status_message'] = f'data error: {self.tracker} request timed out after 10 seconds'
                except httpx.RequestError as e:
                    meta['tracker_status'][self.tracker]['status_message'] = f'data error: Unable to upload to {self.tracker}: {e}'
                except Exception:
                    meta['tracker_status'][self.tracker]['status_message'] = f'data error: It may have uploaded, go check: {self.tracker}'
                    return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."

    async def search_existing(self, meta, disctype):
        dupes = []
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdb': meta['tmdb'],
            'categories[]': (await self.get_category_id(meta)),
            'types[]': (await self.get_type_id(meta)),
            # A majority of the ACM library doesn't contain resolution information
            # 'resolutions[]' : await self.get_res_id(meta['resolution']),
            # 'name' : ""
        }
        # Adding Name to search seems to override tmdb
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=self.search_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    for each in data['data']:
                        result = [each][0]['attributes']['name']
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

    async def get_name(self, meta):
        name = meta.get('name')
        aka = meta.get('aka')
        original_title = meta.get('original_title')
        audio = meta.get('audio')
        source = meta.get('source')
        is_disc = meta.get('is_disc')
        subs = self.get_subtitles(meta)
        resolution = meta.get('resolution')
        if aka != '':
            # ugly fix to remove the extra space in the title
            aka = aka + ' '
            name = name.replace(aka, f' / {original_title} {chr(int("202A", 16))}')
        elif aka == '':
            if meta.get('title') != original_title:
                # name = f'{name[:name.find(year)]}/ {original_title} {chr(int("202A", 16))}{name[name.find(year):]}'
                name = name.replace(meta['title'], f"{meta['title']} / {original_title} {chr(int('202A', 16))}")
        if 'AAC' in audio:
            name = name.replace(audio.strip().replace("  ", " "), audio.replace("AAC ", "AAC"))
        name = name.replace("DD+ ", "DD+")
        name = name.replace("UHD BluRay REMUX", "Remux")
        name = name.replace("BluRay REMUX", "Remux")
        name = name.replace("H.265", "HEVC")
        name = name.replace(" Atmos", "")
        if is_disc == 'DVD':
            name = name.replace(f'{source} DVD5', f'{resolution} DVD {source}')
            name = name.replace(f'{source} DVD9', f'{resolution} DVD {source}')
            if audio == meta.get('channels'):
                name = name.replace(f'{audio}', f'MPEG {audio}')

        name = name + self.get_subs_tag(subs)
        return name

    async def get_description(self, meta):
        async with aiofiles.open(f'{meta["base_dir"]}/tmp/{meta["uuid"]}/DESCRIPTION.txt', 'r', encoding='utf-8') as f:
            base = await f.read()

        output_path = f'{meta["base_dir"]}/tmp/{meta["uuid"]}/[{self.tracker}]DESCRIPTION.txt'

        async with aiofiles.open(output_path, 'w', encoding='utf-8') as descfile:
            if meta.get('type') == 'WEBDL' and meta.get('service_longname', ''):
                await descfile.write(
                    f'[center][b][color=#ff00ff][size=18]This release is sourced from {meta["service_longname"]} and is not transcoded,'
                    f'just remuxed from the direct {meta["service_longname"]} stream[/size][/color][/b][/center]\n'
                )

            bbcode = BBCODE()

            discs = meta.get('discs', [])
            if discs:
                if discs[0].get('type') == 'DVD':
                    await descfile.write(f'[spoiler=VOB MediaInfo][code]{discs[0]["vob_mi"]}[/code][/spoiler]\n\n')

                if len(discs) >= 2:
                    for each in discs[1:]:
                        if each.get('type') == 'BDMV':
                            # descfile.write(f"[spoiler={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/spoiler]\n")
                            # descfile.write("\n")
                            pass
                        if each.get('type') == 'DVD':
                            await descfile.write(f'{each.get("name")}:\n')
                            vob_mi = each.get("vob_mi", '')
                            ifo_mi = each.get("ifo_mi", '')
                            await descfile.write(
                                f'[spoiler={os.path.basename(each["vob"])}][code]{vob_mi}[/code][/spoiler] '
                                f'[spoiler={os.path.basename(each["ifo"])}][code]{ifo_mi}[/code][/spoiler]\n\n'
                            )

            desc = re.sub(r'\[center\]\[spoiler=Scene NFO:\].*?\[/center\]', '', base, flags=re.DOTALL)
            desc = bbcode.convert_pre_to_code(desc)
            desc = bbcode.convert_hide_to_spoiler(desc)
            desc = bbcode.convert_comparison_to_collapse(desc, 1000)
            desc = desc.replace('[img]', '[img=300]')

            await descfile.write(desc)

            images = meta.get('image_list', [])

            if images:
                await descfile.write('[center]\n')
                for i in range(min(len(images), int(meta.get('screens', 0)))):
                    image = images[i]
                    web_url = image.get('web_url', '')
                    img_url = image.get('img_url', '')
                    await descfile.write(f'[url={web_url}][img=350]{img_url}[/img][/url]')
                await descfile.write('\n[/center]')

            await descfile.write(f"\n[right][url=https://github.com/Audionut/Upload-Assistant][size=4]{meta['ua_signature']}[/size][/url][/right]")

        async with aiofiles.open(output_path, 'r', encoding='utf-8') as f:
            final_desc = await f.read()

        return final_desc
