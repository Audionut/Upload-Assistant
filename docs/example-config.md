# Upload Assistant `example-config.py` options

This document explains the configuration options found in `data/example-config.py`.

Upload Assistant loads configuration from `data/config.py`.

## How to use

- Generate a config interactively:
  - Run `python config-generator.py` from the repo root.
- Or create your config manually:
  - Copy `data/example-config.py` to `data/config.py`
  - Edit `data/config.py` with your own values

## Config file shape

The config is a Python dict named `config` with these top-level sections:

- `DEFAULT`: global behavior, metadata, screenshots, tool settings.
- `IMAGES`: static icon URLs used in some descriptions.
- `TRACKERS`: which trackers to upload to + per-tracker credentials/options.
- `TORRENT_CLIENTS`: qBittorrent/ruTorrent/etc client configuration.
- `DISCORD`: optional Discord bot integration.

Notes:
- Many numeric values are stored as strings (e.g. `"4"`, `"14000"`). Keep the same type unless you know a specific option is numeric.
- Tracker lists are usually a comma-separated string (e.g. `"MTV, BHD"`).

## How Upload Assistant uses this config (implementation context)

Upload Assistant is structured around a runtime `meta` dict.

At a high level:

1. `data/config.py` is imported and read across the codebase.
2. `src/prep.py` builds and normalizes `meta` from the input path + CLI args + `config` defaults.
3. Tracker metadata is fetched via `src/get_tracker_data.py` / `src/trackermeta.py` and individual tracker modules under `src/trackers/`.
4. Screenshots are captured/optimized via `src/takescreens.py`.
5. Descriptions are assembled via `src/get_desc.py` (plus tracker-specific formatting overrides).
6. Torrents are created via `src/torrentcreate.py` and optionally injected into your client via `src/clients.py`.

Important gotchas:

- Some options are read at module import time (notably in `src/takescreens.py`). If you edit `data/config.py` while Upload Assistant is running, you may need to restart the process for changes to take effect.
- Many `DEFAULT` values are copied into `meta` during preparation, and later code reads `meta` rather than reading `config` again.
- Several settings can be overridden by CLI flags (or by `user-args.json` overrides when enabled).

---

## `DEFAULT` section

### Update notifications
- `update_notification` (bool): Print a notice when an update is available.
- `verbose_notification` (bool): Print the changelog when an update is available.

### Metadata APIs
- `tmdb_api` (str, required): TMDb API key. Get it from https://www.themoviedb.org/settings/api
- `btn_api` (str): BTN API key (used to fetch BTN details).

### Image host selection (priority list)
Order matters: `img_host_1` is primary, later hosts are fallbacks.

- `img_host_1`..`img_host_5` (str): Image host names. Valid examples include `imgbb`, `ptpimg`, `imgbox`, `pixhost`, `lensdump`, `ptscreens`, `onlyimage`, `dalexni`, `zipline`, `passtheimage`, `seedpool_cdn`, `utppm`.

### Image host credentials
- `imgbb_api` (str): API key for imgbb.
- `ptpimg_api` (str): API key for ptpimg.
- `lensdump_api` (str): API key for lensdump.
- `ptscreens_api` (str): API key for ptscreens.
- `onlyimage_api` (str): API key for onlyimage.
- `dalexni_api` (str): API key for dalexni.
- `passtheima_ge_api` (str): API key for passtheimage.
- `zipline_url` (str): Base URL for a Zipline instance.
- `zipline_api_key` (str): Zipline API key.
- `seedpool_cdn_api` (str): Seedpool CDN API key.

### Description extras
- `add_logo` (bool): Add a TMDb logo image at the top of the description.
- `logo_size` (str): Logo size (example default: `"300"`).
- `logo_language` (str): ISO 639-1 language code for logo selection (fallback to English).
- `episode_overview` (bool): Add episode overview text to description.

Implementation notes:
- These are primarily consumed by the description builders (for many trackers via `src/get_desc.py`, and for some trackers via tracker-specific modules in `src/trackers/`).
- `logo_language` influences which TMDb logo is requested; if not available, English is used.
- `add_logo` is a [per-tracker overridable setting](#tracker-overridable-settings).
- `episode_overview` is a [per-tracker overridable setting](#tracker-overridable-settings).

### Screenshots
- `screens` (str): Number of screenshots to capture.
- `cutoff_screens` (str): If at least this many screenshots already exist (e.g. pulled from a description), skip capturing/uploading more.
- `thumbnail_size` (str): Thumbnail width for hosts that support `[img=WIDTH]` (default `"350"`).
- `screens_per_row` (str): Screenshots per row in description (only for some trackers).
- `frame_overlay` (bool): Overlay frame number/type and “Tonemapped” (if applicable) on screenshots.
- `overlay_text_size` (str): Overlay text size (scales with resolution).

Implementation notes:
- Screenshot capture/reuse logic is in `src/takescreens.py`. In particular, `cutoff_screens` is used to decide whether existing images in `meta['image_list']` are “enough” to skip taking new screenshots.
- `thumbnail_size` and `screens_per_row` affect how screenshot BBCode is rendered in descriptions (see `src/get_desc.py`).
- `frame_overlay` triggers extra probing work to collect frame information (slower), and can affect which tonemapping pipeline is used.

### HDR tonemapping
- `tone_map` (bool): Tonemap HDR/DV+HDR screenshots.
- `use_libplacebo` (bool): Use libplacebo-based tonemapping when available.
- `ffmpeg_is_good` (bool): Skip compatibility check (assume your ffmpeg supports libplacebo).
- `ffmpeg_warmup` (bool): Skip “warming up” libplacebo.
- `ffmpeg_compression` (str): ffmpeg screenshot compression level (`0`–`9`).
- `algorithm` (str): Tonemap algorithm (e.g. `mobius`).
- `desat` (str): Tonemap desaturation value.
- `tonemapped_header` (str): BBCode header inserted above screenshots when tonemapping occurred.

Implementation notes:
- Tonemapping decisions happen in `src/takescreens.py` based on `meta['hdr']` and `tone_map`.
- `algorithm`/`desat` are used for the non-libplacebo tonemap filter path.
- `tonemapped_header` is inserted by `src/get_desc.py` (and is a [per-tracker overridable setting](#tracker-overridable-settings)).

### Performance / multiprocessing
- `process_limit` (str): Max number of screenshot optimization processes.
- `threads` (str): Thread limit per process during image optimization.
- `ffmpeg_limit` (bool): Limit CPU usage when running ffmpeg.

Implementation notes:
- These are most visible during screenshot capture/optimization (`src/takescreens.py`). Lower them on shared/limited systems.

### Packs (season packs / multi-disc)
- `multiScreens` (str): Screenshots per disc/episode when uploading packs to supported sites.
- `pack_thumb_size` (str): Thumbnail width for pack screenshots.
- `charLimit` (str): UNIT3D season-pack description character limit cutoff.
- `fileLimit` (str): Files to include before grouping additional files into spoiler blocks.
- `processLimit` (str): Absolute limit on processed files in packs.

Implementation notes:
- Pack description assembly and character limits are enforced in `src/get_desc.py`.
- `charLimit` exists because some UNIT3D sites have strict description length limits.

### Description formatting hooks
These can be [overridden per-tracker](#tracker-overridable-settings) by adding the same key inside that tracker’s config block.

- `custom_description_header` (str): BBCode header added at top of description section.
- `screenshot_header` (str): BBCode header added above screenshots.
- `disc_menu_header` (str): BBCode header added above disc menu screenshots (discs only).
- `custom_signature` (str): BBCode signature appended at bottom of description.

### Torrent client integration
- `default_torrent_client` (str): Name of the client config to use (matches a key under `TORRENT_CLIENTS`, e.g. `"qbittorrent"`).
- `skip_auto_torrent` (bool): Skip automated torrent searching in your qBitTorrent client.

Implementation notes:
- Client injection/search behavior is centralized in `src/clients.py`.
- `skip_auto_torrent` affects whether Upload Assistant tries to find matching torrents in your client for reuse/dupe checking.

### UX / safety toggles
- `sfx_on_prompt` (bool): Play a bell sound effect when asking for confirmation.
- `tracker_pass_checks` (str): Minimum number of trackers that must pass checks to continue upload.
- `use_largest_playlist` (bool): Always use the largest Blu-ray playlist without prompting.
- `keep_images` (bool): If false, do not pull images from tracker descriptions.
- `only_id` (bool): Only grab IDs from trackers (skip description parsing).

Implementation notes:
- `tracker_pass_checks` is used to determine how many trackers must pass early validation before continuing (see `upload.py`).
- `only_id` and `keep_images` influence how much another tracker description is scraped/merged. The optons are independent.

### Sonarr / Radarr integration
- `use_sonarr` (bool): Enable Sonarr searching.
- `sonarr_url` (str): Sonarr base URL.
- `sonarr_api_key` (str): Sonarr API key.
- `sonarr_url_1` / `sonarr_api_key_1` (str): Optional second Sonarr instance.

- `use_radarr` (bool): Enable Radarr searching.
- `radarr_url` (str): Radarr base URL.
- `radarr_api_key` (str): Radarr API key.
- `radarr_url_1` / `radarr_api_key_1` (str): Optional second Radarr instance.

### Torrent creation
- `mkbrr` (bool): Use mkbrr for torrent creation.
- `mkbrr_threads` (str): Worker thread count for hashing ("0" = auto).

Implementation notes:
- `mkbrr`/`mkbrr_threads` are copied into `meta` during prep (`src/prep.py`) and applied during torrent creation (`src/torrentcreate.py`).
- If mkbrr fails, Upload Assistant falls back to the internal `torf` torrent builder.

### User overrides
- `user_overrides` (bool): Use argument overrides from `data/templates/user-args.json`.

Implementation notes:
- When enabled, overrides are loaded and applied in `src/apply_overrides.py`.
- Overrides are matched primarily by TMDb ID (and optionally by “other IDs” like IMDb/TVDb), then translated into the same internal `meta` flags used by CLI args.
- Read the notes at the top of the example overrides.

### Metadata enrichment / matching
- `ping_unit3d` (bool): Try to infer region/distributor IDs from existing torrents and Unit3D sites.
- `get_bluray_info` (bool): Fetch disc metadata from bluray.com (requires IMDb ID).
- `add_bluray_link` (bool): Add bluray.com link to description (requires `get_bluray_info`).
- `use_bluray_images` (bool): Add bluray.com cover/back/slip images to description (requires `get_bluray_info`).
- `bluray_image_size` (str): Width for bluray.com cover images.
- `bluray_score` (float): Minimum score to consider bluray.com release a match.
- `bluray_single_score` (float): Relaxed score threshold if only one bluray.com release exists.

Implementation notes:
- `ping_unit3d` is used for BDMV discs in `src/prep.py` and calls `ping_unit3d` in `src/get_tracker_data.py` to try and fill in missing region/distributor details.
- bluray.com integration is orchestrated from `src/prep.py` and implemented in `src/bluray_com.py`; `bluray_score` thresholds decide whether an auto-match is accepted.

### Logging / output
- `keep_meta` (bool): Do not delete existing `meta.json` before running (NOT recommended).
- `show_upload_duration` (bool): Print how long each tracker upload took.
- `print_tracker_messages` (bool): Print tracker API messages returned during upload.
- `print_tracker_links` (bool): Print direct torrent links after upload.
- `inject_delay` (int): Delay (in seconds) before injecting the torrent to allow the tracker to register the hash and avoid 'unregistered torrent' errors.

Implementation notes:
- `inject_delay` is a [per-tracker overridable setting](#tracker-overridable-settings).

### Emby linking
- `emby_dir` (str | None): Directory for Emby movie linking (enables linking when set).
- `emby_tv_dir` (str | None): Directory for Emby TV linking.

Implementation notes:
- Emby NFO/link behavior is implemented in `src/nfo_link.py`.
- These options are only used when Emby mode is enabled (via CLI flags); setting these paths alone does not automatically enable Emby mode.

### Requests / predb / cross-seeding
- `search_requests` (bool): Search for matching requests on supported trackers.
- `check_predb` (bool): Also search predb for scene releases.
- `prefer_max_16_torrent` (bool): Prefer torrents with piece size <= 16 MiB when searching existing torrents.
- `cross_seeding` (bool): Enable cross-seed suitable torrents found during dupe checking.
- `cross_seed_check_everything` (bool): Cross-seed check all configured trackers even if not selected.

Implementation notes:
- Request searching is implemented per-tracker (for example, several tracker modules check `search_requests` before running request queries).
- `check_predb` is used by the scene-name logic (`src/is_scene.py`) as a fallback when SRRDB does not find a match.
- `prefer_max_16_torrent` affects how existing torrents are chosen from your client (`src/clients.py`).

---

## `IMAGES` section

Static icon images used in some description layouts (notably AR DB link icons):
- `imdb_75`, `tmdb_75`, `tvdb_75`, `tvmaze_75`, `mal_75`

---

## `TRACKERS` section

### `default_trackers`
A comma-separated list of tracker acronyms to upload to by default.

Example:

```python
"default_trackers": "MTV, BHD, AITHER"
```

### Per-tracker blocks
Each tracker acronym (e.g. `"AITHER"`, `"BLU"`) contains a dict of settings.

Common keys you will see:
- `link_dir_name` (str): Custom folder name used when linking content (instead of the acronym).
- `useAPI` (bool): Enable tracker API usage for automatic ID searching/description parsing (some trackers only).
- `api_key` (str): Tracker API key (UNIT3D-style trackers commonly use this).
- `announce_url` (str): Tracker announce URL (often contains `<PASSKEY>` placeholders).
- `anon` (bool): Upload anonymously when supported.
- `modq` (bool): Send uploads to moderator queue when supported.
- `draft` / `draft_default` (bool/str): Save to drafts when supported.

Implementation notes:
- If the exmaple-config does not contain the option for a tracker, then the tracker does not support that specific config option.

Some trackers authenticate via cookies instead of an API key.
If comments in `example-config.py` mention cookies, they are typically expected as a Netscape cookie file in:

- `data/cookies/<TRACKER>.txt`

### `MANUAL`
- `filebrowser` (str): If set, use your own Filebrowser link instead of uploading a file to uguu.se for manual uploads.

---

## `TORRENT_CLIENTS` section

This section defines one or more torrent clients. The name of each client block is referenced elsewhere (for example by `DEFAULT.default_torrent_client`).
- "qbittorrent" is an example of a torrent client name.
- IMPORTANT: do not change the torrent_client attribute, for example `"torrent_client": "rtorrent",` or `"torrent_client": "qbit",`

Security note: these settings can allow the app (and the Web UI) to interact with your torrent client. Do not expose your client’s Web UI to the public internet.

### qBittorrent (`torrent_client: "qbit"`)
Typical keys:
- `qui_proxy_url` (str): Optional. [QUI reverse proxy](https://getqui.com/docs/features/reverse-proxy) URL for qBittorrent. Create a **Client Proxy API Key** in QUI (**Settings → Client Proxy Keys**): name the client (e.g. "Upload Assistant"), choose the qBittorrent instance, then copy the generated proxy URL. Use the **full** URL, e.g. `http://localhost:7476/proxy/<client-api-key>`. The instance is fixed by the key you create. When set, `qbit_url` / `qbit_port` / `qbit_user` / `qbit_pass` are not used.
- `enable_search` (bool): Search client for existing torrents to reuse hashes. NOTE: independant of auto_torrent_searching
- `qbit_url` / `qbit_port` (str): Web UI host/port.
- `qbit_user` / `qbit_pass` (str): Credentials.
- `super_seed_trackers` (list[str]): Trackers to enable super-seeding on.
- `use_tracker_as_tag` (bool): Tag torrents with tracker acronym.
- `qbit_tag` / `qbit_cat` (str): Tag/category for uploaded torrents.
- `qbit_cross_tag` / `qbit_cross_cat` (str): Tag/category for cross-seed torrents.
- `content_layout` (str): Layout hint (example default `"Original"`).
- `linking` (str): `"symlink"`, `"hardlink"`, or empty to disable.
- `allow_fallback` (bool): Fallback to original path injection if linking fails.
- `linked_folder` (list[str]): Destination folder(s) for linked content. This is the top level directory that will contain the linked content.
- `local_path` / `remote_path` (list[str]): Local/remote path mapping (docker/seedbox), case-sensitive. Local path is how UA sees the content, remote path is how the client sees the content.
- `torrent_storage_dir` (str, optional): Only needed if API searching doesn’t work. Falls back to search the client storage directory for existing torrents.

### ruTorrent / rTorrent
- `rtorrent_url` (str): ruTorrent HTTPRPC endpoint URL (often includes credentials).
- `torrent_storage_dir` (str): Session folder path.
- `rtorrent_label` (str): Optional label.
- `linking`, `allow_fallback`, `linked_folder`, `local_path`, `remote_path`: similar meaning as qBittorrent.

### Deluge
- `deluge_url`, `deluge_port`, `deluge_user`, `deluge_pass`
- `torrent_storage_dir`
- `local_path` / `remote_path`

### Transmission
- `transmission_protocol` (str): `http` or `https`
- `transmission_username` / `transmission_password`
- `transmission_host` / `transmission_port`
- `transmission_path` (str): RPC path (default example: `/transmission/rpc`)
- `torrent_storage_dir`, `transmission_label`
- `local_path` / `remote_path`


### Watch folder
- `watch_folder` (str): Path to a watch folder where `.torrent` files should be dropped.

---

## `DISCORD` section

Enables an optional Discord bot.

- `use_discord` (bool): Enable Discord bot.
- `only_unattended` (bool): Only run the bot in unattended mode.
- `send_upload_links` (bool): Send tracker torrent URLs.
- `discord_bot_token` (str): Bot token.
- `discord_channel_id` (str): Target channel.
- `discord_bot_description` (str): Bot description.
- `command_prefix` (str): Command prefix (example `!`).
- See https://github.com/Audionut/Upload-Assistant/wiki/Discord-Bot

### Tracker overridable settings
Tracker overridable settings are settings that you can add inside each tracker config dictionary; these settings override the values inside the DEFAULT config. In order for this to work, you must edit the config file, locate the tracker by name, and add your custom value.

Example:
```python
config = {
    "DEFAULT": {
        "custom_signature": "This is my signature for ALL trackers",
    },
    "TRACKERS": {
        "AITHER": {
            "custom_signature": "This is my signature ONLY for AITHER",
        },
    },
}
