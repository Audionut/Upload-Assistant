# -*- coding: utf-8 -*-
# import discord
import asyncio
import requests
import traceback
import cli_ui
import os
import re
import tmdbsimple as tmdb
from src.bbcode import BBCODE
import json
import httpx
from src.trackers.COMMON import COMMON
from src.console import console
from src.rehostimages import check_hosts
from src.languages import process_desc_language, has_english_language


class TVC():
    """
    Edit for Tracker:
        Edit BASE.torrent with announce and source
        Check for duplicates
        Set type/category IDs
        Upload
    """

    def __init__(self, config):
        self.config = config
        self.tracker = 'TVC'
        self.source_flag = 'TVCHAOS'
        self.upload_url = 'https://tvchaosuk.com/api/torrents/upload'
        self.search_url = 'https://tvchaosuk.com/api/torrents/filter'
        self.torrent_url = 'https://tvchaosuk.com/torrents/'
        self.signature = ""
        self.banned_groups = []
        tmdb.API_KEY = config['DEFAULT']['tmdb_api']

        # TV type mappings used throughout the class (make them instance attributes)
        self.tv_types = [
            "comedy", "documentary", "drama", "entertainment", "factual",
            "foreign", "kids", "movies", "News", "radio", "reality", "soaps",
            "sci-fi", "sport", "holding bin"
        ]
        self.tv_types_ids = [
            "29", "5", "11", "14", "19",
            "43", "32", "44", "45", "51", "52", "30",
            "33", "42", "53"
        ]

        pass

    async def get_cat_id(self, genres):
        # Note sections are based on Genre not type, source, resolution etc..
        # Use instance attributes self.tv_types / self.tv_types_ids defined in __init__
        genres = genres.split(', ')
        if len(genres) >= 1:
            for i in genres:
                g = i.lower().replace(',', '')
                for s in self.tv_types:
                    if s.__contains__(g):
                        return self.tv_types_ids[self.tv_types.index(s)]

        # returning holding bin/misc id
        return self.tv_types_ids[14]

    async def get_res_id(self, tv_pack, resolution):
        if tv_pack:
            resolution_id = {
                '1080p': 'HD1080p Pack',
                '1080i': 'HD1080p Pack',
                '720p': 'HD720p Pack',
                '576p': 'SD Pack',
                '576i': 'SD Pack',
                '540p': 'SD Pack',
                '540i': 'SD Pack',
                '480p': 'SD Pack',
                '480i': 'SD Pack'
            }.get(resolution, 'SD')
        else:
            resolution_id = {
                '1080p': 'HD1080p',
                '1080i': 'HD1080p',
                '720p': 'HD720p',
                '576p': 'SD',
                '576i': 'SD',
                '540p': 'SD',
                '540': 'SD',
                '480p': 'SD',
                '480i': 'SD'
            }.get(resolution, 'SD')
        return resolution_id

    async def append_country_code(self, meta, name):
        if 'origin_country_code' in meta:
            if "IE" in meta['origin_country_code']:
                name += " [IRL]"
            elif "AU" in meta['origin_country_code']:
                name += " [AUS]"
            elif "NZ" in meta['origin_country_code']:
                name += " [NZL]"
            elif "CA" in meta['origin_country_code']:
                name += " [CAN]"
            elif "IT" in meta['origin_country_code']:
                name += " [ITA]"
            elif "FR" in meta['origin_country_code']:
                name += " [FRA]"
            elif "DE" in meta['origin_country_code']:
                name += " [GER]"
            elif "ES" in meta['origin_country_code']:
                name += " [SPA]"
            elif "PT" in meta['origin_country_code']:
                name += " [POR]"
            elif "BE" in meta['origin_country_code']:
                name += " [BEL]"
            elif "DK" in meta['origin_country_code']:
                name += " [DNK]"
            elif "NL" in meta['origin_country_code']:
                name += " [NLD]"
            elif "SE" in meta['origin_country_code']:
                name += " [SWE]"
            elif "NO" in meta['origin_country_code']:
                name += " [NOR]"
            elif "FI" in meta['origin_country_code']:
                name += " [FIN]"
            elif "IS" in meta['origin_country_code']:
                name += " [ISL]"
            elif "PL" in meta['origin_country_code']:
                name += " [POL]"
            elif "RU" in meta['origin_country_code']:
                name += " [RUS]"
            elif "AT" in meta['origin_country_code']:
                name += " [AST]"
            elif "CZ" in meta['origin_country_code']:
                name += " [CZE]"
            elif "EE" in meta['origin_country_code']:
                name += " [EST]"
            elif "CH" in meta['origin_country_code']:
                name += " [CHE]"
        return name

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        url_host_mapping = {
            "ibb.co": "imgbb",
            "ptpimg.me": "ptpimg",
            "imgbox.com": "imgbox",
            "pixhost.to": "pixhost",
            "imagebam.com": "bam",
            "onlyimage.org": "onlyimage",
        }

        approved_image_hosts = ['imgbb', 'ptpimg', 'imgbox', 'pixhost', 'bam', 'onlyimage']
        await check_hosts(meta, self.tracker, url_host_mapping=url_host_mapping, img_host_index=1, approved_image_hosts=approved_image_hosts)
        if 'TVC_images_key' in meta:
            image_list = meta['TVC_images_key']
        else:
            image_list = meta['image_list']

        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await self.get_tmdb_data(meta)
        # load MediaInfo and extract audio languages first
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MediaInfo.json", 'r', encoding='utf-8') as f:
            mi = json.load(f)

            # mi already loaded above; reuse it (no additional file reads)
            # parse audio languages from MediaInfo (pure helper)
            audio_langs_local = self.get_audio_languages(mi)

            if meta['category'] == 'TV':
                cat_id = await self.get_cat_id(meta['genres'])
            else:
                cat_id = 44

            # ensure language detection helpers have run and consider subs too
            if not meta.get('language_checked', False):
                await process_desc_language(meta, desc=None, tracker=self.tracker)

            # prefer pipeline-populated meta values; fall back to local parse
            # treat empty lists as falsy: meta.get('audio_languages') may be [] which should fall back
            audio_meta = meta.get('audio_languages') or audio_langs_local

            # gather subtitle languages (best-effort) but do NOT use them to decide "foreign"
            subtitle_langs_local = []
            try:
                for t in mi.get('media', {}).get('track', []):
                    if t.get('@type') == 'Text' and 'Language' in t and t['Language']:
                        subtitle_langs_local.append(str(t['Language']).strip().title())
            except Exception:
                subtitle_langs_local = []

            subtitle_meta = meta.get('subtitle_languages') or subtitle_langs_local

            # Check English presence in audio only (per new rule)
            audio_has_english = await has_english_language(audio_meta)

            # mark as foreign only when audio languages are present and NONE are English
            if audio_meta and not audio_has_english:
                cat_id = self.tv_types_ids[self.tv_types.index("foreign")]

        resolution_id = await self.get_res_id(meta['tv_pack'] if 'tv_pack' in meta else 0, meta['resolution'])
        # this is a different function that common function
        await self.unit3d_edit_desc(meta, self.tracker, self.signature, image_list)

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
        desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r').read()
        open_torrent = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}].torrent", 'rb')
        files = {'torrent': open_torrent}

        if meta['type'] == "ENCODE" and (str(meta['path']).lower().__contains__("bluray") or str(meta['path']).lower().__contains__("brrip") or str(meta['path']).lower().__contains__("bdrip")):
            type = "BRRip"
        else:
            type = meta['type'].replace('WEBDL', 'WEB-DL')

        # Naming as per TVC rules. Site has unusual naming conventions.
        if meta['category'] == "MOVIE":
            tvc_name = f"{meta['title']} ({meta['year']}) [{meta['resolution']} {type} {str(meta['video'][-3:]).upper()}]"
        else:
            if meta['search_year'] != "":
                year = meta['year']
            else:
                year = ""
            if meta.get('no_season', False) is True:
                season = ''
            if meta.get('no_year', False) is True:
                year = ''

            if meta['category'] == "TV":
                if meta['tv_pack']:
                    # seasons called series here.
                    tvc_name = f"{meta['title']} ({meta['year'] if 'season_air_first_date' and len(meta['season_air_first_date']) >= 4 else meta['season_air_first_date'][:4]}) Series {meta['season_int']} [{meta['resolution']} {type} {str(meta['video'][-3:]).upper()}]".replace("  ", " ").replace(' () ', ' ')
                else:
                    if 'episode_airdate' in meta:
                        tvc_name = f"{meta['title']} ({year}) {meta['season']}{meta['episode']} ({meta['episode_airdate']}) [{meta['resolution']} {type} {str(meta['video'][-3:]).upper()}]".replace("  ", " ").replace(' () ', ' ')
                    else:
                        tvc_name = f"{meta['title']} ({year}) {meta['season']}{meta['episode']} [{meta['resolution']} {type} {str(meta['video'][-3:]).upper()}]".replace("  ", " ").replace(' () ', ' ')

        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MediaInfo.json", 'r', encoding='utf-8') as f:
            mi = json.load(f)

        if not meta['is_disc']:
            self.get_subs_info(meta, mi)

        if meta['video_codec'] == 'HEVC':
            tvc_name = tvc_name.replace(']', ' HEVC]')

        if 'eng_subs' in meta and meta['eng_subs']:
            tvc_name = tvc_name.replace(']', ' SUBS]')
        if 'sdh_subs' in meta and meta['eng_subs']:
            if 'eng_subs' in meta and meta['eng_subs']:
                tvc_name = tvc_name.replace(' SUBS]', ' (ENG + SDH SUBS)]')
            else:
                tvc_name = tvc_name.replace(']', ' (SDH SUBS)]')

        # appending country code.
        tvc_name = await self.append_country_code(meta, tvc_name)

        if meta.get('unattended', False) is False:
            upload_to_tvc = cli_ui.ask_yes_no(f"Upload to {self.tracker} with the name {tvc_name}?", default=False)

            if not upload_to_tvc:
                tvc_name = cli_ui.ask_string("Please enter New Name:")
                upload_to_tvc = cli_ui.ask_yes_no(f"Upload to {self.tracker} with the name {tvc_name}?", default=False)

        data = {
            'name': tvc_name,
            # newline does not seem to work on this site for some reason. if you edit and save it again they will but not if pushed by api
            'description': desc.replace('\n', '<br>').replace('\r', '<br>'),
            'mediainfo': mi_dump,
            'bdinfo': bd_dump,
            'category_id': cat_id,
            'type': resolution_id,
            # 'resolution_id': resolution_id,
            'tmdb': meta['tmdb'],
            'imdb': meta['imdb'],
            'tvdb': meta['tvdb_id'],
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

        if meta.get('category') == "TV":
            data['season_number'] = meta.get('season_int', '0')
            data['episode_number'] = meta.get('episode_int', '0')
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:53.0) Gecko/20100101 Firefox/53.0'
        }
        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip()
        }
        if 'upload_to_tvc' in locals() and upload_to_tvc is False:
            return

        if meta['debug'] is False:
            response = requests.post(url=self.upload_url, files=files, data=data, headers=headers, params=params)
            try:
                # some reason this does not return json instead it returns something like below.
                # b'application/x-bittorrent\n{"success":true,"data":"https:\\/\\/tvchaosuk.com\\/torrent\\/download\\/164633.REDACTED","message":"Torrent uploaded successfully."}'
                # so you need to convert text to json.
                json_data = json.loads(response.text.strip('application/x-bittorrent\n'))
                meta['tracker_status'][self.tracker]['status_message'] = json_data
                # adding torrent link to comment of torrent file
                t_id = json_data['data'].split(".")[1].split("/")[3]
                meta['tracker_status'][self.tracker]['torrent_id'] = t_id
                await common.add_tracker_torrent(meta, self.tracker, self.source_flag,
                                                 self.config['TRACKERS'][self.tracker].get('announce_url'),
                                                 "https://tvchaosuk.com/torrents/" + t_id)

            except Exception:
                console.print(traceback.print_exc())
                console.print("[yellow]It may have uploaded, go check")
                console.print(response.text.strip('application/x-bittorrent\n'))
                return
        else:
            console.print("[cyan]Request Data:")
            console.print(data)
            meta['tracker_status'][self.tracker]['status_message'] = "Debug mode enabled, not uploading."
        open_torrent.close()

    def get_audio_languages(self, mi):
        """
        Parse MediaInfo object and return a list of normalized audio languages.
        Do NOT mutate meta here; return the languages so the caller can decide.
        """
        audio_langs = set()
        for track in mi.get("media", {}).get("track", []):
            if track.get("@type") == "Audio" and "Language" in track:
                lang = str(track["Language"]).strip()
                if lang:
                    audio_langs.add(lang.title())
        return list(audio_langs) if audio_langs else []

    # why the fuck is this even a thing.....
    async def get_tmdb_data(self, meta):
        import tmdbsimple as tmdb
        if meta['category'] == "MOVIE":
            movie = tmdb.Movies(meta['tmdb'])
            response = movie.info()
        else:
            tv = tmdb.TV(meta['tmdb'])
            response = tv.info()

        # TVC stuff
        if meta['category'] == "TV":
            if hasattr(tv, 'release_dates'):
                meta['release_dates'] = tv.release_dates()

            if hasattr(tv, 'networks') and len(tv.networks) != 0 and 'name' in tv.networks[0]:
                meta['networks'] = tv.networks[0]['name']

        try:
            if 'tv_pack' in meta and not meta['tv_pack']:
                episode_info = tmdb.TV_Episodes(meta['tmdb'], meta['season_int'], meta['episode_int']).info()

                meta['episode_airdate'] = episode_info['air_date']
                meta['episode_name'] = episode_info['name']
                meta['episode_overview'] = episode_info['overview']
            if 'tv_pack' in meta and meta['tv_pack']:
                season_info = tmdb.TV_Seasons(meta['tmdb'], meta['season_int']).info()
                meta['season_air_first_date'] = season_info['air_date']

                if hasattr(tv, 'first_air_date'):
                    meta['first_air_date'] = tv.first_air_date
        except Exception:
            console.print(traceback.print_exc())
            console.print(f"Unable to get episode information, Make sure episode {meta['season']}{meta['episode']} exists in TMDB. \nhttps://www.themoviedb.org/{meta['category'].lower()}/{meta['tmdb']}/season/{meta['season_int']}")
            meta['season_air_first_date'] = str({meta["year"]}) + "-N/A-N/A"
            meta['first_air_date'] = str({meta["year"]}) + "-N/A-N/A"

        meta['origin_country_code'] = []
        if 'origin_country' in response:
            if isinstance(response['origin_country'], list):
                for i in response['origin_country']:
                    meta['origin_country_code'].append(i)
            else:
                meta['origin_country_code'].append(response['origin_country'])
                print(type(response['origin_country']))

        elif len(response['production_countries']):
            for i in response['production_countries']:
                if 'iso_3166_1' in i:
                    meta['origin_country_code'].append(i['iso_3166_1'])
        elif len(response['production_companies']):
            meta['origin_country_code'].append(response['production_companies'][0]['origin_country'])

    async def search_existing(self, meta, disctype):
        # Search on TVCUK has been DISABLED due to issues
        # leaving code here for future use when it is re-enabled
        console.print("[red]Cannot search for dupes as search api is not working...")
        console.print("[red]Please make sure you are not uploading duplicates.")
        # https://tvchaosuk.com/api/torrents/filter?api_token=<API_key>&tmdb=138108

        dupes = []

        # UHD, Discs, remux and non-1080p HEVC are not allowed on TVC.
        if meta['resolution'] == '2160p' or (meta['is_disc'] or "REMUX" in meta['type']) or (meta['video_codec'] == 'HEVC' and meta['resolution'] != '1080p'):
            console.print("[bold red]No UHD, Discs, Remuxes or non-1080p HEVC allowed at TVC[/bold red]")
            meta['skipping'] = "TVC"
            return []

        params = {
            'api_token': self.config['TRACKERS'][self.tracker]['api_key'].strip(),
            'tmdb': meta['tmdb'],
            'name': ""
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url=self.search_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    # 404 catch when their api is down
                    if data['data'] != '404':
                        for each in data['data']:
                            print(each[0]['attributes']['name'])
                            result = each[0]['attributes']['name']
                            dupes.append(result)
                    else:
                        console.print("Search API is down, please check manually")
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

    async def unit3d_edit_desc(self, meta, tracker, signature, screens, comparison=False):
        base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r').read()
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{tracker}]DESCRIPTION.txt", 'w') as descfile:
            bbcode = BBCODE()

            # discs (unchanged logic, tightened spacing)
            if meta.get('discs', []) != []:
                discs = meta['discs']
                if discs[0]['type'] == "DVD":
                    descfile.write(f"[spoiler=VOB MediaInfo][code]{discs[0]['vob_mi']}[/code][/spoiler]\n\n")
                if len(discs) >= 2:
                    for each in discs[1:]:
                        if each['type'] == "BDMV":
                            descfile.write(f"[spoiler={each.get('name', 'BDINFO')}][code]{each['summary']}[/code][/spoiler]\n\n")
                        if each['type'] == "DVD":
                            descfile.write(f"{each['name']}:\n")
                            descfile.write(f"[spoiler={os.path.basename(each['vob'])}][code][{each['vob_mi']}[/code][/spoiler] [spoiler={os.path.basename(each['ifo'])}][code][{each['ifo_mi']}[/code][/spoiler]\n\n")
            desc = ""

            # Release info: collect and format
            rd_info = ""
            if meta['category'] != "TV" and 'release_dates' in meta:
                for cc in meta['release_dates']['results']:
                    for rd in cc['release_dates']:
                        if rd['type'] == 6:
                            channel = str(rd['note']) if str(rd['note']) != "" else "N/A Channel"
                            rd_info += f"[color=orange][size=15]{cc['iso_3166_1']} TV Release info [/size][/color]\n{str(rd['release_date'])[:10]} on {channel}\n"

            if rd_info != "":
                desc += f"[center][color=green][size=25]Release Info[/size][/color]\n\n{rd_info}[/center]\n\n"
            elif meta['category'] == "TV" and meta.get('tv_pack') == 1 and 'season_air_first_date' in meta:
                channel = meta.get('networks', 'N/A')
                desc += f"[center][color=green][size=25]Release Info[/size][/color]\n\n[color=orange][size=15]This season premièred {meta['season_air_first_date']} on  {channel}[/size][/color][/center]\n\n"
            elif meta['category'] == "TV" and meta.get('tv_pack') != 1 and 'episode_airdate' in meta:
                channel = meta.get('networks', 'N/A')
                desc += f"[center][color=green][size=25]Release Info[/size][/color]\n\n[color=orange][size=15]Episode aired on {channel} on {meta['episode_airdate']}[/size][/color][/center]\n\n"
            else:
                desc += "[center][color=green][size=25]Release Info[/size][/color]\n\n[color=orange][size=15]TMDB has No TV release info for this[/size][/color][/center]\n\n"

            # PLOT - improved formatting: bold episode label, sentence-per-line
            if meta['category'] == 'TV' and meta.get('tv_pack') != 1 and 'episode_overview' in meta:
                episode_name = str(meta.get('episode_name', '')).strip()
                overview = str(meta.get('episode_overview', '')).strip()

                # split overview into sentences and write each sentence on its own line
                # simple split using .!? but tolerant to missing punctuation

                sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', overview) if s.strip()]

                desc += "[center][color=green][size=25]PLOT[/size][/color]\n"
                if episode_name:
                    desc += f"[b]Episode Name:[/b] {episode_name}\n\n"
                if sentences:
                    for s in sentences:
                        desc += s.rstrip() + "\n"
                else:
                    # fallback if splitting yields nothing
                    desc += overview + "\n"
                desc += "[/center]\n\n"
            else:
                overview = str(meta.get('overview', '')).strip()
                desc += f"[center][color=green][size=25]PLOT[/size][/color]\n{overview}\n[/center]\n\n"

            # Notes/Extra Info (only if base content exists)
            if base.strip() and meta.get('description', '') != "PTP":
                desc += f"[center][color=green][size=25]Notes/Extra Info[/size][/color]\n\n{base}\n\n[/center]\n\n"

            # Links - improved block (get_links returns a centred block)
            desc += self.get_links(meta, "[color=green][size=25]", "[/size][/COLOR]")

            # bbcode conversions & comparison collapse (preserve behavior)
            desc = bbcode.convert_pre_to_code(desc)
            desc = bbcode.convert_hide_to_spoiler(desc)
            if comparison is False:
                desc = bbcode.convert_comparison_to_collapse(desc, 1000)

            # write description
            descfile.write(desc)

            # Keep screenshots handling exactly as original code did
            images = screens
            if len(images) > 0 and int(meta['screens']) >= self.config['TRACKERS'][self.tracker].get('image_count', 2):
                descfile.write("[color=green][size=25]Screenshots[/size][/color]\n\n[center]")
                for each in range(len(images[:self.config['TRACKERS'][self.tracker]['image_count']])):
                    web_url = images[each]['web_url']
                    img_url = images[each]['img_url']
                    descfile.write(f"[url={web_url}][img=350]{img_url}[/img][/url]")
                descfile.write("[/center]")

            if signature is not None:
                descfile.write(signature)
            descfile.close()
        return

    def get_links(self, movie, subheading, heading_end):
        """
        Builds a centered Links block with a short label and icon links.
        Returns the fully formatted block (including heading end tag).
        """
        parts = []
        parts.append(f"\n\n[center]{subheading}Links{heading_end}\n")
        parts.append("[b]External Info Sources:[/b]\n\n")

        if movie.get('imdb_id', "0") != "0":
            parts.append(f"[URL={movie.get('imdb_info', {}).get('imdb_url', '')}][img]{self.config['IMAGES']['imdb_75']}[/img][/URL] ")

        if movie.get('tmdb', "0") != "0":
            parts.append(f"[URL=https://www.themoviedb.org/{str(movie.get('category', '').lower())}/{str(movie.get('tmdb'))}][img]{self.config['IMAGES']['tmdb_75']}[/img][/URL] ")

        if movie.get('tvdb_id', 0) != 0:
            parts.append(f"[URL=https://www.thetvdb.com/?id={str(movie.get('tvdb_id'))}&tab=series][img]{self.config['IMAGES']['tvdb_75']}[/img][/URL] ")

        if movie.get('tvmaze_id', 0) != 0:
            parts.append(f"[URL=https://www.tvmaze.com/shows/{str(movie.get('tvmaze_id'))}][img]{self.config['IMAGES']['tvmaze_75']}[/img][/URL] ")

        if movie.get('mal_id', 0) != 0:
            parts.append(f"[URL=https://myanimelist.net/anime/{str(movie.get('mal_id'))}][img]{self.config['IMAGES']['mal_75']}[/img][/URL] ")

        parts.append("\n\n[/center]\n\n")
        return "".join(parts)

    # get subs function
    # used in naming conventions

    def get_subs_info(self, meta, mi):
        subs = ""
        subs_num = 0
        for s in mi.get("media").get("track"):
            if s["@type"] == "Text":
                subs_num = subs_num + 1
        if subs_num >= 1:
            meta['has_subs'] = 1
        else:
            meta['has_subs'] = 0
        for s in mi.get("media").get("track"):
            if s["@type"] == "Text":
                if "Language" in s:
                    if not subs_num <= 0:
                        subs = subs + s["Language"] + ", "
                        # checking if it has english subs as for data scene.
                        if str(s["Language"]).lower().__contains__("en"):
                            meta['eng_subs'] = 1
                        if str(s).lower().__contains__("sdh"):
                            meta['sdh_subs'] = 1

        return
