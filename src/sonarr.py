# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from collections.abc import Mapping
from typing import Any, Optional, cast

import httpx

from src.console import console

ShowInfo = dict[str, Any]

class SonarrManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.default_config = cast(dict[str, Any], config.get('DEFAULT', {}))

    async def get_sonarr_data(
        self,
        tvdb_id: Optional[int] = None,
        filename: Optional[str] = None,
        title: Optional[str] = None,
        debug: bool = False,
    ) -> Optional[ShowInfo]:
        if not any(key.startswith('sonarr_api_key') for key in self.default_config):
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
            base_url = base_url_value.strip().rstrip('/')

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
                        show_data: ShowInfo = self.extract_show_data(data)

                        if show_data and (show_data.get("tvdb_id") or show_data.get("imdb_id") or show_data.get("tmdb_id")):
                            console.print(f"[green]Found valid show data from Sonarr instance {instance_index if instance_index > 0 else 'default'}[/green]")
                            return show_data
                    else:
                        console.print(f"[yellow]Failed to fetch from Sonarr instance {instance_index if instance_index > 0 else 'default'}: {response.status_code} - {response.text}[/yellow]")

            except httpx.TimeoutException:
                console.print(f"[red]Timeout when fetching from Sonarr instance {instance_index if instance_index > 0 else 'default'}[/red]")
            except httpx.RequestError as e:
                console.print(f"[red]Error fetching from Sonarr instance {instance_index if instance_index > 0 else 'default'}: {e}[/red]")
            except Exception as e:
                console.print(f"[red]Unexpected error with Sonarr instance {instance_index if instance_index > 0 else 'default'}: {e}[/red]")

            # Move to the next instance
            instance_index += 1

        # If we got here, no instances provided valid data
        console.print("[yellow]No Sonarr instance returned valid show data.[/yellow]")
        return None

    def extract_show_data(self, sonarr_data: Any) -> ShowInfo:
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
            sonarr_dict = cast(Mapping[str, Any], sonarr_data)
            series = cast(Mapping[str, Any], sonarr_dict['series'])
            parsed_info = cast(Mapping[str, Any], sonarr_dict.get('parsedEpisodeInfo', {}))
            release_group = parsed_info.get('releaseGroup')

            return {
                "tvdb_id": series.get("tvdbId", None),
                "imdb_id": int(str(series.get("imdbId", "tt0")).replace("tt", "")) if series.get("imdbId") else None,
                "tvmaze_id": series.get("tvMazeId", None),
                "tmdb_id": series.get("tmdbId", None),
                "genres": series.get("genres", []),
                "release_group": release_group if release_group else None,
                "year": series.get("year", None)
            }

        # Handle response from /api/v3/series endpoint (list format)
        if isinstance(sonarr_data, list):
            series_list = cast(list[Mapping[str, Any]], sonarr_data)
            if len(series_list) > 0:
                series = series_list[0]

                return {
                    "tvdb_id": series.get("tvdbId", None),
                    "imdb_id": int(str(series.get("imdbId", "tt0")).replace("tt", "")) if series.get("imdbId") else None,
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


