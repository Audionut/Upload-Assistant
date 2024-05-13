# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
from difflib import SequenceMatcher
from str2bool import str2bool
import urllib
import os
import platform

from src.trackers.COMMON import COMMON
from src.console import console

class BHD():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """
    def __init__(self, config):
        self.config = config
        self.tracker = 'BHD'
        self.source_flag = 'BHD'
        self.upload_url = 'https://beyond-hd.me/api/upload/'
        self.signature = f"\n[center][url=https://beyond-hd.me/forums/topic/toolpython-l4gs-upload-assistant.5456]Created by L4G's Upload Assistant[/url][/center]"
        self.banned_groups = ['Sicario', 'TOMMY', 'x0r', 'nikt0', 'FGT', 'd3g', 'MeGusta', 'YIFY', 'tigole', 'TEKNO3D', 'C4K', 'RARBG', '4K4U', 'EASports', 'ReaLHD']
        pass
    
    async def upload(self, meta):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        cat_id = await self.get_cat_id(meta['category'])
        source_id = await self.get_source(meta['source'])
        type_id = await self.get_type(meta)
        draft = await self.get_live(meta)
        await self.edit_desc(meta)
        tags = await self.get_tags(meta)
        custom, edition = await self.get_edition(meta, tags)
        bhd_name = await self.edit_name(meta)
        if meta['anon'] == 0 and bool(str2bool(str(self.config['TRACKERS'][self.tracker].get('anon', "False")))) == False:
            anon = 0
        else:
            anon = 1
            
        if meta['bdinfo'] != None:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8')
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r', encoding='utf-8')
            
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r').read()
        torrent_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent"
        files = {
            'mediainfo' : mi_dump,
            }
        if os.path.exists(torrent_file):
            open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent", 'rb')
            files['file'] = open_torrent.read()
            open_torrent.close()
        
        data = {
            'name' : bhd_name,
            'category_id' : cat_id,
            'type' : type_id,
            'source': source_id,
            'imdb_id' : meta['imdb_id'].replace('tt', ''),    
            'tmdb_id' : meta['tmdb'],
            'description' : desc,
            'anon' : anon,
            'sd' : meta.get('sd', 0),
            'live' : draft 
            # 'internal' : 0,
            # 'featured' : 0,
            # 'free' : 0,
            # 'double_up' : 0,
            # 'sticky' : 0,
        }
        # Internal
        if self.config['TRACKERS'][self.tracker].get('internal', False) == True:
            if meta['tag'] != "" and (meta['tag'][1:] in self.config['TRACKERS'][self.tracker].get('internal_groups', [])):
                data['internal'] = 1
                
        if meta.get('tv_pack', 0) == 1:
            data['pack'] = 1
        if meta.get('season', None) == "S00":
            data['special'] = 1
        if meta.get('region', "") != "":
            data['region'] = meta['region']
        if custom == True:
            data['custom_edition'] = edition
        elif edition != "":
            data['edition'] = edition
        if len(tags) > 0:
            data['tags'] = ','.join(tags)
        headers = {
            'User-Agent': f'Upload Assistant/2.1 ({platform.system()} {platform.release()})'
        }
        
        url = self.upload_url + self.config['TRACKERS'][self.tracker]['api_key'].strip()
        if meta['debug'] == False:
            response = requests.post(url=url, files=files, data=data, headers=headers)
            try:
                response = response.json()
                if int(response['status_code']) == 0:
                    console.print(f"[red]{response['status_message']}")
                    if response['status_message'].startswith('Invalid imdb_id'):
                        console.print('[yellow]RETRYING UPLOAD')
                        data['imdb_id'] = 1
                        response = requests.post(url=url, files=files, data=data, headers=headers)
                        response = response.json()
                    elif response['satus_message'].startswith('Invalid name value'):
                        console.print(f"[bold yellow]Submitted Name: {bhd_name}")
                console.print(response)
            except:
                console.print("It may have uploaded, go check")
                return 
        else:
            console.print(f"[cyan]Request Data:")
            console.print(data)
        
        





    async def get_cat_id(self, category_name):
        category_id = {
            'MOVIE': '1', 
            'TV': '2', 
            }.get(category_name, '1')
        return category_id

    async def get_source(self, source):
        sources = {
            "Blu-ray" : "Blu-ray",
            "BluRay" : "Blu-ray",
            "HDDVD" : "HD-DVD",
            "HD DVD" : "HD-DVD",
            "Web" : "WEB",
            "HDTV" : "HDTV",
            "UHDTV" : "HDTV",
            "NTSC" : "DVD",  "NTSC DVD" : "DVD",
            "PAL" : "DVD", "PAL DVD": "DVD",
        }
        
        source_id = sources.get(source)
        return source_id

    async def get_type(self, meta):
        if meta['is_disc'] == "BDMV":
            bdinfo = meta['bdinfo']
            bd_sizes = [25, 50, 66, 100]
            for each in bd_sizes:
                if bdinfo['size'] < each:
                    bd_size = each
                    break
            if meta['uhd'] == "UHD" and bd_size != 25:
                type_id = f"UHD {bd_size}"
            else:
                type_id = f"BD {bd_size}"
            if type_id not in ['UHD 100', 'UHD 66', 'UHD 50', 'BD 50', 'BD 25']:
                type_id = "Other"
        elif meta['is_disc'] == "DVD":
            if "DVD5" in meta['dvd_size']:
                type_id = "DVD 5"
            elif "DVD9" in meta['dvd_size']:
                type_id = "DVD 9"    
        else:
            if meta['type'] == "REMUX":
                if meta['source'] == "BluRay":
                    type_id = "BD Remux"
                if meta['source'] in ("PAL DVD", "NTSC DVD"):
                    type_id = "DVD Remux"
                if meta['uhd'] == "UHD":
                    type_id = "UHD Remux"
                if meta['source'] == "HDDVD":
                    type_id = "Other"
            else:
                acceptable_res = ["2160p", "1080p", "1080i", "720p", "576p", "576i", "540p", "480p", "Other"]
                if meta['resolution'] in acceptable_res:
                    type_id = meta['resolution']
                else:
                    type_id = "Other"
        return type_id


        
    async def edit_desc(self, meta):
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r').read()
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w') as desc:
            if meta.get('discs', []) != []:
                discs = meta['discs']
                if discs[0]['type'] == "DVD":
                    desc.write(f"[spoiler=VOB MediaInfo][code]{discs[0]['vob_mi']}[/code][/spoiler]")
                    desc.write("\n")
                if len(discs) >= 2:
                    for each in discs[1:]:
                        if each['type'] == "BDMV":
                            desc.write(f"[spoiler={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/spoiler]")
                            desc.write("\n")
                        elif each['type'] == "DVD":
                            desc.write(f"{each['name']}:\n")
                            desc.write(f"[spoiler={os.path.basename(each['vob'])}][code][{each['vob_mi']}[/code][/spoiler] [spoiler={os.path.basename(each['ifo'])}][code][{each['ifo_mi']}[/code][/spoiler]")
                            desc.write("\n")
                        elif each['type'] == "HDDVD":
                            desc.write(f"{each['name']}:\n")
                            desc.write(f"[spoiler={os.path.basename(each['largest_evo'])}][code][{each['evo_mi']}[/code][/spoiler]\n")
                            desc.write("\n")
            desc.write(base.replace("[img]", "[img width=300]"))
            images = meta['image_list']
            if len(images) > 0: 
                desc.write("[center]")
                for each in range(len(images[:int(meta['screens'])])):
                    web_url = images[each]['web_url']
                    img_url = images[each]['img_url']
                    desc.write(f"[url={web_url}][img width=350]{img_url}[/img][/url]")
                desc.write("[/center]")
            desc.write(self.signature)
            desc.close()
        return
   


    async def search_existing(self, meta):
        dupes = []
        console.print("[yellow]Searching for existing torrents on site...")
        category = meta['category']
        if category == 'MOVIE':
            category = "Movies"
        data = {
            'tmdb_id' : meta['tmdb'],
            'categories' : category,
            'types' : await self.get_type(meta),
        }
        # Search all releases if SD
        if meta['sd'] == 1:
            data['categories'] = None
            data['types'] = None
        if meta['category'] == 'TV':
            if meta.get('tv_pack', 0) == 1:
                data['pack'] = 1
            data['search'] = f"{meta.get('season', '')}{meta.get('episode', '')}"
        url = f"https://beyond-hd.me/api/torrents/{self.config['TRACKERS']['BHD']['api_key'].strip()}?action=search"
        try:
            response = requests.post(url=url, data=data)
            response = response.json()
            if response.get('status_code') == 1:
                for each in response['results']:
                    result = each['name']
                    difference = SequenceMatcher(None, meta['clean_name'].replace('DD+', 'DDP'), result).ratio()
                    if difference >= 0.05:
                        dupes.append(result)
            else:
                console.print(f"[yellow]{response.get('status_message')}")
                await asyncio.sleep(5) 
        except:
            console.print('[bold red]Unable to search for existing torrents on site. Most likely the site is down.')
            await asyncio.sleep(5)

        return dupes

    async def get_live(self, meta): 
        draft = self.config['TRACKERS'][self.tracker]['draft_default'].strip()
        draft = bool(str2bool(str(draft))) #0 for send to draft, 1 for live
        if draft:
            draft_int = 0
        else:
            draft_int = 1
        if meta['draft']:
            draft_int = 0
        return draft_int

    async def get_edition(self, meta, tags):
        custom = False
        edition = meta.get('edition', "")
        if "Hybrid" in tags:
            edition = edition.replace('Hybrid', '').strip()
        editions = ['collector', 'cirector', 'extended', 'limited', 'special', 'theatrical', 'uncut', 'unrated']
        for each in editions:
            if each in meta.get('edition'):
                edition = each
            elif edition == "":
                edition = ""
            else:
                custom = True 
        return custom, edition

    async def get_tags(self, meta):
        tags = []
        if meta['type'] == "WEBRIP":
            tags.append("WEBRip")
        if meta['type'] == "WEBDL":
            tags.append("WEBDL")
        if meta.get('3D') == "3D":
            tags.append('3D')
        if "Dual-Audio" in meta.get('audio', ""):
            tags.append('DualAudio')
        if "Dubbed" in meta.get('audio', ""):
            tags.append('EnglishDub')
        if "Open Matte" in meta.get('edition', ""):
            tags.append("OpenMatte")
        if meta.get('scene', False) == True:
            tags.append("Scene")
        if meta.get('personalrelease', False) == True:
            tags.append('Personal')
        if "hybrid" in meta.get('edition', "").lower():
            tags.append('Hybrid')
        if meta.get('has_commentary', False) == True:
            tags.append('Commentary')
        if "DV" in meta.get('hdr', ''):
            tags.append('DV')
        if "HDR" in meta.get('hdr', ''):
            if "HDR10+" in meta['hdr']:
                tags.append('HDR10+')
            else:
                tags.append('HDR10')
        if "HLG" in meta.get('hdr', ''):
            tags.append('HLG')
        return tags

    async def edit_name(self, meta):
        name = meta.get('name')
        if meta.get('source', '') in ('PAL DVD', 'NTSC DVD', 'DVD', 'NTSC', 'PAL'):
            audio = meta.get('audio', '')
            audio = ' '.join(audio.split())
            name = name.replace(audio, f"{meta.get('video_codec')} {audio}")
        name = name.replace("DD+", "DDP")
        # if meta['type'] == 'WEBDL' and meta.get('has_encode_settings', False) == True:
        #     name = name.replace('H.264', 'x264')
        if meta['category'] == "TV" and meta.get('tv_pack', 0) == 0 and meta.get('episode_title_storage', '').strip() != '' and meta['episode'].strip() != '':
            name = name.replace(meta['episode'], f"{meta['episode']} {meta['episode_title_storage']}", 1)
        return name