# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import re
import asyncio
from data.config import config
from src.console import console
from src.tvmaze import search_tvmaze, get_tvmaze_episode_data
from src.imdb import get_imdb_info_api
from src.tmdb import tmdb_other_meta, get_tmdb_from_imdb, get_episode_details, get_season_details
from src.tvdb import tvdb_data

tvdb_handler = tvdb_data(config)


async def all_ids(meta):
    if meta['debug']:
        console.print("[yellow]Starting metadata retrieval with all IDs present[/yellow]")
    # Create a list of all tasks to run in parallel
    all_tasks = [
        # Core metadata tasks
        tmdb_other_meta(
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
            tvdb_id=meta.get('tvdb_id', 0)
        ),
        get_imdb_info_api(
            meta['imdb_id'],
            manual_language=meta.get('manual_language'),
            debug=meta.get('debug', False)
        )
    ]

    # Always add get_tvdb_episodes for TV category
    if meta.get('category') == 'TV':
        tvdb_episodes_task = tvdb_handler.get_tvdb_episodes(
            meta['tvdb_id'],
            meta.get('debug', False)
        )
        all_tasks.append(tvdb_episodes_task)

    # Add episode-specific tasks if this is a TV show with episodes
    if (meta['category'] == 'TV' and not meta.get('tv_pack', False) and
            'season_int' in meta and 'episode_int' in meta and meta.get('episode_int') != 0):

        # Add TVMaze episode details task
        all_tasks.append(
            get_tvmaze_episode_data(
                meta.get('tvmaze_id'),
                meta.get('season_int'),
                meta.get('episode_int')
            )
        )
        # TMDb last
        all_tasks.append(
            get_episode_details(
                meta.get('tmdb_id'),
                meta.get('season_int'),
                meta.get('episode_int'),
                debug=meta.get('debug', False)
            )
        )
    elif meta['category'] == 'TV' and meta.get('tv_pack', False) and 'season_int' in meta:
        # For TV packs, we might want to get season details instead
        all_tasks.append(
            get_season_details(
                meta.get('tmdb_id'),
                meta.get('season_int'),
                debug=meta.get('debug', False)
            )
        )

    # Execute all tasks in parallel
    try:
        results = await asyncio.gather(*all_tasks, return_exceptions=True)
    except Exception as e:
        console.print(f"[red]Error occurred while gathering tasks: {e}[/red]")
        return meta

    # Process core metadata results
    try:
        tmdb_metadata, imdb_info = results[0:2]
    except Exception as e:
        console.print(f"[red]Error occurred while processing core metadata: {e}[/red]")
        pass
    result_index = 2  # Start processing episode data from this index

    # Process TMDB metadata
    if not isinstance(tmdb_metadata, Exception) and tmdb_metadata:
        meta.update(tmdb_metadata)
    else:
        console.print("[yellow]Warning: Could not get TMDB metadata")

    # Process IMDB info
    if isinstance(imdb_info, dict):
        meta['imdb_info'] = imdb_info

    elif isinstance(imdb_info, Exception):
        console.print(f"[red]IMDb API call failed: {imdb_info}[/red]")
        meta['imdb_info'] = meta.get('imdb_info', {})  # Keep previous IMDb info if it exists
    else:
        console.print("[red]Unexpected IMDb response, setting imdb_info to empty.[/red]")
        meta['imdb_info'] = {}

    # Process TVDB episodes data if it was requested for TV category
    if meta.get('category') == 'TV':
        tvdb_episode_data = results[result_index]
        result_index += 1
        if tvdb_episode_data and not isinstance(tvdb_episode_data, Exception):
            # tvdb_episode_data is a tuple: (episodes_list, series_name)
            if isinstance(tvdb_episode_data, tuple) and len(tvdb_episode_data) == 2:
                episodes_data, series_name = tvdb_episode_data
                meta['tvdb_episode_data'] = episodes_data
                if series_name:
                    meta['tvdb_series_name'] = series_name
                meta['we_checked_tvdb'] = True
            else:
                console.print(f"[yellow]Unexpected TVDb data format: {type(tvdb_episode_data)}[/yellow]")
        elif isinstance(tvdb_episode_data, Exception):
            console.print(f"[yellow]TVDb episode data retrieval failed: {tvdb_episode_data}[/yellow]")

    # Process episode data if this is a TV show
    if meta['category'] == 'TV' and not meta.get('tv_pack', False) and meta.get('episode_int', 0) != 0:
        # Process TVMaze episode data
        tvmaze_episode_data = results[result_index]
        result_index += 1

        if not isinstance(tvmaze_episode_data, Exception) and tvmaze_episode_data:
            meta['tvmaze_episode_data'] = tvmaze_episode_data
            meta['we_asked_tvmaze'] = True
        elif isinstance(tvmaze_episode_data, Exception):
            console.print(f"[yellow]TVMaze episode data retrieval failed: {tvmaze_episode_data}")

        # Process TMDb episode data
        tmdb_episode_data = results[result_index]
        result_index += 1

        if not isinstance(tmdb_episode_data, Exception) and tmdb_episode_data:
            meta['tmdb_episode_data'] = tmdb_episode_data
            meta['we_checked_tmdb'] = True
        elif isinstance(tmdb_episode_data, Exception):
            console.print(f"[yellow]TMDb episode data retrieval failed: {tmdb_episode_data}")

    elif meta['category'] == 'TV' and meta.get('tv_pack', False) and 'season_int' in meta:
        # Process TMDb season data for TV packs
        tmdb_season_data = results[result_index]
        result_index += 1

        if not isinstance(tmdb_season_data, Exception) and tmdb_season_data:
            meta['tmdb_season_data'] = tmdb_season_data
            meta['we_checked_tmdb'] = True
        elif isinstance(tmdb_season_data, Exception):
            console.print(f"[yellow]TMDb season data retrieval failed: {tmdb_season_data}[/yellow]")

    return meta


async def imdb_tmdb_tvdb(meta, filename):
    if meta['debug']:
        console.print("[yellow]IMDb, TMDb, and TVDb IDs are all present[/yellow]")
    # Core metadata tasks that run in parallel
    tasks = [
        tmdb_other_meta(
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
            tvdb_id=meta.get('tvdb_id', 0)
        ),

        get_imdb_info_api(
            meta['imdb_id'],
            manual_language=meta.get('manual_language'),
            debug=meta.get('debug', False)
        ),

        search_tvmaze(
            filename, meta['search_year'], meta.get('imdb_id', 0), meta.get('tvdb_id', 0),
            manual_date=meta.get('manual_date'),
            tvmaze_manual=meta.get('tvmaze_manual'),
            debug=meta.get('debug', False),
            return_full_tuple=False
        ) if meta.get('category') == 'TV' else None
    ]

    # Filter out None tasks
    tasks = [task for task in tasks if task is not None]

    if meta.get('category') == 'TV':
        tvdb_task = tvdb_handler.get_tvdb_episodes(
            meta['tvdb_id'],
            meta.get('debug', False)
        )
        tasks.append(tvdb_task)

        if not meta.get('tv_pack', False) and 'season_int' in meta and 'episode_int' in meta and meta.get('episode_int') != 0:
            # Add TMDb episode details task
            tmdb_episode_task = get_episode_details(
                meta.get('tmdb_id'),
                meta.get('season_int'),
                meta.get('episode_int'),
                debug=meta.get('debug', False)
            )
            tasks.append(tmdb_episode_task)

        if meta.get('tv_pack') and 'season_int' in meta:
            # For TV packs, we might want to get season details instead
            tmdb_season_task = get_season_details(
                meta.get('tmdb_id'),
                meta.get('season_int'),
                debug=meta.get('debug', False)
            )
            tasks.append(tmdb_season_task)

    # Execute all tasks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    result_index = 0

    # Process core metadata (always in first positions)
    if len(results) > result_index:
        tmdb_metadata = results[result_index]
        result_index += 1
        if not isinstance(tmdb_metadata, Exception) and tmdb_metadata:
            meta.update(tmdb_metadata)
        else:
            console.print(f"[yellow]TMDb metadata retrieval failed: {tmdb_metadata}[/yellow]")

    if len(results) > result_index:
        imdb_info = results[result_index]
        result_index += 1
        if isinstance(imdb_info, dict):
            meta['imdb_info'] = imdb_info

        elif isinstance(imdb_info, Exception):
            console.print(f"[red]IMDb API call failed: {imdb_info}[/red]")
            meta['imdb_info'] = meta.get('imdb_info', {})
        else:
            console.print("[red]Unexpected IMDb response, setting imdb_info to empty.[/red]")
            meta['imdb_info'] = {}

    if meta.get('category') == 'TV' and len(results) > result_index:
        tvmaze_id = results[result_index]
        result_index += 1

        if isinstance(tvmaze_id, int):
            meta['tvmaze_id'] = tvmaze_id
        elif isinstance(tvmaze_id, Exception):
            console.print(f"[yellow]TVMaze ID retrieval failed: {tvmaze_id}[/yellow]")
            meta['tvmaze_id'] = 0

    if meta.get('category') == 'TV':
        if len(results) > result_index:
            tvdb_episode_data = results[result_index]
            result_index += 1

            if tvdb_episode_data and not isinstance(tvdb_episode_data, Exception):
                # tvdb_episode_data is a tuple: (episodes_list, series_name)
                if isinstance(tvdb_episode_data, tuple) and len(tvdb_episode_data) == 2:
                    episodes_data, series_name = tvdb_episode_data
                    meta['tvdb_episode_data'] = episodes_data
                    if series_name:
                        meta['tvdb_series_name'] = series_name
                    meta['we_checked_tvdb'] = True
                else:
                    console.print(f"[yellow]Unexpected TVDb data format: {type(tvdb_episode_data)}[/yellow]")
            elif isinstance(tvdb_episode_data, Exception):
                console.print(f"[yellow]TVDb episode data retrieval failed: {tvdb_episode_data}[/yellow]")

        # Process TMDb episode data only if we added that task
        if (not meta.get('tv_pack', False) and 'season_int' in meta and
                'episode_int' in meta and meta.get('episode_int') != 0 and len(results) > result_index):
            tmdb_episode_data = results[result_index]
            result_index += 1

            if not isinstance(tmdb_episode_data, Exception) and tmdb_episode_data:
                meta['tmdb_episode_data'] = tmdb_episode_data
                meta['we_checked_tmdb'] = True

            elif isinstance(tmdb_episode_data, Exception):
                console.print(f"[yellow]TMDb episode data retrieval failed: {tmdb_episode_data}[/yellow]")

        # Process TMDb season data for TV packs
        elif (meta.get('tv_pack', False) and 'season_int' in meta and len(results) > result_index):
            tmdb_season_data = results[result_index]
            result_index += 1

            if not isinstance(tmdb_season_data, Exception) and tmdb_season_data:
                meta['tmdb_season_data'] = tmdb_season_data
                meta['we_checked_tmdb'] = True

            elif isinstance(tmdb_season_data, Exception):
                console.print(f"[yellow]TMDb season data retrieval failed: {tmdb_season_data}[/yellow]")

    return meta


async def imdb_tvdb(meta, filename):
    if meta['debug']:
        console.print("[yellow]Both IMDb and TVDB IDs are present[/yellow]")
    tasks = [
        get_tmdb_from_imdb(
            meta['imdb_id'],
            meta.get('tvdb_id'),
            meta.get('search_year'),
            filename,
            debug=meta.get('debug', False),
            mode=meta.get('mode', 'discord'),
            category_preference=meta.get('category')
        ),
        search_tvmaze(
            filename, meta['search_year'], meta.get('imdb_id', 0), meta.get('tvdb_id', 0),
            manual_date=meta.get('manual_date'),
            tvmaze_manual=meta.get('tvmaze_manual'),
            debug=meta.get('debug', False),
            return_full_tuple=False
        ),
        get_imdb_info_api(
            meta['imdb_id'],
            manual_language=meta.get('manual_language'),
            debug=meta.get('debug', False)
        )
    ]

    if meta.get('category') == 'TV':
        tvdb_episodes_task = tvdb_handler.get_tvdb_episodes(
            meta['tvdb_id'],
            meta.get('debug', False)
        )
        tasks.append(tvdb_episodes_task)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    tmdb_result, tvmaze_id, imdb_info_result = results[:3]
    if isinstance(tmdb_result, tuple) and len(tmdb_result) == 3:
        meta['category'], meta['tmdb_id'], meta['original_language'] = tmdb_result

    meta['tvmaze_id'] = tvmaze_id if isinstance(tvmaze_id, int) else 0

    if isinstance(imdb_info_result, dict):
        meta['imdb_info'] = imdb_info_result

    elif isinstance(imdb_info_result, Exception):
        console.print(f"[red]IMDb API call failed: {imdb_info_result}[/red]")
        meta['imdb_info'] = meta.get('imdb_info', {})  # Keep previous IMDb info if it exists
    else:
        console.print("[red]Unexpected IMDb response, setting imdb_info to empty.[/red]")
        meta['imdb_info'] = {}

    # Process TVDB episodes data if it was requested
    if meta.get('category') == 'TV' and len(results) > 3:
        tvdb_episode_data = results[3]
        if tvdb_episode_data and not isinstance(tvdb_episode_data, Exception):
            # tvdb_episode_data is a tuple: (episodes_list, series_name)
            if isinstance(tvdb_episode_data, tuple) and len(tvdb_episode_data) == 2:
                episodes_data, series_name = tvdb_episode_data
                meta['tvdb_episode_data'] = episodes_data
                if series_name:
                    meta['tvdb_series_name'] = series_name
                meta['we_checked_tvdb'] = True
            else:
                console.print(f"[yellow]Unexpected TVDb data format: {type(tvdb_episode_data)}[/yellow]")
        elif isinstance(tvdb_episode_data, Exception):
            console.print(f"[yellow]TVDb episode data retrieval failed: {tvdb_episode_data}[/yellow]")

    return meta


async def imdb_tmdb(meta, filename):
    # Create a list of coroutines to run concurrently
    coroutines = [
        tmdb_other_meta(
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
            quickie_search=meta.get('quickie_search', False)
        ),
        get_imdb_info_api(
            meta['imdb_id'],
            manual_language=meta.get('manual_language'),
            debug=meta.get('debug', False)
        )
    ]

    # Add TVMaze search if it's a TV category
    if meta['category'] == 'TV':
        coroutines.append(
            search_tvmaze(
                filename, meta['search_year'], meta.get('imdb_id', 0), meta.get('tvdb_id', 0),
                manual_date=meta.get('manual_date'),
                tvmaze_manual=meta.get('tvmaze_manual'),
                debug=meta.get('debug', False),
                return_full_tuple=False
            )
        )

        # Add TMDb episode details if it's a TV show with episodes
        if ('season_int' in meta and 'episode_int' in meta and
                not meta.get('tv_pack', False) and
                meta.get('episode_int') != 0):
            coroutines.append(
                get_episode_details(
                    meta.get('tmdb_id'),
                    meta.get('season_int'),
                    meta.get('episode_int'),
                    debug=meta.get('debug', False)
                )
            )
        elif meta.get('tv_pack', False) and 'season_int' in meta:
            coroutines.append(
                get_season_details(
                    meta.get('tmdb_id'),
                    meta.get('season_int'),
                    debug=meta.get('debug', False)
                )
            )

    # Gather results
    results = await asyncio.gather(*coroutines, return_exceptions=True)

    tmdb_metadata = None
    # Process the results
    if isinstance(results[0], Exception):
        error_msg = f"TMDB metadata retrieval failed: {str(results[0])}"
        console.print(f"[bold red]{error_msg}[/bold red]")
        pass
    elif not results[0]:  # Check if the result is empty (empty dict)
        error_msg = f"Failed to retrieve essential metadata from TMDB ID: {meta['tmdb_id']}"
        console.print(f"[bold red]{error_msg}[/bold red]")
        pass
    else:
        tmdb_metadata = results[0]

    # Update meta with TMDB metadata
    if tmdb_metadata:
        meta.update(tmdb_metadata)

    imdb_info_result = results[1]

    # Process IMDb info
    if isinstance(imdb_info_result, dict):
        meta['imdb_info'] = imdb_info_result

    elif isinstance(imdb_info_result, Exception):
        console.print(f"[red]IMDb API call failed: {imdb_info_result}[/red]")
        meta['imdb_info'] = meta.get('imdb_info', {})  # Keep previous IMDb info if it exists
    else:
        console.print("[red]Unexpected IMDb response, setting imdb_info to empty.[/red]")
        meta['imdb_info'] = {}

    # Process TVMaze results if it was included
    if meta['category'] == 'TV':
        if len(results) > 2:
            tvmaze_result = results[2]
            if isinstance(tvmaze_result, tuple) and len(tvmaze_result) == 3:
                # Handle tuple return: (tvmaze_id, imdbID, tvdbID)
                tvmaze_id, imdb_id, tvdb_id = tvmaze_result
                meta['tvmaze_id'] = tvmaze_id if isinstance(tvmaze_id, int) else 0

                # Set tvdb_id if not already set and we got a valid one
                if not meta.get('tvdb_id', 0) and isinstance(tvdb_id, int) and tvdb_id > 0:
                    meta['tvdb_id'] = tvdb_id
                    if meta.get('debug'):
                        console.print(f"[green]Set TVDb ID from TVMaze: {tvdb_id}[/green]")

            elif isinstance(tvmaze_result, int):
                meta['tvmaze_id'] = tvmaze_result
            elif isinstance(tvmaze_result, Exception):
                console.print(f"[red]TVMaze API call failed: {tvmaze_result}[/red]")
                meta['tvmaze_id'] = 0  # Set default value if an exception occurred
            else:
                console.print(f"[yellow]Unexpected TVMaze result type: {type(tvmaze_result)}[/yellow]")
                meta['tvmaze_id'] = 0

        # Process TMDb episode details if they were included
        if not meta.get('tv_pack', False):
            if len(results) > 3:
                episode_details_result = results[3]
                if isinstance(episode_details_result, dict):
                    meta['tmdb_episode_data'] = episode_details_result
                    meta['we_checked_tmdb'] = True

                elif isinstance(episode_details_result, Exception):
                    console.print(f"[red]TMDb episode details API call failed: {episode_details_result}[/red]")
        else:
            if 'season_int' in meta and len(results) > 3:
                season_details_result = results[3]
                if isinstance(season_details_result, dict):
                    meta['tmdb_season_data'] = season_details_result
                    meta['we_checked_tmdb'] = True

                elif isinstance(season_details_result, Exception):
                    console.print(f"[red]TMDb season details API call failed: {season_details_result}[/red]")

    return meta


async def get_tvmaze_tvdb(filename, search_year, imdb, tmdb, manual_date=None, tvmaze_manual=None, year='', debug=False, tv_movie=False):
    tvdb_data = None
    tvmaze = 0
    tvdb = 0
    if debug:
        console.print("[yellow]Finding both TVMaze and TVDb IDs[/yellow]")
    # Core metadata tasks that run in parallel
    tasks = [
        search_tvmaze(
            filename, search_year, imdb, 0,
            manual_date=manual_date,
            tvmaze_manual=tvmaze_manual,
            debug=debug,
            return_full_tuple=True
        )
    ]
    if (imdb and imdb != 0) or (tmdb and tmdb != 0):
        tasks.append(
            tvdb_handler.get_tvdb_by_external_id(imdb=imdb, tmdb=tmdb, debug=debug, tv_movie=tv_movie)
        )
    else:
        tasks.append(
            tvdb_handler.search_tvdb_series(filename=filename, year=year, debug=debug)
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process TVMaze results
    tvmaze_result = results[0]
    if isinstance(tvmaze_result, tuple) and len(tvmaze_result) == 3:
        # Handle tuple return: (tvmaze_id, imdbID, tvdbID)
        tvmaze = tvmaze_result[0] if isinstance(tvmaze_result[0], int) else 0

    elif isinstance(tvmaze_result, int):
        tvmaze = tvmaze_result
    elif isinstance(tvmaze_result, Exception):
        console.print(f"[red]TVMaze API call failed: {tvmaze_result}[/red]")
        tvmaze = 0  # Set default value if an exception occurred
    else:
        console.print(f"[yellow]Unexpected TVMaze result type: {type(tvmaze_result)}[/yellow]")
        tvmaze = 0

    # Process TVDb results if we added that task
    if (imdb and imdb != 0) or (tmdb and tmdb != 0):
        tvdb = results[1]
    elif len(results) > 1:
        tvdb_result = results[1]
        if tvdb_result and not isinstance(tvdb_result, Exception):
            # Handle tuple return: (series_results, series_id)
            if isinstance(tvdb_result, tuple) and len(tvdb_result) == 2:
                series_results, series_id = tvdb_result
                if series_id:
                    tvdb = int(series_id)
                    if debug:
                        console.print(f"[green]Got TVDb series ID: {series_id}[/green]")
                if series_results:
                    tvdb_data = series_results
            else:
                console.print(f"[yellow]Unexpected TVDb result format: {tvdb_result}[/yellow]")
        elif isinstance(tvdb_result, Exception):
            console.print(f"[yellow]TVDb series data retrieval failed: {tvdb_result}[/yellow]")

    if not tvdb and tvmaze and isinstance(tvmaze_result, tuple) and len(tvmaze_result) == 3:
        tvdb = tvmaze_result[2] if isinstance(tvmaze_result[2], int) else 0
    if debug:
        console.print(f"[blue]TVMaze ID: {tvmaze} | TVDb ID: {tvdb}[/blue]")

    return tvmaze, tvdb, tvdb_data


async def get_tv_data(meta):
    meta['tvdb_series_name'] = None
    if not meta.get('tv_pack', False) and meta.get('episode_int') != 0:
        if (not meta.get('we_checked_tvdb', False) and not meta.get('we_asked_tvmaze', False)) and meta.get('tvmaze_id') != 0 and meta['tvmaze_id'] != 0 and not meta.get('anime', False):
            meta = await get_tvdb_tvmaze_tmdb_episode_data(meta)
        elif meta.get('tvdb_id', 0) and not meta.get('we_checked_tvdb', False):
            tvdb_episode_data, tvdb_name = await tvdb_handler.get_tvdb_episodes(meta['tvdb_id'])
            if tvdb_episode_data:
                meta['tvdb_episode_data'] = tvdb_episode_data
            if tvdb_name:
                meta['tvdb_series_name'] = tvdb_name

        if meta.get('tvdb_series_name', None):
            year = meta['tvdb_series_name']
            year_match = re.search(r'\b(19\d\d|20[0-3]\d)\b', year)
            if year_match:
                meta['search_year'] = year_match.group(0)
            else:
                meta['search_year'] = ""

        if meta.get('tvdb_episode_data', None) and meta.get('tvdb_id', 0):
            try:
                meta['tvdb_season_name'], meta['tvdb_episode_name'], meta['tvdb_overview'], meta['tvdb_season'], meta['tvdb_episode'], meta['tvdb_episode_year'], meta['tvdb_episode_id'] = await tvdb_handler.get_specific_episode_data(meta['tvdb_episode_data'], meta.get('season_int', None), meta.get('episode_int', None), debug=meta.get('debug', False))
            except Exception as e:
                console.print(f"[red]Error fetching TVDb episode data: {e}[/red]")

        if meta.get('tvdb_episode_name', None):
            if 'episode' in meta['tvdb_episode_name'].lower() or 'tba' in meta['tvdb_episode_name'].lower():
                meta['auto_episode_title'] = None
            else:
                meta['auto_episode_title'] = meta['tvdb_episode_name']
        if meta.get('tvdb_overview', None):
            meta['overview_meta'] = meta['tvdb_overview']
        if meta.get('tvdb_season', None) is not None and meta['tvdb_season'] != meta.get('season_int', None) and not meta.get('season', None) and not meta.get('no_season', False) and not meta.get('manual_date', None):
            meta['season_int'] = int(meta['tvdb_season'])
            meta['season'] = f"S{meta['tvdb_season']:02d}"
        if meta.get('tvdb_episode', None) is not None and meta['tvdb_episode'] != meta.get('episode_int', None) and not meta.get('episode', None) and not meta.get('manual_date', None):
            meta['episode_int'] = int(meta['tvdb_episode'])
            meta['episode'] = f"E{meta['tvdb_episode']:02d}"

        # fallback to tvmaze data if tvdb data is available
        if 'tvmaze_episode_data' not in meta or meta['tvmaze_episode_data'] is None:
            meta['tvmaze_episode_data'] = {}
            tvmaze_episode_data = await get_tvmaze_episode_data(meta.get('tvmaze_id'), meta.get('season_int'), meta.get('episode_int'), meta)
            if tvmaze_episode_data:
                meta['tvmaze_episode_data'] = tvmaze_episode_data
        if meta.get('auto_episode_title') is None or meta.get('overview_meta') is None:
            if meta.get('auto_episode_title') is None and meta['tvmaze_episode_data'].get('name') is not None:
                if 'episode' in meta['tvmaze_episode_data'].get("name").lower() or 'tba' in meta['tvmaze_episode_data'].get("name").lower():
                    meta['auto_episode_title'] = None
                else:
                    meta['auto_episode_title'] = meta['tvmaze_episode_data']['name']
            if meta.get('overview_meta') is None and meta['tvmaze_episode_data'].get('overview') is not None:
                meta['overview_meta'] = meta['tvmaze_episode_data'].get('overview', None)

        # fallback to tmdb data if no other data is not available
        if (meta.get('auto_episode_title') is None or meta.get('overview_meta') is None) and meta.get('episode_overview', None):
            if 'tvdb_episode_int' in meta and meta.get('tvdb_episode_int') != 0 and meta.get('tvdb_episode_int') != meta.get('episode_int'):
                episode = meta.get('episode_int')
                season = meta.get('tvdb_season_int')
                if meta['debug']:
                    console.print(f"[yellow]Using absolute episode number from TVDb: {episode}[/yellow]")
                    console.print(f"[yellow]Using matching season number from TVDb: {season}[/yellow]")
            else:
                episode = meta.get('episode_int')
                season = meta.get('season_int')
            if meta['debug']:
                console.print("[yellow]Fetching TMDb episode metadata...")
            if not meta['tmdb_episode_data']:
                episode_details = await get_episode_details(meta.get('tmdb_id'), season, episode, debug=meta.get('debug', False))
            else:
                episode_details = meta.get('tmdb_episode_data', None)
            if meta.get('auto_episode_title') is None and episode_details.get('name') is not None:
                if 'episode' in episode_details.get("name").lower() or 'tba' in episode_details.get("name").lower():
                    meta['auto_episode_title'] = None
                else:
                    meta['auto_episode_title'] = episode_details['name']
            if meta.get('overview_meta') is None and episode_details.get('overview') is not None:
                meta['overview_meta'] = episode_details.get('overview', None)

    elif meta.get('tv_pack', False):
        if not meta.get('we_checked_tvdb', False) and meta.get('tvdb_id', 0):
            tvdb_episode_data, tvdb_name = await tvdb_handler.get_tvdb_episodes(meta['tvdb_id'])
            if tvdb_episode_data:
                meta['tvdb_episode_data'] = tvdb_episode_data
            if tvdb_name:
                meta['tvdb_series_name'] = tvdb_name
        if meta.get('tvdb_series_name', None):
            year = meta['tvdb_series_name']
            year_match = re.search(r'\b(19\d\d|20[0-3]\d)\b', year)
            if year_match:
                meta['search_year'] = year_match.group(0)
            else:
                meta['search_year'] = ""

        if meta.get('tvdb_episode_data', None) and meta.get('tvdb_id', 0):
            try:
                meta['tvdb_season_name'], meta['tvdb_episode_name'], meta['tvdb_overview'], meta['tvdb_season'], meta['tvdb_episode'], meta['tvdb_episode_year'], meta['tvdb_episode_id'] = await tvdb_handler.get_specific_episode_data(meta['tvdb_episode_data'], meta.get('season_int', None), meta.get('episode_int', None), debug=meta.get('debug', False))
            except Exception as e:
                console.print(f"[red]Error fetching TVDb episode data: {e}[/red]")

        if meta.get('tvdb_episode_id', None):
            meta['tvdb_imdb_id'] = await tvdb_handler.get_imdb_id_from_tvdb_episode_id(meta['tvdb_episode_id'], debug=meta.get('debug', False))

    return meta


async def get_tvdb_tvmaze_tmdb_episode_data(meta):
    if meta['debug']:
        console.print("[yellow]Gathering TVDb and TVMaze episode data[/yellow]")

    tasks = []
    task_map = {}  # Track which tasks we added

    # Add TVMaze episode data task
    if meta.get('tvmaze_id'):
        if meta['debug']:
            console.print("[yellow]Fetching TVMaze episode data...[/yellow]")
        tasks.append(
            get_tvmaze_episode_data(
                meta.get('tvmaze_id'),
                meta.get('season_int'),
                meta.get('episode_int')
            )
        )
        task_map['tvmaze'] = len(tasks) - 1

    # Add TVDb episode data task
    if meta.get('tvdb_id'):
        if meta['debug']:
            console.print("[yellow]Fetching TVDb episode data...[/yellow]")
        tasks.append(
            tvdb_handler.get_tvdb_episodes(
                meta['tvdb_id'],
                meta.get('debug', False)
            )
        )
        task_map['tvdb'] = len(tasks) - 1

    if meta.get('tmdb_id'):
        if meta['debug']:
            console.print("[yellow]Fetching TMDb episode data...[/yellow]")
        tasks.append(
            get_episode_details(
                meta.get('tmdb_id'),
                meta.get('season_int'),
                meta.get('episode_int'),
                debug=meta.get('debug', False)
            )
        )
        task_map['tmdb'] = len(tasks) - 1

    if not tasks:
        return meta

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process TVMaze results
    if 'tvmaze' in task_map:
        tvmaze_episode_data = results[task_map['tvmaze']]
        if tvmaze_episode_data and not isinstance(tvmaze_episode_data, Exception):
            meta['tvmaze_episode_data'] = tvmaze_episode_data
            meta['we_asked_tvmaze'] = True

            if meta['debug']:
                console.print("[green]TVMaze episode data retrieved successfully.[/green]")
        elif isinstance(tvmaze_episode_data, Exception):
            console.print(f"[yellow]TVMaze episode data retrieval failed: {tvmaze_episode_data}[/yellow]")

    # Process TVDB results
    if 'tvdb' in task_map:
        tvdb_episodes_result = results[task_map['tvdb']]
        if tvdb_episodes_result and not isinstance(tvdb_episodes_result, Exception):
            if isinstance(tvdb_episodes_result, tuple) and len(tvdb_episodes_result) == 2:
                tvdb_episode_data, tvdb_name = tvdb_episodes_result
                if tvdb_episode_data:
                    meta['tvdb_episode_data'] = tvdb_episode_data
                    meta['we_checked_tvdb'] = True
                    if meta['debug']:
                        console.print(f"[green]TVDb episodes list retrieved with {len(tvdb_episode_data)} episodes[/green]")
                if tvdb_name:
                    meta['tvdb_series_name'] = tvdb_name
                    if meta['debug']:
                        console.print(f"[green]TVDb series name: {tvdb_name}[/green]")
            else:
                console.print(f"[yellow]Unexpected TVDb episodes result format: {tvdb_episodes_result}[/yellow]")
        elif isinstance(tvdb_episodes_result, Exception):
            console.print(f"[yellow]TVDb episode data retrieval failed: {tvdb_episodes_result}[/yellow]")

    # Process TMDb episode details results
    if 'tmdb' in task_map:
        tmdb_episode_data = results[task_map['tmdb']]
        if not isinstance(tmdb_episode_data, Exception) and tmdb_episode_data:
            meta['tmdb_episode_data'] = tmdb_episode_data
            meta['we_checked_tmdb'] = True
            if meta['debug']:
                console.print("[green]TMDb episode data retrieved successfully.[/green]")
        elif isinstance(tmdb_episode_data, Exception):
            console.print(f"[yellow]TMDb episode data retrieval failed: {tmdb_episode_data}[/yellow]")

    return meta
