#!/usr/bin/env python3
"""Interactively add MKV movies from a directory to Radarr.

The script scans a directory for movie content, skips samples, looks up
candidate movies in Radarr, and adds selected movies unmonitored.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_MINIMUM_AVAILABILITY = "released"
DEFAULT_TIMEOUT = 30
MAX_DISPLAY_CANDIDATES = 3
DISC_FOLDER_NAMES = {"bdmv", "video_ts"}
COMPLETED_STATE_STATUSES = {"added", "skipped"}


class RadarrError(Exception):
    """Raised for Radarr API and transport failures."""


@dataclass
class ParsedName:
    primary_title: str | None
    secondary_title: str | None
    year: str | None

    @property
    def search_term(self) -> str:
        if not self.primary_title:
            return self.year or ""
        if self.year:
            return f"{self.primary_title} {self.year}"
        return self.primary_title


@dataclass
class MovieItem:
    path: Path
    parsed: ParsedName
    candidates: list[dict[str, Any]] = field(default_factory=list)
    selected_index: int | None = None
    skipped: bool = False
    skip_reason: str | None = None

    @property
    def selected_candidate(self) -> dict[str, Any] | None:
        if self.selected_index is None:
            return None
        if self.selected_index < 0 or self.selected_index >= len(self.candidates):
            return None
        return self.candidates[self.selected_index]


@dataclass(frozen=True)
class ContentItem:
    path: Path
    parse_path: Path
    kind: str

    @property
    def label(self) -> str:
        return str(self.path)


@dataclass
class RunResult:
    content_item: ContentItem
    status: str
    detail: str
    movie: dict[str, Any] | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def item_id(content_item: ContentItem) -> str:
    identity = f"{content_item.kind}\0{content_item.path.resolve()}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


class StateStore:
    def __init__(self, state_dir: Path, enabled: bool = True) -> None:
        self.state_dir = state_dir
        self.items_dir = state_dir / "items"
        self.enabled = enabled

    def initialize(self, scan_directory: Path, recursive: bool) -> None:
        if not self.enabled:
            return
        self.items_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "scanDirectory": str(scan_directory),
            "recursive": recursive,
            "updatedAt": now_iso(),
        }
        self._write_json(self.state_dir / "manifest.json", manifest)

    def path_for(self, content_item: ContentItem) -> Path:
        return self.items_dir / f"{item_id(content_item)}.json"

    def load(self, content_item: ContentItem) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        path = self.path_for(content_item)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def record_discovered(self, content_item: ContentItem, parsed: ParsedName | None = None) -> None:
        if self.load(content_item):
            return
        self.record(content_item, "pending", "discovered", parsed=parsed, existing_state={})

    def record(
        self,
        content_item: ContentItem,
        status: str,
        detail: str,
        parsed: ParsedName | None = None,
        movie: dict[str, Any] | None = None,
        *,
        existing_state: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return
        existing = existing_state if existing_state is not None else self.load(content_item) or {}
        created_at = existing.get("createdAt") or now_iso()
        record = {
            "id": item_id(content_item),
            "contentPath": str(content_item.path),
            "parsePath": str(content_item.parse_path),
            "kind": content_item.kind,
            "status": status,
            "detail": detail,
            "createdAt": created_at,
            "updatedAt": now_iso(),
        }
        if parsed:
            record["parsed"] = {
                "primaryTitle": parsed.primary_title,
                "secondaryTitle": parsed.secondary_title,
                "year": parsed.year,
                "searchTerm": parsed.search_term,
            }
        elif existing.get("parsed"):
            record["parsed"] = existing["parsed"]
        if movie:
            record["movie"] = {
                "title": movie.get("title") or movie.get("originalTitle"),
                "year": movie.get("year"),
                "tmdbId": movie.get("tmdbId"),
                "imdbId": movie.get("imdbId"),
            }
        elif existing.get("movie"):
            record["movie"] = existing["movie"]

        self._write_json(self.path_for(content_item), record)

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, sort_keys=True)
            file.write("\n")
        temp_path.replace(path)


def normalize_base_url(value: str) -> str:
    return value.rstrip("/")


class RadarrClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.base_url = normalize_base_url(base_url)
        self.api_key = api_key
        self.timeout = timeout

    def get_movies(self) -> list[dict[str, Any]]:
        data = self._request_json("GET", "/api/v3/movie")
        if not isinstance(data, list):
            raise RadarrError("Radarr movie list response was not a list.")
        return data

    def lookup(self, term: str) -> list[dict[str, Any]]:
        data = self._request_json("GET", "/api/v3/movie/lookup", {"term": term})
        if not isinstance(data, list):
            raise RadarrError(f"Radarr lookup response for {term!r} was not a list.")
        return data

    def add_movie(
        self,
        movie: dict[str, Any],
        quality_profile_id: int,
        root_folder_path: str,
        minimum_availability: str,
    ) -> dict[str, Any]:
        payload = copy.deepcopy(movie)
        payload["qualityProfileId"] = quality_profile_id
        payload["rootFolderPath"] = root_folder_path
        payload["monitored"] = False
        payload["minimumAvailability"] = minimum_availability
        payload["addOptions"] = {"searchForMovie": False}

        data = self._request_json("POST", "/api/v3/movie", body=payload)
        if not isinstance(data, dict):
            raise RadarrError("Radarr add response was not an object.")
        return data

    def _request_json(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        encoded_body = None
        headers = {
            "X-Api-Key": self.api_key,
            "Accept": "application/json",
            "User-Agent": "radarr-add-mkv-directory/1.0",
        }
        if body is not None:
            encoded_body = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=encoded_body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            payload = error.read().decode("utf-8", errors="replace")
            message = payload.strip() or error.reason
            raise RadarrError(f"Radarr HTTP {error.code}: {message}") from error
        except urllib.error.URLError as error:
            raise RadarrError(f"Radarr request failed: {error.reason}") from error

        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError as error:
            raise RadarrError(f"Radarr returned invalid JSON from {path}: {error}") from error


def is_sample_mkv(path: Path) -> bool:
    if path.suffix.lower() != ".mkv":
        return False

    return is_sample_path(path)


def is_sample_content_item(path: Path) -> bool:
    return is_sample_path(path)


def is_sample_path(path: Path) -> bool:
    parent_tokens = {part.lower() for part in path.parent.parts}
    if parent_tokens.intersection({"sample", "samples"}):
        return True

    name_for_tokens = path.stem if path.is_file() and path.suffix else path.name
    filename_tokens = release_tokens(name_for_tokens)
    return "sample" in filename_tokens


def release_tokens(value: str) -> set[str]:
    return {token.lower() for token in re.split(r"[^A-Za-z0-9]+", value) if token}


def find_mkv_files(directory: Path, recursive: bool = False) -> tuple[list[Path], list[Path]]:
    iterator = directory.rglob("*") if recursive else directory.iterdir()
    mkvs = sorted(path for path in iterator if path.is_file() and path.suffix.lower() == ".mkv")
    samples = [path for path in mkvs if is_sample_mkv(path)]
    sample_set = set(samples)
    usable = [path for path in mkvs if path not in sample_set]
    return usable, samples


def is_disc_content_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        children = path.iterdir()
    except OSError:
        return False
    return any(child.is_dir() and child.name.lower() in DISC_FOLDER_NAMES for child in children)


def has_disc_ancestor(path: Path, disc_dirs: set[Path]) -> bool:
    return any(parent in disc_dirs for parent in path.parents)


def find_content_items(directory: Path, recursive: bool = False) -> tuple[list[ContentItem], list[ContentItem]]:
    if recursive:
        all_dirs = sorted((path for path in directory.rglob("*") if path.is_dir()), key=lambda path: len(path.parts))
    else:
        all_dirs = sorted(path for path in directory.iterdir() if path.is_dir())

    disc_paths = [path for path in all_dirs if is_disc_content_dir(path)]
    disc_path_set = set(disc_paths)

    iterator = directory.rglob("*") if recursive else directory.iterdir()
    mkv_paths = sorted(
        path
        for path in iterator
        if path.is_file()
        and path.suffix.lower() == ".mkv"
        and not has_disc_ancestor(path, disc_path_set)
    )

    content_items = [
        ContentItem(path=path, parse_path=path, kind="disc")
        for path in disc_paths
    ] + [
        ContentItem(path=path, parse_path=path, kind="mkv")
        for path in mkv_paths
    ]
    content_items.sort(key=lambda item: str(item.path).lower())

    samples = [item for item in content_items if is_sample_content_item(item.path)]
    usable = [item for item in content_items if item not in samples]
    return usable, samples


def multi_replace(text: str, replacements: dict[str, str]) -> str:
    for old, new in replacements.items():
        text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)
    return text


def extract_title_and_year(
    meta: dict[str, Any],
    filename: str,
) -> tuple[str | None, str | None, str | None]:
    """Vendored compatible parser based on Upload Assistant's helper.

    Source: https://github.com/Audionut/Upload-Assistant/blob/master/src/get_name.py
    Function: NameManager.extract_title_and_year
    """

    basename = os.path.basename(filename)
    basename = os.path.splitext(basename)[0]

    secondary_title: str | None = None
    year: str | None = None

    aka_patterns = [" AKA ", ".aka.", " aka ", ".AKA."]
    for pattern in aka_patterns:
        if pattern in basename:
            aka_parts = basename.split(pattern, 1)
            if len(aka_parts) > 1:
                primary_title = aka_parts[0].strip()
                secondary_part = aka_parts[1].strip()

                year_match_primary = re.search(r"\b(19|20)\d{2}\b", primary_title)
                if year_match_primary:
                    year = year_match_primary.group(0)

                secondary_match = re.match(r"^(\d+)", secondary_part)
                if secondary_match:
                    secondary_title = secondary_match.group(1)
                else:
                    year_or_release_match = re.search(
                        r"\b(19|20)\d{2}\b|\bBluRay\b|\bREMUX\b|\b\d+p\b|\bDTS-HD\b|\bAVC\b",
                        secondary_part,
                    )
                    if (
                        year_or_release_match
                        and re.match(r"\b(19|20)\d{2}\b", year_or_release_match.group(0))
                        and not year
                    ):
                        year = year_or_release_match.group(0)
                        secondary_title = secondary_part[: year_or_release_match.start()].strip()
                    else:
                        secondary_title = secondary_part

                primary_title = primary_title.replace(".", " ")
                if secondary_title is not None:
                    secondary_title = secondary_title.replace(".", " ")
                return primary_title, secondary_title, year

    year_start_match = re.match(r"^(19|20)\d{2}", basename)
    if year_start_match:
        title = year_start_match.group(0)
        rest = basename[len(title) :].lstrip(". _-")
        year_match = re.search(r"\b(19|20)\d{2}\b", rest)
        year = year_match.group(0) if year_match else None
        if year:
            return title, None, year

    folder_name = os.path.basename(str(meta.get("uuid", ""))) if meta.get("uuid") else ""
    year_pattern = r"(18|19|20)\d{2}"
    res_pattern = r"\b(480|576|720|1080|2160)[pi]\b"
    type_pattern = (
        r"(WEBDL|BluRay|REMUX|HDRip|Blu-Ray|Web-DL|webrip|web-rip|DVD|"
        r"BD100|BD50|BD25|HDTV|UHD|HDR|DOVI|REPACK|Season)(?=[._\-\s]|$)"
    )
    season_pattern = r"\bS(\d{1,3})\b"
    season_episode_pattern = r"\bS(\d{1,3})E(\d{1,3})\b"
    date_pattern = r"\b(20\d{2})\.(\d{1,2})\.(\d{1,2})\b"
    extension_pattern = r"\.(mkv|mp4)$"

    double_year_pattern = r"\b(18|19|20)\d{2}\.(18|19|20)\d{2}\b"
    double_year_match = re.search(double_year_pattern, folder_name)
    actual_year: str | None = None

    if double_year_match:
        full_match = double_year_match.group(0)
        years = full_match.split(".")
        first_year = years[0]
        second_year = years[1]
        modified_folder_name = folder_name.replace(full_match, first_year)

        res_match = re.search(res_pattern, modified_folder_name, re.IGNORECASE)
        season_pattern_match = re.search(season_pattern, modified_folder_name, re.IGNORECASE)
        season_episode_match = re.search(season_episode_pattern, modified_folder_name, re.IGNORECASE)
        extension_match = re.search(extension_pattern, modified_folder_name, re.IGNORECASE)
        type_match = re.search(type_pattern, modified_folder_name, re.IGNORECASE)

        year_boundary = (
            double_year_match.start() + len(first_year)
            if double_year_match.start() == 0
            else double_year_match.start()
        )
        indices: list[tuple[str, int, str]] = [("year", year_boundary, second_year)]
        if res_match:
            indices.append(("res", res_match.start(), res_match.group()))
        if season_pattern_match:
            indices.append(("season", season_pattern_match.start(), season_pattern_match.group()))
        if season_episode_match:
            indices.append(("season_episode", season_episode_match.start(), season_episode_match.group()))
        if extension_match:
            indices.append(("extension", extension_match.start(), extension_match.group()))
        if type_match:
            indices.append(("type", type_match.start(), type_match.group()))

        folder_name_for_title = modified_folder_name
        actual_year = second_year
    else:
        date_match = re.search(date_pattern, folder_name)
        year_match = re.search(year_pattern, folder_name)
        res_match = re.search(res_pattern, folder_name, re.IGNORECASE)
        season_pattern_match = re.search(season_pattern, folder_name, re.IGNORECASE)
        season_episode_match = re.search(season_episode_pattern, folder_name, re.IGNORECASE)
        extension_match = re.search(extension_pattern, folder_name, re.IGNORECASE)
        type_match = re.search(type_pattern, folder_name, re.IGNORECASE)

        indices = []
        if date_match:
            indices.append(("date", date_match.start(), date_match.group()))
        if year_match and not date_match:
            indices.append(("year", year_match.start(), year_match.group()))
        if res_match:
            indices.append(("res", res_match.start(), res_match.group()))
        if season_pattern_match:
            indices.append(("season", season_pattern_match.start(), season_pattern_match.group()))
        if season_episode_match:
            indices.append(("season_episode", season_episode_match.start(), season_episode_match.group()))
        if extension_match:
            indices.append(("extension", extension_match.start(), extension_match.group()))
        if type_match:
            indices.append(("type", type_match.start(), type_match.group()))

        folder_name_for_title = folder_name
        actual_year = year_match.group() if year_match and not date_match else None

    if indices:
        indices.sort(key=lambda value: value[1])
        _, first_index, _ = indices[0]
        title_part = folder_name_for_title[:first_index]
        title_part = re.sub(r"[\.\-_ ]+$", "", title_part)
        if title_part.count("(") > title_part.count(")"):
            paren_pos = title_part.rfind("(")
            content_after_paren = folder_name_for_title[paren_pos + 1 : first_index].strip()

            if content_after_paren:
                secondary_title = content_after_paren

            title_part = title_part[:paren_pos].rstrip()
    else:
        title_part = folder_name

    replacements = {
        "_": " ",
        ".": " ",
        "DVD9": "",
        "DVD5": "",
        "DVDR": "",
        "BDR": "",
        "HDDVD": "",
        "WEB-DL": "",
        "WEBRip": "",
        "WEB": "",
        "BluRay": "",
        "Blu-ray": "",
        "HDTV": "",
        "DVDRip": "",
        "REMUX": "",
        "HDR": "",
        "UHD": "",
        "4K": "",
        "DVD": "",
        "HDRip": "",
        "BDMV": "",
        "R1": "",
        "R2": "",
        "R3": "",
        "R4": "",
        "R5": "",
        "R6": "",
        "Director's Cut": "",
        "Extended Edition": "",
        "directors cut": "",
        "director cut": "",
        "itunes": "",
    }

    parsed_filename = multi_replace(title_part, replacements)
    processed_secondary = multi_replace(secondary_title or "", replacements)
    secondary_title = processed_secondary if processed_secondary else None

    if parsed_filename:
        bracket_pattern = r"\s*\(([^)]+)\)\s*"
        bracket_match = re.search(bracket_pattern, parsed_filename)

        if bracket_match:
            bracket_content = bracket_match.group(1).strip()
            bracket_content = multi_replace(bracket_content, replacements)

            if not secondary_title and bracket_content:
                secondary_title = bracket_content
                secondary_title = re.sub(r"[\.\-_ ]+$", "", secondary_title)

            parsed_filename = re.sub(bracket_pattern, " ", parsed_filename)
            parsed_filename = re.sub(r"\s+", " ", parsed_filename).strip()

    if parsed_filename:
        return parsed_filename, secondary_title, actual_year

    year_match = re.search(r"(?<!\d)(19|20)\d{2}(?!\d)", basename)
    if year_match:
        year = year_match.group(0)
        return None, None, year

    return None, None, None


def parse_mkv_name(path: Path) -> ParsedName:
    primary_title, secondary_title, year = extract_title_and_year(
        {"debug": False, "uuid": str(path)},
        str(path),
    )
    return ParsedName(
        clean_text(primary_title),
        clean_text(secondary_title),
        clean_text(year),
    )


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def movie_key(movie: dict[str, Any]) -> tuple[str, str] | None:
    tmdb_id = movie.get("tmdbId")
    if tmdb_id not in (None, ""):
        return "tmdb", str(tmdb_id)

    imdb_id = movie.get("imdbId")
    if imdb_id:
        return "imdb", str(imdb_id)

    return None


def existing_movie_keys(movies: list[dict[str, Any]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for movie in movies:
        key = movie_key(movie)
        if key:
            keys.add(key)
    return keys


def pick_best_candidate(candidates: list[dict[str, Any]], year: str | None) -> int | None:
    if not candidates:
        return None
    if year:
        for index, candidate in enumerate(candidates):
            if str(candidate.get("year", "")) == str(year):
                return index
    return 0


def refresh_item_statuses(items: list[MovieItem], existing_keys: set[tuple[str, str]]) -> None:
    seen_in_run: set[tuple[str, str]] = set()
    for item in items:
        if item.skipped and item.skip_reason == "user skipped":
            continue

        if item.selected_candidate is None:
            item.skipped = True
            item.skip_reason = "no candidate selected"
            continue

        key = movie_key(item.selected_candidate)
        if key and key in existing_keys:
            item.skipped = True
            item.skip_reason = "exists in Radarr"
            continue

        if key and key in seen_in_run:
            item.skipped = True
            item.skip_reason = "duplicate selection in this run"
            continue

        if key:
            seen_in_run.add(key)

        if item.skip_reason in {
            "no candidate selected",
            "exists in Radarr",
            "duplicate selection in this run",
        }:
            item.skip_reason = None
            item.skipped = False


def candidate_label(candidate: dict[str, Any] | None) -> str:
    if candidate is None:
        return "none"
    title = candidate.get("title") or candidate.get("originalTitle") or "Unknown title"
    year = candidate.get("year") or "????"
    tmdb = candidate.get("tmdbId") or "-"
    imdb = candidate.get("imdbId") or "-"
    return f"{title} ({year}) tmdb={tmdb} imdb={imdb}"


def display_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return candidates[:MAX_DISPLAY_CANDIDATES]


def prompt_for_item(item: MovieItem, client: RadarrClient) -> str:
    while True:
        print()
        print(f"File: {item.path.name}")
        print(f"Parsed: {item.parsed.search_term or 'no parsed title'}")
        if item.candidates:
            if len(item.candidates) == 1:
                print("Candidate:")
            else:
                print(f"Candidates, showing first {min(MAX_DISPLAY_CANDIDATES, len(item.candidates))} of {len(item.candidates)}:")
            for index, candidate in enumerate(display_candidates(item.candidates), 1):
                selected = "*" if item.selected_index == index - 1 else " "
                print(f"  {selected}{index}. {candidate_label(candidate)}")
        else:
            print("No candidates.")

        try:
            value = input("Choose candidate number to add, [m]anual search, /new search, [s]kip, or [q]uit: ").strip()
        except EOFError:
            value = "q"
        if value.lower() == "q":
            return "quit"
        if value.lower() == "s":
            item.skipped = True
            item.skip_reason = "user skipped"
            return "skip"
        if value.lower() == "m":
            search_term = input("Radarr search term: ").strip()
            if not search_term:
                print("Search term cannot be empty.")
                continue
            try:
                item.candidates = client.lookup(search_term)
            except RadarrError as error:
                print(f"Radarr lookup failed: {error}")
                item.candidates = []
                item.selected_index = None
                continue
            item.selected_index = pick_best_candidate(item.candidates, item.parsed.year)
            item.skipped = False
            item.skip_reason = None
            continue
        if value.startswith("/"):
            term = value[1:].strip()
            if not term:
                print("Search term cannot be empty.")
                continue
            try:
                item.candidates = client.lookup(term)
            except RadarrError as error:
                print(f"Radarr lookup failed: {error}")
                item.candidates = []
                item.selected_index = None
                continue
            item.selected_index = pick_best_candidate(item.candidates, item.parsed.year)
            item.skipped = False
            item.skip_reason = None
            continue
        if value.isdigit():
            candidate_index = int(value) - 1
            if candidate_index < 0 or candidate_index >= len(display_candidates(item.candidates)):
                print("Candidate number is out of range.")
                continue
            item.selected_index = candidate_index
            item.skipped = False
            item.skip_reason = None
            return "add"
        print("Invalid command.")


def process_one_item(
    content_item: ContentItem,
    index: int,
    total: int,
    client: RadarrClient,
    quality_profile_id: int,
    root_folder_path: str,
    minimum_availability: str,
    existing_keys: set[tuple[str, str]],
    state_store: StateStore,
) -> RunResult:
    parsed = parse_mkv_name(content_item.parse_path)
    state_store.record(content_item, "pending", "lookup started", parsed=parsed)
    print()
    print(
        f"[{index}/{total}] Lookup: {content_item.path.name} "
        f"({content_item.kind}) -> {parsed.search_term or 'no parsed title'}"
    )

    candidates: list[dict[str, Any]] = []
    if parsed.search_term:
        candidates = client.lookup(parsed.search_term)

    item = MovieItem(
        path=content_item.path,
        parsed=parsed,
        candidates=candidates,
        selected_index=pick_best_candidate(candidates, parsed.year),
    )

    while True:
        action = prompt_for_item(item, client)
        if action == "quit":
            return RunResult(content_item, "quit", "user quit")
        if action == "skip":
            print(f"SKIP {content_item.path.name}: user skipped")
            state_store.record(content_item, "skipped", "user skipped", parsed=parsed)
            return RunResult(content_item, "skipped", "user skipped")

        candidate = item.selected_candidate
        if candidate is None:
            print("No candidate is selected.")
            continue

        key = movie_key(candidate)
        if key and key in existing_keys:
            print(f"SKIP exists: {candidate_label(candidate)}")
            state_store.record(content_item, "skipped", "exists in Radarr", parsed=parsed, movie=candidate)
            return RunResult(content_item, "skipped", "exists in Radarr", candidate)

        try:
            added = client.add_movie(candidate, quality_profile_id, root_folder_path, minimum_availability)
        except RadarrError as error:
            print(f"FAIL {content_item.path.name}: {error}")
            state_store.record(content_item, "failed", str(error), parsed=parsed, movie=candidate)
            return RunResult(content_item, "failed", str(error), candidate)

        added_key = movie_key(added) or key
        if added_key:
            existing_keys.add(added_key)
        print(f"ADDED {content_item.path.name}: {candidate_label(added)}")
        state_store.record(content_item, "added", candidate_label(added), parsed=parsed, movie=added)
        return RunResult(content_item, "added", candidate_label(added), added)


def print_run_summary(results: list[RunResult], sample_items: list[ContentItem]) -> None:
    added = [result for result in results if result.status == "added"]
    skipped = [result for result in results if result.status == "skipped"]
    failed = [result for result in results if result.status == "failed"]

    print()
    print("Run Summary")
    print("=" * 80)
    print(f"Added: {len(added)}")
    for result in added:
        print(f"  + {result.content_item.path} -> {result.detail}")

    print(f"Skipped: {len(skipped) + len(sample_items)}")
    for item in sample_items:
        print(f"  - {item.path} -> sample content")
    for result in skipped:
        print(f"  - {result.content_item.path} -> {result.detail}")

    print(f"Failed: {len(failed)}")
    for result in failed:
        print(f"  ! {result.content_item.path} -> {result.detail}")
    print("=" * 80)


def state_dir_for(directory: Path, args: argparse.Namespace) -> Path:
    if args.state_dir:
        return Path(args.state_dir).expanduser()
    return directory / ".radarr-add-state"


def completed_result_from_state(content_item: ContentItem, state: dict[str, Any]) -> RunResult:
    status = str(state.get("status") or "skipped")
    detail = str(state.get("detail") or "completed in previous run")
    movie = state.get("movie")
    return RunResult(content_item, status, detail, movie if isinstance(movie, dict) else None)


def should_resume_skip(state: dict[str, Any] | None, no_resume: bool) -> bool:
    if no_resume or not state:
        return False
    return str(state.get("status")) in COMPLETED_STATE_STATUSES


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manually add MKV movies from a directory to Radarr.")
    parser.add_argument("--directory", required=True, help="Directory containing MKV files.")
    parser.add_argument("--radarr-url", default=os.getenv("RADARR_URL"), help="Radarr URL, or RADARR_URL.")
    parser.add_argument("--api-key", default=os.getenv("RADARR_API_KEY"), help="Radarr API key, or RADARR_API_KEY.")
    parser.add_argument("--quality-profile-id", type=int, required=True, help="Radarr quality profile id.")
    parser.add_argument("--root-folder-path", required=True, help="Radarr root folder path for added movies.")
    parser.add_argument(
        "--minimum-availability",
        default=DEFAULT_MINIMUM_AVAILABILITY,
        choices=["announced", "inCinemas", "released"],
        help="Radarr minimum availability.",
    )
    parser.add_argument("--recursive", action="store_true", help="Scan subdirectories recursively.")
    parser.add_argument(
        "--state-dir",
        help="Directory for resume state; defaults to <directory>/.radarr-add-state.",
    )
    parser.add_argument("--no-resume", action="store_true", help="Ignore existing resume state for this run.")
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> Path:
    missing = []
    if not args.radarr_url:
        missing.append("--radarr-url or RADARR_URL")
    if not args.api_key:
        missing.append("--api-key or RADARR_API_KEY")
    if missing:
        raise ValueError(f"Missing required values: {', '.join(missing)}")

    directory = Path(args.directory).expanduser()
    if not directory.exists():
        raise ValueError(f"Directory does not exist: {directory}")
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")
    return directory


def run(args: argparse.Namespace) -> int:
    try:
        directory = validate_args(args)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    client = RadarrClient(args.radarr_url, args.api_key)
    state_store = StateStore(state_dir_for(directory, args), enabled=True)
    state_store.initialize(directory, args.recursive)

    try:
        existing_movies = client.get_movies()
    except RadarrError as error:
        print(f"Unable to load Radarr movies: {error}", file=sys.stderr)
        return 1

    existing_keys = existing_movie_keys(existing_movies)
    content_items, sample_items = find_content_items(directory, recursive=args.recursive)

    if not content_items:
        print("No non-sample MKV or disc content items found.")
        if sample_items:
            print(f"Skipped sample content items: {len(sample_items)}")
        return 0

    if sample_items:
        print(f"Skipped sample content items: {len(sample_items)}")
        for item in sample_items:
            print(f"  sample: {item.path}")
            state_store.record(item, "skipped", "sample content")

    results: list[RunResult] = []
    for index, content_item in enumerate(content_items, 1):
        state = state_store.load(content_item)
        if should_resume_skip(state, args.no_resume):
            result = completed_result_from_state(content_item, state or {})
            print(f"RESUME skip {content_item.path.name}: {result.status} ({result.detail})")
            results.append(result)
            continue

        state_store.record_discovered(content_item)
        try:
            result = process_one_item(
                content_item,
                index,
                len(content_items),
                client,
                args.quality_profile_id,
                args.root_folder_path,
                args.minimum_availability,
                existing_keys,
                state_store,
            )
        except RadarrError as error:
            print(f"FAIL {content_item.path.name}: {error}")
            result = RunResult(content_item, "failed", str(error))

        if result.status == "quit":
            print("Stopped by user.")
            break
        results.append(result)

    print_run_summary(results, sample_items)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
