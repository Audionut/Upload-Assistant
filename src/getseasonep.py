# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import anitopy
import requests
from guessit import guessit

from src.console import console
from src.exceptions import *  # noqa: F403
from src.tags import get_tag
from src.tmdb import daily_to_tmdb_season_episode, get_romaji, get_tmdb_id


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
                    try:
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
                        console.print("[bold yellow]There was an error guessing the season number. Guessing S01. Use [bold green]--season #[/bold green] to correct if needed")
                        season_int = "1"
                        season = "S01"

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
                romaji, mal_id, eng_title, seasonYear, anilist_episodes, meta['demographic'] = await get_romaji(parsed['anime_title'], meta.get('mal_id', 0), meta)
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
                            response = requests.post(url, params=params, timeout=30).json()
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
                            names_response = requests.get(names_url, timeout=30).json()
                            if meta['debug']:
                                console.log(f'[cyan]Matching Season Number from TheXEM\n{names_response}')
                            difference: float = 0.0
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
                console.print("[bold red]Error determining if TV show is anime or not[/bold red]")
                console.print("[bold yellow]Set manual season and episode[/bold yellow]")
                season_int = 1
                season = "S01"
                episode_int = 1
                episode = "E01"

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


async def check_season_pack_completeness(meta):
    completeness = await check_season_pack_detail(meta)
    if not completeness['complete']:
        just_go = False
        unattended = meta.get('unattended', False)
        unattended_confirm = meta.get('unattended_confirm', False)
        try:
            missing_list = [f"S{s:02d}E{e:02d}" for s, e in completeness['missing_episodes']]
        except ValueError:
            console.print("[red]Error determining missing episodes, you should double check the pack manually.")
            missing_list = ["Unknown"]
        if 'Unknown' not in missing_list:
            console.print("[red]Warning: Season pack appears incomplete!")
            console.print(f"[yellow]Missing episodes: {', '.join(missing_list)}")
        else:
            console.print("[red]Warning: Season pack appears incomplete (missing episodes could not be determined).")

        # In unattended mode with no confirmation prompts, ensure we always log that we're proceeding.
        if unattended and not unattended_confirm:
            console.print("[yellow]Unattended mode: continuing despite incomplete season pack (no confirmation).")

        if 'Unknown' not in missing_list:
            # Show first 15 files from filelist
            filelist = meta['filelist']
            files_shown = 0
            batch_size = 15

            console.print(f"[cyan]Filelist ({len(filelist)} files):")
            for i, file in enumerate(filelist[:batch_size]):
                console.print(f"[cyan]  {i+1:2d}. {os.path.basename(file)}")

            files_shown = min(batch_size, len(filelist))

            # Loop to handle showing more files in batches
            while files_shown < len(filelist) and (not unattended or unattended_confirm):
                remaining_files = len(filelist) - files_shown
                console.print(f"[yellow]... and {remaining_files} more files")

                if remaining_files > batch_size:
                    response = input(f"Show (n)ext {batch_size} files, (a)ll remaining files, (c)ontinue with incomplete pack, or (q)uit? (n/a/c/Q): ")
                else:
                    response = input(f"Show (a)ll remaining {remaining_files} files, (c)ontinue with incomplete pack, or (q)uit? (a/c/Q): ")

                if response.lower() == 'n' and remaining_files > batch_size:
                    # Show next batch of files
                    next_batch = filelist[files_shown:files_shown + batch_size]
                    for i, file in enumerate(next_batch):
                        console.print(f"[cyan]  {files_shown + i + 1:2d}. {os.path.basename(file)}")
                    files_shown += len(next_batch)
                elif response.lower() == 'a':
                    # Show all remaining files
                    remaining_batch = filelist[files_shown:]
                    for i, file in enumerate(remaining_batch):
                        console.print(f"[cyan]  {files_shown + i + 1:2d}. {os.path.basename(file)}")
                    files_shown = len(filelist)
                elif response.lower() == 'c':
                    just_go = True
                    break  # Continue with incomplete pack
                else:  # 'q' or any other input
                    console.print("[red]Aborting torrent creation due to incomplete season pack")
                    sys.exit(1)

            # Final confirmation if not in unattended mode
            if (not unattended or unattended_confirm) and not just_go:
                response = input("Continue with incomplete season pack? (y/N): ")
                if response.lower() != 'y':
                    console.print("[red]Aborting torrent creation due to incomplete season pack")
                    sys.exit(1)
    else:
        if meta.get('debug', False):
            console.print("[green]Season pack completeness verified")

    if not completeness['consistent_tags']:
        console.print("[yellow]Warning: Multiple group tags detected in season pack!")
        for tag, files in completeness['tags_found'].items():
            console.print(f"[cyan]Tag: {tag} found in files:")
            for file in files:
                console.print(f"[cyan]  - {file}")


async def check_season_pack_detail(meta):
    if not meta.get('tv_pack'):
        return {'complete': True, 'missing_episodes': [], 'found_episodes': [], 'consistent_tags': True, 'tags_found': {}}

    files = meta.get('filelist', [])
    if not files:
        return {'complete': True, 'missing_episodes': [], 'found_episodes': [], 'consistent_tags': True, 'tags_found': {}}

    found_episodes: list[tuple[int, int]] = []
    season_numbers: set[int] = set()
    tags_found: dict[str, list[str]] = {}  # tag -> list of files with that tag

    # Pattern for standard TV shows: S01E01, S01E01E02
    episode_pattern = r'[Ss](\d{1,2})[Ee](\d{1,3})(?:[Ee](\d{1,3}))?'

    # Pattern for episode-only: E01, E01E02 (without season)
    episode_only_pattern = r'\b[Ee](\d{1,3})(?:[Ee](\d{1,3}))?\b'

    # Pattern for anime: " - 43 (1080p)" or "43 (1080p)" or similar
    anime_pattern = r'(?:\s-\s)?(\d{1,3})\s*\((?:\d+p|480p|480i|576i|576p|720p|1080i|1080p|2160p)\)'

    # Normalize season_int once so all (season, episode) tuples are (int, int)
    raw_season_int = meta.get('season_int', 1)
    try:
        default_season_num = int(raw_season_int)
    except (TypeError, ValueError):
        default_season_num = 1

    for file_path in files:
        filename = os.path.basename(file_path)

        # Extract group tag from each file
        file_tag = await get_tag(file_path, meta, season_pack_check=True)
        if file_tag:
            tag_clean = file_tag.lstrip('-')
            if tag_clean not in tags_found:
                tags_found[tag_clean] = []
            tags_found[tag_clean].append(filename)

        matches = re.findall(episode_pattern, filename)

        for match in matches:
            season_str = match[0]
            episode1_str = match[1]
            episode2_str = match[2] if match[2] else None

            season_num = int(season_str)
            episode1_num = int(episode1_str)
            found_episodes.append((season_num, episode1_num))
            season_numbers.add(season_num)

            if episode2_str:
                episode2_num = int(episode2_str)
                found_episodes.append((season_num, episode2_num))

        if not matches:
            episode_only_matches = re.findall(episode_only_pattern, filename)
            for match in episode_only_matches:
                episode1_num = int(match[0])
                episode2_optional = int(match[1]) if match[1] else None

                season_num = default_season_num
                found_episodes.append((season_num, episode1_num))
                season_numbers.add(season_num)

                if episode2_optional is not None:
                    found_episodes.append((season_num, episode2_optional))

        if not matches and not episode_only_matches:
            anime_matches = re.findall(anime_pattern, filename)
            for match in anime_matches:
                episode_num = int(match)
                season_num = default_season_num
                found_episodes.append((season_num, episode_num))
                season_numbers.add(season_num)

    if not found_episodes:
        console.print("[red]No episodes found in the season pack files.")
        # return true to not annoy the user with bad regex
        return {'complete': True, 'missing_episodes': [], 'found_episodes': [], 'consistent_tags': True, 'tags_found': tags_found}

    # Remove duplicates and sort
    found_episodes = sorted(set(found_episodes))

    missing_episodes = []

    # Check each season for completeness
    for season in season_numbers:
        season_episodes = [ep for s, ep in found_episodes if s == season]
        if not season_episodes:
            continue

        min_ep = min(season_episodes)
        max_ep = max(season_episodes)

        # Check for missing episodes in the range
        for ep_num in range(min_ep, max_ep + 1):
            if ep_num not in season_episodes:
                missing_episodes.append((season, ep_num))

    is_complete = len(missing_episodes) == 0

    # Check if all files have the same group tag
    consistent_tags = len(tags_found) <= 1

    result = {
        'complete': is_complete,
        'missing_episodes': missing_episodes,
        'found_episodes': found_episodes,
        'seasons': list(season_numbers),
        'consistent_tags': consistent_tags,
        'tags_found': tags_found
    }

    if meta.get('debug'):
        console.print("[cyan]Season pack completeness check:")
        console.print(f"[cyan]Found episodes: {found_episodes}")
        if missing_episodes:
            console.print(f"[red]Missing episodes: {missing_episodes}")
        else:
            console.print("[green]Season pack episode list appears complete")
        if tags_found:
            console.print(f"[cyan]Group tags found: {list(tags_found.keys())}")
            if not consistent_tags:
                console.print("[yellow]Warning: Multiple group tags detected in season pack")

    return result
