# Uploading to CZTeam with Upload Assistant

CZTeam (czteam.me) is a Romanian private tracker. This fork of
Upload-Assistant adds CZTeam support via a new tracker plugin (`CZT`),
which slots in alongside every other tracker UA already supports — so
you can include CZTeam in any multi-tracker upload.

This guide walks through setup and your first upload.

---

## 1. Prerequisites

You need:

- **A CZTeam account** in good standing. Upload is open to all logged-in
  users (you don't need uploader class).
- **The CZT fork of Upload-Assistant.** If you have an existing UA install,
  switch its remote; otherwise clone fresh.
- **Browser-exported cookies for czteam.me.** CZTeam protects the login
  form with Cloudflare Turnstile, so UA cannot log in for you — you log
  in once in a real browser, export the cookies, and hand them to UA.
  After that everything runs unattended until the cookies expire.

The rest of the UA prerequisites (Python ≥ 3.9, ffmpeg, mediainfo, TMDb
key, image host config) are unchanged — see the project README.

## 2. Install the fork

```sh
git clone -b czteam https://github.com/<you>/Upload-Assistant.git
cd Upload-Assistant
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp data/example-config.py data/config.py
```

If you already had UA installed, add this fork as a remote and check out
the `czteam` branch instead:

```sh
cd Upload-Assistant
git remote add czteam https://github.com/<you>/Upload-Assistant.git
git fetch czteam
git checkout -b czteam czteam/czteam
```

## 3. Configure `data/config.py`

Find the `CZT` block inside `TRACKERS` and fill it in:

```python
"CZT": {
    # Optional sym/hard-link subdirectory name.
    "link_dir_name": "",
    "username": "your_czteam_username",
    "password": "your_czteam_password",  # used as a fallback; cookies are preferred
    "totp": "",                           # leave empty unless you have 2FA enabled
    # CZTeam whitelists ONLY the bare announce URL on upload — the
    # passkey gets injected by download.php when the .torrent is fetched.
    # Don't put your passkey in here.
    "announce_url": "https://tracker.czteam.me/announce",
    "anon": False,
    "base_url": "https://czteam.me",
},
```

Then add `CZT` to `default_trackers` if you want it picked up by default:

```python
"default_trackers": "BLU, AITHER, HUNO, CZT",
```

## 4. Export your cookies (one-time per ~30 days)

CZTeam's login page uses Cloudflare Turnstile, which a script can't
solve. UA's plugin works around this by reading cookies a real browser
already obtained, the same way UA already handles FileList, HDB, and
other login-captcha trackers.

**Steps:**

1. Log in to https://czteam.me in your browser. Solve the Turnstile
   widget. Make sure "Remember me" is checked so the cookies persist.
2. Install a "Cookies.txt" extension that exports cookies in JSON form:
    - Chrome / Edge: *Get cookies.txt LOCALLY* — pick "JSON" output
    - Firefox: *cookies.txt one click* — choose JSON
    - Any tool that produces an object keyed by cookie name will work.
3. Visit czteam.me in the active tab, click the extension, **Export →
   JSON**. Save the file as:

   ```
   <Upload-Assistant>/data/cookies/CZT.json
   ```

   The file should look like (the three cookies CZTeam uses):

   ```json
   {
     "uid":   {"value": "276913"},
     "pass":  {"value": "..."},
     "hashv": {"value": "..."}
   }
   ```

   If your extension exports a flat object `{"uid": "276913", ...}`,
   wrap each value in `{"value": "..."}` — that's the shape UA's
   `CookieValidator` expects.

4. (Optional but recommended) Restrict the file: `chmod 600
   data/cookies/CZT.json`. It contains a credential equivalent to your
   password until it expires.

You'll re-export when UA reports "cookie validation failed" — typically
once a month or after a password change.

## 5. First upload — dry run

Always start with `--debug` so UA prints the request shape without
actually posting it:

```sh
venv/bin/python upload.py \
    "/path/to/Some.Release.2024.1080p.WEB-DL.H.264-GROUP.mkv" \
    --trackers CZT \
    --debug
```

You should see something like:

```
[CZT] Validating credentials … logged in
[CZT] https://czteam.me/takeupload.php
[CZT] {
  'name':       'Some.Release.2024.1080p.WEB-DL.H.264-GROUP',
  'type':       '29',
  'descr':      '<MediaInfo paste …>',
  'user_descr': '<your BBCode body …>',
  'resolution': '1080p',
  'codec':      'H.264',
  'container':  'MKV',
  'source':     'WEB-DL',
  'url':        'https://www.imdb.com/title/tt1234567/',
  …
}
Debug mode enabled, not uploading.
```

Sanity-check the values. If something looks off (wrong category, bad
codec mapping, etc.), see the troubleshooting section below.

## 6. Real upload

Drop `--debug` to go live:

```sh
venv/bin/python upload.py \
    "/path/to/Some.Release.2024.1080p.WEB-DL.H.264-GROUP.mkv" \
    --trackers CZT
```

UA will:

1. Generate mediainfo + screenshots + BBCode description (using its
   normal pipeline).
2. Build a fresh `.torrent` with the bare announce URL.
3. Fetch the upload form, mint a CSRF token, and POST to
   `https://czteam.me/takeupload.php`.
4. Parse `details.php?id=N` from the response — that's your new
   torrent.
5. Re-download the .torrent via `download.php?torrent=N` (with your
   passkey baked into the announce URL) and hand it to your client for
   fast-resume cross-seed.

The console will print:

```
[ok] CZT upload: https://czteam.me/details.php?id=219234
```

## 7. Multi-tracker uploads

This is where UA earns its keep. With `default_trackers = "BLU, AITHER,
HUNO, CZT"`, a single command uploads to all four:

```sh
venv/bin/python upload.py "/path/to/Release.mkv"
```

Each tracker's plugin runs concurrently; CZT uses its own cookies and
csrf_token mint, independent of the others.

---

## Category mapping

The plugin maps UA's `meta` to CZTeam categories like this:

| UA category | UA hints | CZTeam id | Name |
|---|---|---:|---|
| MOVIE | `is_disc=BDMV`, RO audio/sub | 36 | Full BluRay-RO |
| MOVIE | `is_disc=BDMV` | 29 | Movies/HD |
| MOVIE | `is_disc=DVD`, RO audio/sub | 28 | Movies/DVD-RO |
| MOVIE | `is_disc=DVD` | 20 | Movies/DVD-R |
| MOVIE | WEB-DL/WEBRip/HDTV/ENCODE/REMUX 720p+ + RO | 33 | Movies/HDTV-RO |
| MOVIE | WEB-DL/WEBRip/HDTV/ENCODE/REMUX 720p+ | 29 | Movies/HD |
| MOVIE | XviD or SD | 19 | Movies/XviD |
| MOVIE | (default) | 29 | Movies/HD |
| TV | 720p+ + RO | 34 | TvEps/HD-RO |
| TV | 720p+ | 5 | TvEps/HD |
| TV | (default) | 7 | TvEps |
| Anime | (any) | 23 | Anime |

Romanian audio/subs are auto-detected from `mediainfo` (`Language=ro`,
`Language=rum`, `Language=ron`) and from BluRay BDInfo's subtitle/audio
language lists.

If the plugin picks the wrong bucket, edit `get_category_id()` in
`src/trackers/CZT.py` and PR upstream (this fork).

---

## Troubleshooting

### `Captcha check failed (HTTP 403)` on validate_credentials

UA tried to log in (no cookie file present, or the existing one is
stale) and hit Turnstile. Re-export cookies from your browser as
described in step 4.

### `Invalid announce URL` on upload

Your `announce_url` in `data/config.py` has a passkey or extra path in
it. CZTeam whitelists only `https://tracker.czteam.me/announce`. The
passkey is injected by `download.php` when you fetch the .torrent
back — you never put it in the upload-side announce URL.

### `This torrent has already been uploaded (id N)`

CZTeam dedupes by info_hash. Someone (often you, on a previous attempt)
already uploaded the same release. Pull the existing one via
`download.php?torrent=N` if you want to seed it.

### `Category is not valid`

The plugin produced a `type` field that doesn't match a live category
on CZTeam. Either the category was retired, or `get_category_id()`
returned something odd. Run with `--debug` and check the `'type'` value
against the table above; file an issue with the meta dump.

### `Captcha check failed` returned but I'm logged in

That's actually CSRF, not Turnstile — they share the 403 status. The
plugin re-fetches `/upload.php` before every upload to get a fresh
`csrf_token`. If you see this repeatedly, your `PHPSESSID` cookie is
not being sent. Make sure the export included `PHPSESSID` (some
extensions skip session cookies by default).

### Upload "succeeded" but the torrent isn't in my profile

CZTeam torrents only become **visible** once at least one seeder is
connected to the tracker. Open your client, add the re-issued
`.torrent` UA dropped (it landed in your usual UA tmp dir), and
announce. The torrent appears in browse within seconds.

---

## How the plugin works (for the curious)

The plugin is `src/trackers/CZT.py` (~290 lines). It does **not** use
the UNIT3D base class — CZTeam isn't a UNIT3D site. It's modeled on
`FL.py` (FileList), which is the closest cousin: same BTSource/NVTracker
lineage, same form-POST-to-takeupload.php upload mechanic.

End-to-end flow:

1. **`validate_credentials`** — checks `data/cookies/CZT.json` exists
   and that hitting `/index.php` with those cookies returns a logged-in
   page. If not, falls back to `login()` (which will fail on Turnstile —
   that's the user's cue to re-export).
2. **`upload`** —
    a. `COMMON.create_torrent_for_upload()` writes a fresh
       `[CZT].torrent` with `announce = https://tracker.czteam.me/announce`
       and `info.source = CzT`.
    b. GET `/upload.php` — parse `<input name="csrf_token" value="…">`.
    c. POST multipart `/takeupload.php` with `file`, `name`, `type`,
       `descr` (MediaInfo paste), `user_descr` (BBCode), `url` (IMDB
       URL — server extracts the tt-id), `resolution`, `codec`,
       `container`, `source`, `csrf_token`.
    d. Regex `details\.php\?id=(\d+)` on the response. Surface
       `<p style="color:red">…</p>` errors verbatim if the upload was
       rejected.
3. **`download_new_torrent`** — GET `/download.php?torrent=N`, write
   the result to `[CZT].torrent` for client injection. The .torrent
   that comes back has the user's passkey baked into the announce URL.

The plugin is registered in `src/trackersetup.py` (in
`tracker_class_map` and `http_trackers`).
