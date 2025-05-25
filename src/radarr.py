import httpx
from data.config import config
from src.console import console


async def get_radarr_from_id(tmdb_id, debug=False):
    if config['DEFAULT'].get('radarr_api_key', ""):
        url = f"{config['DEFAULT']['radarr_url']}/api/v3/movie?tmdbId={tmdb_id}&excludeLocalCovers=true"
        headers = {
            "X-Api-Key": config['DEFAULT']['radarr_api_key'],
            "Content-Type": "application/json"
        }
        if debug:
            console.print(f"[green]TMDB ID {tmdb_id}[/green]")
            console.print(f"[blue]Radarr URL:[/blue] {url}")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0)

                if response.status_code == 200:
                    data = response.json()
                    if debug:
                        console.print(f"[blue]Radarr Response Status:[/blue] {response.status_code}")
                        console.print(f"[blue]Radarr Response Data:[/blue] {data}")
                    return data
                else:
                    console.print(f"[yellow]Failed to fetch Radarr movie: {response.status_code} - {response.text}[/yellow]")
                    return None
        except httpx.RequestError as e:
            console.print(f"[red]Error fetching Radarr movie: {e}[/red]")
            return None
        except httpx.TimeoutException:
            console.print(f"[red]Timeout when fetching Radarr movie for TMDB ID {tmdb_id}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]Unexpected error fetching Radarr movie: {e}[/red]")
            return None
    else:
        console.print("[red]Radarr API key is not configured.[/red]")
        return None


async def extract_movie_data(radarr_data):
    if not radarr_data or not isinstance(radarr_data, list) or len(radarr_data) == 0:
        return {
            "imdb_id": None,
            "tmdb_id": None,
            "genres": []
        }

    # Extract the first series from the list
    movie = radarr_data[0]

    return {
        "imdb_id": int(movie.get("imdbId", "tt").replace("tt", "")) if movie.get("imdbId") else None,
        "tmdb_id": movie.get("tmdbId"),
        "genres": movie.get("genres", [])
    }
