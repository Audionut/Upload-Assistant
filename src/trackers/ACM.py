# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import os
import platform
from src.trackers.COMMON import COMMON
from src.console import console
import bencodepy
import httpx


class ACM():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """

    def __init__(self, config):
        self.config = config
        self.tracker = 'ACM'
        self.source_flag = 'AsianCinema'
        self.upload_url = 'https://eiga.moi/api/torrents/upload'
        self.search_url = 'https://eiga.moi/api/torrents/filter'
        self.signature = None
        self.banned_groups = [""]
        pass

    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1',
            'TV': '2',
        }.get(category_name, '0')
        return category_id

    async def get_type(self, meta):
        if meta['is_disc'] == "BDMV":
            bdinfo = meta['bdinfo']
            bd_sizes = [25, 50, 66, 100]
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
            if meta['type'] == "REMUX":
                if meta['source'] == "BluRay":
                    type_string = "REMUX"
                if meta['uhd'] == "UHD":
                    type_string = "UHD REMUX"
            else:
                type_string = meta['type']
            # else:
            #     acceptable_res = ["2160p", "1080p", "1080i", "720p", "576p", "576i", "540p", "480p", "Other"]
            #     if meta['resolution'] in acceptable_res:
            #         type_id = meta['resolution']
            #     else:
            #         type_id = "Other"
        return type_string

    async def get_type_id(self, type):
        type_id = {
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
            'HDTV': '17'
        }.get(type, '0')
        return type_id

    async def get_res_id(self, resolution):
        resolution_id = {
            '2160p': '1',
            '1080p': '2',
            '1080i': '2',
            '720p': '3',
            '576p': '4',
            '576i': '4',
            '480p': '5',
            '480i': '5'
        }.get(resolution, '10')
        return resolution_id

    # ACM rejects uploads with more that 10 keywords
    async def get_keywords(self, keywords):
        if keywords != '':
            keywords_list = keywords.split(',')
            keywords_list = [keyword for keyword in keywords_list if " " not in keyword][:10]
            keywords = ', '.join(keywords_list)
        return keywords

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
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'])
        type_id = await self.get_type_id(await self.get_type(meta))
        resolution_id = await self.get_res_id(meta['resolution'])
        await self.edit_desc(meta)
        region_id = await common.unit3d_region_ids(meta.get('region'))
        distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
        acm_name = await self.edit_name(meta)
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
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8').read()
            bd_dump = None
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent", 'rb')
        files = {'torrent': open_torrent}
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
            'keywords': await self.get_keywords(meta['keywords']),
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
            except Exception:
                console.print("It may have uploaded, go check")
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()

    async def search_existing(self, meta, disctype):
        dupes = []
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdb': meta['tmdb'],
            'categories[]': await self.get_cat_id(meta['category']),
            'types[]': await self.get_type_id(await self.get_type(meta)),
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

    # async def fix_rtl(self, meta):
    #     original_title = meta.get('original_title')
    #     right_to_left_languages: ["Arabic", "Aramaic", "Azeri", "Divehi", "Fula", "Hebrew", "Kurdish", "N'ko", "Persian", "Rohingya", "Syriac", "Urdu"]
    #     if meta.get('original_language') in right_to_left_languages:
    #         return f' / {original_title} {chr(int("202A", 16))}'
    #     return original_title

    async def edit_name(self, meta):
        name = meta.get('name')
        aka = meta.get('aka')
        original_title = meta.get('original_title')
        year = str(meta.get('year'))  # noqa F841
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
        if is_disc == 'DVD':
            name = name.replace(f'{source} DVD5', f'{resolution} DVD {source}')
            name = name.replace(f'{source} DVD9', f'{resolution} DVD {source}')
            if audio == meta.get('channels'):
                name = name.replace(f'{audio}', f'MPEG {audio}')

        name = name + self.get_subs_tag(subs)
        return name

    async def edit_desc(self, meta):
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding='utf-8').read()
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as descfile:
            from src.bbcode import BBCODE
            # Add This line for all web-dls
            if meta['type'] == 'WEBDL' and meta.get('service_longname', '') != '':
                descfile.write(f"[center][b][color=#ff00ff][size=18]This release is sourced from {meta['service_longname']} and is not transcoded, just remuxed from the direct {meta['service_longname']} stream[/size][/color][/b][/center]")
            bbcode = BBCODE()
            if meta.get('discs', []) != []:
                discs = meta['discs']
                if discs[0]['type'] == "DVD":
                    descfile.write(f"[spoiler=VOB MediaInfo][code]{discs[0]['vob_mi']}[/code][/spoiler]\n")
                    descfile.write("\n")
                if len(discs) >= 2:
                    for each in discs[1:]:
                        if each['type'] == "BDMV":
                            # descfile.write(f"[spoiler={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/spoiler]\n")
                            # descfile.write("\n")
                            pass
                        if each['type'] == "DVD":
                            descfile.write(f"{each['name']}:\n")
                            descfile.write(f"[spoiler={os.path.basename(each['vob'])}][code][{each['vob_mi']}[/code][/spoiler] [spoiler={os.path.basename(each['ifo'])}][code][{each['ifo_mi']}[/code][/spoiler]\n")
                            descfile.write("\n")
            desc = base
            desc = bbcode.convert_pre_to_code(desc)
            desc = bbcode.convert_hide_to_spoiler(desc)
            desc = bbcode.convert_comparison_to_collapse(desc, 1000)
            desc = desc.replace('[img]', '[img=300]')
            descfile.write(desc)
            images = meta['image_list']
            if len(images) > 0:
                descfile.write("[center]")
                for each in range(len(images[:int(meta['screens'])])):
                    web_url = images[each]['web_url']
                    img_url = images[each]['img_url']
                    descfile.write(f"[url={web_url}][img=350]{img_url}[/img][/url]")
                descfile.write("[/center]")
            if self.signature is not None:
                descfile.write(self.signature)
            descfile.close()
        return

    async def search_torrent_page(self, meta, disctype):
        torrent_file_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent"
        Name = meta['name']
        quoted_name = f'"{Name}"'

        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'name': quoted_name
        }

        try:
            response = requests.get(url=self.search_url, params=params)
            response.raise_for_status()
            response_data = response.json()

            if response_data['data'] and isinstance(response_data['data'], list):
                details_link = response_data['data'][0]['attributes'].get('details_link')

                if details_link:
                    with open(torrent_file_path, 'rb') as open_torrent:
                        torrent_data = open_torrent.read()

                    torrent = bencodepy.decode(torrent_data)
                    torrent[b'comment'] = details_link.encode('utf-8')
                    updated_torrent_data = bencodepy.encode(torrent)

                    with open(torrent_file_path, 'wb') as updated_torrent_file:
                        updated_torrent_file.write(updated_torrent_data)

                    return details_link
                else:
                    return None
            else:
                return None

        except requests.exceptions.RequestException as e:
            print(f"An error occurred during the request: {e}")
            return None
