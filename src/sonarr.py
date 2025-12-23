# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import httpx
from data.config import config
from src.console import console


async def get_sonarr_data(tvdb_id=None, filename=None, title=None, debug=False):
    if not any(key.startswith('sonarr_api_key') for key in config['DEFAULT']):
        console.print("[red]No Sonarr API keys are configured.[/red]")
        return None

    # Try each Sonarr instance until we get valid data
    instance_index = 0
    max_instances = 4  # Limit to prevent infinite loops

    while instance_index < max_instances:
        # Determine the suffix for this instance
        suffix = "" if instance_index == 0 else f"_{instance_index}"
        api_key_name = f"sonarr_api_key{suffix}"
        url_name = f"sonarr_url{suffix}"

        # Check if this instance exists in config
        if api_key_name not in config['DEFAULT'] or not config['DEFAULT'][api_key_name]:
            # No more instances to try
            break

        # Get instance-specific configuration
        api_key = config['DEFAULT'][api_key_name].strip()
        base_url = config['DEFAULT'][url_name].strip()

        if debug:
            console.print(f"[blue]Trying Sonarr instance {instance_index if instance_index > 0 else 'default'}[/blue]")

        # Build the appropriate URL
        if tvdb_id:
            url = f"{base_url}/api/v3/series?tvdbId={tvdb_id}&includeSeasonImages=false"
        elif filename and title:
            url = f"{base_url}/api/v3/parse?title={title}&path={filename}"
        else:
            instance_index += 1
            continue

        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }

        if debug:
            console.print(f"[green]TVDB ID {tvdb_id}[/green]")
            console.print(f"[blue]Sonarr URL:[/blue] {url}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0)

                if response.status_code == 200:
                    data = response.json()

                    if debug:
                        console.print(f"[blue]Sonarr Response Status:[/blue] {response.status_code}")
                        console.print(f"[blue]Sonarr Response Data:[/blue] {data}")

                    # Check if we got valid data by trying to extract show info
                    show_data = await extract_show_data(data)

                    if show_data and (show_data.get("tvdb_id") or show_data.get("imdb_id") or show_data.get("tmdb_id")):
                        console.print(f"[green]Found valid show data from Sonarr instance {instance_index if instance_index > 0 else 'default'}[/green]")
                        return show_data
                else:
                    console.print(f"[yellow]Failed to fetch from Sonarr instance {instance_index if instance_index > 0 else 'default'}: {response.status_code} - {response.text}[/yellow]")

        except httpx.RequestError as e:
            console.print(f"[red]Error fetching from Sonarr instance {instance_index if instance_index > 0 else 'default'}: {e}[/red]")
        except httpx.TimeoutException:
            console.print(f"[red]Timeout when fetching from Sonarr instance {instance_index if instance_index > 0 else 'default'}[/red]")
        except Exception as e:
            console.print(f"[red]Unexpected error with Sonarr instance {instance_index if instance_index > 0 else 'default'}: {e}[/red]")

        # Move to the next instance
        instance_index += 1

    # If we got here, no instances provided valid data
    console.print("[yellow]No Sonarr instance returned valid show data.[/yellow]")
    return None


async def extract_show_data(sonarr_data):
    if not sonarr_data:
        return {
            "tvdb_id": None,
            "imdb_id": None,
            "tvmaze_id": None,
            "tmdb_id": None,
            "genres": [],
            "title": "",
            "year": None,
            "release_group": None
        }

    # Handle response from /api/v3/parse endpoint
    if isinstance(sonarr_data, dict) and 'series' in sonarr_data:
        series = sonarr_data['series']
        release_group = sonarr_data.get('parsedEpisodeInfo', {}).get('releaseGroup')

        return {
            "tvdb_id": series.get("tvdbId", None),
            "imdb_id": int(series.get("imdbId", "tt0").replace("tt", "")) if series.get("imdbId") else None,
            "tvmaze_id": series.get("tvMazeId", None),
            "tmdb_id": series.get("tmdbId", None),
            "genres": series.get("genres", []),
            "release_group": release_group if release_group else None,
            "year": series.get("year", None)
        }

    # Handle response from /api/v3/series endpoint (list format)
    elif isinstance(sonarr_data, list) and len(sonarr_data) > 0:
        series = sonarr_data[0]

        return {
            "tvdb_id": series.get("tvdbId", None),
            "imdb_id": int(series.get("imdbId", "tt0").replace("tt", "")) if series.get("imdbId") else None,
            "tvmaze_id": series.get("tvMazeId", None),
            "tmdb_id": series.get("tmdbId", None),
            "genres": series.get("genres", []),
            "title": series.get("title", ""),
            "year": series.get("year", None),
            "release_group": series.get("releaseGroup") if series.get("releaseGroup") else None
        }

    # Return empty data if the format doesn't match any expected structure
    return {
        "tvdb_id": None,
        "imdb_id": None,
        "tvmaze_id": None,
        "tmdb_id": None,
        "genres": [],
        "title": "",
        "year": None,
        "release_group": None
    }
