from src.console import console
import httpx
import json


async def search_tvmaze(filename, year, imdbID, tvdbID, manual_date=None, tvmaze_manual=None, debug=False, return_full_tuple=False):
    """Searches TVMaze for a show using TVDB ID, IMDb ID, or a title query.

    - If `return_full_tuple=True`, returns `(tvmaze_id, imdbID, tvdbID)`.
    - Otherwise, only returns `tvmaze_id`.
    """
    if debug:
        console.print(f"[cyan]Searching TVMaze for TVDB {tvdbID} or IMDB {imdbID} or {filename} ({year})[/cyan]")
    # Convert TVDB ID to integer
    try:
        tvdbID = int(tvdbID) if tvdbID not in (None, '', '0') else 0
    except ValueError:
        console.print(f"[red]Error: tvdbID is not a valid integer. Received: {tvdbID}[/red]")
        tvdbID = 0

    # Handle IMDb ID - ensure it's an integer without tt prefix
    try:
        if isinstance(imdbID, str) and imdbID.startswith('tt'):
            imdbID = int(imdbID[2:])
        else:
            imdbID = int(imdbID) if imdbID not in (None, '', '0') else 0
    except ValueError:
        console.print(f"[red]Error: imdbID is not a valid integer. Received: {imdbID}[/red]")
        imdbID = 0

    # If manual selection has been provided, return it directly
    if tvmaze_manual:
        try:
            tvmaze_id = int(tvmaze_manual)
            return (tvmaze_id, imdbID, tvdbID) if return_full_tuple else tvmaze_id
        except (ValueError, TypeError):
            console.print(f"[red]Error: tvmaze_manual is not a valid integer. Received: {tvmaze_manual}[/red]")
            tvmaze_id = 0
            return (tvmaze_id, imdbID, tvdbID) if return_full_tuple else tvmaze_id

    tvmaze_id = 0
    results = []

    async def fetch_tvmaze_data(url, params):
        """Helper function to fetch data from TVMaze API."""
        response = await _make_tvmaze_request(url, params)
        if response:
            return [response] if isinstance(response, dict) else response
        return []

    if tvdbID:
        results.extend(await fetch_tvmaze_data("https://api.tvmaze.com/lookup/shows", {"thetvdb": tvdbID}))

    if not results and imdbID:
        results.extend(await fetch_tvmaze_data("https://api.tvmaze.com/lookup/shows", {"imdb": f"tt{imdbID:07d}"}))

    if not results:
        search_resp = await fetch_tvmaze_data("https://api.tvmaze.com/search/shows", {"q": filename})
        results.extend([each['show'] for each in search_resp if 'show' in each])

    if not results:
        first_two_words = " ".join(filename.split()[:2])
        if first_two_words and first_two_words != filename:
            search_resp = await fetch_tvmaze_data("https://api.tvmaze.com/search/shows", {"q": first_two_words})
            results.extend([each['show'] for each in search_resp if 'show' in each])

    # Deduplicate results by TVMaze ID
    seen = set()
    unique_results = [show for show in results if show['id'] not in seen and not seen.add(show['id'])]

    if not unique_results:
        if debug:
            console.print("[yellow]No TVMaze results found.[/yellow]")
        return (tvmaze_id, imdbID, tvdbID) if return_full_tuple else tvmaze_id

    # Manual selection process
    if manual_date is not None:
        console.print("[bold]Search results:[/bold]")
        for idx, show in enumerate(unique_results):
            console.print(f"[bold red]{idx + 1}[/bold red]. [green]{show.get('name', 'Unknown')} (TVmaze ID:[/green] [bold red]{show['id']}[/bold red])")
            console.print(f"[yellow]   Premiered: {show.get('premiered', 'Unknown')}[/yellow]")
            console.print(f"   Externals: {json.dumps(show.get('externals', {}), indent=2)}")

        while True:
            try:
                choice = int(input(f"Enter the number of the correct show (1-{len(unique_results)}) or 0 to skip: "))
                if choice == 0:
                    console.print("Skipping selection.")
                    break
                if 1 <= choice <= len(unique_results):
                    selected_show = unique_results[choice - 1]
                    tvmaze_id = int(selected_show['id'])
                    # set the tvdb id since it's sure to be correct
                    # won't get returned outside manual date since full tuple is not returned
                    if 'externals' in selected_show and 'thetvdb' in selected_show['externals']:
                        new_tvdb_id = selected_show['externals']['thetvdb']
                        if new_tvdb_id:
                            tvdbID = int(new_tvdb_id)
                            console.print(f"[green]Updated TVDb ID to: {tvdbID}[/green]")
                    console.print(f"Selected show: {selected_show.get('name')} (TVmaze ID: {tvmaze_id})")
                    break
                else:
                    console.print(f"Invalid choice. Please choose a number between 1 and {len(unique_results)}, or 0 to skip.")
            except ValueError:
                console.print("Invalid input. Please enter a number.")
    else:
        selected_show = unique_results[0]
        tvmaze_id = int(selected_show['id'])
        if debug:
            console.print(f"[cyan]Automatically selected show: {selected_show.get('name')} (TVmaze ID: {tvmaze_id})[/cyan]")

    if 'externals' in selected_show:
        if 'thetvdb' in selected_show['externals'] and not tvdbID:
            tvdbID = selected_show['externals']['thetvdb']
            if tvdbID:
                tvdbID = int(tvdbID)
                return_full_tuple = True
    if debug:
        console.print(f"[cyan]Returning TVmaze ID: {tvmaze_id} (type: {type(tvmaze_id).__name__}), IMDb ID: {imdbID} (type: {type(imdbID).__name__}), TVDB ID: {tvdbID} (type: {type(tvdbID).__name__})[/cyan]")
    if tvmaze_id is None:
        tvmaze_id = 0
    if imdbID is None:
        imdbID = 0
    if tvdbID is None:
        tvdbID = 0

    return (tvmaze_id, imdbID, tvdbID) if return_full_tuple else tvmaze_id


async def _make_tvmaze_request(url, params):
    """Sync function to make the request inside ThreadPoolExecutor."""
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            else:
                return None
    except httpx.HTTPStatusError as e:
        print(f"[ERROR] TVmaze API error: {e.response.status_code}")
    except httpx.RequestError as e:
        print(f"[ERROR] Network error while accessing TVmaze: {e}")
    return {}


async def get_tvmaze_episode_data(tvmaze_id, season, episode):
    url = f"https://api.tvmaze.com/shows/{tvmaze_id}/episodebynumber"
    params = {
        "season": season,
        "number": episode
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            if data:
                # Get show data for additional information
                show_data = {}
                if "show" in data.get("_links", {}) and "href" in data["_links"]["show"]:
                    show_url = data["_links"]["show"]["href"]
                    show_name = data["_links"]["show"].get("name", "")

                    show_response = await client.get(show_url, timeout=10.0)
                    if show_response.status_code == 200:
                        show_data = show_response.json()
                    else:
                        show_data = {"name": show_name}

                # Clean HTML tags from summary
                summary = data.get("summary", "")
                if summary:
                    summary = summary.replace("<p>", "").replace("</p>", "").strip()

                # Format the response in a consistent structure
                result = {
                    "episode_name": data.get("name", ""),
                    "overview": summary,
                    "season_number": data.get("season", season),
                    "episode_number": data.get("number", episode),
                    "air_date": data.get("airdate", ""),
                    "runtime": data.get("runtime", 0),
                    "series_name": show_data.get("name", data.get("_links", {}).get("show", {}).get("name", "")),
                    "series_overview": show_data.get("summary", "").replace("<p>", "").replace("</p>", "").strip(),
                    "image": data.get("image", {}).get("original", None) if data.get("image") else None,
                    "series_image": show_data.get("image", {}).get("original", None) if show_data.get("image") else None,
                }

                return result
            else:
                console.print(f"[yellow]No episode data found for S{season:02d}E{episode:02d}[/yellow]")
                return None

    except httpx.HTTPStatusError as e:
        console.print(f"[red]HTTP error occurred: {e.response.status_code} - {e.response.text}[/red]")
        return None
    except httpx.RequestError as e:
        console.print(f"[red]Request error occurred: {e}[/red]")
        return None
    except Exception as e:
        console.print(f"[red]Error fetching TVMaze episode data: {e}[/red]")
        return None
