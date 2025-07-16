from src.console import console
from guessit import guessit
import anitopy
from pathlib import Path
import asyncio
import requests
import os
import re
from difflib import SequenceMatcher
from src.tmdb import get_tmdb_id, daily_to_tmdb_season_episode, get_romaji
from src.exceptions import *  # noqa: F403


async def get_season_episode(video, meta):
    if meta['category'] == 'TV':
        filelist = meta['filelist']
        meta['tv_pack'] = 0
        is_daily = False
        if not meta.get('anime'):
            try:
                daily_match = re.search(r"\d{4}[-\.]\d{2}[-\.]\d{2}", video)
                if meta.get('manual_date') or daily_match:
                    # Handle daily episodes
                    # The user either provided the --daily argument or a date was found in the filename

                    if meta.get('manual_date') is None and daily_match is not None:
                        meta['manual_date'] = daily_match.group().replace('.', '-')
                    is_daily = True
                    guess_date = meta.get('manual_date', guessit(video).get('date')) if meta.get('manual_date') else guessit(video).get('date')
                    season_int, episode_int = await daily_to_tmdb_season_episode(meta.get('tmdb_id'), guess_date)

                    season = f"S{str(season_int).zfill(2)}"
                    episode = f"E{str(episode_int).zfill(2)}"
                    # For daily shows, pass the supplied date as the episode title
                    # Season and episode will be stripped later to conform with standard daily episode naming format
                    meta['daily_episode_title'] = meta.get('manual_date')

                else:
                    try:
                        guess_year = guessit(video)['year']
                    except Exception:
                        guess_year = ""
                    if guessit(video)["season"] == guess_year:
                        if f"s{guessit(video)['season']}" in video.lower():
                            season_int = str(guessit(video)["season"])
                            season = "S" + season_int.zfill(2)
                        else:
                            season_int = "1"
                            season = "S01"
                    else:
                        season_int = str(guessit(video)["season"])
                        season = "S" + season_int.zfill(2)

            except Exception:
                console.print_exception()
                season_int = "1"
                season = "S01"

            try:
                if is_daily is not True:
                    episodes = ""
                    if len(filelist) == 1:
                        episodes = guessit(video)['episode']
                        if isinstance(episodes, list):
                            episode = ""
                            for item in guessit(video)["episode"]:
                                ep = (str(item).zfill(2))
                                episode += f"E{ep}"
                            episode_int = episodes[0]
                        else:
                            episode_int = str(episodes)
                            episode = "E" + str(episodes).zfill(2)
                    else:
                        episode = ""
                        episode_int = "0"
                        meta['tv_pack'] = 1
            except Exception:
                episode = ""
                episode_int = "0"
                meta['tv_pack'] = 1

        else:
            # If Anime
            # if the mal id is set, then we've already run get_romaji in tmdb.py
            if meta.get('mal_id') == 0 and meta['category'] == "TV":
                parsed = anitopy.parse(Path(video).name)
                romaji, mal_id, eng_title, seasonYear, anilist_episodes, meta['demographic'] = await get_romaji(parsed['anime_title'], meta.get('mal_id', 0))
                if mal_id:
                    meta['mal_id'] = mal_id
                if meta.get('tmdb_id') == 0:
                    year = parsed.get('anime_year', str(seasonYear))
                    meta = await get_tmdb_id(guessit(parsed['anime_title'], {"excludes": ["country", "language"]})['title'], year, meta, meta['category'])
                # meta = await tmdb_other_meta(meta)
            if meta.get('mal_id') != 0 and meta['category'] == "TV":
                parsed = anitopy.parse(Path(video).name)
                tag = parsed.get('release_group', "")
                if tag != "" and meta.get('tag') is None:
                    meta['tag'] = f"-{tag}"
                if len(filelist) == 1:
                    try:
                        episodes = parsed.get('episode_number', guessit(video).get('episode', '1'))
                        if not isinstance(episodes, list) and not episodes.isnumeric():
                            episodes = guessit(video)['episode']
                        if isinstance(episodes, list):
                            episode_int = int(episodes[0])  # Always convert to integer
                            episode = "".join([f"E{str(int(item)).zfill(2)}" for item in episodes])
                        else:
                            episode_int = int(episodes)  # Convert to integer
                            episode = f"E{str(episode_int).zfill(2)}"
                    except Exception:
                        episode_int = 1
                        episode = "E01"

                        if meta.get('uuid'):
                            # Look for episode patterns in uuid
                            episode_patterns = [
                                r'[Ee](\d+)[Ee](\d+)',
                                r'[Ee](\d+)',
                                r'[Ee]pisode[\s_]*(\d+)',
                                r'[\s_\-](\d+)[\s_\-]',
                                r'[\s_\-](\d+)$',
                                r'^(\d+)[\s_\-]',
                            ]

                            for pattern in episode_patterns:
                                match = re.search(pattern, meta['uuid'], re.IGNORECASE)
                                if match:
                                    try:
                                        episode_int = int(match.group(1))
                                        episode = f"E{str(episode_int).zfill(2)}"
                                        break
                                    except (ValueError, IndexError):
                                        continue

                        if episode_int == 1:  # Still using fallback
                            console.print('[bold yellow]There was an error guessing the episode number. Guessing E01. Use [bold green]--episode #[/bold green] to correct if needed')

                        await asyncio.sleep(1.5)
                else:
                    episode = ""
                    episode_int = 0  # Ensure it's an integer
                    meta['tv_pack'] = 1

                try:
                    if meta.get('season_int'):
                        season_int = int(meta.get('season_int'))  # Convert to integer
                    else:
                        season = parsed.get('anime_season', guessit(video).get('season', '1'))
                        season_int = int(season)  # Convert to integer
                    season = f"S{str(season_int).zfill(2)}"
                except Exception:
                    try:
                        if episode_int >= anilist_episodes:
                            params = {
                                'id': str(meta['tvdb_id']),
                                'origin': 'tvdb',
                                'absolute': str(episode_int),
                            }
                            url = "https://thexem.info/map/single"
                            response = requests.post(url, params=params).json()
                            if response['result'] == "failure":
                                raise XEMNotFound  # noqa: F405
                            if meta['debug']:
                                console.log(f"[cyan]TheXEM Absolute -> Standard[/cyan]\n{response}")
                            season_int = int(response['data']['scene']['season'])  # Convert to integer
                            season = f"S{str(season_int).zfill(2)}"
                            if len(filelist) == 1:
                                episode_int = int(response['data']['scene']['episode'])  # Convert to integer
                                episode = f"E{str(episode_int).zfill(2)}"
                        else:
                            season_int = 1  # Default to 1 if error occurs
                            season = "S01"
                            names_url = f"https://thexem.info/map/names?origin=tvdb&id={str(meta['tvdb_id'])}"
                            names_response = requests.get(names_url).json()
                            if meta['debug']:
                                console.log(f'[cyan]Matching Season Number from TheXEM\n{names_response}')
                            difference = 0
                            if names_response['result'] == "success":
                                for season_num, values in names_response['data'].items():
                                    for lang, names in values.items():
                                        if lang == "jp":
                                            for name in names:
                                                romaji_check = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", romaji.lower().replace(' ', ''))
                                                name_check = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", name.lower().replace(' ', ''))
                                                diff = SequenceMatcher(None, romaji_check, name_check).ratio()
                                                if romaji_check in name_check and diff >= difference:
                                                    season_int = int(season_num) if season_num != "all" else 1  # Convert to integer
                                                    season = f"S{str(season_int).zfill(2)}"
                                                    difference = diff
                                        if lang == "us":
                                            for name in names:
                                                eng_check = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", eng_title.lower().replace(' ', ''))
                                                name_check = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", name.lower().replace(' ', ''))
                                                diff = SequenceMatcher(None, eng_check, name_check).ratio()
                                                if eng_check in name_check and diff >= difference:
                                                    season_int = int(season_num) if season_num != "all" else 1  # Convert to integer
                                                    season = f"S{str(season_int).zfill(2)}"
                                                    difference = diff
                            else:
                                raise XEMNotFound  # noqa: F405
                    except Exception:
                        if meta['debug']:
                            console.print_exception()
                        try:
                            season = guessit(video).get('season', '1')
                            season_int = int(season)  # Convert to integer
                        except Exception:
                            season_int = 1  # Default to 1 if error occurs
                            season = "S01"
                        console.print(f"[bold yellow]{meta['title']} does not exist on thexem, guessing {season}")
                        console.print(f"[bold yellow]If [green]{season}[/green] is incorrect, use --season to correct")
                        await asyncio.sleep(3)
            else:
                return meta

        if meta.get('manual_season', None) is None:
            meta['season'] = season
        else:
            season_int = meta['manual_season'].lower().replace('s', '')
            meta['season'] = f"S{meta['manual_season'].lower().replace('s', '').zfill(2)}"
        if meta.get('manual_episode', None) is None:
            meta['episode'] = episode
        else:
            episode_int = meta['manual_episode'].lower().replace('e', '')
            meta['episode'] = f"E{meta['manual_episode'].lower().replace('e', '').zfill(2)}"
            meta['tv_pack'] = 0

        # if " COMPLETE " in Path(video).name.replace('.', ' '):
        #     meta['season'] = "COMPLETE"
        meta['season_int'] = season_int
        meta['episode_int'] = episode_int

        # Manual episode title
        if 'manual_episode_title' in meta and meta['manual_episode_title'] == "":
            meta['episode_title'] = meta.get('manual_episode_title')

        # Guess the part of the episode (if available)
        meta['part'] = ""
        if meta['tv_pack'] == 1:
            part = guessit(os.path.dirname(video)).get('part')
            meta['part'] = f"Part {part}" if part else ""

    return meta
