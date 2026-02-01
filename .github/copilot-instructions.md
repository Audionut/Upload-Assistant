# Upload Assistant – Copilot Instructions

## Project overview
- Entry point is upload.py; it orchestrates config loading, CLI parsing, prep, torrent creation, tracker uploads, and client injection.
- Core workflow flows through `meta` (a shared dict) populated/updated across modules; see `Prep.gather_prep()` in the prep module under src/.
- `Prep.gather_prep()` builds most of the operational `meta` state (disc detection, file lists, IDs, names, and screenshot behavior) and creates tmp/<uuid>/; many downstream modules assume these keys exist.
- Metadata lookups are coordinated by `MetadataSearchingManager` in the metadata_searching module under src/, which runs TMDb/IMDb/TVDb/TVMaze calls in parallel and merges results back into `meta`.
- Pre-upload validation and per-tracker status are handled by `TrackerStatusManager` in the trackerstatus module under src/ before `process_trackers` runs uploads.
- Trackers are implemented as per-site classes under src/trackers/ with shared helpers in `COMMON`; selection/validation is centralized in `TRACKER_SETUP` within the trackersetup module.
- Torrent creation is handled by `TorrentCreator` in the torrentcreate module under src/ using `torf` (and optionally mkbrr). Output files live in tmp/<uuid>/ and are named like [tracker].torrent.
- Client injection/searching for existing torrents is abstracted in `Clients` in the clients module under src/ with mixins under src/torrent_clients/.

## Configuration & state
- User configuration is a Python dict in data/config.py; new installs copy data/example-config.py. upload.py has explicit error reporting for config syntax/type issues.
- The working directory per run is tmp/<uuid>/; many modules read/write artifacts there (torrents, mediainfo, screenshots). Keep this layout when adding features.
- Disc handling is keyed off `meta['is_disc']` with values like "BDMV" and "DVD" and determines whether `meta['filelist']` is populated vs using the folder path directly in later steps.

## Key integrations
- External APIs: TMDb/IMDb/TVDB/TVMaze, image hosts, and tracker HTTP APIs. See per-tracker config sections in data/example-config.py and tracker classes under src/trackers/.

## Developer workflows
- Install dependencies: pip install -r requirements.txt.
- Lint/type-check settings live in pyproject.toml: Ruff configured with line-length 176 and Pyright strict mode.
- Main CLI usage: python upload.py "<path>" [options]; argument definitions are in `Args` in the args module under src/.
- Web UI mode: use -webui/--webui; server code lives under web_ui/.

## Lint & type-check expectations
- Follow Ruff and Pyright settings in pyproject.toml when making changes.

## SonarQube rules
- When touching a file, run SonarQube analysis for that file and fix any reported issues.
- Default SonarQube ruleset, with these overrides:
	- python:S3776 level off
	- python:S107 level off
	- python:S125 level off
	- python:S117 level off
	- python:S3358 level off
	- python:S1192 threshold 10
  	- python:S101 level off
  	- python:S100 level off
  	- python:S5843 level off
  	- python:S1542 level off
  	- python:S1135 level off
- follow SonarQube ruleset with overrides when adding or modifying code.

## Codebase conventions
- Most core functions are async; prefer async IO and `asyncio.to_thread()` for blocking work (e.g., torrent hashing in the torrentcreate module under src/).
- `meta` keys are widely reused across modules; avoid renaming keys without tracing references (search in src/).
- `Prep.gather_prep()` sets `meta['uuid']` to the folder name when not provided and creates tmp/<uuid>/; new features should write artifacts there and reuse the same `meta['uuid']` value.
- Metadata retrieval uses `asyncio.gather` with `return_exceptions=True` in the metadata_searching module under src/; when adding new calls, preserve the parallel task pattern and the existing TV vs TV-pack branching.
- Tracker status uses per-tracker deep copies of `meta` and merges selective fields under a lock in the trackerstatus module under src/; avoid writing shared `meta` outside the lock when adding new cross-tracker flags.
- Tracker uploads are processed via `process_trackers` in the trackerhandle module under src/; ensure new tracker classes integrate with `TRACKER_SETUP` and expected status dicts.
