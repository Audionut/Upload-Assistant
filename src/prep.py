# -*- coding: utf-8 -*-
from src.console import console
from src.clients import Clients
from data.config import config
from src.tvmaze import search_tvmaze
from src.imdb import get_imdb_info_api, search_imdb
from src.tmdb import tmdb_other_meta, get_tmdb_imdb_from_mediainfo, get_tmdb_from_imdb, get_tmdb_id
from src.region import get_region, get_distributor, get_service
from src.exportmi import exportInfo, mi_resolution, validate_mediainfo
from src.getseasonep import get_season_episode
from src.get_tracker_data import get_tracker_data, ping_unit3d
from src.bluray_com import get_bluray_releases
from src.metadata_searching import all_ids, imdb_tvdb, imdb_tmdb, get_tv_data, imdb_tmdb_tvdb, get_tvdb_series, get_tvmaze_tvdb
from src.apply_overrides import get_source_override
from src.is_scene import is_scene
from src.audio import get_audio_v2
from src.edition import get_edition
from src.video import get_video_codec, get_video_encode, get_uhd, get_hdr, get_video, get_resolution, get_type, is_3d, is_sd
from src.tags import get_tag, tag_override
from src.get_disc import get_disc, get_dvd_size
from src.get_source import get_source
from src.sonarr import get_sonarr_data
from src.radarr import get_radarr_data
from src.languages import parsed_mediainfo

try:
    import traceback
    import os
    import re
    import asyncio
    from guessit import guessit
    import ntpath
    from pathlib import Path
    import time
    from difflib import SequenceMatcher
except ModuleNotFoundError:
    console.print(traceback.print_exc())
    console.print('[bold red]Missing Module Found. Please reinstall required dependancies.')
    console.print('[yellow]pip3 install --user -U -r requirements.txt')
    exit()
except KeyboardInterrupt:
    exit()


class Prep():
    """
    Prepare for upload:
        Mediainfo/BDInfo
        Screenshots
        Database Identifiers (TMDB/IMDB/MAL/etc)
        Create Name
    """
    def __init__(self, screens, img_host, config):
        self.screens = screens
        self.config = config
        self.img_host = img_host.lower()

    async def gather_prep(self, meta, mode):
        # set some details we'll need
        meta['cutoff'] = int(self.config['DEFAULT'].get('cutoff_screens', 1))
        tvdb_api_get = str(self.config['DEFAULT'].get('tvdb_api', None))
        if tvdb_api_get is None or len(tvdb_api_get) < 20:
            tvdb_api = None
        else:
            tvdb_api = tvdb_api_get
        tvdb_token_get = str(self.config['DEFAULT'].get('tvdb_token', None))
        if tvdb_token_get is None or len(tvdb_token_get) < 20:
            tvdb_token = None
        else:
            tvdb_token = tvdb_token_get
        meta['mode'] = mode
        meta['isdir'] = os.path.isdir(meta['path'])
        base_dir = meta['base_dir']
        meta['saved_description'] = False
        client = Clients(config=config)
        meta['skip_auto_torrent'] = config['DEFAULT'].get('skip_auto_torrent', False)
        hash_ids = ['infohash', 'torrent_hash', 'skip_auto_torrent']
        tracker_ids = ['ptp', 'bhd', 'btn', 'blu', 'aither', 'lst', 'oe', 'hdb', 'huno']
        use_sonarr = config['DEFAULT'].get('use_sonarr', False)
        use_radarr = config['DEFAULT'].get('use_radarr', False)
        meta['print_tracker_messages'] = config['DEFAULT'].get('print_tracker_messages', False)
        meta['print_tracker_links'] = config['DEFAULT'].get('print_tracker_links', True)

        # make sure these are set in meta
        meta['we_checked_tvdb'] = False
        meta['we_checked_tmdb'] = False
        meta['we_asked_tvmaze'] = False
        meta['audio_languages'] = None
        meta['subtitle_languages'] = None

        folder_id = os.path.basename(meta['path'])
        if meta.get('uuid', None) is None:
            meta['uuid'] = folder_id
        if not os.path.exists(f"{base_dir}/tmp/{meta['uuid']}"):
            Path(f"{base_dir}/tmp/{meta['uuid']}").mkdir(parents=True, exist_ok=True)

        if meta['debug']:
            console.print(f"[cyan]ID: {meta['uuid']}")

        meta['is_disc'], videoloc, bdinfo, meta['discs'] = await get_disc(meta)

        # Debugging information
        # console.print(f"Debug: meta['filelist'] before population: {meta.get('filelist', 'Not Set')}")

        if meta['is_disc'] == "BDMV":
            video, meta['scene'], meta['imdb_id'] = await is_scene(meta['path'], meta, meta.get('imdb_id', 0))
            meta['filelist'] = []  # No filelist for discs, use path
            search_term = os.path.basename(meta['path'])
            search_file_folder = 'folder'
            try:
                guess_name = bdinfo['title'].replace('-', ' ')
                filename = guessit(re.sub(r"[^0-9a-zA-Z\[\\]]+", " ", guess_name), {"excludes": ["country", "language"]})['title']
                untouched_filename = bdinfo['title']
                try:
                    meta['search_year'] = guessit(bdinfo['title'])['year']
                except Exception:
                    meta['search_year'] = ""
            except Exception:
                guess_name = bdinfo['label'].replace('-', ' ')
                filename = guessit(re.sub(r"[^0-9a-zA-Z\[\\]]+", " ", guess_name), {"excludes": ["country", "language"]})['title']
                untouched_filename = bdinfo['label']
                try:
                    meta['search_year'] = guessit(bdinfo['label'])['year']
                except Exception:
                    meta['search_year'] = ""

            if meta.get('resolution', None) is None:
                meta['resolution'] = await mi_resolution(bdinfo['video'][0]['res'], guessit(video), width="OTHER", scan="p", height="OTHER", actual_height=0)
                try:
                    is_hfr = bdinfo['video'][0]['fps'].split()[0] if bdinfo['video'] else "25"
                    if int(float(is_hfr)) > 30:
                        meta['hfr'] = True
                    else:
                        meta['hfr'] = False
                except Exception:
                    meta['hfr'] = False

            meta['sd'] = await is_sd(meta['resolution'])

            mi = None

        elif meta['is_disc'] == "DVD":
            video, meta['scene'], meta['imdb_id'] = await is_scene(meta['path'], meta, meta.get('imdb_id', 0))
            meta['filelist'] = []
            search_term = os.path.basename(meta['path'])
            search_file_folder = 'folder'
            guess_name = meta['discs'][0]['path'].replace('-', ' ')
            filename = guessit(guess_name, {"excludes": ["country", "language"]})['title']
            untouched_filename = os.path.basename(os.path.dirname(meta['discs'][0]['path']))
            try:
                meta['search_year'] = guessit(meta['discs'][0]['path'])['year']
            except Exception:
                meta['search_year'] = ""
            if not meta.get('edit', False):
                mi = await exportInfo(f"{meta['discs'][0]['path']}/VTS_{meta['discs'][0]['main_set'][0][:2]}_1.VOB", False, meta['uuid'], meta['base_dir'], export_text=False, is_dvd=True, debug=meta['debug'])
                meta['mediainfo'] = mi
            else:
                mi = meta['mediainfo']

            meta['dvd_size'] = await get_dvd_size(meta['discs'], meta.get('manual_dvds'))
            meta['resolution'], meta['hfr'] = await get_resolution(guessit(video), meta['uuid'], base_dir)
            meta['sd'] = await is_sd(meta['resolution'])

        elif meta['is_disc'] == "HDDVD":
            video, meta['scene'], meta['imdb_id'] = await is_scene(meta['path'], meta, meta.get('imdb_id', 0))
            meta['filelist'] = []
            search_term = os.path.basename(meta['path'])
            search_file_folder = 'folder'
            guess_name = meta['discs'][0]['path'].replace('-', '')
            filename = guessit(guess_name, {"excludes": ["country", "language"]})['title']
            untouched_filename = os.path.basename(meta['discs'][0]['path'])
            videopath = meta['discs'][0]['largest_evo']
            try:
                meta['search_year'] = guessit(meta['discs'][0]['path'])['year']
            except Exception:
                meta['search_year'] = ""
            if not meta.get('edit', False):
                mi = await exportInfo(meta['discs'][0]['largest_evo'], False, meta['uuid'], meta['base_dir'], export_text=False, debug=meta['debug'])
                meta['mediainfo'] = mi
            else:
                mi = meta['mediainfo']
            meta['resolution'], meta['hfr'] = await get_resolution(guessit(video), meta['uuid'], base_dir)
            meta['sd'] = await is_sd(meta['resolution'])

        else:
            # handle some specific cases that trouble guessit and then id grabbing
            def extract_title_and_year(filename):
                basename = os.path.basename(filename)
                basename = os.path.splitext(basename)[0]

                secondary_title = None
                year = None

                # Check for AKA patterns first
                aka_patterns = [' AKA ', '.aka.', ' aka ', '.AKA.']
                for pattern in aka_patterns:
                    if pattern in basename:
                        aka_parts = basename.split(pattern, 1)
                        if len(aka_parts) > 1:
                            primary_title = aka_parts[0].strip()
                            secondary_part = aka_parts[1].strip()

                            # Look for a year in the primary title
                            year_match_primary = re.search(r'\b(19|20)\d{2}\b', primary_title)
                            if year_match_primary:
                                year = year_match_primary.group(0)

                            # Process secondary title
                            secondary_match = re.match(r"^(\d+)", secondary_part)
                            if secondary_match:
                                secondary_title = secondary_match.group(1)
                            else:
                                # Catch everything after AKA until it hits a year or release info
                                year_or_release_match = re.search(r'\b(19|20)\d{2}\b|\bBluRay\b|\bREMUX\b|\b\d+p\b|\bDTS-HD\b|\bAVC\b', secondary_part)
                                if year_or_release_match:
                                    # Check if we found a year in the secondary part
                                    if re.match(r'\b(19|20)\d{2}\b', year_or_release_match.group(0)):
                                        # If no year was found in primary title, or we want to override
                                        if not year:
                                            year = year_or_release_match.group(0)

                                    secondary_title = secondary_part[:year_or_release_match.start()].strip()
                                else:
                                    secondary_title = secondary_part

                            primary_title = primary_title.replace('.', ' ')
                            secondary_title = secondary_title.replace('.', ' ')
                            return primary_title, secondary_title, year

                # if not AKA, catch titles that begin with a year
                year_start_match = re.match(r'^(19|20)\d{2}', basename)
                if year_start_match:
                    title = year_start_match.group(0)
                    rest = basename[len(title):].lstrip('. _-')
                    # Look for another year in the rest of the title
                    year_match = re.search(r'\b(19|20)\d{2}\b', rest)
                    year = year_match.group(0) if year_match else None
                    return title, None, year

                # If no pattern match works but there's still a year in the filename, extract it
                year_match = re.search(r'(?<!\d)(19|20)\d{2}(?!\d)', basename)
                if year_match:
                    year = year_match.group(0)
                    return None, None, year

                return None, None, None

            videopath, meta['filelist'] = await get_video(videoloc, meta.get('mode', 'discord'))
            search_term = os.path.basename(meta['filelist'][0]) if meta['filelist'] else None
            search_file_folder = 'file'

            video, meta['scene'], meta['imdb_id'] = await is_scene(videopath, meta, meta.get('imdb_id', 0))

            title, secondary_title, extracted_year = extract_title_and_year(video)
            if meta['debug']:
                console.print(f"Title: {title}, Secondary Title: {secondary_title}, Year: {extracted_year}")
            if secondary_title:
                meta['secondary_title'] = secondary_title
            if extracted_year and not meta.get('year'):
                meta['year'] = extracted_year

            if meta.get('isdir', False):
                guess_name = os.path.basename(meta['path']).replace("_", "").replace("-", "") if meta['path'] else ""
            else:
                guess_name = ntpath.basename(video).replace('-', ' ')

            if title:
                filename = title
            else:
                filename = guessit(re.sub(r"[^0-9a-zA-Z\[\\]]+", " ", guess_name), {"excludes": ["country", "language"]}).get("title", guessit(re.sub("[^0-9a-zA-Z]+", " ", guess_name), {"excludes": ["country", "language"]})["title"])
            untouched_filename = os.path.basename(video)

            # rely only on guessit for search_year for tv matching
            try:
                meta['search_year'] = guessit(video)['year']
            except Exception:
                meta['search_year'] = ""

            if not meta.get('edit', False):
                mi = await exportInfo(videopath, meta['isdir'], meta['uuid'], base_dir, export_text=True)
                meta['mediainfo'] = mi
            else:
                mi = meta['mediainfo']

            if meta.get('resolution', None) is None:
                meta['resolution'], meta['hfr'] = await get_resolution(guessit(video), meta['uuid'], base_dir)

            meta['sd'] = await is_sd(meta['resolution'])

        if " AKA " in filename.replace('.', ' '):
            filename = filename.split('AKA')[0]
        meta['filename'] = filename
        meta['bdinfo'] = bdinfo

        meta['valid_mi'] = True
        if not meta['is_disc']:
            valid_mi = validate_mediainfo(base_dir, folder_id, path=meta['path'], filelist=meta['filelist'], debug=meta['debug'])
            if not valid_mi:
                console.print("[red]MediaInfo validation failed. This file does not contain (Unique ID).")
                meta['valid_mi'] = False
                await asyncio.sleep(2)

        # Check if there's a language restriction
        if meta['has_languages'] is not None:
            try:
                audio_languages = []
                parsed_info = await parsed_mediainfo(meta)
                for audio_track in parsed_info.get('audio', []):
                    if 'language' in audio_track and audio_track['language']:
                        audio_languages.append(audio_track['language'].lower())
                any_of_languages = meta['has_languages'].lower().split(",")
                if all(len(lang.strip()) == 2 for lang in any_of_languages):
                    raise Exception(f"Warning: Languages should be full names, not ISO codes. Found: {any_of_languages}")
                # We need to have user input languages and file must have audio tracks.
                if len(any_of_languages) > 0 and len(audio_languages) > 0 and not set(any_of_languages).intersection(set(audio_languages)):
                    console.print(f"[red] None of the required languages ({meta['has_languages']}) is available on the file {audio_languages}")
                    raise Exception("No matching languages")
            except Exception as e:
                console.print(f"[red]Error checking languages: {e}")

        if 'description' not in meta or meta.get('description') is None:
            meta['description'] = ""

        description_text = meta.get('description', '')
        if description_text is None:
            description_text = ""
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'w', newline="", encoding='utf8') as description:
            if len(description_text):
                description.write(description_text)

        # auto torrent searching with qbittorrent that grabs torrent ids for metadata searching
        if not any(meta.get(id_type) for id_type in hash_ids + tracker_ids):
            await client.get_pathed_torrents(meta['path'], meta)

        # Ensure all manual IDs have proper default values
        meta['tmdb_manual'] = meta.get('tmdb_manual') or 0
        meta['imdb_manual'] = meta.get('imdb_manual') or 0
        meta['mal_manual'] = meta.get('mal_manual') or 0
        meta['tvdb_manual'] = meta.get('tvdb_manual') or 0
        meta['tvmaze_manual'] = meta.get('tvmaze_manual') or 0

        # Set tmdb_id
        try:
            meta['tmdb_id'] = int(meta['tmdb_manual'])
        except (ValueError, TypeError):
            meta['tmdb_id'] = 0

        # Set imdb_id with proper handling for 'tt' prefix
        try:
            if not meta.get('imdb_id'):
                imdb_value = meta['imdb_manual']
                if imdb_value:
                    if str(imdb_value).startswith('tt'):
                        meta['imdb_id'] = int(str(imdb_value)[2:])
                    else:
                        meta['imdb_id'] = int(imdb_value)
                else:
                    meta['imdb_id'] = 0
        except (ValueError, TypeError):
            meta['imdb_id'] = 0

        # Set mal_id
        try:
            meta['mal_id'] = int(meta['mal_manual'])
        except (ValueError, TypeError):
            meta['mal_id'] = 0

        # Set tvdb_id
        try:
            meta['tvdb_id'] = int(meta['tvdb_manual'])
        except (ValueError, TypeError):
            meta['tvdb_id'] = 0

        try:
            meta['tvmaze_id'] = int(meta['tvmaze_manual'])
        except (ValueError, TypeError):
            meta['tvmaze_id'] = 0

        if not meta.get('category', None):
            meta['category'] = await self.get_cat(video, meta)
        else:
            meta['category'] = meta['category'].upper()

        ids = None
        if meta.get('category', None) == "TV" and use_sonarr and meta.get('tvdb_id', 0) == 0:
            ids = await get_sonarr_data(filename=meta.get('path', ''), title=meta.get('filename', None), debug=meta.get('debug', False))
            if ids:
                if meta['debug']:
                    console.print(f"TVDB ID: {ids['tvdb_id']}")
                    console.print(f"IMDB ID: {ids['imdb_id']}")
                    console.print(f"TVMAZE ID: {ids['tvmaze_id']}")
                    console.print(f"TMDB ID: {ids['tmdb_id']}")
                    console.print(f"Genres: {ids['genres']}")
                    console.print(f"Release Group: {ids['release_group']}")
                    console.print(f"Year: {ids['year']}")
                if 'anime' not in [genre.lower() for genre in ids['genres']]:
                    meta['not_anime'] = True
                if meta.get('tvdb_id', 0) == 0 and ids['tvdb_id'] is not None:
                    meta['tvdb_id'] = ids['tvdb_id']
                if meta.get('imdb_id', 0) == 0 and ids['imdb_id'] is not None:
                    meta['imdb_id'] = ids['imdb_id']
                if meta.get('tvmaze_id', 0) == 0 and ids['tvmaze_id'] is not None:
                    meta['tvmaze_id'] = ids['tvmaze_id']
                if meta.get('tmdb_id', 0) == 0 and ids['tmdb_id'] is not None:
                    meta['tmdb_id'] = ids['tmdb_id']
                if meta.get('tag', None) is None:
                    meta['tag'] = ids['release_group']
                if meta.get('manual_year', 0) == 0 and ids['year'] is not None:
                    meta['manual_year'] = ids['year']
            else:
                ids = None

        if meta.get('category', None) == "MOVIE" and use_radarr and meta.get('tmdb_id', 0) == 0:
            ids = await get_radarr_data(filename=meta.get('uuid', ''), debug=meta.get('debug', False))
            if ids:
                if meta['debug']:
                    console.print(f"IMDB ID: {ids['imdb_id']}")
                    console.print(f"TMDB ID: {ids['tmdb_id']}")
                    console.print(f"Genres: {ids['genres']}")
                    console.print(f"Year: {ids['year']}")
                    console.print(f"Release Group: {ids['release_group']}")
                if meta.get('imdb_id', 0) == 0 and ids['imdb_id'] is not None:
                    meta['imdb_id'] = ids['imdb_id']
                if meta.get('tmdb_id', 0) == 0 and ids['tmdb_id'] is not None:
                    meta['tmdb_id'] = ids['tmdb_id']
                if meta.get('manual_year', 0) == 0 and ids['year'] is not None:
                    meta['manual_year'] = ids['year']
                if meta.get('tag', None) is None:
                    meta['tag'] = ids['release_group']
            else:
                ids = None

        # check if we've already searched torrents
        if 'base_torrent_created' not in meta:
            meta['base_torrent_created'] = False
        if 'we_checked_them_all' not in meta:
            meta['we_checked_them_all'] = False

        # if not auto qbittorrent search, this also checks with the infohash if passed.
        if meta.get('infohash') is not None and not meta['base_torrent_created'] and not meta['we_checked_them_all'] and not ids:
            meta = await client.get_ptp_from_hash(meta)

        if not meta.get('image_list') and not meta.get('edit', False) and not ids:
            # Reuse information from trackers with fallback
            await get_tracker_data(video, meta, search_term, search_file_folder, meta['category'])

        if meta.get('category', None) == "TV" and use_sonarr and meta.get('tvdb_id', 0) != 0 and ids is None and not meta.get('matched_tracker', None):
            ids = await get_sonarr_data(tvdb_id=meta.get('tvdb_id', 0), debug=meta.get('debug', False))
            if ids:
                if meta['debug']:
                    console.print(f"TVDB ID: {ids['tvdb_id']}")
                    console.print(f"IMDB ID: {ids['imdb_id']}")
                    console.print(f"TVMAZE ID: {ids['tvmaze_id']}")
                    console.print(f"TMDB ID: {ids['tmdb_id']}")
                    console.print(f"Genres: {ids['genres']}")
                if 'anime' not in [genre.lower() for genre in ids['genres']]:
                    meta['not_anime'] = True
                if meta.get('tvdb_id', 0) == 0 and ids['tvdb_id'] is not None:
                    meta['tvdb_id'] = ids['tvdb_id']
                if meta.get('imdb_id', 0) == 0 and ids['imdb_id'] is not None:
                    meta['imdb_id'] = ids['imdb_id']
                if meta.get('tvmaze_id', 0) == 0 and ids['tvmaze_id'] is not None:
                    meta['tvmaze_id'] = ids['tvmaze_id']
                if meta.get('tmdb_id', 0) == 0 and ids['tmdb_id'] is not None:
                    meta['tmdb_id'] = ids['tmdb_id']
                if meta.get('tag', None) is None:
                    meta['tag'] = ids['release_group']
                if meta.get('manual_year', 0) == 0 and ids['year'] is not None:
                    meta['manual_year'] = ids['year']
            else:
                ids = None

        if meta.get('category', None) == "MOVIE" and use_radarr and meta.get('tmdb_id', 0) != 0 and ids is None and not meta.get('matched_tracker', None):
            ids = await get_radarr_data(tmdb_id=meta.get('tmdb_id', 0), debug=meta.get('debug', False))
            if ids:
                if meta['debug']:
                    console.print(f"IMDB ID: {ids['imdb_id']}")
                    console.print(f"TMDB ID: {ids['tmdb_id']}")
                    console.print(f"Genres: {ids['genres']}")
                    console.print(f"Year: {ids['year']}")
                    console.print(f"Release Group: {ids['release_group']}")
                if meta.get('imdb_id', 0) == 0 and ids['imdb_id'] is not None:
                    meta['imdb_id'] = ids['imdb_id']
                if meta.get('tmdb_id', 0) == 0 and ids['tmdb_id'] is not None:
                    meta['tmdb_id'] = ids['tmdb_id']
                if meta.get('manual_year', 0) == 0 and ids['year'] is not None:
                    meta['manual_year'] = ids['year']
                if meta.get('tag', None) is None:
                    meta['tag'] = ids['release_group']
            else:
                ids = None

        # if there's no region/distributor info, lets ping some unit3d trackers and see if we get it
        ping_unit3d_config = self.config['DEFAULT'].get('ping_unit3d', False)
        if (not meta.get('region') or not meta.get('distributor')) and meta['is_disc'] == "BDMV" and ping_unit3d_config and not meta.get('edit', False):
            await ping_unit3d(meta)

        # the first user override check that allows to set metadata ids.
        # it relies on imdb or tvdb already being set.
        user_overrides = config['DEFAULT'].get('user_overrides', False)
        if user_overrides and (meta.get('imdb_id') != 0 or meta.get('tvdb_id') != 0):
            meta = await get_source_override(meta, other_id=True)
            meta['category'] = meta.get('category', None).upper()
            # set a flag so that the other check later doesn't run
            meta['no_override'] = True

        if meta['debug']:
            console.print("ID inputs into prep")
            console.print("category:", meta.get("category"))
            console.print(f"Raw TVDB ID: {meta['tvdb_id']} (type: {type(meta['tvdb_id']).__name__})")
            console.print(f"Raw IMDb ID: {meta['imdb_id']} (type: {type(meta['imdb_id']).__name__})")
            console.print(f"Raw TMDb ID: {meta['tmdb_id']} (type: {type(meta['tmdb_id']).__name__})")
            console.print(f"Raw TVMAZE ID: {meta['tvmaze_id']} (type: {type(meta['tvmaze_id']).__name__})")
            console.print(f"Raw MAL ID: {meta['mal_id']} (type: {type(meta['mal_id']).__name__})")

        console.print("[yellow]Building meta data.....")

        # set a timer to check speed
        if meta['debug']:
            meta_start_time = time.time()

        if meta.get('manual_language'):
            meta['original_langauge'] = meta.get('manual_language').lower()

        meta['type'] = await get_type(video, meta['scene'], meta['is_disc'], meta)

        # if it's not an anime, we can run season/episode checks now to speed the process
        if meta.get("not_anime", False) and meta.get("category") == "TV":
            meta = await get_season_episode(video, meta)

        # Run a check against mediainfo to see if it has tmdb/imdb
        if (meta.get('tmdb_id') == 0 or meta.get('imdb_id') == 0):
            meta['category'], meta['tmdb_id'], meta['imdb_id'] = await get_tmdb_imdb_from_mediainfo(
                mi, meta['category'], meta['is_disc'], meta['tmdb_id'], meta['imdb_id']
            )

        # run a search to find tmdb and imdb ids if we don't have them
        if meta.get('tmdb_id') == 0 and meta.get('imdb_id') == 0:
            if meta.get('category') == "TV":
                year = meta.get('manual_year', '') or meta.get('search_year', '') or meta.get('year', '')
            else:
                year = meta.get('manual_year', '') or meta.get('year', '') or meta.get('search_year', '')
            tmdb_task = get_tmdb_id(filename, year, meta.get('category', None), untouched_filename, attempted=0, debug=meta['debug'], secondary_title=meta.get('secondary_title', None), path=meta.get('path', None))
            imdb_task = search_imdb(filename, year, quickie=True, category=meta.get('category', None), debug=meta['debug'], secondary_title=meta.get('secondary_title', None), path=meta.get('path', None))
            tmdb_result, imdb_result = await asyncio.gather(tmdb_task, imdb_task)
            tmdb_id, category = tmdb_result
            meta['category'] = category
            meta['tmdb_id'] = int(tmdb_id)
            meta['imdb_id'] = int(imdb_result)
            meta['quickie_search'] = True

        # If we have an IMDb ID but no TMDb ID, fetch TMDb ID from IMDb
        elif meta.get('imdb_id') != 0 and meta.get('tmdb_id') == 0:
            category, tmdb_id, original_language = await get_tmdb_from_imdb(
                meta['imdb_id'],
                meta.get('tvdb_id'),
                meta.get('search_year'),
                filename,
                debug=meta.get('debug', False),
                mode=meta.get('mode', 'discord'),
                category_preference=meta.get('category'),
                imdb_info=meta.get('imdb_info', None)
                )

            meta['category'] = category
            meta['tmdb_id'] = int(tmdb_id)
            meta['original_language'] = original_language

        # if we have all of the ids, search everything all at once
        if int(meta['imdb_id']) != 0 and int(meta['tvdb_id']) != 0 and int(meta['tmdb_id']) != 0 and int(meta['tvmaze_id']) != 0:
            meta = await all_ids(meta, tvdb_api, tvdb_token)

        # Check if IMDb, TMDb, and TVDb IDs are all present
        elif int(meta['imdb_id']) != 0 and int(meta['tvdb_id']) != 0 and int(meta['tmdb_id']) != 0 and not meta.get('quickie_search', False):
            meta = await imdb_tmdb_tvdb(meta, filename, tvdb_api, tvdb_token)

        # Check if both IMDb and TVDB IDs are present
        elif int(meta['imdb_id']) != 0 and int(meta['tvdb_id']) != 0 and not meta.get('quickie_search', False):
            meta = await imdb_tvdb(meta, filename, tvdb_api, tvdb_token)

        # Check if both IMDb and TMDb IDs are present
        elif int(meta['imdb_id']) != 0 and int(meta['tmdb_id']) != 0 and not meta.get('quickie_search', False):
            meta = await imdb_tmdb(meta, filename)

        # we have tmdb id one way or another, so lets get data if needed
        if int(meta['tmdb_id']) != 0:
            if not meta.get('edit', False):
                # if we have these fields already, we probably got them from a multi id searching
                # and don't need to fetch them again
                essential_fields = ['title', 'year', 'genres', 'overview']
                tmdb_metadata_populated = all(meta.get(field) is not None for field in essential_fields)
            else:
                # if we're in that blastard edit mode, ignore any previous set data and get fresh
                tmdb_metadata_populated = False

            if not tmdb_metadata_populated:
                max_attempts = 2
                delay_seconds = 5
                for attempt in range(1, max_attempts + 1):
                    try:
                        tmdb_metadata = await tmdb_other_meta(
                            tmdb_id=meta['tmdb_id'],
                            path=meta.get('path'),
                            search_year=meta.get('search_year'),
                            category=meta.get('category'),
                            imdb_id=meta.get('imdb_id', 0),
                            manual_language=meta.get('manual_language'),
                            anime=meta.get('anime', False),
                            mal_manual=meta.get('mal_manual'),
                            aka=meta.get('aka', ''),
                            original_language=meta.get('original_language'),
                            poster=meta.get('poster'),
                            debug=meta.get('debug', False),
                            mode=meta.get('mode', 'cli'),
                            tvdb_id=meta.get('tvdb_id', 0),
                            quickie_search=meta.get('quickie_search', False),
                        )

                        if tmdb_metadata and all(tmdb_metadata.get(field) for field in ['title', 'year']):
                            meta.update(tmdb_metadata)
                            break  # Success, exit loop
                        else:
                            error_msg = f"Failed to retrieve essential metadata from TMDB ID: {meta['tmdb_id']}"
                            console.print(f"[bold red]{error_msg}[/bold red]")
                            if attempt < max_attempts:
                                console.print(f"[yellow]Retrying TMDB metadata fetch in {delay_seconds} seconds... (Attempt {attempt + 1}/{max_attempts})[/yellow]")
                                await asyncio.sleep(delay_seconds)
                            else:
                                raise ValueError(error_msg)
                    except Exception as e:
                        error_msg = f"TMDB metadata retrieval failed for ID {meta['tmdb_id']}: {str(e)}"
                        console.print(f"[bold red]{error_msg}[/bold red]")
                        if attempt < max_attempts:
                            console.print(f"[yellow]Retrying TMDB metadata fetch in {delay_seconds} seconds... (Attempt {attempt + 1}/{max_attempts})[/yellow]")
                            await asyncio.sleep(delay_seconds)
                        else:
                            raise RuntimeError(error_msg) from e

        if meta.get('retrieved_aka', None) is not None:
            meta['aka'] = meta['retrieved_aka']

        # If there's a mismatch between IMDb and TMDb IDs, try to resolve it
        if meta.get('imdb_mismatch', False):
            if meta['debug']:
                console.print("[yellow]IMDb ID mismatch detected, attempting to resolve...[/yellow]")
            # if there's a secondary title, TMDb is probably correct
            if meta.get('secondary_title', None):
                meta['imdb_id'] = 0
                meta['imdb_info'] = None
            # Otherwise, IMDb used some other regex and we'll trust it more than guessit
            else:
                category, tmdb_id, original_language = await get_tmdb_from_imdb(
                    meta['imdb_id'],
                    meta.get('tvdb_id'),
                    meta.get('search_year'),
                    filename,
                    debug=meta.get('debug', False),
                    mode=meta.get('mode', 'discord'),
                    category_preference=meta.get('category'),
                    imdb_info=meta.get('imdb_info', None)
                )

                meta['category'] = category
                meta['tmdb_id'] = int(tmdb_id)
                meta['original_language'] = original_language

                try:
                    tmdb_metadata = await tmdb_other_meta(
                        tmdb_id=meta['tmdb_id'],
                        path=meta.get('path'),
                        search_year=meta.get('search_year'),
                        category=meta.get('category'),
                        imdb_id=meta.get('imdb_id', 0),
                        manual_language=meta.get('manual_language'),
                        anime=meta.get('anime', False),
                        mal_manual=meta.get('mal_manual'),
                        aka=meta.get('aka', ''),
                        original_language=meta.get('original_language'),
                        poster=meta.get('poster'),
                        debug=meta.get('debug', False),
                        mode=meta.get('mode', 'cli'),
                        tvdb_id=meta.get('tvdb_id', 0),
                        quickie_search=meta.get('quickie_search', False),
                    )

                    if not tmdb_metadata or not all(tmdb_metadata.get(field) for field in ['title', 'year']):
                        error_msg = f"Failed to retrieve essential metadata from TMDB ID: {meta['tmdb_id']}"
                        console.print(f"[bold red]{error_msg}[/bold red]")
                        raise ValueError(error_msg)

                    meta.update(tmdb_metadata)

                except Exception as e:
                    error_msg = f"TMDB metadata retrieval failed for ID {meta['tmdb_id']}: {str(e)}"
                    console.print(f"[bold red]{error_msg}[/bold red]")
                    raise RuntimeError(error_msg) from e

        # Get IMDb ID if not set
        if meta.get('imdb_id') == 0:
            meta['imdb_id'] = await search_imdb(filename, meta['search_year'], quickie=False, category=meta.get('category', None), debug=meta.get('debug', False))

        # Ensure IMDb info is retrieved if it wasn't already fetched
        if meta.get('imdb_info', None) is None and int(meta['imdb_id']) != 0:
            imdb_info = await get_imdb_info_api(meta['imdb_id'], manual_language=meta.get('manual_language'), debug=meta.get('debug', False))
            meta['imdb_info'] = imdb_info
            meta['tv_year'] = imdb_info.get('tv_year', None)
        check_valid_data = meta.get('imdb_info', {}).get('title', "")
        if check_valid_data:
            aka = meta.get('imdb_info', {}).get('aka', "").strip()
            title = meta.get('imdb_info', {}).get('title', "").strip().lower()
            year = str(meta.get('imdb_info', {}).get('year', ""))

            if aka and not meta.get('aka'):
                aka_trimmed = aka[4:].strip().lower() if aka.lower().startswith("aka") else aka.lower()
                difference = SequenceMatcher(None, title, aka_trimmed).ratio()
                if difference >= 0.7 or not aka_trimmed or aka_trimmed in title:
                    aka = None

                if aka is not None:
                    if f"({year})" in aka:
                        aka = aka.replace(f"({year})", "").strip()
                    meta['aka'] = f"AKA {aka.strip()}"
                    meta['title'] = f"{meta.get('imdb_info', {}).get('title', '').strip()}"

        if meta.get('aka', None) is None:
            meta['aka'] = ""

        if meta['category'] == "TV":
            if meta.get('tvmaze_id', 0) == 0 and meta.get('tvdb_id', 0) == 0:
                await get_tvmaze_tvdb(meta, filename, tvdb_api, tvdb_token)
            elif meta.get('tvmaze_id', 0) == 0:
                meta['tvmaze_id'], meta['imdb_id'], meta['tvdb_id'] = await search_tvmaze(
                    filename, meta['search_year'], meta.get('imdb_id', 0), meta.get('tvdb_id', 0),
                    manual_date=meta.get('manual_date'),
                    tvmaze_manual=meta.get('tvmaze_manual'),
                    debug=meta.get('debug', False),
                    return_full_tuple=True
                )
            else:
                meta.setdefault('tvmaze_id', 0)
            if meta.get('tvdb_id', 0) == 0 and tvdb_api and tvdb_token:
                meta['tvdb_id'] = await get_tvdb_series(base_dir, title=meta.get('title', ''), year=meta.get('year', ''), apikey=tvdb_api, token=tvdb_token, debug=meta.get('debug', False))

            # if it was skipped earlier, make sure we have the season/episode data
            if not meta.get('not_anime', False):
                meta = await get_season_episode(video, meta)
            # all your episode data belongs to us
            meta = await get_tv_data(meta, base_dir, tvdb_api, tvdb_token)

        # if we're using tvdb, lets use it's series name if it applies
        # language check since tvdb returns original language names
        if tvdb_api and tvdb_token and meta.get('original_language', "") == "en":
            if meta.get('tvdb_episode_data') and meta.get('tvdb_episode_data').get('series_name') != "" and meta.get('title') != meta.get('tvdb_episode_data').get('series_name'):
                series_name = meta.get('tvdb_episode_data').get('series_name', '')
                if meta['debug']:
                    console.print(f"[yellow]tvdb series name: {series_name}")
                year_match = re.search(r'\b(19|20)\d{2}\b', series_name)
                if year_match:
                    extracted_year = year_match.group(0)
                    meta['search_year'] = extracted_year
                    series_name = re.sub(r'\s*\b(19|20)\d{2}\b\s*', '', series_name).strip()
                series_name = series_name.replace('(', '').replace(')', '').strip()
                meta['title'] = series_name
            elif meta.get('tvdb_series_name') and meta.get('tvdb_series_name') != "" and meta.get('title') != meta.get('tvdb_series_name'):
                series_name = meta.get('tvdb_series_name')
                if meta['debug']:
                    console.print(f"[yellow]tvdb series name: {series_name}")
                year_match = re.search(r'\b(19|20)\d{2}\b', series_name)
                if year_match:
                    extracted_year = year_match.group(0)
                    meta['search_year'] = extracted_year
                    series_name = re.sub(r'\s*\b(19|20)\d{2}\b\s*', '', series_name).strip()
                series_name = series_name.replace('(', '').replace(')', '').strip()
                meta['title'] = series_name

        # bluray.com data if config
        get_bluray_info = self.config['DEFAULT'].get('get_bluray_info', False)
        meta['bluray_score'] = int(float(self.config['DEFAULT'].get('bluray_score', 100)))
        meta['bluray_single_score'] = int(float(self.config['DEFAULT'].get('bluray_single_score', 100)))
        meta['use_bluray_images'] = self.config['DEFAULT'].get('use_bluray_images', False)
        if meta.get('is_disc') == "BDMV" and get_bluray_info and (meta.get('distributor') is None or meta.get('region') is None) and meta.get('imdb_id') != 0:
            await get_bluray_releases(meta)

        # and if we getting bluray images, we'll rehost them
        if meta.get('is_disc') == "BDMV" and meta.get('use_bluray_images', False):
            from src.rehostimages import check_hosts
            url_host_mapping = {
                "ibb.co": "imgbb",
                "pixhost.to": "pixhost",
                "imgbox.com": "imgbox",
            }

            approved_image_hosts = ['imgbox', 'imgbb', 'pixhost']
            await check_hosts(meta, "covers", url_host_mapping=url_host_mapping, img_host_index=1, approved_image_hosts=approved_image_hosts)

        # user override check that only sets data after metadata setting
        if user_overrides and not meta.get('no_override', False):
            meta = await get_source_override(meta)

        if meta.get('tag') == "-SubsPlease":  # SubsPlease-specific
            tracks = meta.get('mediainfo', {}).get('media', {}).get('track', [])  # Get all tracks
            bitrate = tracks[1].get('BitRate', '') if len(tracks) > 1 and not isinstance(tracks[1].get('BitRate', ''), dict) else ''  # Check that bitrate is not a dict
            bitrate_oldMediaInfo = tracks[0].get('OverallBitRate', '') if len(tracks) > 0 and not isinstance(tracks[0].get('OverallBitRate', ''), dict) else ''  # Check for old MediaInfo
            meta['episode_title'] = ""
            if (bitrate.isdigit() and int(bitrate) >= 8000000) or (bitrate_oldMediaInfo.isdigit() and int(bitrate_oldMediaInfo) >= 8000000) and meta.get('resolution') == "1080p":  # 8Mbps for 1080p
                meta['service'] = "CR"
            elif (bitrate.isdigit() or bitrate_oldMediaInfo.isdigit()) and meta.get('resolution') == "1080p":  # Only assign if at least one bitrate is present, otherwise leave it to user
                meta['service'] = "HIDI"
            elif (bitrate.isdigit() and int(bitrate) >= 4000000) or (bitrate_oldMediaInfo.isdigit() and int(bitrate_oldMediaInfo) >= 4000000) and meta.get('resolution') == "720p":  # 4Mbps for 720p
                meta['service'] = "CR"
            elif (bitrate.isdigit() or bitrate_oldMediaInfo.isdigit()) and meta.get('resolution') == "720p":
                meta['service'] = "HIDI"

        meta['video'] = video

        meta['audio'], meta['channels'], meta['has_commentary'] = await get_audio_v2(mi, meta, bdinfo)

        meta['3D'] = await is_3d(mi, bdinfo)

        meta['source'], meta['type'] = await get_source(meta['type'], video, meta['path'], meta['is_disc'], meta, folder_id, base_dir)

        meta['uhd'] = await get_uhd(meta['type'], guessit(meta['path']), meta['resolution'], meta['path'])
        meta['hdr'] = await get_hdr(mi, bdinfo)

        meta['distributor'] = await get_distributor(meta['distributor'])

        if meta.get('is_disc', None) == "BDMV":  # Blu-ray Specific
            meta['region'] = await get_region(bdinfo, meta.get('region', None))
            meta['video_codec'] = await get_video_codec(bdinfo)
        else:
            meta['video_encode'], meta['video_codec'], meta['has_encode_settings'], meta['bit_depth'] = await get_video_encode(mi, meta['type'], bdinfo)

        if meta.get('no_edition') is False:
            meta['edition'], meta['repack'], meta['webdv'] = await get_edition(meta['uuid'], bdinfo, meta['filelist'], meta.get('manual_edition'), meta)
            if "REPACK" in meta.get('edition', ""):
                meta['repack'] = re.search(r"REPACK[\d]?", meta['edition'])[0]
                meta['edition'] = re.sub(r"REPACK[\d]?", "", meta['edition']).strip().replace('  ', ' ')
        else:
            meta['edition'] = ""

        meta.get('stream', False)
        meta['stream'] = await self.stream_optimized(meta['stream'])

        if meta.get('tag', None) is None:
            if meta.get('we_need_tag', False):
                meta['tag'] = await get_tag(meta['scene_name'], meta)
            else:
                meta['tag'] = await get_tag(video, meta)
                # all lowercase filenames will have bad group tag, it's probably a scene release.
                # some extracted files do not match release name so lets double check if it really is a scene release
                if not meta.get('scene') and meta['tag']:
                    base = os.path.basename(video)
                    match = re.match(r"^(.+)\.[a-zA-Z0-9]{3}$", os.path.basename(video))
                    if match and (not meta['is_disc'] or meta.get('keep_folder', False)):
                        base = match.group(1)
                        is_all_lowercase = base.islower()
                        if is_all_lowercase:
                            release_name = await is_scene(videopath, meta, meta.get('imdb_id', 0), lower=True)
                            if release_name is not None:
                                try:
                                    meta['scene_name'] = release_name
                                    meta['tag'] = await self.get_tag(release_name, meta)
                                except Exception:
                                    console.print("[red]Error getting tag from scene name, check group tag.[/red]")

        else:
            if not meta['tag'].startswith('-') and meta['tag'] != "":
                meta['tag'] = f"-{meta['tag']}"

        meta = await tag_override(meta)

        if meta['tag'][1:].startswith(meta['channels']):
            meta['tag'] = meta['tag'].replace(f"-{meta['channels']}", '')

        if meta.get('no_tag', False):
            meta['tag'] = ""

        if meta.get('service', None) in (None, ''):
            meta['service'], meta['service_longname'] = await get_service(video, meta.get('tag', ''), meta['audio'], meta['filename'])
        elif meta.get('service'):
            services = await get_service(get_services_only=True)
            meta['service_longname'] = max((k for k, v in services.items() if v == meta['service']), key=len, default=meta['service'])

        # return duplicate ids so I don't have to catch every site file
        # this has the other adavantage of stringifying immb for this object
        meta['tmdb'] = meta.get('tmdb_id')
        if int(meta.get('imdb_id')) != 0:
            imdb_str = str(meta['imdb_id']).zfill(7)
            meta['imdb'] = imdb_str
        else:
            meta['imdb'] = '0'
        meta['mal'] = meta.get('mal_id')
        meta['tvdb'] = meta.get('tvdb_id')
        meta['tvmaze'] = meta.get('tvmaze_id')

        # we finished the metadata, time it
        if meta['debug']:
            meta_finish_time = time.time()
            console.print(f"Metadata processed in {meta_finish_time - meta_start_time:.2f} seconds")

        return meta

    async def get_cat(self, video, meta):
        if meta.get('category'):
            return meta.get('category')

        path_patterns = [
            r'(?i)[\\/](?:tv|tvshows|tv.shows|series|shows)[\\/]',
            r'(?i)[\\/](?:season\s*\d+|s\d+|complete)[\\/]',
            r'(?i)[\\/](?:s\d{1,2}e\d{1,2}|s\d{1,2}|season\s*\d+)',
            r'(?i)(?:complete series|tv pack|season\s*\d+\s*complete)'
        ]

        filename_patterns = [
            r'(?i)s\d{1,2}e\d{1,2}',
            r'(?i)\d{1,2}x\d{2}',
            r'(?i)(?:season|series)\s*\d+',
            r'(?i)e\d{2,3}\s*\-',
            r'(?i)(?:complete|full)\s*(?:season|series)'
        ]

        path = meta.get('path', '')
        uuid = meta.get('uuid', '')

        for pattern in path_patterns:
            if re.search(pattern, path):
                return "TV"

        for pattern in filename_patterns:
            if re.search(pattern, uuid) or re.search(pattern, os.path.basename(path)):
                return "TV"

        return "MOVIE"

    async def stream_optimized(self, stream_opt):
        if stream_opt is True:
            stream = 1
        else:
            stream = 0
        return stream
