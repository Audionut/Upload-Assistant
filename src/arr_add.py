# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import json
import os
import re
import time
import traceback
from typing import Any, Optional, cast

import aiofiles
from typing_extensions import TypeAlias

from src.clients import Clients
from src.console import console
from src.get_tracker_data import TrackerDataManager
from src.radarr import RadarrManager
from src.sonarr import SonarrManager
from src.tvdb import tvdb_data

Meta: TypeAlias = dict[str, Any]
RadarrAddDuplicateKey: TypeAlias = tuple[str, str]
SonarrAddDuplicateKey: TypeAlias = tuple[str, str, str]

RADARR_ADD_TRACKER_ID_KEYS: tuple[str, ...] = (
    'aither', 'ulcx', 'lst', 'blu', 'oe', 'btn', 'bhd', 'huno', 'hdb', 'rf', 'otw', 'yus', 'dp', 'sp',
    'ras', 'lume', 'hhd', 'rmc', 'ptp', 'ant'
)
RADARR_ADD_VIDEO_EXTENSIONS: tuple[str, ...] = ('.mkv', '.mp4', '.ts')
SONARR_ADD_SKIPPED_TRACKER_ID_KEYS: tuple[str, ...] = ('ptp', 'rf', 'ant')
SONARR_ADD_TRACKER_ID_KEYS: tuple[str, ...] = tuple(
    key for key in RADARR_ADD_TRACKER_ID_KEYS if key not in SONARR_ADD_SKIPPED_TRACKER_ID_KEYS
)
SONARR_ADD_TRACKER_META_KEYS: dict[str, str] = {
    'AITHER': 'aither',
    'ULCX': 'ulcx',
    'LST': 'lst',
    'BLU': 'blu',
    'OE': 'oe',
    'BTN': 'btn',
    'BHD': 'bhd',
    'HUNO': 'huno',
    'HDB': 'hdb',
    'RF': 'rf',
    'OTW': 'otw',
    'YUS': 'yus',
    'DP': 'dp',
    'SP': 'sp',
    'RAS': 'ras',
    'LUME': 'lume',
    'HHD': 'hhd',
    'RMC': 'rmc',
    'PTP': 'ptp',
    'ANT': 'ant',
}


def _safe_int_id(value: Any) -> Optional[int]:
    try:
        parsed = int(str(value).replace("tt", ""))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _detect_radarr_add_disc(path: str) -> str:
    if not os.path.isdir(path):
        return ""
    try:
        for entry in os.scandir(path):
            if entry.is_dir():
                entry_name = entry.name.upper()
                if entry_name == "BDMV":
                    return "BDMV"
                if entry_name == "VIDEO_TS":
                    return "DVD"
    except OSError:
        return ""
    return ""


def _first_video_file(path: str) -> Optional[str]:
    if os.path.isfile(path) and path.lower().endswith(RADARR_ADD_VIDEO_EXTENSIONS):
        return path
    if not os.path.isdir(path):
        return None
    try:
        for root, _dirs, files in os.walk(path):
            for file in sorted(files):
                if file.lower().endswith(RADARR_ADD_VIDEO_EXTENSIONS):
                    return os.path.join(root, file)
    except OSError:
        return None
    return None


def _normalize_arr_add_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


async def _radarr_add_duplicate_key(name_manager: Any, meta: Meta, path: str) -> Optional[RadarrAddDuplicateKey]:
    title, _secondary_title, year = await name_manager.extract_title_and_year(meta, path)
    if not title or not year:
        return None
    normalized_title = _normalize_arr_add_title(title)
    return (normalized_title, str(year)) if normalized_title else None


def _radarr_add_duplicate_label(key: RadarrAddDuplicateKey) -> str:
    title, year = key
    return f"{title} ({year})"


def _radarr_add_duplicate_key_from_movie(movie: Any) -> Optional[RadarrAddDuplicateKey]:
    if not isinstance(movie, dict):
        return None
    title_value = movie.get("title") or movie.get("originalTitle")
    year_value = movie.get("year")
    if not title_value or not year_value:
        return None
    title = _normalize_arr_add_title(str(title_value))
    year = str(year_value)
    return (title, year) if title and year else None


def radarr_add_seen_key_file(base_dir: str, meta: Meta) -> str:
    queue_name = str(meta.get('queue') or "default").replace(" ", "_")
    return os.path.join(base_dir, "tmp", f"{queue_name}_radarr_add_title_years.json")


def radarr_add_unable_log_file(base_dir: str, meta: Meta) -> str:
    queue_name = str(meta.get('queue') or "default").replace(" ", "_")
    return os.path.join(base_dir, "tmp", f"{queue_name}_radarr_add_unable_titles.json")


async def load_radarr_add_seen_keys(path: str) -> set[RadarrAddDuplicateKey]:
    if not os.path.exists(path):
        return set()
    try:
        async with aiofiles.open(path, encoding='utf-8') as f:
            content = await f.read()
        loaded = json.loads(content) if content.strip() else []
    except Exception:
        return set()

    keys: set[RadarrAddDuplicateKey] = set()
    if not isinstance(loaded, list):
        return keys
    for item in loaded:
        if isinstance(item, dict):
            title = item.get("title")
            year = item.get("year")
            if isinstance(title, str) and isinstance(year, str) and title and year:
                keys.add((title, year))
    return keys


async def _save_radarr_add_seen_keys(path: str, seen_title_years: set[RadarrAddDuplicateKey]) -> None:
    data = [
        {"title": title, "year": year}
        for title, year in sorted(seen_title_years)
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    async with aiofiles.open(path, "w", encoding='utf-8') as f:
        await f.write(json.dumps(data, indent=4))


async def _remember_radarr_add_key(
    duplicate_key: Optional[RadarrAddDuplicateKey],
    seen_title_years: set[RadarrAddDuplicateKey],
    seen_key_file: Optional[str],
) -> None:
    if not duplicate_key:
        return
    seen_title_years.add(duplicate_key)
    if seen_key_file:
        await _save_radarr_add_seen_keys(seen_key_file, seen_title_years)


async def _record_radarr_add_unable_title(
    path: str,
    search_term: str,
    reason: str,
    meta: Meta,
    unable_log_file: Optional[str],
) -> None:
    if not unable_log_file:
        return

    record = {
        "path": path,
        "title": search_term,
        "reason": reason,
        "timestamp": str(int(time.time())),
    }
    tracker_ids = {
        key: str(meta[key])
        for key in RADARR_ADD_TRACKER_ID_KEYS
        if meta.get(key) not in (None, "", 0, "0")
    }
    if tracker_ids:
        record["tracker_ids"] = json.dumps(tracker_ids, sort_keys=True)

    existing: list[dict[str, str]] = []
    if os.path.exists(unable_log_file):
        try:
            async with aiofiles.open(unable_log_file, encoding='utf-8') as f:
                content = await f.read()
            loaded = json.loads(content) if content.strip() else []
            if isinstance(loaded, list):
                existing = [
                    cast(dict[str, str], item)
                    for item in loaded
                    if isinstance(item, dict)
                ]
        except Exception:
            existing = []

    existing = [item for item in existing if item.get("path") != path]
    existing.append(record)
    os.makedirs(os.path.dirname(unable_log_file), exist_ok=True)
    async with aiofiles.open(unable_log_file, "w", encoding='utf-8') as f:
        await f.write(json.dumps(existing, indent=4))


async def _sonarr_add_duplicate_keys(name_manager: Any, meta: Meta, path: str) -> set[SonarrAddDuplicateKey]:
    title, _secondary_title, year = await name_manager.extract_title_and_year(meta, path)
    if not title:
        return set()
    normalized_title = _normalize_arr_add_title(title)
    if not normalized_title:
        return set()

    keys: set[SonarrAddDuplicateKey] = {(normalized_title, "title", "")}
    tvdb_id = _safe_int_id(meta.get('tvdb_id') or meta.get('tvdb'))
    if tvdb_id:
        keys.add((normalized_title, "tvdb_id", str(tvdb_id)))
    if year:
        keys.add((normalized_title, "year", str(year)))
    return keys


def _sonarr_add_duplicate_label(key: SonarrAddDuplicateKey) -> str:
    title, key_type, value = key
    if key_type == "tvdb_id":
        return f"{title} tvdb={value}"
    if key_type == "title":
        return title
    return f"{title} ({value})"


def _sonarr_add_duplicate_keys_from_series(series: Any) -> set[SonarrAddDuplicateKey]:
    if not isinstance(series, dict):
        return set()
    title_value = series.get("title") or series.get("originalTitle")
    if not title_value:
        return set()
    title = _normalize_arr_add_title(str(title_value))
    if not title:
        return set()

    keys: set[SonarrAddDuplicateKey] = {(title, "title", "")}
    tvdb_id = _safe_int_id(series.get("tvdbId"))
    if tvdb_id:
        keys.add((title, "tvdb_id", str(tvdb_id)))
    year_value = series.get("year")
    if year_value:
        keys.add((title, "year", str(year_value)))
    return keys


def _sonarr_add_first_seen_key(
    duplicate_keys: set[SonarrAddDuplicateKey],
    seen_keys: set[SonarrAddDuplicateKey],
) -> Optional[SonarrAddDuplicateKey]:
    key_types = ("tvdb_id", "year") if any(key[1] in ("tvdb_id", "year") for key in duplicate_keys) else ("title",)
    for key_type in key_types:
        for key in sorted(duplicate_keys):
            if key[1] == key_type and key in seen_keys:
                return key
    return None


def _sonarr_add_lookup_label(duplicate_keys: set[SonarrAddDuplicateKey], fallback: str) -> str:
    for key_type in ("year", "title", "tvdb_id"):
        for key in sorted(duplicate_keys):
            if key[1] == key_type:
                return _sonarr_add_duplicate_label(key)
    return fallback


def sonarr_add_seen_key_file(base_dir: str, meta: Meta) -> str:
    queue_name = str(meta.get('queue') or "default").replace(" ", "_")
    return os.path.join(base_dir, "tmp", f"{queue_name}_sonarr_add_series.json")


def sonarr_add_unable_log_file(base_dir: str, meta: Meta) -> str:
    queue_name = str(meta.get('queue') or "default").replace(" ", "_")
    return os.path.join(base_dir, "tmp", f"{queue_name}_sonarr_add_unable_titles.json")


async def load_sonarr_add_seen_keys(path: str) -> set[SonarrAddDuplicateKey]:
    if not os.path.exists(path):
        return set()
    try:
        async with aiofiles.open(path, encoding='utf-8') as f:
            content = await f.read()
        loaded = json.loads(content) if content.strip() else []
    except Exception:
        return set()

    keys: set[SonarrAddDuplicateKey] = set()
    if not isinstance(loaded, list):
        return keys
    for item in loaded:
        if isinstance(item, dict):
            title = item.get("title")
            tvdb_id = item.get("tvdb_id")
            year = item.get("year")
            if isinstance(title, str) and title:
                keys.add((title, "title", ""))
            if isinstance(title, str) and isinstance(tvdb_id, str) and title and tvdb_id:
                keys.add((title, "tvdb_id", tvdb_id))
            if isinstance(title, str) and isinstance(year, str) and title and year:
                keys.add((title, "year", year))
    return keys


async def _save_sonarr_add_seen_keys(path: str, seen_keys: set[SonarrAddDuplicateKey]) -> None:
    data: list[dict[str, str]] = []
    for title, key_type, value in sorted(seen_keys):
        item = {"title": title}
        if key_type == "tvdb_id":
            item["tvdb_id"] = value
        elif key_type == "year":
            item["year"] = value
        data.append(item)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    async with aiofiles.open(path, "w", encoding='utf-8') as f:
        await f.write(json.dumps(data, indent=4))


async def _remember_sonarr_add_keys(
    duplicate_keys: set[SonarrAddDuplicateKey],
    seen_keys: set[SonarrAddDuplicateKey],
    seen_key_file: Optional[str],
) -> None:
    if not duplicate_keys:
        return
    seen_keys.update(duplicate_keys)
    if seen_key_file:
        await _save_sonarr_add_seen_keys(seen_key_file, seen_keys)


async def _record_sonarr_add_unable_title(
    path: str,
    search_term: str,
    reason: str,
    meta: Meta,
    unable_log_file: Optional[str],
) -> None:
    if not unable_log_file:
        return

    record = {
        "path": path,
        "title": search_term,
        "reason": reason,
        "timestamp": str(int(time.time())),
    }
    tracker_ids = {
        key: str(meta[key])
        for key in SONARR_ADD_TRACKER_ID_KEYS
        if meta.get(key) not in (None, "", 0, "0")
    }
    if tracker_ids:
        record["tracker_ids"] = json.dumps(tracker_ids, sort_keys=True)

    existing: list[dict[str, str]] = []
    if os.path.exists(unable_log_file):
        try:
            async with aiofiles.open(unable_log_file, encoding='utf-8') as f:
                content = await f.read()
            loaded = json.loads(content) if content.strip() else []
            if isinstance(loaded, list):
                existing = [
                    cast(dict[str, str], item)
                    for item in loaded
                    if isinstance(item, dict)
                ]
        except Exception:
            existing = []

    existing = [item for item in existing if item.get("path") != path]
    existing.append(record)
    os.makedirs(os.path.dirname(unable_log_file), exist_ok=True)
    async with aiofiles.open(unable_log_file, "w", encoding='utf-8') as f:
        await f.write(json.dumps(existing, indent=4))


def _prepare_radarr_add_meta(meta: Meta, path: str, base_dir: str) -> tuple[str, str]:
    path_basename = os.path.basename(os.path.normpath(path))
    video_file = _first_video_file(path)
    is_disc = _detect_radarr_add_disc(path)

    meta['path'] = path
    meta['base_dir'] = base_dir
    meta['uuid'] = path_basename
    meta['category'] = "MOVIE"
    meta['manual_category'] = "movie"
    meta['is_disc'] = is_disc
    meta['isdir'] = os.path.isdir(path)
    meta['filelist'] = [video_file] if video_file else []
    meta['video'] = video_file or path
    meta['trackers'] = []
    meta['requested_trackers'] = []
    meta['description'] = ""
    meta['image_list'] = []
    meta['unattended'] = True
    meta['unattended_confirm'] = False
    meta['onlyID'] = True
    meta['only_id'] = True
    meta['keep_images'] = False
    meta['client_ids_only'] = True
    meta['skip_auto_torrent'] = False
    meta['base_torrent_created'] = True
    meta['we_checked_them_all'] = False
    meta['debug'] = bool(meta.get('debug', False))

    if os.path.isfile(path):
        return os.path.basename(path), "file"
    return path_basename, "folder"


def _prepare_sonarr_add_meta(meta: Meta, path: str, base_dir: str) -> tuple[str, str]:
    path_basename = os.path.basename(os.path.normpath(path))
    video_file = _first_video_file(path)

    meta['path'] = path
    meta['base_dir'] = base_dir
    meta['uuid'] = path_basename
    meta['filename'] = path_basename
    meta['category'] = "TV"
    meta['manual_category'] = "tv"
    meta['is_disc'] = ""
    meta['isdir'] = os.path.isdir(path)
    meta['filelist'] = [video_file] if video_file else []
    meta['video'] = video_file or path
    meta['trackers'] = []
    meta['requested_trackers'] = []
    meta['description'] = ""
    meta['image_list'] = []
    meta['unattended'] = True
    meta['unattended_confirm'] = False
    meta['onlyID'] = True
    meta['only_id'] = True
    meta['keep_images'] = False
    meta['client_ids_only'] = True
    meta['skip_auto_torrent'] = False
    meta['base_torrent_created'] = True
    meta['we_checked_them_all'] = False
    meta['debug'] = bool(meta.get('debug', False))

    if os.path.isfile(path):
        return os.path.basename(path), "file"
    return path_basename, "folder"


async def _get_sonarr_add_tracker_data(config: dict[str, Any], meta: Meta, search_term: str, search_file_folder: str) -> None:
    attempted_trackers: set[str] = set()

    while not _safe_int_id(meta.get('tvdb_id') or meta.get('tvdb')):
        remaining_tracker_keys = [
            key
            for key in SONARR_ADD_TRACKER_ID_KEYS
            if key not in attempted_trackers and meta.get(key) not in (None, "", 0, "0")
        ]
        if not remaining_tracker_keys:
            return

        meta.pop('matched_tracker', None)
        meta.pop('no_tracker_match', None)
        await TrackerDataManager(config).get_tracker_data(
            None,
            meta,
            search_term=search_term,
            search_file_folder=search_file_folder,
            cat="TV",
            only_id=True,
        )

        if _safe_int_id(meta.get('tvdb_id') or meta.get('tvdb')):
            return

        matched_tracker = str(meta.get('matched_tracker') or "").upper()
        matched_tracker_key = SONARR_ADD_TRACKER_META_KEYS.get(matched_tracker)
        if not matched_tracker_key:
            return

        attempted_trackers.add(matched_tracker_key)
        meta[matched_tracker_key] = None
        if meta.get('debug', False):
            console.print(f"[yellow]Sonarr add: {matched_tracker} did not return TVDb; trying remaining tracker IDs.[/yellow]")


async def _resolve_sonarr_add_tvdb_from_external_ids(
    config: dict[str, Any],
    meta: Meta,
    imdb_id: Optional[int],
    tmdb_id: Optional[int],
) -> Optional[int]:
    if not imdb_id and not tmdb_id:
        return None

    console.print("[yellow]Sonarr add: no TVDb ID from trackers; trying TVDb lookup from IMDb/TMDb.[/yellow]")
    tvdb_id, tvdb_series_name = await tvdb_data(config).get_tvdb_by_external_id(
        imdb_id,
        tmdb_id,
        debug=bool(meta.get('debug', False)),
    )
    resolved_tvdb_id = _safe_int_id(tvdb_id)
    if not resolved_tvdb_id:
        return None

    meta['tvdb_id'] = resolved_tvdb_id
    meta['tvdb'] = resolved_tvdb_id
    if tvdb_series_name:
        meta['tvdb_series_name'] = tvdb_series_name
    if meta.get('debug', False):
        console.print(f"[green]Sonarr add: found TVDb ID from IMDb/TMDb lookup: {resolved_tvdb_id}[/green]")
    return resolved_tvdb_id


async def process_radarr_add(
    meta: Meta,
    base_dir: str,
    seen_title_years: set[RadarrAddDuplicateKey],
    seen_key_file: Optional[str],
    unable_log_file: Optional[str],
    config: dict[str, Any],
    name_manager: Any,
) -> bool:
    path = str(meta.get('path') or "")
    if not path:
        console.print("[red]Radarr add skipped: no input path was available.[/red]")
        return True

    search_term, search_file_folder = _prepare_radarr_add_meta(meta, path, base_dir)
    duplicate_key = await _radarr_add_duplicate_key(name_manager, meta, path)
    if duplicate_key and duplicate_key in seen_title_years:
        console.print(f"[red]Radarr add skipped duplicate title/year before qBittorrent search: {_radarr_add_duplicate_label(duplicate_key)}[/red]")
        return True

    if config.get('DEFAULT', {}).get('use_radarr', False):
        lookup_term = _radarr_add_duplicate_label(duplicate_key) if duplicate_key else search_term
        radarr_existing = await RadarrManager(config).existing_movie_by_lookup_term(lookup_term, debug=meta.get('debug', False))
        if radarr_existing.get("status") == "exists":
            detail = str(radarr_existing.get("detail") or "")
            console.print(f"[red]Radarr add skipped before qBittorrent search: {detail}[/red]")
            movie_key = _radarr_add_duplicate_key_from_movie(radarr_existing.get("movie"))
            await _remember_radarr_add_key(duplicate_key or movie_key, seen_title_years, seen_key_file)
            return True

    console.print(f"[green]Radarr add: gathering tracker IDs for {os.path.basename(path)}[/green]")

    try:
        await Clients(config).get_pathed_torrents(path, meta)
    except Exception as e:
        console.print(f"[red]Radarr add skipped: qBittorrent search failed for {path}: {e}[/red]")
        if meta.get('debug', False):
            console.print(traceback.format_exc())
        return True

    tracker_ids = {
        key: str(meta[key])
        for key in RADARR_ADD_TRACKER_ID_KEYS
        if meta.get(key) not in (None, "", 0, "0")
    }
    if not tracker_ids:
        reason = "No tracker IDs found in qBittorrent."
        await _record_radarr_add_unable_title(path, search_term, reason, meta, unable_log_file)
        console.print(f"[yellow]Radarr add unable: {search_term} was logged because no tracker IDs were found in qBittorrent.[/yellow]")
        return True

    if meta.get('debug', False):
        console.print(f"[cyan]Radarr add tracker IDs from qBittorrent: {tracker_ids}[/cyan]")

    await TrackerDataManager(config).get_tracker_data(
        None,
        meta,
        search_term=search_term,
        search_file_folder=search_file_folder,
        cat="MOVIE",
        only_id=True,
    )

    tmdb_id = _safe_int_id(meta.get('tmdb_id') or meta.get('tmdb'))
    imdb_id = _safe_int_id(meta.get('imdb_id') or meta.get('imdb'))
    if not tmdb_id and not imdb_id and meta.get('debug', False):
        console.print(f"[yellow]Tracker IDs did not return TMDb or IMDb for {os.path.basename(path)}; trying Radarr filename fallback.[/yellow]")

    result = await RadarrManager(config).add_movie_by_ids(
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
        fallback_filename=search_term,
        debug=meta.get('debug', False),
    )
    status = str(result.get("status") or "failed")
    detail = str(result.get("detail") or "")
    used_filename_fallback = bool(result.get("used_filename_fallback", False))
    if status == "added":
        if used_filename_fallback:
            console.print(f"[red]Radarr add filename fallback used: {detail}[/red]")
        else:
            console.print(f"[green]Radarr add complete: {detail}[/green]")
        await _remember_radarr_add_key(duplicate_key, seen_title_years, seen_key_file)
        return True
    if status == "exists":
        if used_filename_fallback:
            console.print(f"[red]Radarr add filename fallback skipped: {detail}[/red]")
        else:
            console.print(f"[red]Radarr add skipped: {detail}[/red]")
        await _remember_radarr_add_key(duplicate_key, seen_title_years, seen_key_file)
        return True

    reason = detail or "Radarr add failed."
    await _record_radarr_add_unable_title(path, search_term, reason, meta, unable_log_file)
    console.print(f"[red]Radarr add failed for {os.path.basename(path)}: {detail}[/red]")
    return False


async def process_sonarr_add(
    meta: Meta,
    base_dir: str,
    seen_keys: set[SonarrAddDuplicateKey],
    seen_key_file: Optional[str],
    unable_log_file: Optional[str],
    config: dict[str, Any],
    name_manager: Any,
) -> bool:
    path = str(meta.get('path') or "")
    if not path:
        console.print("[red]Sonarr add skipped: no input path was available.[/red]")
        return True

    search_term, search_file_folder = _prepare_sonarr_add_meta(meta, path, base_dir)
    duplicate_keys = await _sonarr_add_duplicate_keys(name_manager, meta, path)
    seen_key = _sonarr_add_first_seen_key(duplicate_keys, seen_keys)
    if seen_key:
        console.print(f"[red]Sonarr add skipped duplicate series before qBittorrent search: {_sonarr_add_duplicate_label(seen_key)}[/red]")
        return True

    if config.get('DEFAULT', {}).get('use_sonarr', False):
        lookup_term = _sonarr_add_lookup_label(duplicate_keys, search_term)
        sonarr_existing = await SonarrManager(config).existing_series_by_lookup_term(lookup_term, debug=meta.get('debug', False))
        if sonarr_existing.get("status") == "exists":
            detail = str(sonarr_existing.get("detail") or "")
            console.print(f"[red]Sonarr add skipped before qBittorrent search: {detail}[/red]")
            series_keys = _sonarr_add_duplicate_keys_from_series(sonarr_existing.get("series"))
            await _remember_sonarr_add_keys(series_keys or duplicate_keys, seen_keys, seen_key_file)
            return True

    console.print(f"[green]Sonarr add: gathering tracker IDs for {os.path.basename(path)}[/green]")

    try:
        await Clients(config).get_pathed_torrents(path, meta)
    except Exception as e:
        console.print(f"[red]Sonarr add skipped: qBittorrent search failed for {path}: {e}[/red]")
        if meta.get('debug', False):
            console.print(traceback.format_exc())
        return True

    tracker_ids = {
        key: str(meta[key])
        for key in SONARR_ADD_TRACKER_ID_KEYS
        if meta.get(key) not in (None, "", 0, "0")
    }
    if not tracker_ids:
        console.print(f"[yellow]Sonarr add skipped: no tracker IDs found in qBittorrent for {os.path.basename(path)}[/yellow]")
        return True

    if meta.get('debug', False):
        console.print(f"[cyan]Sonarr add tracker IDs from qBittorrent: {tracker_ids}[/cyan]")

    await _get_sonarr_add_tracker_data(config, meta, search_term, search_file_folder)

    tvdb_id = _safe_int_id(meta.get('tvdb_id') or meta.get('tvdb'))
    imdb_id = _safe_int_id(meta.get('imdb_id') or meta.get('imdb'))
    tmdb_id = _safe_int_id(meta.get('tmdb_id') or meta.get('tmdb'))
    if not tvdb_id:
        tvdb_id = await _resolve_sonarr_add_tvdb_from_external_ids(config, meta, imdb_id, tmdb_id)
    duplicate_keys.update(await _sonarr_add_duplicate_keys(name_manager, meta, path))
    seen_key = _sonarr_add_first_seen_key(duplicate_keys, seen_keys)
    if seen_key:
        console.print(f"[red]Sonarr add skipped duplicate series after tracker lookup: {_sonarr_add_duplicate_label(seen_key)}[/red]")
        return True
    if not tvdb_id and meta.get('debug', False):
        console.print(f"[yellow]Tracker IDs did not return TVDb for {os.path.basename(path)}; logging title as unable to add.[/yellow]")
    if not tvdb_id:
        reason = "Tracker IDs did not return a TVDb ID after trying available trackers."
        await _record_sonarr_add_unable_title(path, search_term, reason, meta, unable_log_file)
        console.print(f"[red]Sonarr add unable: {search_term} was logged because no TVDb ID was found.[/red]")
        return True

    result = await SonarrManager(config).add_series_by_ids(
        tvdb_id=tvdb_id,
        imdb_id=imdb_id,
        tmdb_id=tmdb_id,
        debug=meta.get('debug', False),
    )
    status = str(result.get("status") or "failed")
    detail = str(result.get("detail") or "")
    series_keys = _sonarr_add_duplicate_keys_from_series(result.get("series"))
    if status == "added":
        console.print(f"[green]Sonarr add complete: {detail}[/green]")
        await _remember_sonarr_add_keys(series_keys or duplicate_keys, seen_keys, seen_key_file)
        return True
    if status == "exists":
        console.print(f"[red]Sonarr add skipped: {detail}[/red]")
        await _remember_sonarr_add_keys(series_keys or duplicate_keys, seen_keys, seen_key_file)
        return True

    console.print(f"[red]Sonarr add failed for {os.path.basename(path)}: {detail}[/red]")
    return False
