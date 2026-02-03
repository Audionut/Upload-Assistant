# Upload Assistant – Copilot Instructions

## Project overview
- Entry point is upload.py; it orchestrates config loading, CLI parsing, prep, torrent creation, tracker uploads, and client injection.
- Core workflow flows through `meta` (a shared dict) populated/updated across modules; see `Prep.gather_prep()` in the prep module under src/.
- `Prep.gather_prep()` builds most of the operational `meta` state (disc detection, file lists, IDs, names, and screenshot behavior) and creates tmp/<uuid>/; many downstream modules assume these keys exist.
- Metadata lookups are coordinated by `MetadataSearchingManager` in the metadata_searching module under src/, which runs TMDb/IMDb/TVDb/TVMaze calls in parallel and merges results back into `meta`.
- Pre-upload validation and per-tracker status are handled by `TrackerStatusManager` in the trackerstatus module under src/ before `process_trackers` runs uploads.
- Trackers are implemented as per-site classes under src/trackers/ with shared helpers in `COMMON`; selection/validation is centralized in `TRACKER_SETUP` within the trackersetup module.
- Per site tracker classes handle login, form population, and upload logic; see individual classes under src/trackers/.
- Per site tracker classes should not overwrite pre-populated `meta` objects directly; instead, they should define their own unique keys (e.g., `meta['thr_upload_info']`) to avoid cross-tracker interference.
- Torrent creation is handled by `TorrentCreator` in the torrentcreate module under src/ using `torf` (and optionally mkbrr). Output files live in tmp/<uuid>/ and are named like [tracker].torrent.
- Client injection/searching for existing torrents is abstracted in `Clients` in the clients module under src/ with mixins under src/torrent_clients/.

## Configuration & state
- User configuration is a Python dict in data/config.py; new installs copy data/example-config.py. upload.py has explicit error reporting for config syntax/type issues.
- The working directory per run is tmp/<uuid>/; many modules read/write artifacts there (torrents, mediainfo, screenshots). Keep this layout when adding features.
- Disc handling is keyed off `meta['is_disc']` with values like "BDMV" and "DVD" and determines whether `meta['filelist']` is populated vs using the folder path directly in later steps.

## Key integrations
- External APIs: TMDb/IMDb/TVDB/TVMaze, image hosts, and tracker HTTP/S APIs. See per-tracker config sections in data/example-config.py and tracker classes under src/trackers/.

## Developer workflows
- Install dependencies: pip install -r requirements.txt.
- Additionally, install ruff (pip install ruff) and pyright (npm install pyright) for linting/type-checking.
- Lint/type-check settings live in pyproject.toml: Ruff configured with line-length 176 and Pyright strict mode.
- Main CLI usage: python upload.py "<path>" [options]; argument definitions are in `Args` in the args module under src/.
- Web UI mode: use -webui/--webui; server code lives under web_ui/.

## Lint & type-check expectations
- Follow Ruff and Pyright settings in pyproject.toml when making changes.

## Python version
- All changes must be python version 3.9+ compatible.

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
- Follow SonarQube ruleset with overrides when adding or modifying code.

## Codebase conventions
- Ensure metadata gathering, tracker status management, and upload processing follow established async patterns:
- In unattended mode `meta['unattended']` is True; avoid prompts and use concurrent task firing where appropriate.
- Ensure no blocking calls within async functions; use non-blocking features to allow individual tasks to complete immediately, independent of other tasks, especially for I/O-bound operations.
- Minimize async overhead, and only use async where it provides clear benefits (e.g., concurrent network, CPU-bound or I/O calls).
- `meta` keys are widely reused across modules; Do not rename keys.
- `Prep.gather_prep()` sets `meta['uuid']` to the folder name when not provided and creates tmp/<uuid>/; new features should write artifacts there and reuse the same `meta['uuid']` value.
- Tracker status uses per-tracker deep copies of `meta` and merges selective fields under a lock in the trackerstatus module under src/; avoid writing shared `meta` outside the lock when adding new tracker flags.
- Tracker uploads are processed via `process_trackers` in the trackerhandle module under src/; ensure new tracker classes integrate with `TRACKER_SETUP` and expected status dicts.
- Use `console.print()` from the `console` object in the common module under src/ for user-facing messages instead of print().
- Use `cli_ui` module under src/ for prompts and progress bars instead of raw input() or other methods.
- Ensure any new arguments and config options are added to the documentation in docs/ and data/example-config.py.
