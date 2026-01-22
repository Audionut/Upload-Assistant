# Upload Assistant CLI arguments

This document describes the command-line arguments parsed in `src/args.py`.

## Help output

- `-h` shows a short/curated help (common options only).
- `--help` shows the full argparse help.

## Basic usage

```text
upload.py [path...] [options]
```

- `path` (positional): One or more paths to a file or directory.
  - Quoting is recommended (single or double quotes) especially when paths contain spaces.
  - The parser has a small recovery mechanism: if extra “unknown” tokens were provided and the joined `path` doesn’t exist, it will append those tokens into the path until it finds an existing path.

### Validation rules

- You must provide either at least one `path` OR `--site-upload`.
- If `--site-upload` is provided without a `path`, the parser injects a dummy path internally (so downstream code can continue).

## Modes / workflows

- `--queue QUEUE_NAME`: Process an entire folder (including files/subfolders) in a named queue.
- `-lq`, `--limit-queue N`: Limit the amount of sucessfull uploads processed when running the queue (default `0` unlimited).
- `-sc`, `--site-check`: Search trackers for suitable uploads and create a log file (no uploading).
- `-su`, `--site-upload TRACKER`: Process site searches and upload to a single tracker (tracker acronym is uppercased).
- `--unit3d`: Parse a text output file from `UNIT3D-Upload-Checker`.

## Screenshots / images

- `-s`, `--screens N`: Number of screenshots.
  - Default comes from config: `DEFAULT.screens`.
- `-mf`, `--manual_frames "1,250,500"`: Comma-separated frame numbers to use as screenshots.
  - Parsed into a list of integers; invalid format exits.
- `-comps`, `--comparison PATH`: Use comparison images from a folder.
- `-comps_index`, `--comparison_index N`: Which comparison index is the “main” images (required when using `--comparison`).
- `-menus`, `--disc-menus PATH`: Raw Disc only (Blu-ray/DVD). Folder containing disc menu screenshots (all images in folder are used).
- `-ih`, `--imghost HOST`: Select image host.
  - Choices: `imgbb`, `ptpimg`, `imgbox`, `pixhost`, `lensdump`, `ptscreens`, `onlyimage`, `dalexni`, `zipline`, `passtheimage`, `seedpool_cdn`.
- `-siu`, `--skip-imagehost-upload`: Skip uploading images to an image host.

## Description inputs

- `-pb`, `--desclink URL`: Custom description link (hastebin/pastebin).
- `-df`, `--descfile PATH`: Custom description file path (or filename in current working directory).
  - Stored as an absolute path.
- `-nfo`, `--nfo`: Use `.nfo` in directory for description.

## Metadata overrides (IDs, category/type/source, title shaping)

- These will override what Upload Assistant automatically decides. Recommend to only use overrides when needed to correct automatic detection.

### Category / type / source / resolution

- `-c`, `--category {movie,tv,fanres}`: Override the category.
- `-t`, `--type {disc,remux,encode,webdl,web-dl,webrip,hdtv,dvdrip}`: Override release type.
  - Stored as uppercase with `-` removed (e.g. `web-dl` → `WEBDL`).
- `--source {Blu-ray,BluRay,DVD,DVD5,DVD9,HDDVD,WEB,HDTV,UHDTV,LaserDisc,DCP}`: Override the source string.
- `-res`, `--resolution {2160p,1080p,1080i,720p,576p,576i,480p,480i,8640p,4320p,other}`: Override the resolution.

### External IDs

- `-tmdb`, `--tmdb TMDB_ID`: TMDb id; supports `movie/123` or `tv/123` forms.
  - Also accepts TMDb URLs and extracts the id.
  - Sets category based on `movie` vs `tv` when provided in that form.
- `-imdb`, `--imdb IMDB_ID`: IMDb id.
- `-mal`, `--mal MAL_ID`: MAL id.
- `-tvmaze`, `--tvmaze TVMAZE_ID`: TVMaze id.
- `-tvdb`, `--tvdb TVDB_ID`: TVDB id.

Note: if a manual TMDb or IMDb id is present in the incoming `meta` before parsing, the parser clears `tmdb_manual`, `tmdb_id`, `tmdb`, `imdb_id`, `imdb` in `meta` so CLI values take precedence cleanly.

### Tags / edition / language

- `-g`, `--tag [GROUP ...]`: Group tag.
  - Stored with a leading dash, e.g. `-g NTb` → `-NTb`.
- `-serv`, `--service [SERVICE ...]`: Streaming service.
- `-dist`, `--distributor [NAME ...]`: Disc distributor (Criterion, BFI, etc.).
- `-edition`, `--edition`, `--repack [TEXT ...]`: Edition/repack string.
- `-ol`, `--original-language LANG`: Set original audio language.
- `-oil`, `--only-if-languages [LANG ...]`: Require at least one language to upload (comma-separated list in a single string is supported).

### TV fields

- `-season`, `--season N`: Season (string).
  - Stored as `manual_season` in `meta`.
- `-episode`, `--episode N`: Episode (string).
  - Stored as `manual_episode` in `meta`.
- `-met`, `--manual-episode-title [TITLE ...]`: Manual episode title.
  - Passing the option with no words sets an empty string.
- `-daily`, `--daily YYYY-MM-DD`: Air date (parsed via `datetime.date.fromisoformat`).

### Title shaping toggles

- `--no-season`: Remove Season from title.
- `--no-year`: Remove Year from title.
- `--no-aka`: Remove AKA from title.
- `--no-dub`: Remove Dubbed from title.
- `--no-dual`: Remove Dual-Audio from title.
- `--no-tag`: Remove Group Tag from title.
- `--no-edition`: Remove Edition from title.
- `--dual-audio`: Add Dual-Audio to the title.

### Misc metadata flags

- `--not-anime`: Manually mark release as not anime. NOTE: invokes a quicker processing path for TV content when metadata ids (such as TMDB) are also provided.
- `-year`, `--year YYYY`: Override the year found.
- `-mc`, `--commentary`: Manually indicate commentary tracks are included.
- `-sfxs`, `--sfx-subtitles`: Manually indicate “SFX subtitles” are included.
- `-e`, `--extras`: Indicates extras are included (mainly Blu-ray discs).
- `-sort`, `--sorted-filelist`: Use the largest video file instead of the first video file found. NOTE: useful for anime content when additional content is present in a folder.
- `-kf`, `--keep-folder`: Keep the folder containing the single file (only when supplying a directory).
- `-knfo`, `--keep-nfo`: Keep nfo file where applicable for specific tracker/s. With single files, must be used in conjunction with `--keep-folder` above.
- `-reg`, `--region REGION`: Region for discs.

## Tracker-specific references (existing torrent ids/links)

These accept either an id or a full URL; when a URL is provided, the parser attempts to extract the id.
These will parse the torrent descriptions from supported sites, and grab metadata ids to assist with accuracy.

- `-ptp`, `--ptp ID_OR_URL`: PTP torrent id/permalink. (Extracts `torrentid` from query string.)
- `-blu`, `--blu ID_OR_URL`: BLU torrent id/link. (Extracts last path segment.)
- `-aither`, `--aither ID_OR_URL`: Aither torrent id/link. (Extracts last path segment.)
- `-lst`, `--lst ID_OR_URL`: LST torrent id/link. (Extracts last path segment.)
- `-oe`, `--oe ID_OR_URL`: OE torrent id/link. (Extracts last path segment.)
- `-tik`, `--tik ID_OR_URL`: TIK torrent id/link. (No URL parsing here; passes through.)
- `-hdb`, `--hdb ID_OR_URL`: HDB torrent id/link. (Extracts `id` from query string.)
- `-btn`, `--btn ID_OR_URL`: BTN torrent id/link. (Extracts `id` from query string.)
- `-bhd`, `--bhd ID_OR_URL`: BHD torrent id/link.
  - Tries to extract trailing numeric id from URLs like `/download/... .12345`.
- `-huno`, `--huno ID_OR_URL`: HUNO torrent id/link. (Extracts last path segment.)
- `-ulcx`, `--ulcx ID_OR_URL`: ULCX torrent id/link. (Extracts last path segment.)

Thise will use the specified hash to get tracker ids from qBitTorrent or rTorrent.
- `-th`, `--torrenthash HASH`: Torrent hash containing the torrent id in the comment field of the torrent.

## Upload selection / dupe / requests

- `-tk`, `--trackers LIST`: Upload only to these trackers (instead of a default torrent list from config).
  - Accepts comma-separated tracker acronyms (e.g. `--trackers blu,bhd`) and normalizes to uppercase.
- `-rtk`, `--trackers-remove LIST`: Remove only these trackers when processing default trackers.
- `-tpc`, `--trackers-pass N`: How many trackers must pass checks (dupe/banned-group/etc) for the uploading process to complete.
- `-req`, `--search_requests`: Search for matching requests on supported trackers.
- `-sat`, `--skip_auto_torrent`: Skip automated qBittorrent client torrent searching.
- `-onlyID`, `--onlyID`: Only grab meta ids from tracker (tmdb/imdb/etc), not description text. NOTE: description images are controlled with `keep_images` set in config.py.
- `-sdc`, `--skip-dupe-check`: Ignore dupes and upload anyway (skips dupe check). NOTE: know what you are doing!
- `-sda`, `--skip-dupe-asking`: Don’t prompt about any dupes that Upload Assistant finds; just treat these dupes as actual dupes.
- `-ddc`, `--double-dupe-check`: Run a second dupe-check pass on trackers that previously passed checks, immediately before uploading. NOTE: mainly useful when racing as a preventive dupe upload catch.
- `-dr`, `--draft`: Send to drafts (BHD, LST).
- `-mq`, `--modq`: Send to modQ. NOTE: only for suppported UNIT3D type sites.
- `-fl`, `--freeleech N`: Freeleech percentage (1–100). Default `0`. NOTE: accepts any numeric value, although UNIT3D defaults to only allowing filtering of specific percentages.

## Anonymity / seeding / streaming flags

- `-a`, `--anon`: Upload anonymously.
- `-ns`, `--no-seed`: Do not add the torrent to the client.
- `-st`, `--stream`: Stream optimized upload.
- `-webdv`, `--webdv`: Indicates a Dolby Vision layer converted using `dovi_tool` (HYBRID).
- `-hc`, `--hardcoded-subs`: Contains hardcoded subs.
  - Note: stored in `meta` under key `hardcoded-subs` (with a hyphen).
- `-pr`, `--personalrelease`: Personal release.

## Torrent creation / hashing options

- `-mps`, `--max-piece-size {1,2,4,8,16,32,64,128}`: Max piece size in MiB.
- `-nh`, `--nohash`: Don’t hash `.torrent`.
- `-rh`, `--rehash`: Rehash `.torrent` even if it was not needed.
- `-mkbrr`, `--mkbrr`: Use mkbrr for torrent hashing.
- `-entropy`, `--entropy N`: Use entropy in created torrents (32 or 64 bits).
- `-rt`, `--randomized N`: Create N extra torrents with random infohash (default `0`).
- `--infohash HASH`: V1 info hash to use as the base.
- `-frc`, `--force-recheck`: (qBittorrent only with auto torrent searching) Force recheck torrent before uploading. NOTE: will find the best seeded torrent file from a supported site, for the related content, and force a recheck before uploading.

## Torrent client integration

- `-client`, `--client NAME`: Use this torrent client instead of default.
- `-qbt`, `--qbit-tag TAG`: Add to qBittorrent with this tag.
- `-qbc`, `--qbit-cat CATEGORY`: Add to qBittorrent with this category.
- `-rtl`, `--rtorrent-label LABEL`: Add to rTorrent with this label.

## Cleanup / temp directory

- `-dm`, `--delete-meta`: Delete only `meta.json` from tmp directory.
- `-dtmp`, `--delete-tmp`: Delete tmp directory for the working file/folder.
- `-cleanup`, `--cleanup`: Clean up the entire tmp directory.

## Debugging / output

- `-debug`, `--debug`: Debug mode; runs through motions without uploading.
- `-ffdebug`, `--ffdebug`: Show debugging info from ffmpeg while taking screenshots.
- `-uptimer`, `--upload-timer`: Print time to upload to each site.
- `-stn`, `--show-tracker-names`: Show tracker-specific release names before confirmation prompt. Useful to preview how your release name will appear on each target tracker.

## VapourSynth screenshots

- `-vs`, `--vapoursynth`: Use VapourSynth for screenshots (requires VS install). NOTE: probably broken.

## Emby support

- `-emby`, `--emby`: Create an Emby-compliant NFO file and optionally symlink the content.
- `-emby_cat`, `--emby_cat {movie|tv}`: Set the expected category for Emby.
- `-emby_debug`, `--emby_debug`: Specifc debugging mode. NOT recommended.

## SPD-only

- `-ch`, `--channel ID_OR_TAG`: SPD: Channel id number or tag (without `@`).

## Unattended (hidden)

These are suppressed from help output:

- `-ua`, `--unattended`: Doesn't prompt for anything. Will default to skipping a tracker related upload, instead of prompting a question. Use only if you know what you are doing, and are familar with any Upload Assistant quirks.
- `-uac`, `--unattended_confirm`: Requires `-ua`. Unattended mode with some prompting.
