# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from collections.abc import Mapping
from typing import Any, Optional, cast

import httpx

from src.console import console

MovieInfo = dict[str, Any]

class RadarrManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.default_config = cast(dict[str, Any], config.get('DEFAULT', {}))

    async def get_radarr_data(self, tmdb_id: Optional[int] = None, filename: Optional[str] = None, debug: bool = False) -> Optional[MovieInfo]:
        if not any(key.startswith('radarr_api_key') for key in self.default_config):
            console.print("[red]No Radarr API keys are configured.[/red]")
            return None

        # Try each Radarr instance until we get valid data
        instance_index = 0
        max_instances = 4  # Limit instances to prevent infinite loops

        while instance_index < max_instances:
            # Determine the suffix for this instance
            suffix = "" if instance_index == 0 else f"_{instance_index}"
            api_key_name = f"radarr_api_key{suffix}"
            url_name = f"radarr_url{suffix}"

            # Check if this instance exists in config
            api_key_value = self.default_config.get(api_key_name)
            if not isinstance(api_key_value, str) or not api_key_value.strip():
                # This slot isn't configured; try the next suffix (supports configs starting at _1)
                instance_index += 1
                continue

            # Get instance-specific configuration
            base_url_value = self.default_config.get(url_name)
            if not isinstance(base_url_value, str) or not base_url_value.strip():
                instance_index += 1
                continue

            api_key = api_key_value.strip()
            base_url = base_url_value.strip()

            if debug:
                console.print(f"[blue]Trying Radarr instance {instance_index if instance_index > 0 else 'default'}[/blue]")

            # Build the appropriate URL
            if tmdb_id:
                url = f"{base_url}/api/v3/movie?tmdbId={tmdb_id}&excludeLocalCovers=true"
            elif filename:
                url = f"{base_url}/api/v3/movie/lookup?term={filename}"
            else:
                instance_index += 1
                continue

            headers = {
                "X-Api-Key": api_key,
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

                        # Check if we got valid data by trying to extract movie info
                        movie_data = await self.extract_movie_data(data, filename)

                        if movie_data and (movie_data.get("imdb_id") or movie_data.get("tmdb_id")):
                            console.print(f"[green]Found valid movie data from Radarr instance {instance_index if instance_index > 0 else 'default'}[/green]")
                            return movie_data
                    else:
                        console.print(f"[yellow]Failed to fetch from Radarr instance {instance_index if instance_index > 0 else 'default'}: {response.status_code} - {response.text}[/yellow]")

            except httpx.TimeoutException:
                console.print(f"[red]Timeout when fetching from Radarr instance {instance_index if instance_index > 0 else 'default'}[/red]")
            except httpx.RequestError as e:
                console.print(f"[red]Error fetching from Radarr instance {instance_index if instance_index > 0 else 'default'}: {e}[/red]")
            except Exception as e:
                console.print(f"[red]Unexpected error with Radarr instance {instance_index if instance_index > 0 else 'default'}: {e}[/red]")

            # Move to the next instance
            instance_index += 1

        # If we got here, no instances provided valid data
        console.print("[yellow]No Radarr instance returned valid movie data.[/yellow]")
        return None

    async def extract_movie_data(self, radarr_data: Any, filename: Optional[str] = None) -> Optional[MovieInfo]:
        if not radarr_data or not isinstance(radarr_data, list):
            return {
                "imdb_id": None,
                "tmdb_id": None,
                "year": None,
                "genres": [],
                "release_group": None
            }
        items = cast(list[Mapping[str, Any]], radarr_data)
        if len(items) == 0:
            return {
                "imdb_id": None,
                "tmdb_id": None,
                "year": None,
                "genres": [],
                "release_group": None
            }

        if filename:
            movie: Optional[Mapping[str, Any]] = None
            for item in items:
                movie_file = cast(Mapping[str, Any], item.get("movieFile", {}))
                if movie_file.get("originalFilePath") == filename:
                    movie = item
                    break
            else:
                return None
        else:
            movie = items[0]

        release_group = None
        movie_file = cast(Mapping[str, Any], movie.get("movieFile", {}))
        if movie_file.get("releaseGroup"):
            release_group = movie_file["releaseGroup"]

        return {
            "imdb_id": int(str(movie.get("imdbId", "tt0")).replace("tt", "")) if movie.get("imdbId") else None,
            "tmdb_id": movie.get("tmdbId", None),
            "year": movie.get("year", None),
            "genres": movie.get("genres", []),
            "release_group": release_group if release_group else None
        }


