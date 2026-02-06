# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from typing import Any, Callable, Optional, cast

console: Any = None

try:
    import asyncio
    import ntpath
    import os
    import re
    import sys
    import time
    from difflib import SequenceMatcher

    import aiofiles
    import cli_ui
    import guessit

    from src.apply_overrides import ApplyOverrides
    from src.audio import AudioManager
    from src.bluray_com import get_bluray_releases
    from src.cleanup import cleanup_manager
    from src.clients import Clients
    from src.console import console
    from src.edition import get_edition
    from src.exportmi import exportInfo, get_conformance_error, mi_resolution, validate_mediainfo
    from src.get_disc import DiscInfoManager
    from src.get_name import NameManager
    from src.get_source import get_source
    from src.get_tracker_data import TrackerDataManager
    from src.getseasonep import SeasonEpisodeManager
    from src.imdb import imdb_manager
    from src.is_scene import SceneManager
    from src.languages import languages_manager
    from src.metadata_searching import MetadataSearchingManager
    from src.radarr import RadarrManager
    from src.region import get_distributor, get_region, get_service
    from src.rehostimages import RehostImagesManager
    from src.sonarr import SonarrManager
    from src.tags import get_tag, tag_override
    from src.tmdb import TmdbManager
    from src.tvdb import tvdb_data
    from src.tvmaze import tvmaze_manager
    from src.video import video_manager

    guessit_module: Any = cast(Any, guessit)
    GuessitFn = Callable[[str, Optional[dict[str, Any]]], dict[str, Any]]

    def guessit_fn(value: str, options: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return cast(dict[str, Any], guessit_module.guessit(value, options))

except ModuleNotFoundError:
    if console is not None:
        console.print('Missing Module Found. Please reinstall required dependencies from requirements.txt.', markup=False)
    else:
        print('Missing Module Found. Please reinstall required dependencies from requirements.txt.')
    raise SystemExit(1) from None
except KeyboardInterrupt:
    exit()


def _normalize_search_year(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, (str, int)):
        return str(value)
    return str(value)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Prep:
    """
    Prepare for upload:
        Mediainfo/BDInfo
        Screenshots
        Database Identifiers (TMDB/IMDB/MAL/etc)
        Create Name
    """

    def __init__(self, screens: int, img_host: str, config: dict[str, Any]) -> None:
        self.screens = screens
        self.config = config
        self.img_host = img_host.lower()
        self.tvdb_handler = tvdb_data(config)
        self.overrides = ApplyOverrides(config)
        self.audio_manager = AudioManager(config)
        self.disc_info_manager = DiscInfoManager(config)
        self.name_manager = NameManager(config)
        self.tracker_data_manager = TrackerDataManager(config)
        self.scene_manager = SceneManager(config)
        self.metadata_searching_manager = MetadataSearchingManager(config)
        self.tmdb_manager = TmdbManager(config)
        self.season_episode_manager = SeasonEpisodeManager(config)
        self.radarr_manager = RadarrManager(config)
        self.sonarr_manager = SonarrManager(config)
        self.rehost_images_manager = RehostImagesManager(config)

    async def gather_prep(self, meta: dict[str, Any], mode: str) -> dict[str, Any]:
        # set a timer to check speed
        meta_start_time = time.time()
        pathed_time_start = meta_start_time
        filename = ""
        untouched_filename = ""
        videopath = ""
        search_term = ""
        search_file_folder = ""
        bdinfo: dict[str, Any] = {}
        mi: Optional[dict[str, Any]] = None
        # set some details we'll need
        meta['cutoff'] = int(self.config['DEFAULT'].get('cutoff_screens', 1))

        meta['mode'] = mode
        meta['isdir'] = os.path.isdir(meta['path'])
        base_dir = meta['base_dir']
        meta['saved_description'] = False
        client = Clients(config=self.config)
        meta['skip_auto_torrent'] = meta.get('skip_auto_torrent', False) or self.config['DEFAULT'].get('skip_auto_torrent', False)
        hash_ids = ['infohash', 'torrent_hash', 'skip_auto_torrent']
        tracker_ids = ['aither', 'ulcx', 'lst', 'blu', 'oe', 'btn', 'bhd', 'huno', 'hdb', 'rf', 'otw', 'yus', 'dp', 'sp', 'ptp']
        use_sonarr = self.config['DEFAULT'].get('use_sonarr', False)
        use_radarr = self.config['DEFAULT'].get('use_radarr', False)
        meta['print_tracker_messages'] = self.config['DEFAULT'].get('print_tracker_messages', False)
        meta['print_tracker_links'] = self.config['DEFAULT'].get('print_tracker_links', True)
        only_id_val = meta.get('onlyID')
        only_id = bool(self.config['DEFAULT'].get('only_id', False) if only_id_val is None else only_id_val)
        meta['only_id'] = only_id
        meta['keep_images'] = bool(self.config['DEFAULT'].get('keep_images', True) if not meta.get('keep_images') else True)
        mkbrr_threads = self.config['DEFAULT'].get('mkbrr_threads', "0")
        meta['mkbrr_threads'] = mkbrr_threads

        # make sure these are set in meta
        meta['we_checked_tvdb'] = False
        meta['we_checked_tmdb'] = False
        meta['we_asked_tvmaze'] = False
        meta['audio_languages'] = None
        meta['subtitle_languages'] = None
        meta['aither_trumpable'] = None

        folder_id = os.path.basename(meta['path'])
        if meta.get('uuid') is None:
            meta['uuid'] = folder_id
        if not os.path.exists(f"{base_dir}/tmp/{meta['uuid']}"):
            os.makedirs(f"{base_dir}/tmp/{meta['uuid']}", mode=0o700, exist_ok=True)

        if meta['debug']:
            console.print(f"[cyan]ID: {meta['uuid']}")

        try:
            meta['is_disc'], videoloc, bdinfo, meta['discs'] = await self.disc_info_manager.get_disc(meta)
        except Exception:
            raise
        if meta.get('debug', False):
            console.print(f"[blue]is_disc: [yellow]{meta['is_disc']}[/yellow][/blue]")
        # Debugging information
        # console.print(f"Debug: meta['filelist'] before population: {meta.get('filelist', 'Not Set')}")

        if meta['is_disc'] == "BDMV":
            video, meta['scene'], meta['imdb_id'] = await self.scene_manager.is_scene(meta['path'], meta, meta.get('imdb_id', 0))
            meta['filelist'] = []  # No filelist for discs, use path
            search_term = os.path.basename(meta['path'])
            search_file_folder = 'folder'
            try:
                if meta.get('emby', False):
                    title, secondary_title, extracted_year = await self.name_manager.extract_title_and_year(meta, video)
                    if meta['debug']:
                        console.print(f"Title: {title}, Secondary Title: {secondary_title}, Year: {extracted_year}")
                    if secondary_title:
                        meta['secondary_title'] = secondary_title
                    if extracted_year and not meta.get('year'):
                        meta['year'] = extracted_year
                    if title:
                        filename = title
                        untouched_filename = search_term
                        meta['regex_title'] = title
                        meta['regex_secondary_title'] = secondary_title
                        meta['regex_year'] = extracted_year
                    else:
                        guess_name = search_term.replace('-', ' ')
                        untouched_filename = search_term
                        filename = str(guessit_fn(guess_name, {"excludes": ["country", "language"]}).get('title', ''))
                else:
                    title, secondary_title, extracted_year = await self.name_manager.extract_title_and_year(meta, video)
                    if meta['debug']:
                        console.print(f"Title: {title}, Secondary Title: {secondary_title}, Year: {extracted_year}")
                    if secondary_title:
                        meta['secondary_title'] = secondary_title
                    if extracted_year and not meta.get('year'):
                        meta['year'] = extracted_year
                    if title:
                        filename = title
                        untouched_filename = search_term
                    else:
                        guess_name = bdinfo['title'].replace('-', ' ')
                        untouched_filename = bdinfo['title']
                        filename = str(guessit_fn(re.sub(r"[^0-9a-zA-Z\[\\]]+", " ", guess_name), {"excludes": ["country", "language"]}).get('title', ''))
                try:
                    meta['search_year'] = guessit_fn(bdinfo['title'])['year']
                except Exception:
                    meta['search_year'] = ""
            except Exception:
                guess_name = bdinfo['label'].replace('-', ' ')
                filename = str(guessit_fn(re.sub(r"[^0-9a-zA-Z\[\\]]+", " ", guess_name), {"excludes": ["country", "language"]}).get('title', ''))
                untouched_filename = bdinfo['label']
                try:
                    meta['search_year'] = guessit_fn(bdinfo['label'])['year']
                except Exception:
                    meta['search_year'] = ""

            if meta.get('resolution') is None and not meta.get('emby', False):
                meta['resolution'] = await mi_resolution(
                    bdinfo['video'][0]['res'],
                    guessit_fn(video),
                    width="OTHER",
                    scan="p",
                )
                try:
                    is_hfr = bdinfo['video'][0]['fps'].split()[0] if bdinfo['video'] else "25"
                    if int(float(is_hfr)) > 30:
                        meta['hfr'] = True
                    else:
                        meta['hfr'] = False
                except Exception:
                    meta['hfr'] = False
            else:
                meta['resolution'] = "1080p"

            meta['sd'] = await video_manager.is_sd(str(meta.get('resolution', '')))

            mi = None

        elif meta['is_disc'] == "DVD":
            video, meta['scene'], meta['imdb_id'] = await self.scene_manager.is_scene(meta['path'], meta, meta.get('imdb_id', 0))
            meta['filelist'] = []
            search_term = os.path.basename(meta['path'])
            search_file_folder = 'folder'
            if meta.get('emby', False):
                title, secondary_title, extracted_year = await self.name_manager.extract_title_and_year(meta, video)
                if meta['debug']:
                    console.print(f"Title: {title}, Secondary Title: {secondary_title}, Year: {extracted_year}")
                if secondary_title:
                    meta['secondary_title'] = secondary_title
                if extracted_year and not meta.get('year'):
                    meta['year'] = extracted_year
                if title:
                    filename = title
                    untouched_filename = search_term
                    meta['regex_title'] = title
                    meta['regex_secondary_title'] = secondary_title
                    meta['regex_year'] = extracted_year
                else:
                    guess_name = search_term.replace('-', ' ')
                    filename = guess_name
                    untouched_filename = search_term
                meta['resolution'] = "480p"
                meta['search_year'] = ""
            else:
                title, secondary_title, extracted_year = await self.name_manager.extract_title_and_year(meta, video)
                if meta['debug']:
                    console.print(f"Title: {title}, Secondary Title: {secondary_title}, Year: {extracted_year}")
                if secondary_title:
                    meta['secondary_title'] = secondary_title
                if extracted_year and not meta.get('year'):
                    meta['year'] = extracted_year
                if title:
                    filename = title
                    untouched_filename = search_term
                else:
                    guess_name = meta['discs'][0]['path'].replace('-', ' ')
                    filename = str(guessit_fn(guess_name, {"excludes": ["country", "language"]}).get('title', ''))
                    untouched_filename = os.path.basename(os.path.dirname(meta['discs'][0]['path']))
                try:
                    meta['search_year'] = guessit_fn(meta['discs'][0]['path'])['year']
                except Exception:
                    meta['search_year'] = ""
                if not meta.get('edit', False):
                    mi = await exportInfo(f"{meta['discs'][0]['path']}/VTS_{meta['discs'][0]['main_set'][0][:2]}_0.IFO", False, meta['uuid'], meta['base_dir'], is_dvd=True, debug=meta.get('debug', False))
                    meta['mediainfo'] = mi
                else:
                    mi = meta['mediainfo']

                meta['dvd_size'] = await self.disc_info_manager.get_dvd_size(meta['discs'], meta.get('manual_dvds'))
                meta['resolution'], meta['hfr'] = await video_manager.get_resolution(guessit_fn(video), meta['uuid'], base_dir)
                meta['sd'] = await video_manager.is_sd(meta['resolution'])

        elif meta['is_disc'] == "HDDVD":
            video, meta['scene'], meta['imdb_id'] = await self.scene_manager.is_scene(meta['path'], meta, meta.get('imdb_id', 0))
            meta['filelist'] = []
            search_term = os.path.basename(meta['path'])
            search_file_folder = 'folder'
            guess_name = meta['discs'][0]['path'].replace('-', '')
            filename = str(guessit_fn(guess_name, {"excludes": ["country", "language"]}).get('title', ''))
            untouched_filename = os.path.basename(meta['discs'][0]['path'])
            videopath = meta['discs'][0]['largest_evo']
            try:
                meta['search_year'] = guessit_fn(meta['discs'][0]['path'])['year']
            except Exception:
                meta['search_year'] = ""
            if not meta.get('edit', False):
                mi = await exportInfo(meta['discs'][0]['largest_evo'], False, meta['uuid'], meta['base_dir'], debug=meta['debug'])
                meta['mediainfo'] = mi
            else:
                mi = meta['mediainfo']
            meta['resolution'], meta['hfr'] = await video_manager.get_resolution(guessit_fn(video), meta['uuid'], base_dir)
            meta['sd'] = await video_manager.is_sd(meta['resolution'])

        else:
            videopath, meta['filelist'] = await video_manager.get_video(videoloc, meta.get('mode', 'discord'), meta.get('sorted_filelist', False), meta.get('debug', False))
            filelist = cast(list[str], meta.get('filelist') or [])
            meta['filelist'] = filelist
            search_term = os.path.basename(filelist[0]) if filelist else ""
            search_file_folder = 'file'

            video, meta['scene'], meta['imdb_id'] = await self.scene_manager.is_scene(videopath, meta, meta.get('imdb_id', 0))

            try:
                title, secondary_title, extracted_year = await self.name_manager.extract_title_and_year(meta, video)
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
            except Exception as e:
                console.print(f"[red]Error extracting title and year: {e}[/red]")
                raise Exception(f"Error extracting title and year: {e}") from e

            try:
                if title:
                    filename = title
                    meta['regex_title'] = title
                    meta['regex_secondary_title'] = secondary_title
                    meta['regex_year'] = extracted_year
                else:
                    try:
                        filename = str(guessit_fn(re.sub(r"[^0-9a-zA-Z\[\\]]+", " ", guess_name), {"excludes": ["country", "language"]}).get(
                            "title",
                            str(guessit_fn(re.sub("[^0-9a-zA-Z]+", " ", guess_name), {"excludes": ["country", "language"]}).get("title", ""))
                        ))
                    except Exception:
                        try:
                            guess_name = ntpath.basename(video).replace('-', ' ')
                            filename = str(guessit_fn(re.sub(r"[^0-9a-zA-Z\[\\]]+", " ", guess_name), {"excludes": ["country", "language"]}).get(
                                "title",
                                str(guessit_fn(re.sub("[^0-9a-zA-Z]+", " ", guess_name), {"excludes": ["country", "language"]}).get("title", ""))
                            ))
                        except Exception as e:
                            console.print(f"[red]Error extracting title from video name: {e}[/red]")
                            raise Exception(f"Error extracting title from video name: {e}") from e

                untouched_filename = os.path.basename(video)
            except Exception as e:
                console.print(f"[red]Error processing filename: {e}[/red]")
                raise Exception(f"Error processing filename: {e}") from e

            try:
                if not meta.get('emby', False):
                    # rely only on guessit for search_year for tv matching
                    try:
                        meta['search_year'] = guessit_fn(video)['year']
                    except Exception:
                        meta['search_year'] = ""

                    if not meta.get('edit', False):
                        mi = await exportInfo(videopath, meta['isdir'], meta['uuid'], base_dir, is_dvd=meta.get('is_disc', False), debug=meta.get('debug', False))
                        meta['mediainfo'] = mi
                    else:
                        mi = meta['mediainfo']

                    if meta.get('resolution') is None:
                        meta['resolution'], meta['hfr'] = await video_manager.get_resolution(guessit_fn(video), meta['uuid'], base_dir)

                    meta['sd'] = await video_manager.is_sd(meta['resolution'])
                else:
                    meta['resolution'] = "1080p"
                    meta['search_year'] = ""
            except Exception as e:
                console.print(f"[red]Error processing Mediainfo: {e}[/red]")
                raise Exception(f"Error processing Mediainfo: {e}") from e

        source_size = 0
        if not meta['is_disc']:
            # Sum every non-disc file so downstream steps know the total payload size
            filelist = cast(list[str], meta.get('filelist') or [])
            files_to_measure = filelist if filelist else ([videopath] if videopath else [])
            for file_path in files_to_measure:
                if not os.path.isfile(file_path):
                    if meta.get('debug'):
                        console.print(f"[yellow]Skipping size check for missing file: {file_path}")
                    continue
                try:
                    source_size += os.path.getsize(file_path)
                except OSError as exc:
                    if meta.get('debug'):
                        console.print(f"[yellow]Unable to stat {file_path}: {exc}")

        else:
            # Disc structures can span many files; walk the tree rooted at meta['path']
            disc_root = meta.get('path')
            disc_root_str = disc_root if isinstance(disc_root, str) else ""
            if disc_root_str and os.path.exists(disc_root_str):
                for root, _, files in os.walk(disc_root_str):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        try:
                            source_size += os.path.getsize(file_path)
                        except OSError as exc:
                            if meta.get('debug'):
                                console.print(f"[yellow]Unable to stat {file_path}: {exc}")
                            continue
            else:
                if meta.get('debug'):
                    console.print(f"[yellow]Disc path missing, source size set to 0: {disc_root_str}")

        meta['source_size'] = source_size
        if meta['debug']:
            console.print(f"[cyan]Calculated source size: {meta['source_size']} bytes")

        filename = str(filename)
        untouched_filename = str(untouched_filename)
        if " AKA " in filename.replace('.', ' '):
            filename = filename.split('AKA')[0]
        meta['filename'] = filename
        meta['bdinfo'] = bdinfo

        conform_issues = await get_conformance_error(meta)
        if conform_issues:
            upload = False
            if not meta['unattended'] or (meta['unattended'] and meta.get('unattended_confirm', False)):
                try:
                    upload = cli_ui.ask_yes_no("Found Conformance errors in mediainfo (possible cause: corrupted file, incomplete download, new codec, etc...), proceed to upload anyway?", default=False)
                except EOFError:
                    console.print("\n[red]Exiting on user request (Ctrl+C)[/red]")
                    await cleanup_manager.cleanup()
                    cleanup_manager.reset_terminal()
                    sys.exit(1)
            if upload is False:
                console.print("[red]Not uploading. Check if the file has finished downloading and can be played back properly (uncorrupted).")
                tmp_dir = f"{meta['base_dir']}/tmp/{meta['uuid']}"
                # Cleanup meta so we don't reuse it later
                if os.path.exists(tmp_dir):
                    try:
                        for file in os.listdir(tmp_dir):
                            file_path = os.path.join(tmp_dir, file)
                            if os.path.isfile(file_path) and file.endswith((".txt", ".json")):
                                os.remove(file_path)
                                if meta['debug']:
                                    console.print(f"[yellow]Removed temporary metadata file: {file_path}[/yellow]")
                    except Exception as e:
                        console.print(f"[red]Error cleaning up temporary metadata files: {e}[/red]", highlight=False)
                console.print("[red]Not uploading due to conformance errors.[/red]")
                raise Exception("Conformance errors found in mediainfo")

        meta['valid_mi'] = True
        if not meta['is_disc'] and not meta.get('emby', False):
            try:
                valid_mi = validate_mediainfo(meta, debug=meta['debug'])
            except Exception as e:
                console.print(f"[red]MediaInfo validation failed: {str(e)}[/red]")
                raise Exception(f"Upload Assistant does not support no audio media. Details: {str(e)}") from e
            if not valid_mi:
                console.print("[red]MediaInfo validation failed. This file does not contain (Unique ID).")
                meta['valid_mi'] = False
                await asyncio.sleep(2)

        # Check if there's a language restriction
        if meta['has_languages'] is not None and not meta.get('emby', False):
            try:
                parsed_info = await languages_manager.parsed_mediainfo(meta)
                audio_languages = [
                    audio_track['language'].lower()
                    for audio_track in parsed_info.get('audio', [])
                    if 'language' in audio_track and audio_track['language']
                ]
                any_of_languages = meta['has_languages'].lower().split(",")
                if all(len(lang.strip()) == 2 for lang in any_of_languages):
                    raise Exception(f"Warning: Languages should be full names, not ISO codes. Found: {any_of_languages}")
                # We need to have user input languages and file must have audio tracks.
                if len(any_of_languages) > 0 and len(audio_languages) > 0 and not set(any_of_languages).intersection(set(audio_languages)):
                    console.print(f"[red] None of the required languages ({meta['has_languages']}) is available on the file {audio_languages}")
                    raise Exception("No matching languages")
            except Exception as e:
                console.print(f"[red]{e}[/red]")
                raise Exception("Language check failed") from e

        if not meta.get('emby', False):
            if 'description' not in meta or meta.get('description') is None:
                meta['description'] = ""

            description_text = meta.get('description', '')
            if description_text is None:
                description_text = ""
            async with aiofiles.open(
                f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt",
                "w",
                newline="",
                encoding="utf8",
            ) as description:
                if len(description_text):
                    await description.write(description_text)

        meta['skip_trackers'] = False
        if meta.get('emby', False):
            only_id = True
            meta['only_id'] = True
            meta['keep_images'] = False
            if meta.get('imdb_id', 0) != 0:
                meta['skip_trackers'] = True
        if meta.get('emby_debug', False):
            meta['skip_trackers'] = True

        if meta['debug']:
            pathed_time_start = time.time()

        if not meta.get('emby') and meta.get('trackers'):
            trackers = meta['trackers']
        else:
            default_trackers = self.config['TRACKERS'].get('default_trackers', '')
            trackers = [tracker.strip() for tracker in default_trackers.split(',')]

        if isinstance(trackers, str):
            trackers = [t.strip().upper() for t in trackers.split(',')] if "," in trackers else [trackers.strip().upper()]
        else:
            trackers = [t.strip().upper() for t in trackers]
        meta['trackers'] = trackers
        meta['requested_trackers'] = trackers

        # auto torrent searching with qbittorrent that grabs torrent ids for metadata searching
        if not any(meta.get(id_type) for id_type in hash_ids + tracker_ids) and not meta.get('skip_trackers', False) and not meta.get('edit', False):
            await client.get_pathed_torrents(meta['path'], meta)

        if meta['debug']:
            pathed_time_end = time.time()
            console.print(f"Pathed torrent data processed in {pathed_time_end - pathed_time_start:.2f} seconds")

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

        if not meta.get('category'):
            meta['category'] = await self.get_cat(video, meta)
        else:
            meta['category'] = meta['category'].upper()

        ids = None
        if not meta.get('skip_trackers', False):
            if meta.get('category') == "TV" and use_sonarr and meta.get('tvdb_id', 0) == 0:
                ids = await self.sonarr_manager.get_sonarr_data(filename=meta.get('path', ''), title=meta.get('filename'), debug=meta.get('debug', False))
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
                    if meta.get('manual_year', 0) == 0 and ids['year'] is not None:
                        meta['manual_year'] = ids['year']
                else:
                    ids = None

            if meta.get('category') == "MOVIE" and use_radarr and meta.get('tmdb_id', 0) == 0:
                ids = await self.radarr_manager.get_radarr_data(filename=meta.get('uuid', ''), debug=meta.get('debug', False))
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

            if not meta.get('edit', False) and not ids:
                # Reuse information from trackers with fallback
                await self.tracker_data_manager.get_tracker_data(video, meta, search_term, search_file_folder, meta['category'], only_id=only_id)

            if meta.get('category', None) == "TV" and use_sonarr and meta.get('tvdb_id', 0) != 0 and ids is None and not meta.get('matched_tracker', None):
                ids = await self.sonarr_manager.get_sonarr_data(tvdb_id=meta.get('tvdb_id', 0), debug=meta.get('debug', False))
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
                    if meta.get('manual_year', 0) == 0 and ids['year'] is not None:
                        meta['manual_year'] = ids['year']
                else:
                    ids = None

            if meta.get('category', None) == "MOVIE" and use_radarr and meta.get('tmdb_id', 0) != 0 and ids is None and not meta.get('matched_tracker', None):
                ids = await self.radarr_manager.get_radarr_data(tmdb_id=meta.get('tmdb_id', 0), debug=meta.get('debug', False))
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
                else:
                    ids = None

        # if there's no region/distributor info, lets ping some unit3d trackers and see if we get it
        ping_unit3d_config = self.config['DEFAULT'].get('ping_unit3d', False)
        if (not meta.get('region') or not meta.get('distributor')) and meta['is_disc'] == "BDMV" and ping_unit3d_config and not meta.get('edit', False) and not meta.get('emby', False) and not meta.get('site_check', False):
            await self.tracker_data_manager.ping_unit3d(meta)

        # the first user override check that allows to set metadata ids.
        # it relies on imdb or tvdb already being set.
        user_overrides = self.config['DEFAULT'].get('user_overrides', False)
        if user_overrides and (meta.get('imdb_id') != 0 or meta.get('tvdb_id') != 0) and not meta.get('emby', False):
            meta = await self.overrides.get_source_override(meta, other_id=True)
            category = meta.get('category')
            meta['category'] = str(category).upper() if category is not None else ''
            # set a flag so that the other check later doesn't run
            meta['no_override'] = True

        emby_cat = meta.get('emby_cat')
        if emby_cat is not None and str(emby_cat).upper() != str(meta.get('category') or '').upper():
            return meta

        if meta['debug']:
            console.print("ID inputs into prep")
            console.print("category:", meta.get("category"))
            console.print(f"Raw TVDB ID: {meta['tvdb_id']} (type: {type(meta['tvdb_id']).__name__})")
            console.print(f"Raw IMDb ID: {meta['imdb_id']} (type: {type(meta['imdb_id']).__name__})")
            console.print(f"Raw TMDb ID: {meta['tmdb_id']} (type: {type(meta['tmdb_id']).__name__})")
            console.print(f"Raw TVMAZE ID: {meta['tvmaze_id']} (type: {type(meta['tvmaze_id']).__name__})")
            console.print(f"Raw MAL ID: {meta['mal_id']} (type: {type(meta['mal_id']).__name__})")

        if meta.get('mal_id', 0) != 0:
            meta['anime'] = True
            meta['not_anime'] = True

        console.print("[yellow]Building meta data.....")

        # set a timer to check speed
        if meta['debug']:
            meta_middle_time = time.time()
            console.print(f"Source/tracker data processed in {meta_middle_time - meta_start_time:.2f} seconds")

        manual_language = meta.get('manual_language')
        if isinstance(manual_language, str) and manual_language:
            meta['original_language'] = manual_language.lower()

        meta['type'] = await video_manager.get_type(video, meta['scene'], meta['is_disc'], meta)

        # if it's not an anime, we can run season/episode checks now to speed the process
        if meta.get("not_anime", False) and meta.get("category") == "TV":
            meta = await self.season_episode_manager.get_season_episode(video, meta)

        mi_data: dict[str, Any] = mi or {}

        # Run a check against mediainfo to see if it has tmdb/imdb
        if (meta.get('tmdb_id') == 0 or meta.get('imdb_id') == 0) and not meta.get('emby', False):
            meta['category'], meta['tmdb_id'], meta['imdb_id'], meta['tvdb_id'] = await self.tmdb_manager.get_tmdb_imdb_from_mediainfo(
                mi_data, meta
            )

        # Flag for emby if no IDs were found
        if meta.get('imdb_id', 0) == 0 and meta.get('tvdb_id', 0) == 0 and meta.get('tmdb_id', 0) == 0 and meta.get('tvmaze_id', 0) == 0 and meta.get('mal_id', 0) == 0 and meta.get('emby', False):
            meta['no_ids'] = True

        meta['video_duration'] = await video_manager.get_video_duration(meta)
        duration = meta.get('video_duration', None)

        unattended = not (not meta['unattended'] or meta['unattended'] and meta.get('unattended_confirm', False))
        debug = bool(meta.get('emby_debug', False) or meta['debug'])

        # run a search to find tmdb and imdb ids if we don't have them
        if int(meta.get('tmdb_id') or 0) == 0 and int(meta.get('imdb_id') or 0) == 0:
            if meta.get('category') == "TV":
                year = meta.get('manual_year', '') or meta.get('search_year', '') or meta.get('year', '')
            elif meta.get('emby_debug', False):
                year = ""
            else:
                year = meta.get('manual_year', '') or meta.get('year', '') or meta.get('search_year', '')
            year_value = _normalize_search_year(year)
            category_pref = meta.get('category') or ''
            tmdb_task: asyncio.Task[tuple[int, str]] = asyncio.create_task(
                self.tmdb_manager.get_tmdb_id(
                    filename,
                    year_value,
                    category_pref,
                    untouched_filename,
                    attempted=0,
                    debug=debug,
                    secondary_title=meta.get('secondary_title', None),
                    unattended=unattended,
                )
            )
            imdb_task: asyncio.Task[int] = asyncio.create_task(
                imdb_manager.search_imdb(
                    filename,
                    year_value,
                    quickie=True,
                    category=category_pref,
                    debug=debug,
                    secondary_title=meta.get('secondary_title', None),
                    untouched_filename=untouched_filename,
                    duration=duration,
                    unattended=unattended,
                )
            )
            tmdb_result, imdb_result = await asyncio.gather(tmdb_task, imdb_task)
            tmdb_id, category = tmdb_result
            meta['category'] = category
            meta['tmdb_id'] = _to_int(tmdb_id)
            meta['imdb_id'] = _to_int(imdb_result)
            meta['quickie_search'] = True
            meta['no_ids'] = True

        # If we have an IMDb ID but no TMDb ID, fetch TMDb ID from IMDb
        if int(meta.get('imdb_id') or 0) != 0 and int(meta.get('tmdb_id') or 0) == 0:
            imdb_id_value = _to_int(meta.get('imdb_id'))
            tvdb_id_value = _to_int(meta.get('tvdb_id'))
            search_year_value = _normalize_search_year(meta.get('search_year'))
            category, tmdb_id, original_language, filename_search = await self.tmdb_manager.get_tmdb_from_imdb(
                imdb_id_value,
                tvdb_id_value if tvdb_id_value else None,
                search_year_value,
                filename,
                debug=meta.get('debug', False),
                mode=meta.get('mode', 'discord'),
                category_preference=meta.get('category'),
                imdb_info=meta.get('imdb_info', None)
            )

            meta['category'] = category
            meta['tmdb_id'] = _to_int(tmdb_id)
            meta['original_language'] = original_language
            meta['no_ids'] = filename_search

        # if we have all of the ids, search everything all at once
        if int(meta.get('imdb_id') or 0) != 0 and int(meta.get('tvdb_id') or 0) != 0 and int(meta.get('tmdb_id') or 0) != 0 and int(meta.get('tvmaze_id') or 0) != 0:
            meta = await self.metadata_searching_manager.all_ids(meta)

        # Check if IMDb, TMDb, and TVDb IDs are all present
        elif int(meta.get('imdb_id') or 0) != 0 and int(meta.get('tvdb_id') or 0) != 0 and int(meta.get('tmdb_id') or 0) != 0 and not meta.get('quickie_search', False):
            meta = await self.metadata_searching_manager.imdb_tmdb_tvdb(meta, filename)

        # Check if both IMDb and TVDB IDs are present
        elif int(meta.get('imdb_id') or 0) != 0 and int(meta.get('tvdb_id') or 0) != 0 and not meta.get('quickie_search', False):
            meta = await self.metadata_searching_manager.imdb_tvdb(meta, filename)

        # Check if both IMDb and TMDb IDs are present
        elif int(meta.get('imdb_id') or 0) != 0 and int(meta.get('tmdb_id') or 0) != 0 and not meta.get('quickie_search', False):
            meta = await self.metadata_searching_manager.imdb_tmdb(meta, filename)

        # we should have tmdb id one way or another, so lets get data if needed
        if int(meta.get('tmdb_id') or 0) != 0:
            await self.tmdb_manager.set_tmdb_metadata(meta, filename)

        # If there's a mismatch between IMDb and TMDb IDs, try to resolve it
        if meta.get('imdb_mismatch', False) and "subsplease" not in meta.get('uuid', '').lower():
            if meta['debug']:
                console.print("[yellow]IMDb ID mismatch detected, attempting to resolve...[/yellow]")
            # with refactored tmdb, it quite likely to be correct
            meta['imdb_id'] = meta.get('mismatched_imdb_id', 0)
            meta['imdb_info'] = None

        # Get IMDb ID if not set
        if meta.get('imdb_id') == 0:
            try:
                search_year_value = _normalize_search_year(meta.get('search_year'))
                meta['imdb_id'] = await imdb_manager.search_imdb(
                    filename,
                    search_year_value,
                    quickie=False,
                    category=meta.get('category', None),
                    debug=debug,
                    secondary_title=meta.get('secondary_title', None),
                    untouched_filename=untouched_filename,
                    attempted=0,
                    duration=duration,
                    unattended=unattended,
                )
            except Exception as e:
                console.print(f"[red]Error searching IMDb: {e}[/red]")
                raise Exception(f"Error searching IMDb: {e}") from e

        # user might have skipped tmdb earlier, lets double check
        if meta.get('imdb_id') != 0 and meta.get('tmdb_id') == 0:
            console.print("[yellow]No TMDB ID found, attempting to fetch from IMDb...[/yellow]")
            imdb_id_value = _to_int(meta.get('imdb_id'))
            tvdb_id_value = _to_int(meta.get('tvdb_id'))
            search_year_value = _normalize_search_year(meta.get('search_year'))
            category, tmdb_id, original_language, filename_search = await self.tmdb_manager.get_tmdb_from_imdb(
                imdb_id_value,
                tvdb_id_value if tvdb_id_value else None,
                search_year_value,
                filename,
                debug=meta.get('debug', False),
                mode=meta.get('mode', 'discord'),
                category_preference=meta.get('category'),
                imdb_info=meta.get('imdb_info', None)
            )

            meta['category'] = category
            meta['tmdb_id'] = _to_int(tmdb_id)
            meta['original_language'] = original_language
            meta['no_ids'] = filename_search

        tmdb_id_value = _to_int(meta.get('tmdb_id'))
        if tmdb_id_value != 0:
            await self.tmdb_manager.set_tmdb_metadata(meta, filename)

        # Ensure IMDb info is retrieved if it wasn't already fetched
        imdb_id_value = _to_int(meta.get('imdb_id'))
        if meta.get('imdb_info', None) is None and imdb_id_value != 0:
            imdb_info = await imdb_manager.get_imdb_info_api(imdb_id_value, manual_language=meta.get('manual_language'), debug=meta.get('debug', False))
            meta['imdb_info'] = imdb_info

        check_valid_data = meta.get('imdb_info', {}).get('title', "")
        if check_valid_data:
            try:
                title = meta['title'].lower().strip()
            except KeyError:
                console.print("[red]Title is missing from TMDB....")
                sys.exit(1)
            aka = meta.get('imdb_info', {}).get('title', "").strip().lower()
            imdb_aka = meta.get('imdb_info', {}).get('aka', "").strip().lower()
            year = str(meta.get('imdb_info', {}).get('year', ""))

            if aka and not meta.get('aka'):
                aka_trimmed = aka[4:].strip().lower() if aka.lower().startswith("aka") else aka.lower()
                difference = SequenceMatcher(None, title, aka_trimmed).ratio()
                if difference >= 0.7 or not aka_trimmed or aka_trimmed in title:
                    aka = None

                difference = SequenceMatcher(None, title, imdb_aka).ratio()
                if difference >= 0.7 or not imdb_aka or imdb_aka in title:
                    imdb_aka = None

                if aka is not None:
                    if f"({year})" in aka:
                        aka = meta.get('imdb_info', {}).get('title', "").replace(f"({year})", "").strip()
                    else:
                        aka = meta.get('imdb_info', {}).get('title', "").strip()
                    meta['aka'] = f"AKA {aka.strip()}"
                    meta['title'] = meta['title'].strip()
                elif imdb_aka is not None:
                    if f"({year})" in imdb_aka:
                        imdb_aka = meta.get('imdb_info', {}).get('aka', "").replace(f"({year})", "").strip()
                    else:
                        imdb_aka = meta.get('imdb_info', {}).get('aka', "").strip()
                    meta['aka'] = f"AKA {imdb_aka.strip()}"
                    meta['title'] = meta['title'].strip()

        if meta.get('aka', None) is None:
            meta['aka'] = ""

        # if it was skipped earlier, make sure we have the season/episode data
        if not meta.get('not_anime', False) and meta.get('category') == "TV":
            meta = await self.season_episode_manager.get_season_episode(video, meta)

        if meta['category'] == "TV" and meta.get('tv_pack'):
            await self.season_episode_manager.check_season_pack_completeness(meta)

        # lets check for tv movies
        meta['tv_movie'] = False
        is_tv_movie = meta.get('imdb_info', {}).get('type', '')
        tv_movie_keywords = ['tv movie', 'tv special', 'tvmovie']
        if any(re.search(rf'(^|,\s*){re.escape(keyword)}(\s*,|$)', is_tv_movie, re.IGNORECASE) for keyword in tv_movie_keywords):
            if meta['debug']:
                console.print(f"[yellow]Identified as TV Movie based on IMDb type: {is_tv_movie}[/yellow]")
            meta['tv_movie'] = True

        if meta['category'] == "TV" or meta.get('tv_movie', False):
            both_ids_searched = False
            search_year_value = _normalize_search_year(meta.get('search_year'))
            if meta.get('tvmaze_id', 0) == 0 and meta.get('tvdb_id', 0) == 0:
                tvmaze, tvdb, tvdb_data, tvdb_name = await self.metadata_searching_manager.get_tvmaze_tvdb(
                    filename,
                    search_year_value or "",
                    meta.get('imdb_id', 0),
                    meta.get('tmdb_id', 0),
                    meta.get('manual_data'),
                    meta.get('tvmaze_manual', 0),
                    year=meta.get('year', ''),
                    debug=meta.get('debug', False),
                    tv_movie=meta.get('tv_movie', False)
                )
                both_ids_searched = True
                if tvmaze:
                    meta['tvmaze_id'] = tvmaze
                    if meta['debug']:
                        console.print(f"[blue]Found TVMAZE ID from search: {tvmaze}[/blue]")
                if tvdb:
                    meta['tvdb_id'] = tvdb
                    if meta['debug']:
                        console.print(f"[blue]Found TVDB ID from search: {tvdb}[/blue]")
                if tvdb_data:
                    meta['tvdb_search_results'] = tvdb_data
                    if meta['debug']:
                        console.print("[blue]Found TVDB search results from search.[/blue]")
                if tvdb_name:
                    meta['tvdb_series_name'] = tvdb_name
                    if meta['debug']:
                        console.print(f"[blue]Found TVDB series name from search: {tvdb_name}[/blue]")
            if meta.get('tvmaze_id', 0) == 0 and not both_ids_searched:
                if meta['debug']:
                    console.print("[yellow]No TVMAZE ID found, attempting to fetch...[/yellow]")
                meta['tvmaze_id'] = await tvmaze_manager.search_tvmaze(
                    filename, search_year_value or "", meta.get('imdb_id', 0), meta.get('tvdb_id', 0),
                    manual_date=meta.get('manual_date'),
                    tvmaze_manual=meta.get('tvmaze_manual'),
                    debug=meta.get('debug', False),
                    return_full_tuple=False
                )
            if meta.get('tvdb_id', 0) == 0:
                if meta['debug']:
                    console.print("[yellow]No TVDB ID found, attempting to fetch...[/yellow]")
                try:
                    series_results, series_id = await self.tvdb_handler.search_tvdb_series(filename=filename, year=meta.get('year', ''), debug=meta.get('debug', False))
                    if series_id:
                        meta['tvdb_id'] = series_id
                        console.print(f"[blue]Found TVDB series ID from search: {series_id}[/blue]")
                    if series_results:
                        meta['tvdb_search_results'] = series_results
                except Exception as e:
                    console.print(f"[red]Error searching TVDB: {e}[/red]")

            # all your episode data belongs to us
            meta = await self.metadata_searching_manager.get_tv_data(meta)

            if meta.get('tvdb_imdb_id', None):
                imdb = meta['tvdb_imdb_id'].replace('tt', '')
                if imdb.isdigit() and imdb != meta.get('imdb_id', 0):
                    episode_info = await imdb_manager.get_imdb_from_episode(imdb, debug=True)
                    if episode_info:
                        series_id = episode_info.get('series', {}).get('series_id', None)
                        if series_id:
                            series_imdb = series_id.replace('tt', '')
                            if series_imdb.isdigit() and int(series_imdb) != meta.get('imdb_id', 0):
                                if meta['debug']:
                                    console.print(f"[yellow]Updating IMDb ID from episode data: {series_imdb}")
                                meta['imdb_id'] = int(series_imdb)
                                imdb_info = await imdb_manager.get_imdb_info_api(meta['imdb_id'], manual_language=meta.get('manual_language'), debug=meta.get('debug', False))
                                meta['imdb_info'] = imdb_info
                                check_valid_data = meta.get('imdb_info', {}).get('title', "")
                                if check_valid_data:
                                    title = meta.get('title', "").strip()
                                    aka = meta.get('imdb_info', {}).get('aka', "").strip()
                                    year = str(meta.get('imdb_info', {}).get('year', ""))

                                    if aka:
                                        aka_trimmed = aka[4:].strip().lower() if aka.lower().startswith("aka") else aka.lower()
                                        difference = SequenceMatcher(None, title.lower(), aka_trimmed).ratio()
                                        if difference >= 0.7 or not aka_trimmed or aka_trimmed in title:
                                            aka = None

                                        if aka is not None:
                                            if f"({year})" in aka:
                                                aka = meta.get('imdb_info', {}).get('aka', "").replace(f"({year})", "").strip()
                                            else:
                                                aka = meta.get('imdb_info', {}).get('aka', "").strip()
                                            meta['aka'] = f"AKA {aka.strip()}"
                                        else:
                                            meta['aka'] = ""
                                    else:
                                        meta['aka'] = ""

            if meta.get('tvdb_series_name') and meta['category'] == "TV":
                series_name = meta.get('tvdb_series_name')
                if series_name and meta.get('title') != series_name:
                    if meta['debug']:
                        console.print(f"[yellow]tvdb series name: {series_name}")
                    year_match = re.search(r'\b(19|20)\d{2}\b', series_name)
                    if year_match:
                        extracted_year = year_match.group(0)
                        meta['search_year'] = extracted_year
                        series_name = re.sub(r'\s*\b(19|20)\d{2}\b\s*', '', series_name).strip()
                    series_name = series_name.replace('(', '').replace(')', '').strip()
                    if series_name and year_match:  # Only set if not empty and year was found
                        meta['title'] = series_name

        # bluray.com data if config
        get_bluray_info = self.config['DEFAULT'].get('get_bluray_info', False)
        meta['bluray_score'] = int(float(self.config['DEFAULT'].get('bluray_score', 100)))
        meta['bluray_single_score'] = int(float(self.config['DEFAULT'].get('bluray_single_score', 100)))
        meta['use_bluray_images'] = self.config['DEFAULT'].get('use_bluray_images', False)
        if meta.get('is_disc') in ("BDMV", "DVD") and get_bluray_info and (meta.get('distributor') is None or meta.get('region') is None) and meta.get('imdb_id') != 0 and not meta.get('emby', False) and not meta.get('edit', False) and not meta.get('site_check', False):
            releases = await get_bluray_releases(meta)

            if releases and meta.get('is_disc') in ("BDMV", "DVD") and meta.get('use_bluray_images', False):
                # and if we getting bluray/dvd images, we'll rehost them
                    url_host_mapping = {
                        "ibb.co": "imgbb",
                        "pixhost.to": "pixhost",
                        "imgbox.com": "imgbox",
                    }

                    approved_image_hosts = ['imgbox', 'imgbb', 'pixhost']
                    await self.rehost_images_manager.check_hosts(
                        meta,
                        "covers",
                        url_host_mapping=url_host_mapping,
                        img_host_index=1,
                        approved_image_hosts=approved_image_hosts,
                    )

        # user override check that only sets data after metadata setting
        if user_overrides and not meta.get('no_override', False) and not meta.get('emby', False):
            meta = await self.overrides.get_source_override(meta)

        meta['video'] = video

        if not meta.get('emby', False):
            meta['container'] = await video_manager.get_container(meta)

            meta['audio'], meta['channels'], meta['has_commentary'] = await self.audio_manager.get_audio_v2(mi_data, meta, bdinfo)

            meta['3D'] = await video_manager.is_3d(bdinfo)

            is_disc_value = str(meta.get('is_disc') or "")
            meta['source'], meta['type'] = await get_source(meta['type'], video, str(meta.get('path') or ""), is_disc_value, meta, folder_id, base_dir)

            meta['uhd'] = await video_manager.get_uhd(
                meta['type'],
                guessit_fn(str(meta.get('path') or "")),
                str(meta.get('resolution', '')),
                str(meta.get('path') or ""),
            )
            meta['hdr'] = await video_manager.get_hdr(mi_data, bdinfo)

            meta['distributor'] = await get_distributor(meta['distributor'])
            if meta['distributor'] is None:
                meta['distributor'] = ""

            if meta.get('is_disc', None) == "BDMV":  # Blu-ray Specific
                meta['region'] = await get_region(bdinfo, meta.get('region', None))
                meta['video_codec'] = await video_manager.get_video_codec(bdinfo)
            else:
                meta['video_encode'], meta['video_codec'], meta['has_encode_settings'], meta['bit_depth'] = await video_manager.get_video_encode(mi_data, meta['type'], bdinfo)

            if meta['region'] is None:
                meta['region'] = ""

            if meta.get('no_edition') is False:
                manual_edition = meta.get('manual_edition') or ""
                meta['edition'], meta['repack'], meta['webdv'] = await get_edition(meta['uuid'], bdinfo, meta['filelist'], manual_edition, meta)
                if "REPACK" in meta.get('edition', ""):
                    repack_match = re.search(r"REPACK[\d]?", meta['edition'])
                    if repack_match:
                        meta['repack'] = repack_match.group(0)
                    meta['edition'] = re.sub(r"REPACK[\d]?", "", meta['edition']).strip().replace('  ', ' ')
            else:
                meta['edition'] = ""

            meta['valid_mi_settings'] = True
            if not meta['is_disc'] and meta['type'] in ["ENCODE"] and meta['video_codec'] not in ["AV1"]:
                valid_mi_settings = validate_mediainfo(meta, debug=meta['debug'], settings=True)
                if not valid_mi_settings:
                    console.print("[red]MediaInfo validation failed. This file does not contain encode settings.")
                    meta['valid_mi_settings'] = False
                    await asyncio.sleep(2)

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
                                release_name, _, _ = await self.scene_manager.is_scene(videopath, meta, meta.get('imdb_id', 0), lower=True)
                                if release_name:
                                    try:
                                        meta['scene_name'] = release_name
                                        meta['tag'] = await get_tag(release_name, meta)
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

            if meta.get('service', None) in (None, ''):
                meta['service'], meta['service_longname'] = await get_service(video, meta.get('tag', ''), meta['audio'], meta['filename'])
            elif meta.get('service'):
                services = cast(dict[str, str], await get_service(get_services_only=True))
                service_code = str(meta.get('service') or '')
                meta['service_longname'] = max((k for k, v in services.items() if v == service_code), key=len, default=service_code)

            # Parse NFO for scene releases to get service
            if meta['scene'] and not meta.get('service') and meta['category'] == "TV":
                await self.parse_scene_nfo(meta)

            # Combine genres from TMDB and IMDb
            tmdb_genres = str(meta.get('genres') or '')
            imdb_genres = str(meta.get('imdb_info', {}).get('genres') or '')

            all_genres: list[str] = []
            if tmdb_genres:
                all_genres.extend([g.strip() for g in tmdb_genres.split(',') if g.strip()])
            if imdb_genres:
                all_genres.extend([g.strip() for g in imdb_genres.split(',') if g.strip()])

            seen: set[str] = set()
            unique_genres: list[str] = []
            for genre in all_genres:
                genre_lower = genre.lower()
                if genre_lower not in seen:
                    seen.add(genre_lower)
                    unique_genres.append(genre)

            meta['combined_genres'] = ', '.join(unique_genres) if unique_genres else ''

        # return duplicate ids so I don't have to catch every site file
        # this has the other advantage of stringing imdb for this object
        meta['tmdb'] = meta.get('tmdb_id')
        imdb_id_value = _to_int(meta.get('imdb_id'))
        if imdb_id_value != 0:
            imdb_str = str(imdb_id_value).zfill(7)
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

    async def get_cat(self, _video: str, meta: dict[str, Any]) -> Optional[str]:
        if meta.get('manual_category'):
            manual_category = meta.get('manual_category')
            return manual_category.upper() if isinstance(manual_category, str) else None

        path_patterns = [
            r'(?i)[\\/](?:tv|tvshows|tv.shows|series|shows)[\\/]',
            r'(?i)[\\/](?:season\s*\d+|s\d+)[\\/]',
            r'(?i)[\\/](?:s\d{1,2}e\d{1,2}|s\d{1,2}|season\s*\d+)',
            r'(?i)(?:tv pack|season\s*\d+)'
        ]

        filename_patterns = [
            r'(?i)s\d{1,2}e\d{1,2}',
            r'(?i)s\d{1,2}',
            r'(?i)\b\d{1,2}x\d{2}\b',
            r'(?i)(?:season|series)\s*\d+',
            r'(?i)e\d{2,3}\s*\-',
            r'(?i)\d{4}\.\d{1,2}\.\d{1,2}'
        ]

        path = meta.get('path', '')
        uuid = meta.get('uuid', '')
        if meta.get('debug', False):
            console.print(f"[cyan]Checking category for path: {path} and uuid: {uuid}[/cyan]")

        for pattern in path_patterns:
            if re.search(pattern, path):
                if meta.get('debug', False):
                    console.print(f"[cyan]Matched TV pattern in path: {pattern}[/cyan]")
                return "TV"

        for pattern in filename_patterns:
            if re.search(pattern, uuid) or re.search(pattern, os.path.basename(path)):
                if meta.get('debug', False):
                    console.print(f"[cyan]Matched TV pattern in filename: {pattern}[/cyan]")
                return "TV"

        if "subsplease" in path.lower() or "subsplease" in uuid.lower():
            anime_pattern = r'(?:\s-\s)?(\d{1,3})\s*\((?:\d+p|480p|480i|576i|576p|720p|1080i|1080p|2160p)\)'
            if re.search(anime_pattern, path.lower()) or re.search(anime_pattern, uuid.lower()):
                if meta.get('debug', False):
                    console.print(f"[cyan]Matched Anime pattern for SubsPlease: {anime_pattern}[/cyan]")
                return "TV"

        return "MOVIE"

    async def stream_optimized(self, stream_opt: bool) -> int:
        stream = 1 if stream_opt is True else 0
        return stream

    async def parse_scene_nfo(self, meta: dict[str, Any]) -> None:
        try:
            nfo_file = meta.get('scene_nfo_file', '')

            if not nfo_file:
                if meta['debug']:
                    console.print("[yellow]No NFO file found for scene release[/yellow]")
                return

            if meta['debug']:
                console.print(f"[cyan]Parsing NFO file: {nfo_file}[/cyan]")

            async with aiofiles.open(nfo_file, encoding='utf-8', errors='ignore') as f:
                nfo_content = await f.read()

            # Parse Source field
            source_match = re.search(r'^Source\s*:\s*(.+?)$', nfo_content, re.MULTILINE | re.IGNORECASE)
            if source_match:
                nfo_source = source_match.group(1).strip()
                if meta['debug']:
                    console.print(f"[cyan]Found source in NFO: {nfo_source}[/cyan]")

                # Check if source matches any service
                services = cast(dict[str, str], await get_service(get_services_only=True))

                # Exact match
                for service_name, service_code in services.items():
                    if nfo_source.upper() == service_name.upper() or nfo_source.upper() == service_code.upper():
                        meta['service'] = service_code
                        meta['service_longname'] = service_name
                        if meta['debug']:
                            console.print(f"[green]Matched service: {service_code} ({service_name})[/green]")
                        break

        except Exception as e:
            if meta['debug']:
                console.print(f"[red]Error parsing NFO file: {e}[/red]")
