# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import asyncio
import os
import re
import sys
from collections.abc import Mapping
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Optional, cast

import anitopy
import guessit
import httpx

from src.console import console
from src.exceptions import *  # noqa: F403
from src.tags import get_tag
from src.tmdb import TmdbManager

guessit_module: Any = cast(Any, guessit)
GuessitFn = Callable[[str, Optional[dict[str, Any]]], dict[str, Any]]


def guessit_fn(value: str, options: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return cast(dict[str, Any], guessit_module.guessit(value, options))

Meta = dict[str, Any]


def _guessit_data(value: str, options: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return guessit_fn(value, options)


def _anitopy_parse(value: str) -> dict[str, Any]:
    anitopy_any = cast(Any, anitopy)
    return cast(dict[str, Any], anitopy_any.parse(value) or {})


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class SeasonEpisodeManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self.tmdb_manager = TmdbManager(config)

    async def get_season_episode(self, video: str, meta: Meta) -> Meta:
        if meta['category'] == 'TV':
            filelist = cast(list[str], meta.get('filelist', []))
            meta['tv_pack'] = 0
            is_daily = False
            season_int = 1
            episode_int = 0
            season = "S01"
            episode = ""
            romaji = ""
            eng_title = ""
            anilist_episodes = 0
            if not meta.get('anime'):
                try:
                    daily_match = re.search(r"\d{4}[-\.]\d{2}[-\.]\d{2}", video)
                    if (meta.get('manual_date') or daily_match) and not meta.get('manual_season'):
                        # Handle daily episodes
                        # The user either provided the --daily argument or a date was found in the filename

                        if meta.get('manual_date') is None and daily_match is not None:
                            meta['manual_date'] = daily_match.group().replace('.', '-')
                        is_daily = True
                        guess_data = _guessit_data(video)
                        guess_date_raw = meta.get('manual_date') or guess_data.get('date')
                        guess_date = str(guess_date_raw) if guess_date_raw else ""
                        tmdb_id_value = _safe_int(meta.get('tmdb_id', 0), 0)
                        season_int, episode_int = await self.tmdb_manager.daily_to_tmdb_season_episode(tmdb_id_value, guess_date)

                        season = f"S{str(season_int).zfill(2)}"
                        episode = f"E{str(episode_int).zfill(2)}"
                        # For daily shows, pass the supplied date as the episode title
                        # Season and episode will be stripped later to conform with standard daily episode naming format
                        meta['daily_episode_title'] = meta.get('manual_date')

                    else:
                        try:
                            guess_year = str(_guessit_data(video).get('year') or "")
                        except Exception:
                            guess_year = ""
                        try:
                            guess_data = _guessit_data(video)
                            season_guess = str(guess_data.get("season") or "")
                            if season_guess == guess_year:
                                if f"s{season_guess}" in video.lower():
                                    season_int = int(season_guess)
                                    season = "S" + str(season_int).zfill(2)
                                else:
                                    season_int = 1
                                    season = "S01"
                            else:
                                season_int = int(guess_data.get("season") or 1)
                                season = "S" + str(season_int).zfill(2)
                        except Exception:
                            console.print("[bold yellow]There was an error guessing the season number. Guessing S01. Use [bold green]--season #[/bold green] to correct if needed")
                            season_int = 1
                            season = "S01"

                except Exception:
                    console.print_exception()
                    season_int = 1
                    season = "S01"

                try:
                    if is_daily is not True:
                        episodes = ""
                        if len(filelist) == 1:
                            guess_data = _guessit_data(video)
                            episodes = guess_data.get('episode')
                            if isinstance(episodes, list):
                                episode = ""
                                episodes_list = cast(list[Any], episodes)
                                for item in episodes_list:
                                    ep = (str(item).zfill(2))
                                    episode += f"E{ep}"
                                episode_int = _safe_int(episodes_list[0], 0) if episodes_list else 0
                            else:
                                episode_int = _safe_int(episodes, 0)
                                episode = "E" + str(episode_int).zfill(2) if episodes is not None else ""
                        else:
                            episode = ""
                            episode_int = 0
                            meta['tv_pack'] = 1
                except Exception:
                    episode = ""
                    episode_int = 0
                    meta['tv_pack'] = 1

            else:
                # If Anime
                # if the mal id is set, then we've already run get_romaji in tmdb.py
                if meta.get('mal_id') == 0 and meta['category'] == "TV":
                    parsed = _anitopy_parse(Path(video).name)
                    romaji, mal_id, eng_title, seasonYear, anilist_episodes, meta['demographic'] = await self.tmdb_manager.get_romaji(
                        str(parsed.get('anime_title', '')),
                        _safe_int(meta.get('mal_id', 0), 0),
                        meta,
                    )
                    mal_id_value = _safe_int(mal_id, 0)
                    if mal_id_value:
                        meta['mal_id'] = mal_id_value
                    anilist_episodes = _safe_int(anilist_episodes, 0)
                    if meta.get('tmdb_id') == 0:
                        year = str(parsed.get('anime_year', str(seasonYear)))
                        guess_title = _guessit_data(str(parsed.get('anime_title', '')), {"excludes": ["country", "language"]}).get('title', '')
                        tmdb_id_value, category_value = await self.tmdb_manager.get_tmdb_id(str(guess_title), year, meta, meta['category'])
                        meta['tmdb_id'] = tmdb_id_value
                        meta['category'] = category_value
                    # meta = await tmdb_other_meta(meta)
                if meta.get('mal_id') != 0 and meta['category'] == "TV":
                    parsed = _anitopy_parse(Path(video).name)
                    tag = str(parsed.get('release_group', ""))
                    if tag != "" and meta.get('tag') is None:
                        meta['tag'] = f"-{tag}"
                    if len(filelist) == 1:
                        try:
                            guess_data = _guessit_data(video)
                            episodes = parsed.get('episode_number', guess_data.get('episode', '1'))
                            if not isinstance(episodes, list) and not str(episodes).isnumeric():
                                episodes = guess_data.get('episode')
                            if isinstance(episodes, list):
                                episodes_list = cast(list[Any], episodes)
                                episode_int = _safe_int(episodes_list[0], 1) if episodes_list else 1
                                episode = "".join([f"E{str(_safe_int(item, 0)).zfill(2)}" for item in episodes_list])
                            else:
                                episode_int = _safe_int(episodes, 1)
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
                            season_int = _safe_int(meta.get('season_int'), 1)
                        else:
                            guess_data = _guessit_data(video)
                            season_value = parsed.get('anime_season', guess_data.get('season', '1'))
                            season_int = _safe_int(season_value, 1)
                        season = f"S{season_int:02d}"
                    except Exception:
                        try:
                            if episode_int >= anilist_episodes:
                                params = {
                                    'id': str(meta['tvdb_id']),
                                    'origin': 'tvdb',
                                    'absolute': str(episode_int),
                                }
                                url = "https://thexem.info/map/single"
                                async with httpx.AsyncClient(timeout=30.0) as client:
                                    response = (await client.post(url, params=params)).json()
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
                                async with httpx.AsyncClient(timeout=30.0) as client:
                                    names_response = (await client.get(names_url)).json()
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
                                season = _guessit_data(video).get('season', '1')
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
                manual_season_str = str(meta['manual_season']).lower().replace('s', '')
                meta['daily_episode_title'] = None  # Clear daily episode title if manual season is set
                season_int = _safe_int(manual_season_str, 1)
                meta['season'] = f"S{manual_season_str.zfill(2)}"
            if meta.get('manual_episode', None) is None:
                meta['episode'] = episode
            else:
                manual_episode_str = str(meta['manual_episode']).lower().replace('e', '')
                episode_int = _safe_int(manual_episode_str, 0)
                meta['episode'] = f"E{manual_episode_str.zfill(2)}"
                meta['tv_pack'] = 0

            # if " COMPLETE " in Path(video).name.replace('.', ' '):
            #     meta['season'] = "COMPLETE"
            meta['season_int'] = season_int
            meta['episode_int'] = episode_int

            # Manual episode title
            if 'manual_episode_title' in meta and meta['manual_episode_title']:
                meta['episode_title'] = meta.get('manual_episode_title')

            # Guess the part of the episode (if available)
            meta['part'] = ""
            if meta['tv_pack'] == 1:
                part = _guessit_data(os.path.dirname(video)).get('part')
                meta['part'] = f"Part {part}" if part else ""

        return meta

    async def check_season_pack_completeness(self, meta: Meta) -> None:
        completeness = cast(Mapping[str, Any], await self.check_season_pack_detail(meta))
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
                        response = await asyncio.to_thread(input, f"Show (n)ext {batch_size} files, (a)ll remaining files, (c)ontinue with incomplete pack, or (q)uit? (n/a/c/Q): ")
                    else:
                        response = await asyncio.to_thread(input, f"Show (a)ll remaining {remaining_files} files, (c)ontinue with incomplete pack, or (q)uit? (a/c/Q): ")

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
                    response = await asyncio.to_thread(input, "Continue with incomplete season pack? (y/N): ")
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

    async def check_season_pack_detail(self, meta: Meta) -> dict[str, Any]:
        if not meta.get('tv_pack'):
            return {'complete': True, 'missing_episodes': [], 'found_episodes': [], 'consistent_tags': True, 'tags_found': {}}

        files = cast(list[str], meta.get('filelist', []))
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
            episode_only_matches: list[tuple[str, str]] = []

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

        missing_episodes: list[tuple[int, int]] = []

        # Check each season for completeness
        for season in season_numbers:
            season_episodes = [ep for s, ep in found_episodes if s == season]
            if not season_episodes:
                continue

            min_ep = min(season_episodes)
            max_ep = max(season_episodes)

            # Check for missing episodes in the range
            missing_episodes.extend(
                [(season, ep_num) for ep_num in range(min_ep, max_ep + 1) if ep_num not in season_episodes]
            )

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


