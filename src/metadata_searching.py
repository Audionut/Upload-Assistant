import re
import asyncio
from src.console import console
from src.tvmaze import search_tvmaze, get_tvmaze_episode_data
from src.imdb import get_imdb_info_api
from src.tmdb import tmdb_other_meta, get_tmdb_from_imdb, get_episode_details
from src.tvdb import get_tvdb_episode_data, get_tvdb_series_data, get_tvdb_series_episodes, get_tvdb_series


async def all_ids(meta, tvdb_api=None, tvdb_token=None):
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

    # Add episode-specific tasks if this is a TV show with episodes
    if (meta['category'] == 'TV' and not meta.get('tv_pack', False) and
            'season_int' in meta and 'episode_int' in meta and meta.get('episode_int') != 0):

        # Add TVDb task if we have credentials
        if tvdb_api and tvdb_token:
            all_tasks.append(
                get_tvdb_episode_data(
                    meta['base_dir'],
                    tvdb_token,
                    meta.get('tvdb_id'),
                    meta.get('season_int'),
                    meta.get('episode_int'),
                    api_key=tvdb_api,
                    debug=meta.get('debug', False)
                )
            )

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
    elif meta.get('category') == 'TV' and meta.get('tv_pack', False):
        if tvdb_api and tvdb_token:
            all_tasks.append(
                get_tvdb_series_data(
                    meta['base_dir'],
                    tvdb_token,
                    meta.get('tvdb_id'),
                    api_key=tvdb_api,
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
        meta['tv_year'] = imdb_info.get('tv_year', None)

    elif isinstance(imdb_info, Exception):
        console.print(f"[red]IMDb API call failed: {imdb_info}[/red]")
        meta['imdb_info'] = meta.get('imdb_info', {})  # Keep previous IMDb info if it exists
    else:
        console.print("[red]Unexpected IMDb response, setting imdb_info to empty.[/red]")
        meta['imdb_info'] = {}

    # Process episode data if this is a TV show
    if meta['category'] == 'TV' and not meta.get('tv_pack', False) and meta.get('episode_int', 0) != 0:
        # Process TVDb episode data (if included)
        if tvdb_api and tvdb_token:
            tvdb_episode_data = results[result_index]
            result_index += 1

            if tvdb_episode_data and not isinstance(tvdb_episode_data, Exception):
                meta['tvdb_episode_data'] = tvdb_episode_data
                meta['we_checked_tvdb'] = True

                # Process episode name
                if meta['tvdb_episode_data'].get('episode_name'):
                    episode_name = meta['tvdb_episode_data'].get('episode_name')
                    if episode_name and isinstance(episode_name, str) and episode_name.strip():
                        if 'episode' in episode_name.lower():
                            meta['auto_episode_title'] = None
                            meta['tvdb_episode_title'] = None
                        else:
                            meta['tvdb_episode_title'] = episode_name.strip()
                            meta['auto_episode_title'] = episode_name.strip()
                    else:
                        meta['auto_episode_title'] = None

                # Process overview
                if meta['tvdb_episode_data'].get('overview'):
                    overview = meta['tvdb_episode_data'].get('overview')
                    if overview and isinstance(overview, str) and overview.strip():
                        meta['overview_meta'] = overview.strip()
                    else:
                        meta['overview_meta'] = None
                else:
                    meta['overview_meta'] = None

                # Process season and episode numbers
                if meta['tvdb_episode_data'].get('season_name'):
                    meta['tvdb_season_name'] = meta['tvdb_episode_data'].get('season_name')

                if meta['tvdb_episode_data'].get('season_number'):
                    meta['tvdb_season_number'] = meta['tvdb_episode_data'].get('season_number')

                if meta['tvdb_episode_data'].get('episode_number'):
                    meta['tvdb_episode_number'] = meta['tvdb_episode_data'].get('episode_number')

                if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('series_name'):
                    year = meta['tvdb_episode_data'].get('series_name')
                    year_match = re.search(r'\b(19\d\d|20[0-3]\d)\b', year)
                    if year_match:
                        meta['search_year'] = year_match.group(0)
                    else:
                        meta['search_year'] = ""

            elif isinstance(tvdb_episode_data, Exception):
                console.print(f"[yellow]TVDb episode data retrieval failed: {tvdb_episode_data}")

        # Process TVMaze episode data
        tvmaze_episode_data = results[result_index]
        result_index += 1

        if not isinstance(tvmaze_episode_data, Exception) and tvmaze_episode_data:
            meta['tvmaze_episode_data'] = tvmaze_episode_data

            # Only set title if not already set
            if meta.get('auto_episode_title') is None and tvmaze_episode_data.get('name') is not None:
                if 'episode' in tvmaze_episode_data.get('name', '').lower():
                    meta['auto_episode_title'] = None
                else:
                    meta['auto_episode_title'] = tvmaze_episode_data['name']

            # Only set overview if not already set
            if meta.get('overview_meta') is None and tvmaze_episode_data.get('overview') is not None:
                meta['overview_meta'] = tvmaze_episode_data.get('overview', None)
            meta['we_asked_tvmaze'] = True
        elif isinstance(tvmaze_episode_data, Exception):
            console.print(f"[yellow]TVMaze episode data retrieval failed: {tvmaze_episode_data}")

        # Process TMDb episode data
        tmdb_episode_data = results[result_index]
        result_index += 1

        if not isinstance(tmdb_episode_data, Exception) and tmdb_episode_data:
            meta['tmdb_episode_data'] = tmdb_episode_data
            meta['we_checked_tmdb'] = True

            # Only set title if not already set
            if meta.get('auto_episode_title') is None and tmdb_episode_data.get('name') is not None:
                if 'episode' in tmdb_episode_data.get('name', '').lower():
                    meta['auto_episode_title'] = None
                else:
                    meta['auto_episode_title'] = tmdb_episode_data['name']

            # Only set overview if not already set
            if meta.get('overview_meta') is None and tmdb_episode_data.get('overview') is not None:
                meta['overview_meta'] = tmdb_episode_data.get('overview', None)
        elif isinstance(tmdb_episode_data, Exception):
            console.print(f"[yellow]TMDb episode data retrieval failed: {tmdb_episode_data}")

    elif meta.get('category') == 'TV' and meta.get('tv_pack', False):
        if tvdb_api and tvdb_token:
            # Process TVDb series data
            tvdb_series_data = results[result_index]
            result_index += 1

            if tvdb_series_data and not isinstance(tvdb_series_data, Exception):
                meta['tvdb_series_name'] = tvdb_series_data
                meta['we_checked_tvdb'] = True

            elif isinstance(tvdb_series_data, Exception):
                console.print(f"[yellow]TVDb series data retrieval failed: {tvdb_series_data}")
    return meta


async def imdb_tmdb_tvdb(meta, filename, tvdb_api=None, tvdb_token=None):
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

    if (meta.get('category') == 'TV' and not meta.get('tv_pack', False) and
            'season_int' in meta and 'episode_int' in meta and meta.get('episode_int') != 0):

        if tvdb_api and tvdb_token:
            tvdb_task = get_tvdb_episode_data(
                meta['base_dir'], tvdb_token, meta.get('tvdb_id'),
                meta.get('season_int'), meta.get('episode_int'),
                api_key=tvdb_api, debug=meta.get('debug', False)
            )
            tasks.append(tvdb_task)

        tasks.append(
            get_episode_details(
                meta.get('tmdb_id'), meta.get('season_int'), meta.get('episode_int'),
                debug=meta.get('debug', False)
            )
        )

    elif meta.get('category') == 'TV' and meta.get('tv_pack', False) and tvdb_api and tvdb_token:
        tvdb_series_task = get_tvdb_series_data(
            meta['base_dir'], tvdb_token, meta.get('tvdb_id'),
            api_key=tvdb_api, debug=meta.get('debug', False)
        )
        tasks.append(tvdb_series_task)

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
            meta['tv_year'] = imdb_info.get('tv_year', None)

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

    if meta.get('category') == 'TV' and not meta.get('tv_pack', False) and meta.get('episode_int') != 0:
        if tvdb_api and tvdb_token and len(results) > result_index:
            tvdb_episode_data = results[result_index]
            result_index += 1

            if tvdb_episode_data and not isinstance(tvdb_episode_data, Exception):
                meta['tvdb_episode_data'] = tvdb_episode_data
                meta['we_checked_tvdb'] = True

                if meta['tvdb_episode_data'].get('episode_name'):
                    episode_name = meta['tvdb_episode_data'].get('episode_name')
                    if episode_name and isinstance(episode_name, str) and episode_name.strip():
                        if 'episode' in episode_name.lower():
                            meta['auto_episode_title'] = None
                            meta['tvdb_episode_title'] = None
                        else:
                            meta['tvdb_episode_title'] = episode_name.strip()
                            meta['auto_episode_title'] = episode_name.strip()
                    else:
                        meta['auto_episode_title'] = None

                if meta['tvdb_episode_data'].get('overview'):
                    overview = meta['tvdb_episode_data'].get('overview')
                    if overview and isinstance(overview, str) and overview.strip():
                        meta['overview_meta'] = overview.strip()
                    else:
                        meta['overview_meta'] = None
                else:
                    meta['overview_meta'] = None

                if meta['tvdb_episode_data'].get('season_name'):
                    meta['tvdb_season_name'] = meta['tvdb_episode_data'].get('season_name')

                if meta['tvdb_episode_data'].get('season_number'):
                    meta['tvdb_season_number'] = meta['tvdb_episode_data'].get('season_number')

                if meta['tvdb_episode_data'].get('episode_number'):
                    meta['tvdb_episode_number'] = meta['tvdb_episode_data'].get('episode_number')

                if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('series_name'):
                    year = meta['tvdb_episode_data'].get('series_name')
                    year_match = re.search(r'\b(19\d\d|20[0-3]\d)\b', year)
                    if year_match:
                        meta['search_year'] = year_match.group(0)
                    else:
                        meta['search_year'] = ""
            elif isinstance(tvdb_episode_data, Exception):
                console.print(f"[yellow]TVDb episode data retrieval failed: {tvdb_episode_data}[/yellow]")

        if len(results) > result_index:
            tmdb_episode_data = results[result_index]
            result_index += 1

            if not isinstance(tmdb_episode_data, Exception) and tmdb_episode_data:
                meta['tmdb_episode_data'] = tmdb_episode_data
                meta['we_checked_tmdb'] = True

                if meta.get('auto_episode_title') is None and tmdb_episode_data.get('name') is not None:
                    if 'episode' in tmdb_episode_data.get('name', '').lower():
                        meta['auto_episode_title'] = None
                    else:
                        meta['auto_episode_title'] = tmdb_episode_data['name']

                if meta.get('overview_meta') is None and tmdb_episode_data.get('overview') is not None:
                    meta['overview_meta'] = tmdb_episode_data.get('overview', None)
            elif isinstance(tmdb_episode_data, Exception):
                console.print(f"[yellow]TMDb episode data retrieval failed: {tmdb_episode_data}[/yellow]")

    elif meta.get('category') == 'TV' and meta.get('tv_pack', False) and tvdb_api and tvdb_token:
        tvdb_series_data = results[result_index]
        result_index += 1

        if tvdb_series_data and not isinstance(tvdb_series_data, Exception):
            meta['tvdb_series_name'] = tvdb_series_data
            meta['we_checked_tvdb'] = True
        elif isinstance(tvdb_series_data, Exception):
            console.print(f"[yellow]TVDb series data retrieval failed: {tvdb_series_data}[/yellow]")

    return meta


async def imdb_tvdb(meta, filename, tvdb_api=None, tvdb_token=None):
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

    # Add TVDb tasks if we have credentials and it's a TV show with episodes
    add_tvdb_tasks = (
        tvdb_api and tvdb_token and
        'season_int' in meta and 'episode_int' in meta and
        meta.get('category') == 'TV' and
        not meta.get('tv_pack', False) and
        meta.get('episode_int') != 0
    )

    if add_tvdb_tasks:
        tvdb_episode_data = await get_tvdb_episode_data(
            meta['base_dir'],
            tvdb_token,
            meta.get('tvdb_id'),
            meta.get('season_int'),
            meta.get('episode_int'),
            api_key=tvdb_api,
            debug=meta.get('debug', False)
        )

        if tvdb_episode_data:
            console.print("[green]TVDB episode data retrieved successfully.[/green]")
            meta['tvdb_episode_data'] = tvdb_episode_data
            meta['we_checked_tvdb'] = True

            # Process episode name
            if meta['tvdb_episode_data'].get('episode_name'):
                episode_name = meta['tvdb_episode_data'].get('episode_name')
                if episode_name and isinstance(episode_name, str) and episode_name.strip():
                    if 'episode' in episode_name.lower():
                        meta['auto_episode_title'] = None
                        meta['tvdb_episode_title'] = None
                    else:
                        meta['tvdb_episode_title'] = episode_name.strip()
                        meta['auto_episode_title'] = episode_name.strip()
                else:
                    meta['auto_episode_title'] = None

            # Process overview
            if meta['tvdb_episode_data'].get('overview'):
                overview = meta['tvdb_episode_data'].get('overview')
                if overview and isinstance(overview, str) and overview.strip():
                    meta['overview_meta'] = overview.strip()
                else:
                    meta['overview_meta'] = None
            else:
                meta['overview_meta'] = None

            if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('series_name'):
                year = meta['tvdb_episode_data'].get('series_name')
                year_match = re.search(r'\b(19\d\d|20[0-3]\d)\b', year)
                if year_match:
                    meta['search_year'] = year_match.group(0)
                else:
                    meta['search_year'] = ""

    add_name_tasks = (
        tvdb_api and tvdb_token and
        meta.get('category') == 'TV' and
        meta.get('tv_pack', False)
    )

    if add_name_tasks:
        tvdb_series_data = await get_tvdb_series_data(
            meta['base_dir'],
            tvdb_token,
            meta.get('tvdb_id'),
            api_key=tvdb_api,
            debug=meta.get('debug', False)
        )

        if tvdb_series_data:
            console.print("[green]TVDB series data retrieved successfully.[/green]")
            meta['tvdb_series_name'] = tvdb_series_data
            meta['we_checked_tvdb'] = True

    results = await asyncio.gather(*tasks, return_exceptions=True)
    tmdb_result, tvmaze_id, imdb_info_result = results[:3]
    if isinstance(tmdb_result, tuple) and len(tmdb_result) == 3:
        meta['category'], meta['tmdb_id'], meta['original_language'] = tmdb_result

    meta['tvmaze_id'] = tvmaze_id if isinstance(tvmaze_id, int) else 0

    if isinstance(imdb_info_result, dict):
        meta['imdb_info'] = imdb_info_result
        meta['tv_year'] = imdb_info_result.get('tv_year', None)

    elif isinstance(imdb_info_result, Exception):
        console.print(f"[red]IMDb API call failed: {imdb_info_result}[/red]")
        meta['imdb_info'] = meta.get('imdb_info', {})  # Keep previous IMDb info if it exists
    else:
        console.print("[red]Unexpected IMDb response, setting imdb_info to empty.[/red]")
        meta['imdb_info'] = {}
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
        meta['tv_year'] = imdb_info_result.get('tv_year', None)

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
        if len(results) > 3:
            episode_details_result = results[3]
            if isinstance(episode_details_result, dict):
                meta['tmdb_episode_data'] = episode_details_result
                meta['we_checked_tmdb'] = True

            elif isinstance(episode_details_result, Exception):
                console.print(f"[red]TMDb episode details API call failed: {episode_details_result}[/red]")
    return meta


async def get_tvmaze_tvdb(meta, filename, tvdb_api=None, tvdb_token=None):
    if meta['debug']:
        console.print("[yellow]Both TVMaze and TVDb IDs are present[/yellow]")
    # Core metadata tasks that run in parallel
    tasks = [
        search_tvmaze(
            filename, meta['search_year'], meta.get('imdb_id', 0), meta.get('tvdb_id', 0),
            manual_date=meta.get('manual_date'),
            tvmaze_manual=meta.get('tvmaze_manual'),
            debug=meta.get('debug', False),
            return_full_tuple=False
        )
    ]
    if tvdb_api and tvdb_token:
        tasks.append(
            get_tvdb_series(
                meta['base_dir'], meta.get('title', ''), meta.get('year', ''),
                apikey=tvdb_api, token=tvdb_token, debug=meta.get('debug', False)
            )
        )

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process TVMaze results
    tvmaze_result = results[0]
    if isinstance(tvmaze_result, tuple) and len(tvmaze_result) == 3:
        # Handle tuple return: (tvmaze_id, imdbID, tvdbID)
        tvmaze_id, imdb_id, tvdb_id = tvmaze_result
        meta['tvmaze_id'] = tvmaze_id if isinstance(tvmaze_id, int) else 0

        # Set tvdb_id if not already set and we got a valid one
        if not meta.get('tvdb_id', 0) and isinstance(tvdb_id, int) and tvdb_id > 0:
            meta['tvdb_id'] = tvdb_id
            if meta.get('debug'):
                console.print(f"[green]Set TVDb ID from TVMaze: {tvdb_id}[/green]")
        if not meta.get('imdb_id', 0) and isinstance(imdb_id, str) and imdb_id.strip():
            meta['imdb_id'] = imdb_id
            if meta.get('debug'):
                console.print(f"[green]Set IMDb ID from TVMaze: {imdb_id}[/green]")

    elif isinstance(tvmaze_result, int):
        meta['tvmaze_id'] = tvmaze_result
    elif isinstance(tvmaze_result, Exception):
        console.print(f"[red]TVMaze API call failed: {tvmaze_result}[/red]")
        meta['tvmaze_id'] = 0  # Set default value if an exception occurred
    else:
        console.print(f"[yellow]Unexpected TVMaze result type: {type(tvmaze_result)}[/yellow]")
        meta['tvmaze_id'] = 0

    # Process TVDb results if we added that task
    if len(results) > 1 and tvdb_api and tvdb_token:
        tvdb_result = results[1]
        if tvdb_result and not isinstance(tvdb_result, Exception):
            meta['tvdb_id'] = tvdb_result
            if meta.get('debug'):
                console.print(f"[green]Got TVDb series data: {tvdb_result}[/green]")
        elif isinstance(tvdb_result, Exception):
            console.print(f"[yellow]TVDb series data retrieval failed: {tvdb_result}[/yellow]")

    return meta


async def get_tv_data(meta, base_dir, tvdb_api=None, tvdb_token=None):
    if not meta.get('tv_pack', False) and meta.get('episode_int') != 0:
        if not meta.get('auto_episode_title') or not meta.get('overview_meta'):
            # prioritze tvdb metadata if available
            if tvdb_api and tvdb_token and not meta.get('we_checked_tvdb', False):
                if meta['debug']:
                    console.print("[yellow]Fetching TVDb metadata...")
                if meta.get('tvdb_id') and meta['tvdb_id'] != 0:
                    meta['tvdb_season_int'], meta['tvdb_episode_int'] = await get_tvdb_series_episodes(base_dir, tvdb_token, meta.get('tvdb_id'), meta.get('season_int'), meta.get('episode_int'), tvdb_api, debug=meta.get('debug', False))
                    tvdb_episode_data = await get_tvdb_episode_data(base_dir, tvdb_token, meta['tvdb_id'], meta.get('tvdb_season_int'), meta.get('tvdb_episode_int'), api_key=tvdb_api, debug=meta.get('debug', False))
                    if tvdb_episode_data:
                        meta['tvdb_episode_data'] = tvdb_episode_data

                        if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('episode_name') and meta.get('auto_episode_title') is None:
                            episode_name = meta['tvdb_episode_data'].get('episode_name')
                            if episode_name and isinstance(episode_name, str) and episode_name.strip():
                                if 'episode' in episode_name.lower():
                                    meta['auto_episode_title'] = None
                                    meta['tvdb_episode_title'] = None
                                else:
                                    meta['tvdb_episode_title'] = episode_name.strip()
                                    meta['auto_episode_title'] = episode_name.strip()
                            else:
                                meta['auto_episode_title'] = None

                        if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('overview') and meta.get('original_language', "") == "en":
                            overview = meta['tvdb_episode_data'].get('overview')
                            if overview and isinstance(overview, str) and overview.strip():
                                meta['overview_meta'] = overview.strip()
                            else:
                                meta['overview_meta'] = None
                        elif meta.get('original_language') != "en":
                            meta['overview_meta'] = None
                        else:
                            meta['overview_meta'] = None

                        if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('season_name'):
                            meta['tvdb_season_name'] = meta['tvdb_episode_data'].get('season_name')

                        if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('season_number'):
                            meta['tvdb_season_number'] = meta['tvdb_episode_data'].get('season_number')

                        if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('episode_number'):
                            meta['tvdb_episode_number'] = meta['tvdb_episode_data'].get('episode_number')

                        if meta.get('tvdb_episode_data') and meta['tvdb_episode_data'].get('series_name'):
                            year = meta['tvdb_episode_data'].get('series_name')
                            year_match = re.search(r'\b(19\d\d|20[0-3]\d)\b', year)
                            if year_match:
                                meta['search_year'] = year_match.group(0)
                            else:
                                meta['search_year'] = ""

            # fallback to tvmaze data if tvdb data is available
            if meta.get('auto_episode_title') is None or meta.get('overview_meta') is None and (not meta.get('we_asked_tvmaze', False) and meta.get('episode_overview', None)):
                tvmaze_episode_data = await get_tvmaze_episode_data(meta.get('tvmaze_id'), meta.get('season_int'), meta.get('episode_int'))
                if tvmaze_episode_data:
                    meta['tvmaze_episode_data'] = tvmaze_episode_data
                    if meta.get('auto_episode_title') is None and tvmaze_episode_data.get('name') is not None:
                        if 'episode' in tvmaze_episode_data.get("name").lower():
                            meta['auto_episode_title'] = None
                        else:
                            meta['auto_episode_title'] = tvmaze_episode_data['name']
                    if meta.get('overview_meta') is None and tvmaze_episode_data.get('overview') is not None:
                        meta['overview_meta'] = tvmaze_episode_data.get('overview', None)

            # fallback to tmdb data if no other data is not available
            if (meta.get('auto_episode_title') is None or meta.get('overview_meta') is None) and (not meta.get('we_checked_tmdb', False) and meta.get('episode_overview', None)):
                if 'tvdb_episode_int' in meta and meta.get('tvdb_episode_int') != 0 and meta.get('tvdb_episode_int') != meta.get('episode_int'):
                    episode = meta.get('episode_int')
                    season = meta.get('tvdb_season_int')
                    if meta['debug']:
                        console.print(f"[yellow]Using absolute episode number from TVDb: {episode}[/yellow]")
                        console.print(f"[yellow]Using matching season number from TVDb: {season}[/yellow]")
                else:
                    episode = meta.get('episode_int')
                    season = meta.get('season_int')
                if not meta.get('we_checked_tmdb', False):
                    if meta['debug']:
                        console.print("[yellow]Fetching TMDb episode metadata...")
                    episode_details = await get_episode_details(meta.get('tmdb_id'), season, episode, debug=meta.get('debug', False))
                else:
                    episode_details = meta.get('tmdb_episode_data', None)
                if meta.get('auto_episode_title') is None and episode_details.get('name') is not None:
                    if 'episode' in episode_details.get("name").lower():
                        meta['auto_episode_title'] = None
                    else:
                        meta['auto_episode_title'] = episode_details['name']
                if meta.get('overview_meta') is None and episode_details.get('overview') is not None:
                    meta['overview_meta'] = episode_details.get('overview', None)

            if 'tvdb_season_int' in meta and meta['tvdb_season_int'] and meta['tvdb_episode_int'] != 0:
                meta['episode_int'] = meta['tvdb_episode_int']
                meta['season_int'] = meta['tvdb_season_int']
                meta['season'] = "S" + str(meta['season_int']).zfill(2)
                meta['episode'] = "E" + str(meta['episode_int']).zfill(2)
    elif meta.get('tv_pack', False):
        if tvdb_api and tvdb_token:
            meta['tvdb_series_name'] = await get_tvdb_series_data(base_dir, tvdb_token, meta.get('tvdb_id'), tvdb_api, debug=meta.get('debug', False))
    return meta
