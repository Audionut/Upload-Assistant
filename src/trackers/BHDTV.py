# -*- coding: utf-8 -*-
# import discord
import requests
from src.console import console
from pprint import pprint
import os
import traceback
from src.trackers.COMMON import COMMON
from pymediainfo import MediaInfo


class BHDTV():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """

    def __init__(self, config):
        self.config = config
        self.tracker = 'BHDTV'
        self.source_flag = 'BIT-HDTV'
        # search not implemented
        # self.search_url = 'https://api.bit-hdtv.com/torrent/search/advanced'
        self.upload_url = 'https://www.bit-hdtv.com/takeupload.php'
        # self.forum_link = 'https://www.bit-hdtv.com/rules.php'
        self.banned_groups = []
        pass

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await self.edit_desc(meta)
        cat_id = await self.get_cat_id(meta)
        sub_cat_id = ""
        if meta['category'] == 'MOVIE':
            sub_cat_id = await self.get_type_movie_id(meta)
        elif meta['category'] == 'TV' and not meta['tv_pack']:
            sub_cat_id = await self.get_type_tv_id(meta['type'])
        else:
            # must be TV pack
            sub_cat_id = await self.get_type_tv_pack_id(meta['type'])

        resolution_id = await self.get_res_id(meta['resolution'])
        # region_id = await common.unit3d_region_ids(meta.get('region'))
        # distributor_id = await common.unit3d_distributor_ids(meta.get('distributor'))
        if meta['anon'] == 0 and not self.config['TRACKERS'][self.tracker].get('anon', False):
            anon = 0
        else:
            anon = 1  # noqa F841

        if meta['bdinfo'] is not None:
            mi_dump = None
            bd_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8').read()
        else:
            mi_dump = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'r', encoding='utf-8').read()
            bd_dump = None
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', encoding='utf-8').read()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent", 'rb')
        files = {'file': open_torrent}

        if meta['is_disc'] != 'BDMV':
            # Beautify MediaInfo for HDT using custom template
            video = meta['filelist'][0]
            mi_template = os.path.abspath(f"{meta['base_dir']}/data/templates/MEDIAINFO.txt")
            if os.path.exists(mi_template):
                media_info = MediaInfo.parse(video, output="STRING", full=False,
                                             mediainfo_options={"inform": f"file://{mi_template}"})

        data = {
            'api_key': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'name': meta['name'].replace(' ', '.').replace(':.', '.').replace(':', '.').replace('DD+', 'DDP'),
            'mediainfo': mi_dump if bd_dump is None else bd_dump,
            'cat': cat_id,
            'subcat': sub_cat_id,
            'resolution': resolution_id,
            # 'anon': anon,
            # admins asked to remove short description.
            'sdescr': " ",
            'descr': media_info if bd_dump is None else "Disc so Check Mediainfo dump ",
            'screen': desc,
            'url': f"https://www.tvmaze.com/shows/{meta['tvmaze_id']}" if meta['category'] == 'TV' else f"https://www.imdb.com/title/tt{meta['imdb_id']}",
            'format': 'json'
        }

        if meta['debug'] is False:
            response = requests.post(url=self.upload_url, data=data, files=files)
            try:
                # pprint(data)
                meta['tracker_status'][self.tracker]['status_message'] = response.json()
            except Exception:
                console.print("[cyan]It may have uploaded, go check")
                # cprint(f"Request Data:", 'cyan')
                pprint(data)
                console.print(traceback.print_exc())
        else:
            console.print("[cyan]Request Data:")
            pprint(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        # # adding my anounce url to torrent.
        if 'view' in response.json()['data']:
            await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS']['BHDTV'].get('my_announce_url'), response.json()['data']['view'])
        else:
            await common.add_tracker_torrent(meta, self.tracker, self.source_flag,
                                             self.config['TRACKERS']['BHDTV'].get('my_announce_url'),
                                             "Torrent Did not upload")
        open_torrent.close()

    async def get_cat_id(self, meta):
        category_id = '0'
        if meta['category'] == 'MOVIE':
            category_id = '7'
        elif meta['tv_pack']:
            category_id = '12'
        else:
            # must be tv episode
            category_id = '10'
        return category_id

    async def get_type_movie_id(self, meta):
        type_id = '0'
        test = meta['type']  # noqa F841
        if meta['type'] == 'DISC':
            if meta['3D']:
                type_id = '46'
            else:
                type_id = '2'
        elif meta['type'] == 'REMUX':
            if str(meta['name']).__contains__('265'):
                type_id = '48'
            elif meta['3D']:
                type_id = '45'
            else:
                type_id = '2'
        elif meta['type'] == 'HDTV':
            type_id = '6'
        elif meta['type'] == 'ENCODE':
            if str(meta['name']).__contains__('265'):
                type_id = '43'
            elif meta['3D']:
                type_id = '44'
            else:
                type_id = '1'
        elif meta['type'] == 'WEBDL' or meta['type'] == 'WEBRIP':
            type_id = '5'

        return type_id

    async def get_type_tv_id(self, type):
        type_id = {
            'HDTV': '7',
            'WEBDL': '8',
            'WEBRIP': '8',
            # 'WEBRIP': '55',
            # 'SD': '59',
            'ENCODE': '10',
            'REMUX': '11',
            'DISC': '12',
        }.get(type, '0')
        return type_id

    async def get_type_tv_pack_id(self, type):
        type_id = {
            'HDTV': '13',
            'WEBDL': '14',
            'WEBRIP': '8',
            # 'WEBRIP': '55',
            # 'SD': '59',
            'ENCODE': '16',
            'REMUX': '17',
            'DISC': '18',
        }.get(type, '0')
        return type_id

    async def get_res_id(self, resolution):
        resolution_id = {
            '2160p': '4',
            '1080p': '3',
            '1080i': '2',
            '720p': '1'
        }.get(resolution, '10')
        return resolution_id

    async def edit_desc(self, meta):
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r', encoding='utf-8').read()
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', encoding='utf-8') as desc:
            desc.write(base.replace("[img=250]", "[img=250x250]"))
            images = meta['image_list']
            if len(images) > 0:
                for each in range(len(images)):
                    web_url = images[each]['web_url']
                    img_url = images[each]['img_url']
                    desc.write(f"[url={web_url}][img]{img_url}[/img][/url] ")
            # desc.write(common.get_links(meta, "[COLOR=red][size=4]", "[/size][/color]"))
            desc.close()
        return

    async def search_existing(self, meta, disctype):
        console.print("[red]Dupes must be checked Manually")
        return ['Dupes must be checked Manually']
        # hopefully someone else has the time to implement this.
