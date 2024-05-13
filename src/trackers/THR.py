# -*- coding: utf-8 -*-
import asyncio
from torf import Torrent
import requests
import json
import glob
from difflib import SequenceMatcher
import cli_ui
import base64
import os
import re
import platform
from unidecode import unidecode

from src.console import console 


class THR():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """
    def __init__(self, config):
        self.config = config
        self.username = config['TRACKERS']['THR'].get('username')
        self.password = config['TRACKERS']['THR'].get('password')
        self.banned_groups = [""]
        pass
    
    async def upload(self, session, meta):
        await self.edit_torrent(meta)
        cat_id = await self.get_cat_id(meta)
        subs = self.get_subtitles(meta)
        pronfo = await self.edit_desc(meta)
        thr_name = unidecode(meta['name'].replace('DD+', 'DDP'))

        # Confirm the correct naming order for FL
        cli_ui.info(f"THR name: {thr_name}")
        if meta.get('unattended', False) == False:
            thr_confirm = cli_ui.ask_yes_no("Correct?", default=False)
            if thr_confirm != True:
                thr_name_manually = cli_ui.ask_string("Please enter a proper name", default="")
                if thr_name_manually == "":
                    console.print('No proper name given')
                    console.print("Aborting...")
                    return
                else:
                    thr_name = thr_name_manually
        torrent_name = re.sub(r"[^0-9a-zA-Z. '\-\[\]]+", " ", thr_name)


        if meta.get('is_disc', '') == 'BDMV':
            mi_file = None
            # bd_file = f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8'
        else:
            mi_file = os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt")
            with open(mi_file, 'r') as f:
                mi_file = f.read()
                f.close()
            # bd_file = None

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[THR]DESCRIPTION.txt", 'r') as f:
            desc = f.read()
            f.close()
        
        torrent_path = os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/[THR]{meta['clean_name']}.torrent")
        with open(torrent_path, 'rb') as f:
            tfile = f.read()
            f.close()
        
        #Upload Form
        url = 'https://www.torrenthr.org/takeupload.php'
        files = {
            'tfile' : (f'{torrent_name}.torrent', tfile)
        }
        payload = {
            'name' : thr_name,
            'descr' : desc,
            'type' : cat_id,
            'url' : f"https://www.imdb.com/title/tt{meta.get('imdb_id').replace('tt', '')}/",
            'tube' : meta.get('youtube', '')
        }
        headers = {
            'User-Agent' : f'Upload Assistant/2.1 ({platform.system()} {platform.release()})'
        }
        #If pronfo fails, put mediainfo into THR parser
        if meta.get('is_disc', '') != 'BDMV':
            files['nfo'] = ("MEDIAINFO.txt", mi_file)
        if subs != []:
            payload['subs[]'] = tuple(subs)


        if meta['debug'] == False:
            thr_upload_prompt = True
        else:
            thr_upload_prompt = cli_ui.ask_yes_no("send to takeupload.php?", default=False)
        if thr_upload_prompt == True:
            await asyncio.sleep(0.5)
            response = session.post(url=url, files=files, data=payload, headers=headers)
            try:
                if meta['debug']:
                    console.print(response.text)
                if response.url.endswith('uploaded=1'):
                    console.print(f'[green]Successfully Uploaded at: {response.url}')
                #Check if actually uploaded
            except:
                if meta['debug']:
                    console.print(response.text)
                console.print("It may have uploaded, go check")
                return 
        else:
            console.print(f"[cyan]Request Data:")
            console.print(payload)
            
    
    
    async def get_cat_id(self, meta):
        if meta['category'] == "MOVIE":
            if meta.get('is_disc') == "BMDV":
                cat = '40'
            elif meta.get('is_disc') == "DVD" or meta.get('is_disc') == "HDDVD":
                cat = '14'
            else:
                if meta.get('sd') == 1:
                    cat = '4'
                else:
                    cat = '17'
        elif meta['category'] == "TV":
            if meta.get('sd') == 1:
                cat = '7'
            else:
                cat = '34'
        elif meta.get('anime') != False:
            cat = '31'
        return cat

    def get_subtitles(self, meta):
        subs = []
        sub_langs = []
        if meta.get('is_disc', '') != 'BDMV':
            with open(f"{meta.get('base_dir')}/tmp/{meta.get('uuid')}/MediaInfo.json", 'r', encoding='utf-8') as f:
                mi = json.load(f)
            for track in mi['media']['track']:
                if track['@type'] == "Text":
                    language = track.get('Language')
                    if language in ['hr', 'en', 'bs', 'sr', 'sl']:
                        if language not in sub_langs:
                            sub_langs.append(language)
        else:
            for sub in meta['bdinfo']['subtitles']:
                if sub not in sub_langs:
                    sub_langs.append(sub)
        if sub_langs != []:
            subs = []
            sub_lang_map = {
                'hr' : 1, 'en' : 2, 'bs' : 3, 'sr' : 4, 'sl' : 5,
                'Croatian' : 1, 'English' : 2, 'Bosnian' : 3, 'Serbian' : 4, 'Slovenian' : 5
            }
            for sub in sub_langs:
                language = sub_lang_map.get(sub)
                if language != None:
                    subs.append(language)
        return subs





    async def edit_torrent(self, meta):
        if os.path.exists(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent"):
            THR_torrent = Torrent.read(f"{meta['base_dir']}/tmp/{meta['uuid']}/BASE.torrent")
            THR_torrent.metainfo['announce'] = self.config['TRACKERS']['THR']['announce_url']
            THR_torrent.metainfo['info']['source'] = "[https://www.torrenthr.org] TorrentHR.org"
            Torrent.copy(THR_torrent).write(f"{meta['base_dir']}/tmp/{meta['uuid']}/[THR]{meta['clean_name']}.torrent", overwrite=True)
        return 
        
    async def edit_desc(self, meta):
        pronfo = False
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r').read()
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[THR]DESCRIPTION.txt", 'w', encoding='utf-8') as desc:
            if meta['tag'] == "":
                tag = ""
            else:
                tag = f" / {meta['tag'][1:]}"
            if meta['is_disc'] == "DVD":
                res = meta['source']
            else:
                res = meta['resolution']
            desc.write("[quote=Info]")
            name_aka = f"{meta['title']} {meta['aka']} {meta['year']}"
            name_aka = unidecode(name_aka)
            # name_aka = re.sub("[^0-9a-zA-Z. '\-\[\]]+", " ", name_aka)
            desc.write(f"Name: {' '.join(name_aka.split())}\n\n")
            desc.write(f"Overview: {meta['overview']}\n\n")
            desc.write(f"{res} / {meta['type']}{tag}\n\n")
            desc.write(f"Category: {meta['category']}\n")
            desc.write(f"TMDB: https://www.themoviedb.org/{meta['category'].lower()}/{meta['tmdb']}\n")
            if meta['imdb_id'] != "0":
                desc.write(f"IMDb: https://www.imdb.com/title/tt{meta['imdb_id']}\n")
            if meta['tvdb_id'] != "0":
                desc.write(f"TVDB: https://www.thetvdb.com/?id={meta['tvdb_id']}&tab=series\n")
            desc.write("[/quote]")
            desc.write(base)
            # REHOST IMAGES
            os.chdir(f"{meta['base_dir']}/tmp/{meta['uuid']}")
            image_glob = glob.glob("*.png")
            if 'POSTER.png' in image_glob:
                image_glob.remove('POSTER.png')
            image_list = []
            for image in image_glob:
                url = "https://img2.torrenthr.org/api/1/upload"
                data = {
                    'key' : self.config['TRACKERS']['THR'].get('img_api'),
                    # 'source' : base64.b64encode(open(image, "rb").read()).decode('utf8')
                }
                files = {'source' : open(image, 'rb')}
                response = requests.post(url, data = data, files=files)
                try:
                    response = response.json()
                    # med_url = response['image']['medium']['url']
                    img_url = response['image']['url']
                    image_list.append(img_url)
                except json.decoder.JSONDecodeError:
                    console.print("[yellow]Failed to upload image")
                    console.print(response.text)
                except KeyError:
                    console.print("[yellow]Failed to upload image")
                    console.print(response)
                await asyncio.sleep(1)
            desc.write("[align=center]")
            if meta.get('is_disc', '') == 'BDMV':
                with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt") as bd_file:
                    desc.write(f"[nfo]{bd_file.read()}[/nfo]")
                    bd_file.close()
            else:
                # ProNFO
                pronfo_url = f"https://www.pronfo.com/api/v1/access/upload/{self.config['TRACKERS']['THR'].get('pronfo_api_key', '')}"
                data = {
                    'content' : open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt", 'r').read(),
                    'theme' : self.config['TRACKERS']['THR'].get('pronfo_theme', 'gray'),
                    'rapi' : self.config['TRACKERS']['THR'].get('pronfo_rapi_id')
                }
                response = requests.post(pronfo_url, data=data)
                try:
                    response = response.json()
                    if response.get('error', True) == False:
                        mi_img = response.get('url')
                        desc.write(f"\n[img]{mi_img}[/img]\n")
                        pronfo = True
                except:
                    console.print('[bold red]Error parsing pronfo response, using THR parser instead')
                    if meta['debug']:
                        console.print(f"[red]{response}")
                        console.print(response.text) 

            for each in image_list[:int(meta['screens'])]:
                desc.write(f"\n[img]{each}[/img]\n")
            # if pronfo:
            #     with open(os.path.abspath(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO.txt"), 'r') as mi_file:
            #         full_mi = mi_file.read()
            #         desc.write(f"[/align]\n[hide=FULL MEDIAINFO]{full_mi}[/hide][align=center]")
            #         mi_file.close()
            desc.write("\n\n[size=2][url=https://www.torrenthr.org/forums.php?action=viewtopic&topicid=8977]Created by L4G's Upload Assistant[/url][/size][/align]")
            desc.close()
        return pronfo

   


    def search_existing(self, session, imdb_id):
        from bs4 import BeautifulSoup
        imdb_id = imdb_id.replace('tt', '')
        search_url = f"https://www.torrenthr.org/browse.php?search={imdb_id}&blah=2&incldead=1"
        search = session.get(search_url)
        soup = BeautifulSoup(search.text, 'html.parser')
        dupes = []
        for link in soup.find_all('a', href=True):
            if link['href'].startswith('details.php'):
                if link.get('onmousemove', False):
                    dupe = link['onmousemove'].split("','/images")
                    dupe = dupe[0].replace("return overlibImage('", "")
                    dupes.append(dupe)
        return dupes

    def login(self, session):
        url = 'https://www.torrenthr.org/takelogin.php'
        payload = {
            'username' : self.username,
            'password' : self.password,
            'ssl' : 'yes'
        }
        headers = {
            'User-Agent' : f'Upload Assistant/2.1 ({platform.system()} {platform.release()})'
        }
        resp = session.post(url, headers=headers, data=payload)
        if resp.url == "https://www.torrenthr.org/index.php":
            console.print('[green]Successfully logged in')
        return session
