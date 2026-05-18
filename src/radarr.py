# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from collections.abc import Mapping
from typing import Any, Optional, cast

import httpx

from src.console import console

MovieInfo = dict[str, Any]
RadarrAddResult = dict[str, Any]

class RadarrManager:
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
    def _movie_label(movie: Mapping[str, Any]) -> str:
        title = movie.get("title") or movie.get("originalTitle") or "Unknown title"
        year = movie.get("year") or "????"
        tmdb = movie.get("tmdbId") or "-"
        imdb = movie.get("imdbId") or "-"
        return f"{title} ({year}) tmdb={tmdb} imdb={imdb}"

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

    def _get_instance_config(self, instance_index: int) -> Optional[dict[str, Any]]:
        suffix = "" if instance_index == 0 else f"_{instance_index}"
        api_key_name = f"radarr_api_key{suffix}"
        url_name = f"radarr_url{suffix}"

        api_key_value = self.default_config.get(api_key_name)
        base_url_value = self.default_config.get(url_name)
        if not isinstance(api_key_value, str) or not api_key_value.strip():
            return None
        if not isinstance(base_url_value, str) or not base_url_value.strip():
            return None

        quality_profile_id = self.default_config.get(f"radarr_quality_profile_id{suffix}", self.default_config.get("radarr_quality_profile_id"))
        root_folder_path = self.default_config.get(f"radarr_root_folder_path{suffix}", self.default_config.get("radarr_root_folder_path"))
        minimum_availability = self.default_config.get(
            f"radarr_minimum_availability{suffix}",
            self.default_config.get("radarr_minimum_availability", "released"),
        )

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
            "minimum_availability": str(minimum_availability or "released").strip(),
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

    async def _lookup_movie_by_ids(self, client: httpx.AsyncClient, instance: Mapping[str, Any], tmdb_id: Optional[int], imdb_id: Optional[int]) -> Optional[dict[str, Any]]:
        lookup_candidates: list[tuple[str, dict[str, Any]]] = []
        if tmdb_id:
            lookup_candidates.append(("/api/v3/movie/lookup/tmdb", {"tmdbId": tmdb_id}))
            lookup_candidates.append(("/api/v3/movie/lookup", {"term": f"tmdb:{tmdb_id}"}))
        normalized_imdb = self._normalize_imdb_id(imdb_id)
        if normalized_imdb:
            lookup_candidates.append(("/api/v3/movie/lookup/imdb", {"imdbId": normalized_imdb}))
            lookup_candidates.append(("/api/v3/movie/lookup", {"term": f"imdb:{normalized_imdb}"}))

        for path, params in lookup_candidates:
            try:
                data = await self._request_json(client, "GET", instance, path, params=params)
            except httpx.HTTPStatusError:
                continue

            if isinstance(data, list):
                items = cast(list[dict[str, Any]], data)
                if items:
                    return items[0]
            elif isinstance(data, dict):
                return cast(dict[str, Any], data)
        return None

    async def _lookup_movie_by_filename(self, client: httpx.AsyncClient, instance: Mapping[str, Any], filename: Optional[str]) -> Optional[dict[str, Any]]:
        if not filename:
            return None
        data = await self._request_json(client, "GET", instance, "/api/v3/movie/lookup", params={"term": filename})
        if isinstance(data, list):
            items = cast(list[dict[str, Any]], data)
            return items[0] if items else None
        if isinstance(data, dict):
            return cast(dict[str, Any], data)
        return None

    async def _existing_movie(self, client: httpx.AsyncClient, instance: Mapping[str, Any], tmdb_id: Optional[int], imdb_id: Optional[int]) -> Optional[dict[str, Any]]:
        data = await self._request_json(client, "GET", instance, "/api/v3/movie")
        if not isinstance(data, list):
            return None

        normalized_imdb = self._normalize_imdb_id(imdb_id)
        for item in cast(list[dict[str, Any]], data):
            if tmdb_id and str(item.get("tmdbId") or "") == str(tmdb_id):
                return item
            if normalized_imdb and str(item.get("imdbId") or "").lower() == normalized_imdb.lower():
                return item
        return None

    async def add_movie_by_ids(self, tmdb_id: Optional[int] = None, imdb_id: Optional[int] = None, fallback_filename: Optional[str] = None, debug: bool = False) -> RadarrAddResult:
        if not tmdb_id and not imdb_id and not fallback_filename:
            return {"status": "skipped", "detail": "no TMDb ID, IMDb ID, or filename was available"}

        instances = self._iter_configured_instances()
        if not instances:
            return {"status": "failed", "detail": "No Radarr API keys are configured."}

        last_error = ""
        async with httpx.AsyncClient() as client:
            for instance in instances:
                label = instance["label"]
                if not instance["quality_profile_id"] or not instance["root_folder_path"]:
                    last_error = (
                        f"Radarr instance {label} is missing radarr_quality_profile_id "
                        "or radarr_root_folder_path."
                    )
                    if debug:
                        console.print(f"[yellow]{last_error}[/yellow]")
                    continue

                try:
                    existing = await self._existing_movie(client, instance, tmdb_id, imdb_id)
                    if existing:
                        return {
                            "status": "exists",
                            "detail": f"already in Radarr: {self._movie_label(existing)}",
                            "movie": existing,
                        }

                    used_filename_fallback = False
                    movie = await self._lookup_movie_by_ids(client, instance, tmdb_id, imdb_id)
                    if not movie:
                        movie = await self._lookup_movie_by_filename(client, instance, fallback_filename)
                        used_filename_fallback = movie is not None
                        if not movie:
                            last_error = f"Radarr instance {label} did not find a movie for TMDb={tmdb_id} IMDb={imdb_id} filename={fallback_filename}."
                            if debug:
                                console.print(f"[yellow]{last_error}[/yellow]")
                            continue

                    if used_filename_fallback:
                        fallback_tmdb_id = movie.get("tmdbId")
                        fallback_imdb_id = movie.get("imdbId")
                        existing_from_fallback = await self._existing_movie(
                            client,
                            instance,
                            self._coerce_optional_int(fallback_tmdb_id),
                            self._coerce_optional_int(fallback_imdb_id),
                        )
                        if existing_from_fallback:
                            return {
                                "status": "exists",
                                "detail": f"already in Radarr: {self._movie_label(existing_from_fallback)}",
                                "movie": existing_from_fallback,
                                "used_filename_fallback": True,
                            }

                    payload = dict(movie)
                    payload["qualityProfileId"] = instance["quality_profile_id"]
                    payload["rootFolderPath"] = instance["root_folder_path"]
                    payload["monitored"] = False
                    payload["minimumAvailability"] = instance["minimum_availability"]
                    payload["addOptions"] = {"searchForMovie": False}

                    added = await self._request_json(client, "POST", instance, "/api/v3/movie", body=payload)
                    if isinstance(added, dict):
                        return {
                            "status": "added",
                            "detail": f"added to Radarr: {self._movie_label(cast(dict[str, Any], added))}",
                            "movie": added,
                            "used_filename_fallback": used_filename_fallback,
                        }
                    return {"status": "added", "detail": "added to Radarr", "used_filename_fallback": used_filename_fallback}
                except httpx.HTTPStatusError as e:
                    response_text = e.response.text.strip()
                    last_error = f"Radarr instance {label} HTTP {e.response.status_code}: {response_text or e.response.reason_phrase}"
                    if debug:
                        console.print(f"[yellow]{last_error}[/yellow]")
                except httpx.RequestError as e:
                    last_error = f"Radarr instance {label} request failed: {e}"
                    if debug:
                        console.print(f"[yellow]{last_error}[/yellow]")

        return {"status": "failed", "detail": last_error or "Radarr add failed."}

    async def existing_movie_by_lookup_term(self, term: Optional[str], debug: bool = False) -> RadarrAddResult:
        if not term:
            return {"status": "skipped", "detail": "no Radarr lookup term was available"}

        instances = self._iter_configured_instances()
        if not instances:
            return {"status": "failed", "detail": "No Radarr API keys are configured."}

        last_error = ""
        async with httpx.AsyncClient() as client:
            for instance in instances:
                label = instance["label"]
                try:
                    movie = await self._lookup_movie_by_filename(client, instance, term)
                    if not movie:
                        last_error = f"Radarr instance {label} did not find a lookup candidate for {term}."
                        if debug:
                            console.print(f"[yellow]{last_error}[/yellow]")
                        continue

                    existing = await self._existing_movie(
                        client,
                        instance,
                        self._coerce_optional_int(movie.get("tmdbId")),
                        self._coerce_optional_int(movie.get("imdbId")),
                    )
                    if existing:
                        return {
                            "status": "exists",
                            "detail": f"already in Radarr: {self._movie_label(existing)}",
                            "movie": existing,
                        }
                except httpx.HTTPStatusError as e:
                    response_text = e.response.text.strip()
                    last_error = f"Radarr instance {label} HTTP {e.response.status_code}: {response_text or e.response.reason_phrase}"
                    if debug:
                        console.print(f"[yellow]{last_error}[/yellow]")
                except httpx.RequestError as e:
                    last_error = f"Radarr instance {label} request failed: {e}"
                    if debug:
                        console.print(f"[yellow]{last_error}[/yellow]")

        return {"status": "missing", "detail": last_error or f"not found in Radarr: {term}"}

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
            base_url = base_url_value.strip().rstrip('/')

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
