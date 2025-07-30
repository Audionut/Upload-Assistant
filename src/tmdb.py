from src.console import console
from src.imdb import get_imdb_aka_api, get_imdb_info_api
from src.args import Args
from data.config import config
import re
from guessit import guessit
import cli_ui
import anitopy
from datetime import datetime
from difflib import SequenceMatcher
import requests
import json
import httpx
import asyncio
import os

TMDB_API_KEY = config['DEFAULT'].get('tmdb_api', False)
TMDB_BASE_URL = "https://api.themoviedb.org/3"


async def get_tmdb_from_imdb(imdb_id, tvdb_id=None, search_year=None, filename=None, debug=False, mode="discord", category_preference=None, imdb_info=None):
    """Fetches TMDb ID using IMDb or TVDb ID.

    - Returns `(category, tmdb_id, original_language)`
    - If TMDb fails, prompts the user (if in CLI mode).
    """
    if not str(imdb_id).startswith("tt"):
        if isinstance(imdb_id, str) and imdb_id.isdigit():
            imdb_id = f"tt{int(imdb_id):07d}"
        elif isinstance(imdb_id, int):
            imdb_id = f"tt{imdb_id:07d}"

    async def _tmdb_find_by_external_source(external_id, source):
        """Helper function to find a movie or TV show on TMDb by external ID."""
        url = f"{TMDB_BASE_URL}/find/{external_id}"
        params = {"api_key": TMDB_API_KEY, "external_source": source}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception:
                console.print(f"[bold red]Failed to fetch TMDb data: {response.status_code}[/bold red]")
                return {}

        return {}

    # Check TVDb for an ID first if present
    if tvdb_id:
        info_tvdb = await _tmdb_find_by_external_source(str(tvdb_id), "tvdb_id")
        if debug:
            console.print("TVDB INFO", info_tvdb)
        if info_tvdb.get("tv_results"):
            return "TV", info_tvdb['tv_results'][0]['id'], info_tvdb['tv_results'][0].get('original_language')

    # Use IMDb ID if no TVDb ID is provided
    info = await _tmdb_find_by_external_source(imdb_id, "imdb_id")

    # Check if both movie and TV results exist
    has_movie_results = bool(info.get("movie_results"))
    has_tv_results = bool(info.get("tv_results"))

    # If we have results in multiple categories but a category preference is set, respect that preference
    if category_preference and has_movie_results and has_tv_results:
        if category_preference == "MOVIE" and has_movie_results:
            if debug:
                console.print("[green]Found both movie and TV results, using movie based on preference")
            return "MOVIE", info['movie_results'][0]['id'], info['movie_results'][0].get('original_language')
        elif category_preference == "TV" and has_tv_results:
            if debug:
                console.print("[green]Found both movie and TV results, using TV based on preference")
            return "TV", info['tv_results'][0]['id'], info['tv_results'][0].get('original_language')

    # If no preference or preference doesn't match available results, proceed with normal logic
    if has_movie_results:
        if debug:
            console.print("Movie INFO", info)
        return "MOVIE", info['movie_results'][0]['id'], info['movie_results'][0].get('original_language')

    elif has_tv_results:
        if debug:
            console.print("TV INFO", info)
        return "TV", info['tv_results'][0]['id'], info['tv_results'][0].get('original_language')

    console.print("[yellow]TMDb was unable to find anything with that IMDb ID, checking TVDb...")

    # If both TMDb and TVDb fail, fetch IMDb info and attempt a title search
    imdb_id = imdb_id.replace("tt", "")
    imdb_id = int(imdb_id) if imdb_id.isdigit() else 0
    imdb_info = imdb_info or await get_imdb_info_api(imdb_id, {})
    title = imdb_info.get("title") or filename
    year = imdb_info.get("year") or search_year
    original_language = imdb_info.get("original language", "en")

    console.print(f"[yellow]TMDb was unable to find anything from external IDs, searching TMDb for {title} ({year})[/yellow]")

    # Create meta dictionary with minimal required fields
    meta = {
        'tmdb_id': 0,
        'category': "MOVIE",  # Default to MOVIE
        'debug': debug,
        'mode': mode
    }

    # Try as movie first
    tmdb_id, category = await get_tmdb_id(
        title,
        year,
        meta,
        "MOVIE",
        imdb_info.get('original title', imdb_info.get('localized title', None))
    )

    # If no results, try as TV
    if tmdb_id == 0:
        meta['category'] = "TV"
        tmdb_id, category = await get_tmdb_id(
            title,
            year,
            meta,
            "TV",
            imdb_info.get('original title', imdb_info.get('localized title', None))
        )

    # Extract necessary values from the result
    tmdb_id = tmdb_id or 0
    category = category or "MOVIE"

    # **User Prompt for Manual TMDb ID Entry**
    if tmdb_id in ('None', '', None, 0, '0') and mode == "cli":
        console.print('[yellow]Unable to find a matching TMDb entry[/yellow]')
        tmdb_id = console.input("Please enter TMDb ID (format: tv/12345 or movie/12345): ")
        parser = Args(config=config)
        category, tmdb_id = parser.parse_tmdb_id(id=tmdb_id, category=category)

    return category, tmdb_id, original_language


async def get_tmdb_id(filename, search_year, category, untouched_filename="", attempted=0, debug=False, secondary_title=None, path=None, final_attempt=None):
    search_results = {"results": []}
    secondary_results = {"results": []}
    if final_attempt is None:
        final_attempt = False
    if attempted is None:
        attempted = 0

    async with httpx.AsyncClient() as client:
        try:
            # Primary search attempt with year
            if category == "MOVIE":
                if debug:
                    console.print(f"[green]Searching TMDb for movie:[/] [cyan]{filename}[/cyan] (Year: {search_year})")

                params = {
                    "api_key": TMDB_API_KEY,
                    "query": filename,
                    "language": "en-US",
                    "include_adult": "true"
                }

                if search_year:
                    params["year"] = search_year

                response = await client.get(f"{TMDB_BASE_URL}/search/movie", params=params)
                try:
                    response.raise_for_status()
                    search_results = response.json()
                except Exception:
                    console.print(f"[bold red]Failure with primary movie search: {response.status_code}[/bold red]")

            elif category == "TV":
                if debug:
                    console.print(f"[green]Searching TMDb for TV show:[/] [cyan]{filename}[/cyan] (Year: {search_year})")

                params = {
                    "api_key": TMDB_API_KEY,
                    "query": filename,
                    "language": "en-US",
                    "include_adult": "true"
                }

                if search_year:
                    params["first_air_date_year"] = search_year

                response = await client.get(f"{TMDB_BASE_URL}/search/tv", params=params)
                try:
                    response.raise_for_status()
                    search_results = response.json()
                except Exception:
                    console.print(f"[bold red]Failed with primary TV search: {response.status_code}[/bold red]")

            if debug:
                console.print(f"[yellow]Search results (primary): {json.dumps(search_results.get('results', [])[:2], indent=2)}[/yellow]")

            # Check if results were found
            if search_results.get('results'):
                tmdb_id = search_results['results'][0]['id']
                return tmdb_id, category

            # If no results and we have a secondary title, try searching with that
            if not search_results.get('results') and secondary_title and attempted < 3:
                console.print(f"[yellow]No results found for primary title. Trying secondary title: {secondary_title}[/yellow]")
                secondary_meta = await get_tmdb_id(
                    secondary_title,
                    search_year,
                    category,
                    untouched_filename,
                    attempted + 1,
                    debug=debug,
                    secondary_title=secondary_title
                )

                if secondary_meta.get('tmdb_id', 0) != 0:
                    tmdb_id = secondary_meta['tmdb_id']
                    return tmdb_id, category

        except Exception as e:
            console.print(f"[bold red]TMDb search error:[/bold red] {e}")
            search_results = {"results": []}  # Reset search_results on exception

        # Secondary attempt: Try searching without the year
        console.print("[yellow]Retrying without year...[/yellow]")
        try:
            if category == "MOVIE":
                if debug:
                    console.print(f"[green]Searching TMDb for movie:[/] [cyan]{filename}[/cyan] (Without year)")

                params = {
                    "api_key": TMDB_API_KEY,
                    "query": filename,
                    "language": "en-US",
                    "include_adult": "true"
                }

                response = await client.get(f"{TMDB_BASE_URL}/search/movie", params=params)
                try:
                    response.raise_for_status()
                    search_results = response.json()
                except Exception:
                    console.print(f"[bold red]Failed with secondary movie search: {response.status_code}[/bold red]")

            elif category == "TV":
                if debug:
                    console.print(f"[green]Searching TMDb for TV show:[/] [cyan]{filename}[/cyan] (Without year)")

                params = {
                    "api_key": TMDB_API_KEY,
                    "query": filename,
                    "language": "en-US",
                    "include_adult": "true"
                }

                response = await client.get(f"{TMDB_BASE_URL}/search/tv", params=params)
                try:
                    response.raise_for_status()
                    search_results = response.json()
                except Exception:
                    console.print(f"[bold red]Failed secondary TV search: {response.status_code}[/bold red]")

            if debug:
                console.print(f"[yellow]Search results (secondary): {json.dumps(search_results.get('results', [])[:2], indent=2)}[/yellow]")

            # Check if results were found
            if search_results.get('results'):
                tmdb_id = search_results['results'][0]['id']
                return tmdb_id, category

            # Try with secondary title without year
            if not search_results.get('results') and secondary_title and attempted < 3:
                console.print(f"[yellow]No results found for primary title without year. Trying secondary title: {secondary_title}[/yellow]")

                if category == "MOVIE":
                    if debug:
                        console.print(f"[green]Searching TMDb for movie with secondary title:[/] [cyan]{secondary_title}[/cyan] (Without year)")

                    params = {
                        "api_key": TMDB_API_KEY,
                        "query": secondary_title,
                        "language": "en-US",
                        "include_adult": "true"
                    }

                    response = await client.get(f"{TMDB_BASE_URL}/search/movie", params=params)
                    try:
                        response.raise_for_status()
                        secondary_results = response.json()
                    except Exception:
                        console.print(f"[bold red]Failed with secondary title movie search: {response.status_code}[/bold red]")

                elif category == "TV":
                    if debug:
                        console.print(f"[green]Searching TMDb for TV show with secondary title:[/] [cyan]{secondary_title}[/cyan] (Without year)")

                    params = {
                        "api_key": TMDB_API_KEY,
                        "query": secondary_title,
                        "language": "en-US",
                        "include_adult": "true"
                    }

                    response = await client.get(f"{TMDB_BASE_URL}/search/tv", params=params)
                    try:
                        response.raise_for_status()
                        secondary_results = response.json()
                    except Exception:
                        console.print(f"[bold red]Failed with secondary title TV search: {response.status_code}[/bold red]")

                if debug:
                    console.print(f"[yellow]Secondary title search results: {json.dumps(secondary_results.get('results', [])[:2], indent=2)}[/yellow]")

                if secondary_results.get('results'):
                    tmdb_id = secondary_results['results'][0]['id']
                    return tmdb_id, category

        except Exception as e:
            console.print(f"[bold red]Secondary search error:[/bold red] {e}")

        # If still no match, attempt alternative category switch
        if attempted < 1:
            new_category = "TV" if category == "MOVIE" else "MOVIE"
            console.print(f"[bold yellow]Switching category to {new_category} and retrying...[/bold yellow]")
            return await get_tmdb_id(filename, search_year, new_category, untouched_filename, attempted + 1, debug=debug, secondary_title=secondary_title, path=path)

        # Last attempt: Try parsing a better title
        if attempted == 1:
            try:
                parsed_title = anitopy.parse(
                    guessit(untouched_filename, {"excludes": ["country", "language"]})['title']
                )['anime_title']
                original_category = "MOVIE"
                console.print(f"[bold yellow]Trying parsed title: {parsed_title}[/bold yellow]")
                return await get_tmdb_id(parsed_title, search_year, original_category, untouched_filename, attempted + 2, debug=debug, secondary_title=secondary_title, path=path)
            except KeyError:
                console.print("[bold red]Failed to parse title for TMDb search.[/bold red]")

        # lets try with a folder name if we have one
        if attempted > 1 and path and not final_attempt:
            try:
                folder_name = os.path.basename(path).replace("_", "").replace("-", "") if path else ""
                title = guessit(folder_name, {"excludes": ["country", "language"]})['title']
                original_category = "MOVIE"
                console.print(f"[bold yellow]Trying folder name: {title}[/bold yellow]")
                return await get_tmdb_id(title, search_year, original_category, untouched_filename, attempted + 3, debug=debug, secondary_title=secondary_title, path=path, final_attempt=True)
            except Exception as e:
                console.print(f"[bold red]Folder name search error:[/bold red] {e}")
                search_results = {"results": []}

        # No match found, prompt user if in CLI mode
        console.print(f"[bold red]Unable to find TMDb match for {filename}[/bold red]")

        tmdb_id = cli_ui.ask_string("Please enter TMDb ID in this format: tv/12345 or movie/12345")
        parser = Args(config=config)
        category, tmdb_id = parser.parse_tmdb_id(id=tmdb_id, category=category)

        return tmdb_id, category


async def tmdb_other_meta(
    tmdb_id,
    path=None,
    search_year=None,
    category=None,
    imdb_id=0,
    manual_language=None,
    anime=False,
    mal_manual=None,
    aka='',
    original_language=None,
    poster=None,
    debug=False,
    mode="discord",
    tvdb_id=0,
    quickie_search=False
):
    """
    Fetch metadata from TMDB for a movie or TV show.
    Returns a dictionary containing metadata that can be used to update the meta object.
    """
    tmdb_metadata = {}

    # Initialize variables that might not be set in all code paths
    retrieved_aka = ""
    year = None
    title = None
    youtube = None
    overview = ""
    genres = ""
    genre_ids = ""
    keywords = ""
    directors = []
    original_title = ""
    runtime = 60
    certification = ""
    backdrop = ""
    logo_path = ""
    poster_path = ""
    tmdb_type = ""
    mal_id = 0
    demographic = ""
    imdb_mismatch = False

    if tmdb_id == 0:
        try:
            title = guessit(path, {"excludes": ["country", "language"]})['title'].lower()
            title = title.split('aka')[0]
            result = await get_tmdb_id(
                guessit(title, {"excludes": ["country", "language"]})['title'],
                search_year,
                {'tmdb_id': 0, 'search_year': search_year, 'debug': debug, 'category': category, 'mode': mode},
                category
            )

            if result['tmdb_id'] == 0:
                result = await get_tmdb_id(
                    title,
                    "",
                    {'tmdb_id': 0, 'search_year': "", 'debug': debug, 'category': category, 'mode': mode},
                    category
                )

            tmdb_id = result['tmdb_id']

            if tmdb_id == 0:
                if mode == 'cli':
                    console.print("[bold red]Unable to find tmdb entry. Exiting.")
                    exit()
                else:
                    console.print("[bold red]Unable to find tmdb entry")
                    return {}
        except Exception:
            if mode == 'cli':
                console.print("[bold red]Unable to find tmdb entry. Exiting.")
                exit()
            else:
                console.print("[bold red]Unable to find tmdb entry")
                return {}

    youtube = None
    title = None
    year = None
    original_imdb_id = imdb_id

    async with httpx.AsyncClient() as client:
        # Get main media details first (movie or TV show)
        main_url = f"{TMDB_BASE_URL}/{('movie' if category == 'MOVIE' else 'tv')}/{tmdb_id}"

        # Make the main API call to get basic data
        response = await client.get(main_url, params={"api_key": TMDB_API_KEY})
        try:
            response.raise_for_status()
            media_data = response.json()
        except Exception:
            console.print(f"[bold red]Failed to fetch media data: {response.status_code}[/bold red]")
            return {}

        if debug:
            console.print(f"[cyan]TMDB Response: {json.dumps(media_data, indent=2)[:600]}...")

        # Extract basic info from media_data
        if category == "MOVIE":
            title = media_data['title']
            original_title = media_data.get('original_title', title)
            year = datetime.strptime(media_data['release_date'], '%Y-%m-%d').year if media_data['release_date'] else search_year
            runtime = media_data.get('runtime', 60)
            if quickie_search or not imdb_id:
                imdb_id_str = str(media_data.get('imdb_id', '')).replace('tt', '')
                if imdb_id_str == "None":
                    imdb_id_str = ""
                if imdb_id and imdb_id_str and (int(imdb_id_str) != imdb_id):
                    imdb_mismatch = True
                imdb_id = int(imdb_id_str) if imdb_id_str.isdigit() else 0
            tmdb_type = 'Movie'
        else:  # TV show
            title = media_data['name']
            original_title = media_data.get('original_name', title)
            year = datetime.strptime(media_data['first_air_date'], '%Y-%m-%d').year if media_data['first_air_date'] else search_year
            runtime_list = media_data.get('episode_run_time', [60])
            runtime = runtime_list[0] if runtime_list else 60
            tmdb_type = media_data.get('type', 'Scripted')

        overview = media_data['overview']
        original_language_from_tmdb = media_data['original_language']

        poster_path = media_data.get('poster_path', '')
        if poster is None and poster_path:
            poster = f"https://image.tmdb.org/t/p/original{poster_path}"

        backdrop = media_data.get('backdrop_path', '')
        if backdrop:
            backdrop = f"https://image.tmdb.org/t/p/original{backdrop}"

        # Prepare all API endpoints for concurrent requests
        endpoints = [
            # External IDs
            client.get(f"{main_url}/external_ids", params={"api_key": TMDB_API_KEY}),
            # Videos
            client.get(f"{main_url}/videos", params={"api_key": TMDB_API_KEY}),
            # Keywords
            client.get(f"{main_url}/keywords", params={"api_key": TMDB_API_KEY}),
            # Credits
            client.get(f"{main_url}/credits", params={"api_key": TMDB_API_KEY})
        ]

        # Add logo request if needed
        if config['DEFAULT'].get('add_logo', False):
            endpoints.append(
                client.get(f"{TMDB_BASE_URL}/{('movie' if category == 'MOVIE' else 'tv')}/{tmdb_id}/images",
                           params={"api_key": TMDB_API_KEY})
            )

        # Add IMDB API call if we already have an IMDB ID
        if imdb_id != 0:
            # Get AKA and original language from IMDB immediately, don't wait
            endpoints.append(get_imdb_aka_api(imdb_id, manual_language))

        # Make all requests concurrently
        results = await asyncio.gather(*endpoints, return_exceptions=True)

        # Process results with the correct indexing
        external_data, videos_data, keywords_data, credits_data, *rest = results
        idx = 0
        logo_data = None
        imdb_data = None

        # Get logo data if it was requested
        if config['DEFAULT'].get('add_logo', False):
            logo_data = rest[idx]
            idx += 1

        # Get IMDB data if it was requested
        if imdb_id != 0:
            imdb_data = rest[idx]
            # Process IMDB data
            if isinstance(imdb_data, Exception):
                console.print("[yellow]Failed to get AKA and original language from IMDB[/yellow]")
                retrieved_aka, retrieved_original_language = "", None
            else:
                retrieved_aka, retrieved_original_language = imdb_data

        # Process external IDs
        if isinstance(external_data, Exception):
            console.print("[bold red]Failed to fetch external IDs[/bold red]")
        else:
            try:
                external = external_data.json()
                # Process IMDB ID
                if quickie_search or imdb_id == 0:
                    imdb_id_str = external.get('imdb_id', None)
                    if imdb_id_str and imdb_id_str not in ["", " ", "None", None]:
                        imdb_id_clean = imdb_id_str.lstrip('t')
                        if imdb_id_clean.isdigit():
                            imdb_id_clean_int = int(imdb_id_clean)
                            if imdb_id_clean_int != int(original_imdb_id) and quickie_search and original_imdb_id != 0:
                                imdb_mismatch = True
                                imdb_id = original_imdb_id
                            else:
                                imdb_id = int(imdb_id_clean)
                else:
                    imdb_id = int(imdb_id)

                # Process TVDB ID
                if tvdb_id == 0:
                    tvdb_id = external.get('tvdb_id', None)
                    if tvdb_id in ["", " ", "None", None]:
                        tvdb_id = 0
            except Exception:
                console.print("[bold red]Failed to process external IDs[/bold red]")

        # Process videos
        if isinstance(videos_data, Exception):
            console.print("[yellow]Unable to grab videos from TMDb.[/yellow]")
        else:
            try:
                videos = videos_data.json()
                for each in videos.get('results', []):
                    if each.get('site', "") == 'YouTube' and each.get('type', "") == "Trailer":
                        youtube = f"https://www.youtube.com/watch?v={each.get('key')}"
                        break
            except Exception:
                console.print("[yellow]Unable to process videos from TMDb.[/yellow]")

        # Process keywords
        if isinstance(keywords_data, Exception):
            console.print("[bold red]Failed to fetch keywords[/bold red]")
            keywords = ""
        else:
            try:
                kw_json = keywords_data.json()
                if category == "MOVIE":
                    keywords = ', '.join([keyword['name'].replace(',', ' ') for keyword in kw_json.get('keywords', [])])
                else:  # TV
                    keywords = ', '.join([keyword['name'].replace(',', ' ') for keyword in kw_json.get('results', [])])
            except Exception:
                console.print("[bold red]Failed to process keywords[/bold red]")
                keywords = ""

        # Process credits
        if isinstance(credits_data, Exception):
            console.print("[bold red]Failed to fetch credits[/bold red]")
            directors = []
        else:
            try:
                credits = credits_data.json()
                directors = []
                for each in credits.get('cast', []) + credits.get('crew', []):
                    if each.get('known_for_department', '') == "Directing" or each.get('job', '') == "Director":
                        directors.append(each.get('original_name', each.get('name')))
            except Exception:
                console.print("[bold red]Failed to process credits[/bold red]")
                directors = []

        # Process genres
        genres_data = await get_genres(media_data)
        genres = genres_data['genre_names']
        genre_ids = genres_data['genre_ids']

        # Process logo if needed
        if config['DEFAULT'].get('add_logo', False) and logo_data and not isinstance(logo_data, Exception):
            try:
                logo_json = logo_data.json()
                logo_path = await get_logo(tmdb_id, category, debug, TMDB_API_KEY=TMDB_API_KEY, TMDB_BASE_URL=TMDB_BASE_URL, logo_json=logo_json)
            except Exception:
                console.print("[yellow]Failed to process logo[/yellow]")
                logo_path = ""

    # Get AKA and original language from IMDB if needed
    if imdb_id != 0 and imdb_data is None:
        retrieved_aka, retrieved_original_language = await get_imdb_aka_api(imdb_id, manual_language)
    elif imdb_data is None:
        retrieved_aka, retrieved_original_language = "", None

    # Use retrieved original language or fallback to TMDB's value
    if retrieved_original_language is not None:
        original_language = retrieved_original_language
    else:
        original_language = original_language_from_tmdb

    # Get anime information if applicable
    if not anime:
        mal_id, retrieved_aka, anime, demographic = await get_anime(
            media_data,
            {'title': title, 'aka': retrieved_aka, 'mal_id': 0}
        )

    if mal_manual is not None and mal_manual != 0:
        mal_id = mal_manual

    # Check if AKA is too similar to title and clear it if needed
    if retrieved_aka:
        difference = SequenceMatcher(None, title.lower(), retrieved_aka[5:].lower()).ratio()
        if difference >= 0.7 or retrieved_aka[5:].strip() == "" or retrieved_aka[5:].strip().lower() in title.lower():
            retrieved_aka = ""
        if year and f"({year})" in retrieved_aka:
            retrieved_aka = retrieved_aka.replace(f"({year})", "").strip()

    # Build the metadata dictionary
    tmdb_metadata = {
        'title': title,
        'year': year,
        'imdb_id': imdb_id,
        'tvdb_id': tvdb_id,
        'original_language': original_language,
        'original_title': original_title,
        'keywords': keywords,
        'genres': genres,
        'genre_ids': genre_ids,
        'tmdb_directors': directors,
        'mal_id': mal_id,
        'anime': anime,
        'demographic': demographic,
        'retrieved_aka': retrieved_aka,
        'poster': poster,
        'tmdb_poster': poster_path,
        'logo': logo_path,
        'backdrop': backdrop,
        'overview': overview,
        'tmdb_type': tmdb_type,
        'runtime': runtime,
        'youtube': youtube,
        'certification': certification,
        'imdb_mismatch': imdb_mismatch
    }

    return tmdb_metadata


async def get_keywords(tmdb_id, category):
    """Get keywords for a movie or TV show using httpx"""
    endpoint = "movie" if category == "MOVIE" else "tv"
    url = f"{TMDB_BASE_URL}/{endpoint}/{tmdb_id}/keywords"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params={"api_key": TMDB_API_KEY})
            try:
                response.raise_for_status()
                data = response.json()
            except Exception:
                console.print(f"[bold red]Failed to fetch keywords: {response.status_code}[/bold red]")
                return ""

            if category == "MOVIE":
                keywords = [keyword['name'].replace(',', ' ') for keyword in data.get('keywords', [])]
            else:  # TV
                keywords = [keyword['name'].replace(',', ' ') for keyword in data.get('results', [])]

            return ', '.join(keywords)
        except Exception as e:
            console.print(f'[yellow]Failed to get keywords: {str(e)}')
            return ''


async def get_genres(response_data):
    """Extract genres from TMDB response data"""
    if response_data is not None:
        tmdb_genres = response_data.get('genres', [])

        if tmdb_genres:
            # Extract genre names and IDs
            genre_names = [genre['name'].replace(',', ' ') for genre in tmdb_genres]
            genre_ids = [str(genre['id']) for genre in tmdb_genres]

            # Create and return both strings
            return {
                'genre_names': ', '.join(genre_names),
                'genre_ids': ', '.join(genre_ids)
            }

    # Return empty values if no genres found
    return {
        'genre_names': '',
        'genre_ids': ''
    }


async def get_directors(tmdb_id, category):
    """Get directors for a movie or TV show using httpx"""
    endpoint = "movie" if category == "MOVIE" else "tv"
    url = f"{TMDB_BASE_URL}/{endpoint}/{tmdb_id}/credits"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params={"api_key": TMDB_API_KEY})
            try:
                response.raise_for_status()
                data = response.json()
            except Exception:
                console.print(f"[bold red]Failed to fetch credits: {response.status_code}[/bold red]")
                return []

            directors = []
            for each in data.get('cast', []) + data.get('crew', []):
                if each.get('known_for_department', '') == "Directing" or each.get('job', '') == "Director":
                    directors.append(each.get('original_name', each.get('name')))
            return directors
        except Exception as e:
            console.print(f'[yellow]Failed to get directors: {str(e)}')
            return []


async def get_anime(response, meta):
    tmdb_name = meta['title']
    if meta.get('aka', "") == "":
        alt_name = ""
    else:
        alt_name = meta['aka']
    anime = False
    animation = False
    demographic = ''
    for each in response['genres']:
        if each['id'] == 16:
            animation = True
    if response['original_language'] == 'ja' and animation is True:
        romaji, mal_id, eng_title, season_year, episodes, demographic = await get_romaji(tmdb_name, meta.get('mal_id', None))
        alt_name = f" AKA {romaji}"

        anime = True
        # mal = AnimeSearch(romaji)
        # mal_id = mal.results[0].mal_id
    else:
        mal_id = 0
    if meta.get('mal_id', 0) != 0:
        mal_id = meta.get('mal_id')
    return mal_id, alt_name, anime, demographic


async def get_romaji(tmdb_name, mal):
    if mal is None or mal == 0:
        tmdb_name = tmdb_name.replace('-', "").replace("The Movie", "")
        tmdb_name = ' '.join(tmdb_name.split())
        query = '''
            query ($search: String) {
                Page (page: 1) {
                    pageInfo {
                        total
                    }
                media (search: $search, type: ANIME, sort: SEARCH_MATCH) {
                    id
                    idMal
                    title {
                        romaji
                        english
                        native
                    }
                    seasonYear
                    episodes
                    tags {
                        name
                    }
                }
            }
        }
        '''
        # Define our query variables and values that will be used in the query request
        variables = {
            'search': tmdb_name
        }
    else:
        query = '''
            query ($search: Int) {
                Page (page: 1) {
                    pageInfo {
                        total
                    }
                media (idMal: $search, type: ANIME, sort: SEARCH_MATCH) {
                    id
                    idMal
                    title {
                        romaji
                        english
                        native
                    }
                    seasonYear
                    episodes
                    tags {
                        name
                    }
                }
            }
        }
        '''
        # Define our query variables and values that will be used in the query request
        variables = {
            'search': mal
        }

    # Make the HTTP Api request
    url = 'https://graphql.anilist.co'
    demographic = 'Mina'  # Default to Mina if no tags are found
    try:
        response = requests.post(url, json={'query': query, 'variables': variables})
        json = response.json()

        # console.print('Checking for demographic tags...')

        demographics = ["Shounen", "Seinen", "Shoujo", "Josei", "Kodomo", "Mina"]

        for tag in demographics:
            if tag in response.text:
                demographic = tag
                # print(f"Found {tag} tag")
                break

        media = json['data']['Page']['media']
    except Exception:
        console.print('[red]Failed to get anime specific info from anilist. Continuing without it...')
        media = []
    if media not in (None, []):
        result = {'title': {}}
        difference = 0
        for anime in media:
            search_name = re.sub(r"[^0-9a-zA-Z\[\\]]+", "", tmdb_name.lower().replace(' ', ''))
            for title in anime['title'].values():
                if title is not None:
                    title = re.sub(u'[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\uff00-\uff9f\u4e00-\u9faf\u3400-\u4dbf]+ (?=[A-Za-z ]+–)', "", title.lower().replace(' ', ''), re.U)
                    diff = SequenceMatcher(None, title, search_name).ratio()
                    if diff >= difference:
                        result = anime
                        difference = diff

        romaji = result['title'].get('romaji', result['title'].get('english', ""))
        mal_id = result.get('idMal', 0)
        eng_title = result['title'].get('english', result['title'].get('romaji', ""))
        season_year = result.get('season_year', "")
        episodes = result.get('episodes', 0)
    else:
        romaji = eng_title = season_year = ""
        episodes = mal_id = 0
    if mal_id in [None, 0]:
        mal_id = mal
    if not episodes:
        episodes = 0
    return romaji, mal_id, eng_title, season_year, episodes, demographic


async def get_tmdb_imdb_from_mediainfo(mediainfo, category, is_disc, tmdbid, imdbid):
    if not is_disc:
        if mediainfo['media']['track'][0].get('extra'):
            extra = mediainfo['media']['track'][0]['extra']
            for each in extra:
                try:
                    if each.lower().startswith('tmdb'):
                        parser = Args(config=config)
                        category, tmdbid = parser.parse_tmdb_id(id=extra[each], category=category)
                    if each.lower().startswith('imdb'):
                        try:
                            imdb_id = extract_imdb_id(extra[each])
                            if imdb_id:
                                imdbid = imdb_id
                        except Exception:
                            pass
                except Exception:
                    pass

    return category, tmdbid, imdbid


def extract_imdb_id(value):
    """Extract IMDb ID from various formats"""
    patterns = [
        r'/title/(tt\d+)',  # URL format
        r'^(tt\d+)$',       # Direct tt format
        r'^(\d+)$'          # Plain number
    ]

    for pattern in patterns:
        match = re.search(pattern, value)
        if match:
            imdb_id = match.group(1)
            if not imdb_id.startswith('tt'):
                imdb_id = f"tt{imdb_id}"
            return int(imdb_id.replace('tt', ''))

    return None


async def daily_to_tmdb_season_episode(tmdbid, date):
    date = datetime.fromisoformat(str(date))

    async with httpx.AsyncClient() as client:
        # Get TV show information to get seasons
        response = await client.get(
            f"{TMDB_BASE_URL}/tv/{tmdbid}",
            params={"api_key": TMDB_API_KEY}
        )
        try:
            response.raise_for_status()
            tv_data = response.json()
            seasons = tv_data.get('seasons', [])
        except Exception:
            console.print(f"[bold red]Failed to fetch TV data: {response.status_code}[/bold red]")
            return 0, 0

        # Find the latest season that aired before or on the target date
        season = 1
        for each in seasons:
            if not each.get('air_date'):
                continue

            air_date = datetime.fromisoformat(each['air_date'])
            if air_date <= date:
                season = int(each['season_number'])

        # Get the specific season information
        season_response = await client.get(
            f"{TMDB_BASE_URL}/tv/{tmdbid}/season/{season}",
            params={"api_key": TMDB_API_KEY}
        )
        try:
            season_response.raise_for_status()
            season_data = season_response.json()
            season_info = season_data.get('episodes', [])
        except Exception:
            console.print(f"[bold red]Failed to fetch season data: {season_response.status_code}[/bold red]")
            return 0, 0

        # Find the episode that aired on the target date
        episode = 1
        for each in season_info:
            if str(each.get('air_date', '')) == str(date.date()):
                episode = int(each['episode_number'])
                break
        else:
            console.print(f"[yellow]Unable to map the date ([bold yellow]{str(date)}[/bold yellow]) to a Season/Episode number")

    return season, episode


async def get_episode_details(tmdb_id, season_number, episode_number, debug=False):
    async with httpx.AsyncClient() as client:
        try:
            # Get episode details
            response = await client.get(
                f"{TMDB_BASE_URL}/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}",
                params={"api_key": TMDB_API_KEY, "append_to_response": "images,credits,external_ids"}
            )
            try:
                response.raise_for_status()
                episode_data = response.json()
            except Exception:
                console.print(f"[bold red]Failed to fetch episode data: {response.status_code}[/bold red]")
                return {}

            if debug:
                console.print(f"[cyan]Episode Data: {json.dumps(episode_data, indent=2)[:600]}...")

            # Extract relevant information
            episode_info = {
                'name': episode_data.get('name', ''),
                'overview': episode_data.get('overview', ''),
                'air_date': episode_data.get('air_date', ''),
                'still_path': episode_data.get('still_path', ''),
                'vote_average': episode_data.get('vote_average', 0),
                'episode_number': episode_data.get('episode_number', 0),
                'season_number': episode_data.get('season_number', 0),
                'runtime': episode_data.get('runtime', 0),
                'crew': [],
                'guest_stars': [],
                'director': '',
                'writer': '',
                'imdb_id': episode_data.get('external_ids', {}).get('imdb_id', '')
            }

            # Extract crew information
            for crew_member in episode_data.get('crew', []):
                episode_info['crew'].append({
                    'name': crew_member.get('name', ''),
                    'job': crew_member.get('job', ''),
                    'department': crew_member.get('department', '')
                })

                # Extract director and writer specifically
                if crew_member.get('job') == 'Director':
                    episode_info['director'] = crew_member.get('name', '')
                elif crew_member.get('job') == 'Writer':
                    episode_info['writer'] = crew_member.get('name', '')

            # Extract guest stars
            for guest in episode_data.get('guest_stars', []):
                episode_info['guest_stars'].append({
                    'name': guest.get('name', ''),
                    'character': guest.get('character', ''),
                    'profile_path': guest.get('profile_path', '')
                })

            # Get full image URLs
            if episode_info['still_path']:
                episode_info['still_url'] = f"https://image.tmdb.org/t/p/original{episode_info['still_path']}"

            return episode_info

        except Exception:
            console.print(f"[red]Error fetching episode details for {tmdb_id}[/red]")
            console.print(f"[red]Season: {season_number}, Episode: {episode_number}[/red]")
            return {}


async def get_logo(tmdb_id, category, debug=False, logo_languages=None, TMDB_API_KEY=None, TMDB_BASE_URL=None, logo_json=None):
    logo_path = ""
    if logo_languages and isinstance(logo_languages, str) and ',' in logo_languages:
        logo_languages = [lang.strip() for lang in logo_languages.split(',')]
        if debug:
            console.print(f"[cyan]Parsed logo languages from comma-separated string: {logo_languages}[/cyan]")

    elif logo_languages is None:
        # Get preferred languages in order (from config, then 'en' as fallback)
        logo_languages = [config['DEFAULT'].get('logo_language', 'en'), 'en']
    elif isinstance(logo_languages, str):
        logo_languages = [logo_languages, 'en']

    # Remove duplicates while preserving order
    logo_languages = list(dict.fromkeys(logo_languages))

    if debug:
        console.print(f"[cyan]Looking for logos in languages (in order): {logo_languages}[/cyan]")

    try:
        # Use provided logo_json if available, otherwise fetch it
        image_data = None
        if logo_json:
            image_data = logo_json
            if debug:
                console.print("[cyan]Using provided logo_json data instead of making an HTTP request[/cyan]")
        else:
            # Make HTTP request only if logo_json is not provided
            async with httpx.AsyncClient() as client:
                endpoint = "tv" if category == "TV" else "movie"
                image_response = await client.get(
                    f"{TMDB_BASE_URL}/{endpoint}/{tmdb_id}/images",
                    params={"api_key": TMDB_API_KEY}
                )
                try:
                    image_response.raise_for_status()
                    image_data = image_response.json()
                except Exception:
                    console.print(f"[bold red]Failed to fetch image data: {image_response.status_code}[/bold red]")
                    return ""

        if debug and image_data:
            console.print(f"[cyan]Image Data: {json.dumps(image_data, indent=2)[:500]}...")

        logos = image_data.get('logos', [])

        # Only look for logos that match our specified languages
        for language in logo_languages:
            matching_logo = next((logo for logo in logos if logo.get('iso_639_1') == language), "")
            if matching_logo:
                logo_path = f"https://image.tmdb.org/t/p/original{matching_logo['file_path']}"
                if debug:
                    console.print(f"[cyan]Found logo in language '{language}': {logo_path}[/cyan]")
                break

        # fallback to getting logo with null language if no match found, especially useful for movies it seems
        if not logo_path:
            null_language_logo = next((logo for logo in logos if logo.get('iso_639_1') is None or logo.get('iso_639_1') == ''), None)
            if null_language_logo:
                logo_path = f"https://image.tmdb.org/t/p/original{null_language_logo['file_path']}"
                if debug:
                    console.print(f"[cyan]Found logo with null language: {logo_path}[/cyan]")

        if not logo_path and debug:
            console.print("[yellow]No suitable logo found in preferred languages or null language[/yellow]")

    except Exception as e:
        console.print(f"[red]Error fetching logo: {e}[/red]")

    return logo_path
