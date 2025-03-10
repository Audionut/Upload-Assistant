from src.console import console
import httpx
import json


async def search_tvmaze(filename, year, imdbID, tvdbID, manual_date=None, tvmaze_manual=None, debug=False, return_full_tuple=False):
    """Searches TVMaze for a show using TVDB ID, IMDb ID, or a title query.

    - If `return_full_tuple=True`, returns `(tvmaze_id, imdbID, tvdbID)`.
    - Otherwise, only returns `tvmaze_id`.
    """
    try:
        tvdbID = int(tvdbID) if tvdbID is not None else 0
    except ValueError:
        print(f"Error: tvdbID is not a valid integer. Received: {tvdbID}")
        tvdbID = 0
    try:
        imdbID = f"{imdbID:07d}" if imdbID is not None else 0
    except ValueError:
        print(f"Error: imdbID is not a valid integer. Received: {imdbID}")
        imdbID = 0

    # If manual selection has been provided, return it directly
    if tvmaze_manual:
        return (int(tvmaze_manual), imdbID, tvdbID) if return_full_tuple else int(tvmaze_manual)

    tvmazeID = 0
    results = []

    async def fetch_tvmaze_data(url, params):
        """Helper function to fetch data from TVMaze API."""
        response = await _make_tvmaze_request(url, params)
        if response:
            return [response] if isinstance(response, dict) else response
        return []

    # Primary search logic
    if manual_date is None:
        if tvdbID:
            results.extend(await fetch_tvmaze_data("https://api.tvmaze.com/lookup/shows", {"thetvdb": tvdbID}))

        if not results and imdbID:
            results.extend(await fetch_tvmaze_data("https://api.tvmaze.com/lookup/shows", {"imdb": f"tt{imdbID}"}))

        if not results:
            search_resp = await fetch_tvmaze_data("https://api.tvmaze.com/search/shows", {"q": filename})
            results.extend([each['show'] for each in search_resp if 'show' in each])
    else:
        if tvdbID:
            results.extend(await fetch_tvmaze_data("https://api.tvmaze.com/lookup/shows", {"thetvdb": tvdbID}))

        if imdbID:
            results.extend(await fetch_tvmaze_data("https://api.tvmaze.com/lookup/shows", {"imdb": f"tt{imdbID}"}))

        search_resp = await fetch_tvmaze_data("https://api.tvmaze.com/search/shows", {"q": filename})
        results.extend([each['show'] for each in search_resp if 'show' in each])

    # Deduplicate results by TVMaze ID
    seen = set()
    unique_results = [show for show in results if show['id'] not in seen and not seen.add(show['id'])]

    if not unique_results:
        if debug:
            print("No results found.")
        return (tvmazeID, imdbID, tvdbID) if return_full_tuple else tvmazeID

    # Manual selection process
    if manual_date is not None:
        print("Search results:")
        for idx, show in enumerate(unique_results):
            console.print(f"[bold red]{idx + 1}[/bold red]. [green]{show.get('name', 'Unknown')} (TVmaze ID:[/green] [bold red]{show['id']}[/bold red])")
            console.print(f"[yellow]   Premiered: {show.get('premiered', 'Unknown')}[/yellow]")
            console.print(f"   Externals: {json.dumps(show.get('externals', {}), indent=2)}")

        while True:
            try:
                choice = int(input(f"Enter the number of the correct show (1-{len(unique_results)}) or 0 to skip: "))
                if choice == 0:
                    print("Skipping selection.")
                    break
                if 1 <= choice <= len(unique_results):
                    selected_show = unique_results[choice - 1]
                    tvmazeID = selected_show['id']
                    print(f"Selected show: {selected_show.get('name')} (TVmaze ID: {tvmazeID})")
                    break
                else:
                    print(f"Invalid choice. Please choose a number between 1 and {len(unique_results)}, or 0 to skip.")
            except ValueError:
                print("Invalid input. Please enter a number.")
    else:
        selected_show = unique_results[0]
        tvmazeID = selected_show['id']
        if debug:
            print(f"Automatically selected show: {selected_show.get('name')} (TVmaze ID: {tvmazeID})")

    if debug:
        print(f"Returning TVmaze ID: {tvmazeID}, IMDb ID: {imdbID}, TVDB ID: {tvdbID}")
    return (tvmazeID, imdbID, tvdbID) if return_full_tuple else tvmazeID


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
