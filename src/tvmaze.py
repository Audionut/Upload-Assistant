from src.console import console
import requests
import json


async def search_tvmaze(filename, year, imdbID, tvdbID, meta):
    try:
        tvdbID = int(tvdbID) if tvdbID is not None else 0
    except ValueError:
        print(f"Error: tvdbID is not a valid integer. Received: {tvdbID}")
        tvdbID = 0

    if meta.get('tvmaze_manual'):
        tvmazeID = int(meta['tvmaze_manual'])
        return tvmazeID, imdbID, tvdbID
    else:
        tvmazeID = 0
        results = []

        if imdbID is None:
            imdbID = '0'

        if meta['manual_date'] is None:
            if int(tvdbID) != 0:
                tvdb_resp = await _make_tvmaze_request("https://api.tvmaze.com/lookup/shows", {"thetvdb": tvdbID}, meta)
                if tvdb_resp:
                    results.append(tvdb_resp)
                else:
                    if int(imdbID) != 0:
                        imdb_resp = await _make_tvmaze_request("https://api.tvmaze.com/lookup/shows", {"imdb": f"tt{imdbID}"}, meta)
                        if imdb_resp:
                            results.append(imdb_resp)
                        else:
                            search_resp = await _make_tvmaze_request("https://api.tvmaze.com/search/shows", {"q": filename}, meta)
                            if search_resp:
                                if isinstance(search_resp, list):
                                    results.extend([each['show'] for each in search_resp if 'show' in each])
                                else:
                                    results.append(search_resp)
        else:
            if int(tvdbID) != 0:
                tvdb_resp = await _make_tvmaze_request("https://api.tvmaze.com/lookup/shows", {"thetvdb": tvdbID}, meta)
                if tvdb_resp:
                    results.append(tvdb_resp)
            if int(imdbID) != 0:
                imdb_resp = await _make_tvmaze_request("https://api.tvmaze.com/lookup/shows", {"imdb": f"tt{imdbID}"}, meta)
                if imdb_resp:
                    results.append(imdb_resp)
            search_resp = await _make_tvmaze_request("https://api.tvmaze.com/search/shows", {"q": filename}, meta)
            if search_resp:
                if isinstance(search_resp, list):
                    results.extend([each['show'] for each in search_resp if 'show' in each])
                else:
                    results.append(search_resp)

        if year not in (None, ''):
            results = [show for show in results if str(show.get('premiered', '')).startswith(str(year))]

        seen = set()
        unique_results = []
        for show in results:
            if show['id'] not in seen:
                seen.add(show['id'])
                unique_results.append(show)
        results = unique_results

        if not results:
            if meta['debug']:
                print("No results found.")
            return tvmazeID, imdbID, tvdbID

        if meta['manual_date'] is not None:
            print("Search results:")
            for idx, show in enumerate(results):
                console.print(f"[bold red]{idx + 1}[/bold red]. [green]{show.get('name', 'Unknown')} (TVmaze ID:[/green] [bold red]{show['id']}[/bold red])")
                console.print(f"[yellow]   Premiered: {show.get('premiered', 'Unknown')}[/yellow]")
                console.print(f"   Externals: {json.dumps(show.get('externals', {}), indent=2)}")

            while True:
                try:
                    choice = int(input(f"Enter the number of the correct show (1-{len(results)}) or 0 to skip: "))
                    if choice == 0:
                        print("Skipping selection.")
                        break
                    if 1 <= choice <= len(results):
                        selected_show = results[choice - 1]
                        tvmazeID = selected_show['id']
                        print(f"Selected show: {selected_show.get('name')} (TVmaze ID: {tvmazeID})")
                        break
                    else:
                        print(f"Invalid choice. Please choose a number between 1 and {len(results)}, or 0 to skip.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
        else:
            selected_show = results[0]
            tvmazeID = selected_show['id']
            if meta['debug']:
                print(f"Automatically selected show: {selected_show.get('name')} (TVmaze ID: {tvmazeID})")

        if meta['debug']:
            print(f"Returning results - TVmaze ID: {tvmazeID}, IMDb ID: {imdbID}, TVDB ID: {tvdbID}")
        return tvmazeID, imdbID, tvdbID


async def _make_tvmaze_request(url, params, meta):
    if meta['debug']:
        print(f"Requesting TVmaze API: {url} with params: {params}")
    try:
        resp = requests.get(url, params=params)
        if resp.ok:
            return resp.json()
        else:
            if meta['debug']:
                print(f"HTTP Request failed with status code: {resp.status_code}, response: {resp.text}")
            return None
    except Exception as e:
        print(f"Error making TVmaze request: {e}")
        return None
