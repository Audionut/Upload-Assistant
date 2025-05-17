from src.console import console
from src.imdb import get_imdb_aka_api, get_imdb_info_api, search_imdb
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

TMDB_API_KEY = config['DEFAULT'].get('tmdb_api', False)
TMDB_BASE_URL = "https://api.themoviedb.org/3"


async def get_tmdb_from_imdb(imdb_id, tvdb_id=None, search_year=None, filename=None, debug=False, mode="discord", category_preference=None):
    """Fetches TMDb ID using IMDb or TVDb ID.

    - Returns `(category, tmdb_id, original_language)`
    - If TMDb fails, prompts the user (if in CLI mode).
    """
    if not str(imdb_id).startswith("tt"):
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
    imdb_info = await get_imdb_info_api(imdb_id.replace('tt', ''), {})
    title = imdb_info.get("title") or filename
    year = imdb_info.get("year") or search_year

    console.print(f"[yellow]TMDb was unable to find anything from external IDs, searching TMDb for {title} ({year})[/yellow]")

    # Create meta dictionary with minimal required fields
    meta = {
        'tmdb_id': 0,
        'category': "MOVIE",  # Default to MOVIE
        'debug': debug,
        'mode': mode
    }

    # Try as movie first
    result = await get_tmdb_id(
        title,
        year,
        meta,
        "MOVIE",
        imdb_info.get('original title', imdb_info.get('localized title', None))
    )

    # If no results, try as TV
    if result['tmdb_id'] == 0:
        meta['category'] = "TV"
        result = await get_tmdb_id(
            title,
            year,
            meta,
            "TV",
            imdb_info.get('original title', imdb_info.get('localized title', None))
        )

    # Extract necessary values from the result
    tmdb_id = result.get('tmdb_id', 0)
    category = result.get('category', "MOVIE")
    original_language = result.get('original_language', "en")

    # **User Prompt for Manual TMDb ID Entry**
    if tmdb_id in ('None', '', None, 0, '0') and mode == "cli":
        console.print('[yellow]Unable to find a matching TMDb entry[/yellow]')
        tmdb_id = console.input("Please enter TMDb ID (format: tv/12345 or movie/12345): ")
        parser = Args(config=config)
        category, tmdb_id = parser.parse_tmdb_id(id=tmdb_id, category=category)

    return category, tmdb_id, original_language


async def get_tmdb_id(filename, search_year, meta, category, untouched_filename="", attempted=0):
    if meta['debug']:
        console.print("[bold cyan]Fetching TMDB ID...[/bold cyan]")

    search_results = {"results": []}
    secondary_results = {"results": []}

    async with httpx.AsyncClient() as client:
        try:
            # Primary search attempt with year
            if category == "MOVIE":
                if meta.get('debug', False):
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
                    console.print(f"[bold red]Failed to fetch movie data: {response.status_code}[/bold red]")
                    return meta

            elif category == "TV":
                if meta.get('debug', False):
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
                    console.print(f"[bold red]Failed to fetch TV data: {response.status_code}[/bold red]")
                    return meta

            if meta.get('debug', False):
                console.print(f"[yellow]Search results (primary): {json.dumps(search_results.get('results', [])[:2], indent=2)}[/yellow]")

            # Check if results were found
            if search_results.get('results'):
                meta['tmdb_id'] = search_results['results'][0]['id']
                return meta

            # If no results and we have a secondary title, try searching with that
            if not search_results.get('results') and meta.get('secondary_title') and attempted < 3:
                console.print(f"[yellow]No results found for primary title. Trying secondary title: {meta['secondary_title']}[/yellow]")
                secondary_meta = await get_tmdb_id(
                    meta['secondary_title'],
                    search_year,
                    meta,
                    category,
                    untouched_filename,
                    attempted + 1
                )

                if secondary_meta.get('tmdb_id', 0) != 0:
                    return secondary_meta

        except Exception as e:
            console.print(f"[bold red]TMDb search error:[/bold red] {e}")
            search_results = {"results": []}  # Reset search_results on exception

        # Secondary attempt: Try searching without the year
        console.print("[yellow]Retrying without year...[/yellow]")
        try:
            if category == "MOVIE":
                if meta.get('debug', False):
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
                    console.print(f"[bold red]Failed to fetch movie data: {response.status_code}[/bold red]")
                    return meta

            elif category == "TV":
                if meta.get('debug', False):
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
                    console.print(f"[bold red]Failed to fetch TV data: {response.status_code}[/bold red]")
                    return meta

            if meta.get('debug', False):
                console.print(f"[yellow]Search results (secondary): {json.dumps(search_results.get('results', [])[:2], indent=2)}[/yellow]")

            # Check if results were found
            if search_results.get('results'):
                meta['tmdb_id'] = search_results['results'][0]['id']
                return meta

            # Try with secondary title without year
            if not search_results.get('results') and meta.get('secondary_title') and attempted < 3:
                console.print(f"[yellow]No results found for primary title without year. Trying secondary title: {meta['secondary_title']}[/yellow]")

                if category == "MOVIE":
                    if meta.get('debug', False):
                        console.print(f"[green]Searching TMDb for movie with secondary title:[/] [cyan]{meta['secondary_title']}[/cyan] (Without year)")

                    params = {
                        "api_key": TMDB_API_KEY,
                        "query": meta['secondary_title'],
                        "language": "en-US",
                        "include_adult": "true"
                    }

                    response = await client.get(f"{TMDB_BASE_URL}/search/movie", params=params)
                    try:
                        response.raise_for_status()
                        secondary_results = response.json()
                    except Exception:
                        console.print(f"[bold red]Failed to fetch movie data: {response.status_code}[/bold red]")
                        return meta

                elif category == "TV":
                    if meta.get('debug', False):
                        console.print(f"[green]Searching TMDb for TV show with secondary title:[/] [cyan]{meta['secondary_title']}[/cyan] (Without year)")

                    params = {
                        "api_key": TMDB_API_KEY,
                        "query": meta['secondary_title'],
                        "language": "en-US",
                        "include_adult": "true"
                    }

                    response = await client.get(f"{TMDB_BASE_URL}/search/tv", params=params)
                    try:
                        response.raise_for_status()
                        secondary_results = response.json()
                    except Exception:
                        console.print(f"[bold red]Failed to fetch TV data: {response.status_code}[/bold red]")
                        return meta

                if meta.get('debug', False):
                    console.print(f"[yellow]Secondary title search results: {json.dumps(secondary_results.get('results', [])[:2], indent=2)}[/yellow]")

                if secondary_results.get('results'):
                    meta['tmdb_id'] = secondary_results['results'][0]['id']
                    console.print(f"[green]Found match using secondary title: {meta['secondary_title']}[/green]")
                    return meta

        except Exception as e:
            console.print(f"[bold red]Secondary search error:[/bold red] {e}")

        # If still no match, attempt alternative category switch
        if attempted < 1:
            new_category = "TV" if category == "MOVIE" else "MOVIE"
            console.print(f"[bold yellow]Switching category to {new_category} and retrying...[/bold yellow]")
            return await get_tmdb_id(filename, search_year, meta, new_category, untouched_filename, attempted + 1)

        # Last attempt: Try parsing a better title
        if attempted == 1:
            try:
                parsed_title = anitopy.parse(
                    guessit(untouched_filename, {"excludes": ["country", "language"]})['title']
                )['anime_title']
                console.print(f"[bold yellow]Trying parsed title: {parsed_title}[/bold yellow]")
                return await get_tmdb_id(parsed_title, search_year, meta, meta['category'], untouched_filename, attempted + 2)
            except KeyError:
                console.print("[bold red]Failed to parse title for TMDb search.[/bold red]")

        # No match found, prompt user if in CLI mode
        console.print(f"[bold red]Unable to find TMDb match for {filename}[/bold red]")

        meta['imdb_id'] = await search_imdb(filename, meta['search_year'])
        console.print(f"[yellow]IMDB ID: {meta['imdb_id']}[/yellow]")
        if meta['imdb_id'] != 0:
            category, tmdb_id, original_language = await get_tmdb_from_imdb(
                meta['imdb_id'],
                meta.get('tvdb_id'),
                meta.get('search_year'),
                filename,
                debug=meta.get('debug', False),
                mode=meta.get('mode', 'discord'),
                category_preference=meta.get('category')
            )
            if tmdb_id != 0:
                meta['tmdb_id'] = tmdb_id
                meta['category'] = category
                meta['original_language'] = original_language
                return meta

        if meta.get('mode', 'discord') == 'cli':
            tmdb_id = cli_ui.ask_string("Please enter TMDb ID in this format: tv/12345 or movie/12345")
            parser = Args(config=config)
            meta['category'], meta['tmdb_id'] = parser.parse_tmdb_id(id=tmdb_id, category=meta.get('category'))
            meta['tmdb_manual'] = meta['tmdb_id']

        return meta


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
    tvdb_id=0
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

    async with httpx.AsyncClient() as client:
        if category == "MOVIE":
            # Get movie details
            response = await client.get(
                f"{TMDB_BASE_URL}/movie/{tmdb_id}",
                params={"api_key": TMDB_API_KEY}
            )
            try:
                response.raise_for_status()
                movie_data = response.json()
            except Exception:
                console.print(f"[bold red]Failed to fetch movie data: {response.status_code}[/bold red]")
                return {}

            if debug:
                console.print(f"[cyan]TMDB Response: {json.dumps(movie_data, indent=2)[:600]}...")

            title = movie_data['title']
            year = None
            if movie_data['release_date']:
                year = datetime.strptime(movie_data['release_date'], '%Y-%m-%d').year
            else:
                console.print('[yellow]TMDB does not have a release date, using manual year or year from filename instead (if it exists)')
                year = search_year

            # Get external IDs
            external_resp = await client.get(
                f"{TMDB_BASE_URL}/movie/{tmdb_id}/external_ids",
                params={"api_key": TMDB_API_KEY}
            )
            try:
                external_resp.raise_for_status()
                external = external_resp.json()
            except Exception:
                console.print(f"[bold red]Failed to fetch external ids: {response.status_code}[/bold red]")
                return {}

            if imdb_id == 0:
                imdb_id_str = external.get('imdb_id', None)

                if not imdb_id_str or imdb_id_str in ["", " ", "None", None]:
                    imdb_id = 0
                else:
                    imdb_id_clean = imdb_id_str.lstrip('t')  # Remove 'tt' prefix safely
                    if imdb_id_clean.isdigit():  # Ensure it's a valid numeric string
                        imdb_id = int(imdb_id_clean)
                    else:
                        console.print(f"[bold red]Invalid IMDb ID returned: {imdb_id_str}[/bold red]")
                        imdb_id = 0
            else:
                imdb_id = int(imdb_id)

            # TVDB ID Handling
            if tvdb_id == 0:
                tvdb_id = external.get('tvdb_id', None)
                if tvdb_id in ["", " ", "None", None]:
                    tvdb_id = 0

            # Get videos
            try:
                videos_resp = await client.get(
                    f"{TMDB_BASE_URL}/movie/{tmdb_id}/videos",
                    params={"api_key": TMDB_API_KEY}
                )
                videos_resp.raise_for_status()
                videos = videos_resp.json()

                for each in videos.get('results', []):
                    if each.get('site', "") == 'YouTube' and each.get('type', "") == "Trailer":
                        youtube = f"https://www.youtube.com/watch?v={each.get('key')}"
                        break
            except Exception:
                console.print('[yellow]Unable to grab videos from TMDb.')

            retrieved_aka, retrieved_original_language = await get_imdb_aka_api(imdb_id, manual_language)

            if retrieved_original_language is not None:
                original_language = retrieved_original_language
            else:
                original_language = movie_data['original_language']

            original_title = movie_data.get('original_title', title)

            # Get keywords
            keywords_resp = await client.get(
                f"{TMDB_BASE_URL}/movie/{tmdb_id}/keywords",
                params={"api_key": TMDB_API_KEY}
            )
            try:
                keywords_resp.raise_for_status()
                keywords_data = keywords_resp.json()
            except Exception:
                console.print(f"[bold red]Failed to fetch keywords: {response.status_code}[/bold red]")
                return {}
            keywords = ', '.join([keyword['name'].replace(',', ' ') for keyword in keywords_data.get('keywords', [])])

            # Get genres
            genres_data = await get_genres(movie_data)  # or tv_data
            genres = genres_data['genre_names']
            genre_ids = genres_data['genre_ids']

            # Get directors
            credits_resp = await client.get(
                f"{TMDB_BASE_URL}/movie/{tmdb_id}/credits",
                params={"api_key": TMDB_API_KEY}
            )
            try:
                credits_resp.raise_for_status()
                credits_data = credits_resp.json()
            except Exception:
                console.print(f"[bold red]Failed to fetch credits: {response.status_code}[/bold red]")
                return {}

            directors = []
            for each in credits_data.get('cast', []) + credits_data.get('crew', []):
                if each.get('known_for_department', '') == "Directing" or each.get('job', '') == "Director":
                    directors.append(each.get('original_name', each.get('name')))

            mal_id = 0
            demographic = ''

            if not anime:
                mal_id, retrieved_aka, anime, demographic = await get_anime(
                    movie_data,
                    {'title': title, 'aka': retrieved_aka, 'mal_id': 0}
                )

            if mal_manual is not None and mal_manual != 0:
                mal_id = mal_manual

            poster_path = movie_data.get('poster_path', "")
            if poster is None and poster_path:
                poster = f"https://image.tmdb.org/t/p/original{poster_path}"

            backdrop = movie_data.get('backdrop_path', "")
            if backdrop:
                backdrop = f"https://image.tmdb.org/t/p/original{backdrop}"

            if config['DEFAULT'].get('add_logo', False):
                logo_path = await get_logo(tmdb_id, category, debug, TMDB_API_KEY=TMDB_API_KEY, TMDB_BASE_URL=TMDB_BASE_URL)

            overview = movie_data['overview']
            tmdb_type = 'Movie'
            runtime = movie_data.get('runtime', 60)
            certification = movie_data.get('certification', '')

        elif category == "TV":
            # Get TV show details
            response = await client.get(
                f"{TMDB_BASE_URL}/tv/{tmdb_id}",
                params={"api_key": TMDB_API_KEY}
            )
            try:
                response.raise_for_status()
                tv_data = response.json()
            except Exception:
                console.print(f"[bold red]Failed to fetch TV data: {response.status_code}[/bold red]")
                return {}

            if debug:
                console.print(f"[cyan]TMDB Response: {json.dumps(tv_data, indent=2)[:600]}...")

            title = tv_data['name']
            year = None
            if tv_data['first_air_date']:
                year = datetime.strptime(tv_data['first_air_date'], '%Y-%m-%d').year
            else:
                console.print('[yellow]TMDB does not have a release date, using manual year or year from filename instead (if it exists)')
                year = search_year

            # Get external IDs
            external_resp = await client.get(
                f"{TMDB_BASE_URL}/tv/{tmdb_id}/external_ids",
                params={"api_key": TMDB_API_KEY}
            )
            try:
                external_resp.raise_for_status()
                external = external_resp.json()
            except Exception:
                console.print(f"[bold red]Failed to fetch external ids: {response.status_code}[/bold red]")
                return {}

            if imdb_id == 0:
                imdb_id_str = external.get('imdb_id', None)

                if not imdb_id_str or imdb_id_str in ["", " ", "None", None]:
                    imdb_id = 0
                else:
                    imdb_id_clean = imdb_id_str.lstrip('t')  # Remove 'tt' prefix safely
                    if imdb_id_clean.isdigit():  # Ensure it's a valid numeric string
                        imdb_id = int(imdb_id_clean)
                    else:
                        console.print(f"[bold red]Invalid IMDb ID returned: {imdb_id_str}[/bold red]")
                        imdb_id = 0
            else:
                imdb_id = int(imdb_id)

            # TVDB ID Handling
            if tvdb_id == 0:
                tvdb_id = external.get('tvdb_id', None)
                if tvdb_id in ["", " ", "None", None]:
                    tvdb_id = 0

            # Get videos
            try:
                videos_resp = await client.get(
                    f"{TMDB_BASE_URL}/tv/{tmdb_id}/videos",
                    params={"api_key": TMDB_API_KEY}
                )
                try:
                    videos_resp.raise_for_status()
                    videos = videos_resp.json()
                except Exception:
                    console.print(f"[bold red]Failed to fetch videos: {response.status_code}[/bold red]")
                    return {}

                for each in videos.get('results', []):
                    if each.get('site', "") == 'YouTube' and each.get('type', "") == "Trailer":
                        youtube = f"https://www.youtube.com/watch?v={each.get('key')}"
                        break
            except Exception:
                console.print('[yellow]Unable to grab videos from TMDb.')

            retrieved_aka, retrieved_original_language = await get_imdb_aka_api(imdb_id, manual_language)

            if retrieved_original_language is not None:
                original_language = retrieved_original_language
            else:
                original_language = tv_data['original_language']

            original_title = tv_data.get('original_name', title)

            # Get keywords
            keywords_resp = await client.get(
                f"{TMDB_BASE_URL}/tv/{tmdb_id}/keywords",
                params={"api_key": TMDB_API_KEY}
            )
            try:
                keywords_resp.raise_for_status()
                keywords_data = keywords_resp.json()
            except Exception:
                console.print(f"[bold red]Failed to fetch keywords: {response.status_code}[/bold red]")
                return {}
            keywords = ', '.join([keyword['name'].replace(',', ' ') for keyword in keywords_data.get('results', [])])

            # Get genres
            genres_data = await get_genres(tv_data)
            genres = genres_data['genre_names']
            genre_ids = genres_data['genre_ids']
            # Get directors/creators
            credits_resp = await client.get(
                f"{TMDB_BASE_URL}/tv/{tmdb_id}/credits",
                params={"api_key": TMDB_API_KEY}
            )
            try:
                credits_resp.raise_for_status()
                credits_data = credits_resp.json()
            except Exception:
                console.print(f"[bold red]Failed to fetch credits: {response.status_code}[/bold red]")
                return {}

            directors = []
            for each in credits_data.get('cast', []) + credits_data.get('crew', []):
                if each.get('known_for_department', '') == "Directing" or each.get('job', '') == "Director":
                    directors.append(each.get('original_name', each.get('name')))

            mal_id, retrieved_aka, anime, demographic = await get_anime(
                tv_data,
                {'title': title, 'aka': aka if aka else retrieved_aka, 'mal_id': mal_manual if mal_manual else 0}
            )

            if mal_manual is not None and mal_manual != 0:
                mal_id = mal_manual

            poster_path = tv_data.get('poster_path', '')
            if poster is None and poster_path:
                poster = f"https://image.tmdb.org/t/p/original{poster_path}"

            backdrop = tv_data.get('backdrop_path', "")
            if backdrop:
                backdrop = f"https://image.tmdb.org/t/p/original{backdrop}"

            if config['DEFAULT'].get('add_logo', False):
                logo_path = await get_logo(tmdb_id, category, debug, TMDB_API_KEY=TMDB_API_KEY, TMDB_BASE_URL=TMDB_BASE_URL)

            overview = tv_data['overview']
            tmdb_type = tv_data.get('type', 'Scripted')

            runtime_list = tv_data.get('episode_run_time', [60])
            runtime = runtime_list[0] if runtime_list else 60
            certification = tv_data.get('certification', '')

    # Check if AKA is too similar to title and clear it if needed
    if retrieved_aka:
        difference = SequenceMatcher(None, title.lower(), retrieved_aka[5:].lower()).ratio()
        if difference >= 0.9 or retrieved_aka[5:].strip() == "" or retrieved_aka[5:].strip().lower() in title.lower():
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
        'aka': retrieved_aka,
        'poster': poster,
        'tmdb_poster': poster_path,
        'logo': logo_path,
        'backdrop': backdrop,
        'overview': overview,
        'tmdb_type': tmdb_type,
        'runtime': runtime,
        'youtube': youtube,
        'certification': certification
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
                if each.lower().startswith('tmdb'):
                    parser = Args(config=config)
                    category, tmdbid = parser.parse_tmdb_id(id=extra[each], category=category)
                if each.lower().startswith('imdb'):
                    try:
                        imdbid = str(int(extra[each].replace('tt', ''))).zfill(7)
                    except Exception:
                        pass
    return category, tmdbid, imdbid


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


async def get_logo(tmdb_id, category, debug=False, logo_languages=None, TMDB_API_KEY=None, TMDB_BASE_URL=None):
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
            if debug:
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

            # fallback to getting logo with null language if no match found, espicially useful for movies it seems
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
