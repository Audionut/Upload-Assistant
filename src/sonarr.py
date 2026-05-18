# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from collections.abc import Mapping
from typing import Any, Optional, cast

import httpx

from src.console import console

ShowInfo = dict[str, Any]
SonarrAddResult = dict[str, Any]

class SonarrManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.default_config = cast(dict[str, Any], config.get('DEFAULT', {}))

    @staticmethod
    def _normalize_base_url(value: str) -> str:
        return value.strip().rstrip('/')

    @staticmethod
    def _normalize_imdb_id(value: Optional[int]) -> Optional[str]:
        if not value:
            return None
        imdb_id = str(value).strip()
        if not imdb_id or imdb_id == "0":
            return None
        return imdb_id if imdb_id.startswith("tt") else f"tt{imdb_id.zfill(7)}"

    @staticmethod
    def _series_label(series: Mapping[str, Any]) -> str:
        title = series.get("title") or series.get("originalTitle") or "Unknown title"
        year = series.get("year") or "????"
        tvdb = series.get("tvdbId") or "-"
        imdb = series.get("imdbId") or "-"
        tmdb = series.get("tmdbId") or "-"
        return f"{title} ({year}) tvdb={tvdb} imdb={imdb} tmdb={tmdb}"

    @staticmethod
    def _coerce_optional_int(value: Any) -> Optional[int]:
        if value in (None, "", 0, "0"):
            return None
        try:
            normalized = str(value).strip()
            if normalized.lower().startswith("tt"):
                normalized = normalized[2:]
            parsed = int(normalized)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _coerce_bool(value: Any, default: bool = True) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "1", "yes", "y", "on"):
                return True
            if normalized in ("false", "0", "no", "n", "off"):
                return False
        return default

    def _get_instance_config(self, instance_index: int) -> Optional[dict[str, Any]]:
        suffix = "" if instance_index == 0 else f"_{instance_index}"
        api_key_name = f"sonarr_api_key{suffix}"
        url_name = f"sonarr_url{suffix}"

        api_key_value = self.default_config.get(api_key_name)
        base_url_value = self.default_config.get(url_name)
        if not isinstance(api_key_value, str) or not api_key_value.strip():
            return None
        if not isinstance(base_url_value, str) or not base_url_value.strip():
            return None

        quality_profile_id = self.default_config.get(f"sonarr_quality_profile_id{suffix}", self.default_config.get("sonarr_quality_profile_id"))
        root_folder_path = self.default_config.get(f"sonarr_root_folder_path{suffix}", self.default_config.get("sonarr_root_folder_path"))
        series_type = self.default_config.get(f"sonarr_series_type{suffix}", self.default_config.get("sonarr_series_type", "standard"))
        season_folder = self.default_config.get(f"sonarr_season_folder{suffix}", self.default_config.get("sonarr_season_folder", True))
        monitor = self.default_config.get(f"sonarr_monitor{suffix}", self.default_config.get("sonarr_monitor", "none"))

        try:
            quality_profile_id_int = int(str(quality_profile_id or "0"))
        except (TypeError, ValueError):
            quality_profile_id_int = 0

        return {
            "label": str(instance_index if instance_index > 0 else "default"),
            "base_url": self._normalize_base_url(base_url_value),
            "api_key": api_key_value.strip(),
            "quality_profile_id": quality_profile_id_int,
            "root_folder_path": str(root_folder_path).strip() if root_folder_path is not None else "",
            "series_type": str(series_type or "standard").strip(),
            "season_folder": self._coerce_bool(season_folder, default=True),
            "monitor": str(monitor or "none").strip(),
        }

    def _iter_configured_instances(self) -> list[dict[str, Any]]:
        instances: list[dict[str, Any]] = []
        for instance_index in range(4):
            instance = self._get_instance_config(instance_index)
            if instance:
                instances.append(instance)
        return instances

    async def _request_json(
        self,
        client: httpx.AsyncClient,
        method: str,
        instance: Mapping[str, Any],
        path: str,
        params: Optional[dict[str, Any]] = None,
        body: Optional[dict[str, Any]] = None,
    ) -> Any:
        url = f"{instance['base_url']}{path}"
        headers = {
            "X-Api-Key": str(instance["api_key"]),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        response = await client.request(method, url, headers=headers, params=params, json=body, timeout=20.0)
        response.raise_for_status()
        if not response.content:
            return None
        return response.json()

    async def _lookup_series_by_tvdb_id(self, client: httpx.AsyncClient, instance: Mapping[str, Any], tvdb_id: Optional[int]) -> Optional[dict[str, Any]]:
        if not tvdb_id:
            return None
        data = await self._request_json(client, "GET", instance, "/api/v3/series/lookup", params={"term": f"tvdb:{tvdb_id}"})
        if isinstance(data, list):
            items = cast(list[dict[str, Any]], data)
            for item in items:
                if str(item.get("tvdbId") or "") == str(tvdb_id):
                    return item
            return items[0] if items else None
        if isinstance(data, dict):
            return cast(dict[str, Any], data)
        return None

    async def _lookup_series_by_term(self, client: httpx.AsyncClient, instance: Mapping[str, Any], term: Optional[str]) -> Optional[dict[str, Any]]:
        if not term:
            return None
        data = await self._request_json(client, "GET", instance, "/api/v3/series/lookup", params={"term": term})
        if isinstance(data, list):
            items = cast(list[dict[str, Any]], data)
            return items[0] if items else None
        if isinstance(data, dict):
            if isinstance(data.get("series"), dict):
                return cast(dict[str, Any], data["series"])
            return cast(dict[str, Any], data)
        return None

    async def _existing_series(
        self,
        client: httpx.AsyncClient,
        instance: Mapping[str, Any],
        tvdb_id: Optional[int],
        imdb_id: Optional[int] = None,
        tmdb_id: Optional[int] = None,
    ) -> Optional[dict[str, Any]]:
        data = await self._request_json(client, "GET", instance, "/api/v3/series")
        if not isinstance(data, list):
            return None

        normalized_imdb = self._normalize_imdb_id(imdb_id)
        for item in cast(list[dict[str, Any]], data):
            if tvdb_id and str(item.get("tvdbId") or "") == str(tvdb_id):
                return item
            if normalized_imdb and str(item.get("imdbId") or "").lower() == normalized_imdb.lower():
                return item
            if tmdb_id and str(item.get("tmdbId") or "") == str(tmdb_id):
                return item
        return None

    @staticmethod
    def _prepare_add_payload(series: Mapping[str, Any], instance: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(series)
        payload["qualityProfileId"] = instance["quality_profile_id"]
        payload["rootFolderPath"] = instance["root_folder_path"]
        payload["seriesType"] = instance["series_type"]
        payload["seasonFolder"] = instance["season_folder"]
        payload["monitored"] = False
        if isinstance(payload.get("seasons"), list):
            payload["seasons"] = [
                {**cast(dict[str, Any], season), "monitored": False}
                for season in payload["seasons"]
                if isinstance(season, dict)
            ]
        payload["addOptions"] = {
            "monitor": instance["monitor"],
            "searchForMissingEpisodes": False,
        }
        return payload

    async def existing_series_by_lookup_term(self, term: Optional[str], debug: bool = False) -> SonarrAddResult:
        if not term:
            return {"status": "skipped", "detail": "no Sonarr lookup term was available"}

        instances = self._iter_configured_instances()
        if not instances:
            return {"status": "failed", "detail": "No Sonarr API keys are configured."}

        last_error = ""
        async with httpx.AsyncClient() as client:
            for instance in instances:
                label = instance["label"]
                try:
                    series = await self._lookup_series_by_term(client, instance, term)
                    if not series:
                        last_error = f"Sonarr instance {label} did not find a lookup candidate for {term}."
                        if debug:
                            console.print(f"[yellow]{last_error}[/yellow]")
                        continue

                    existing = await self._existing_series(
                        client,
                        instance,
                        self._coerce_optional_int(series.get("tvdbId")),
                        self._coerce_optional_int(series.get("imdbId")),
                        self._coerce_optional_int(series.get("tmdbId")),
                    )
                    if existing:
                        return {
                            "status": "exists",
                            "detail": f"already in Sonarr: {self._series_label(existing)}",
                            "series": existing,
                        }
                except httpx.HTTPStatusError as e:
                    response_text = e.response.text.strip()
                    last_error = f"Sonarr instance {label} HTTP {e.response.status_code}: {response_text or e.response.reason_phrase}"
                    if debug:
                        console.print(f"[yellow]{last_error}[/yellow]")
                except httpx.RequestError as e:
                    last_error = f"Sonarr instance {label} request failed: {e}"
                    if debug:
                        console.print(f"[yellow]{last_error}[/yellow]")

        return {"status": "missing", "detail": last_error or f"not found in Sonarr: {term}"}

    async def add_series_by_ids(
        self,
        tvdb_id: Optional[int] = None,
        imdb_id: Optional[int] = None,
        tmdb_id: Optional[int] = None,
        fallback_title: Optional[str] = None,
        debug: bool = False,
    ) -> SonarrAddResult:
        if not tvdb_id and not imdb_id and not tmdb_id and not fallback_title:
            return {"status": "skipped", "detail": "no TVDb ID, IMDb ID, TMDb ID, or title was available"}

        instances = self._iter_configured_instances()
        if not instances:
            return {"status": "failed", "detail": "No Sonarr API keys are configured."}

        last_error = ""
        async with httpx.AsyncClient() as client:
            for instance in instances:
                label = instance["label"]
                if not instance["quality_profile_id"] or not instance["root_folder_path"]:
                    last_error = (
                        f"Sonarr instance {label} is missing sonarr_quality_profile_id "
                        "or sonarr_root_folder_path."
                    )
                    if debug:
                        console.print(f"[yellow]{last_error}[/yellow]")
                    continue

                try:
                    existing = await self._existing_series(client, instance, tvdb_id, imdb_id, tmdb_id)
                    if existing:
                        return {
                            "status": "exists",
                            "detail": f"already in Sonarr: {self._series_label(existing)}",
                            "series": existing,
                        }

                    used_title_fallback = False
                    series = await self._lookup_series_by_tvdb_id(client, instance, tvdb_id)
                    if not series:
                        series = await self._lookup_series_by_term(client, instance, fallback_title)
                        used_title_fallback = series is not None
                        if not series:
                            last_error = f"Sonarr instance {label} did not find a series for TVDb={tvdb_id} IMDb={imdb_id} TMDb={tmdb_id} title={fallback_title}."
                            if debug:
                                console.print(f"[yellow]{last_error}[/yellow]")
                            continue

                    if used_title_fallback:
                        existing_from_fallback = await self._existing_series(
                            client,
                            instance,
                            self._coerce_optional_int(series.get("tvdbId")),
                            self._coerce_optional_int(series.get("imdbId")),
                            self._coerce_optional_int(series.get("tmdbId")),
                        )
                        if existing_from_fallback:
                            return {
                                "status": "exists",
                                "detail": f"already in Sonarr: {self._series_label(existing_from_fallback)}",
                                "series": existing_from_fallback,
                                "used_title_fallback": True,
                            }

                    payload = self._prepare_add_payload(series, instance)
                    added = await self._request_json(client, "POST", instance, "/api/v3/series", body=payload)
                    if isinstance(added, dict):
                        return {
                            "status": "added",
                            "detail": f"added to Sonarr: {self._series_label(cast(dict[str, Any], added))}",
                            "series": added,
                            "used_title_fallback": used_title_fallback,
                        }
                    return {"status": "added", "detail": "added to Sonarr", "used_title_fallback": used_title_fallback}
                except httpx.HTTPStatusError as e:
                    response_text = e.response.text.strip()
                    last_error = f"Sonarr instance {label} HTTP {e.response.status_code}: {response_text or e.response.reason_phrase}"
                    if debug:
                        console.print(f"[yellow]{last_error}[/yellow]")
                except httpx.RequestError as e:
                    last_error = f"Sonarr instance {label} request failed: {e}"
                    if debug:
                        console.print(f"[yellow]{last_error}[/yellow]")

        return {"status": "failed", "detail": last_error or "Sonarr add failed."}

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
                        show_data: ShowInfo = await self.extract_show_data(data)

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

    async def extract_show_data(self, sonarr_data: Any) -> ShowInfo:
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

