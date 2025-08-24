# Audionut's Upload Assistant

[![Docker Build](https://github.com/Audionut/Upload-Assistant/actions/workflows/docker-image.yml/badge.svg?branch=master)](https://github.com/Audionut/Upload-Assistant/actions/workflows/docker-image.yml)
[![Test run (Master Branch)](https://img.shields.io/github/actions/workflow/status/Audionut/Upload-Assistant/test-run.yaml?branch=master\&label=Master%20Tests)](https://github.com/Audionut/Upload-Assistant/actions/workflows/test-run.yaml?query=branch%3Amaster)
[![Test run (5.1.5.2)](https://img.shields.io/github/actions/workflow/status/Audionut/Upload-Assistant/test-run.yaml?branch=5.1.5.2\&label=Tests%20\(5.1.5.2\))](https://github.com/Audionut/Upload-Assistant/actions/workflows/test-run.yaml?query=branch%3A5.1.5.2)

**Discord support:** [Join here](https://discord.gg/QHHAZu7e2A)

---

## About

**Upload Assistant** is a simple but powerful tool to automate the tedious parts of uploading.

This project is a fork of [L4G’s original Upload Assistant](https://github.com/L4GSP1KE/Upload-Assistant). Immense thanks to him (and contributors) for laying the foundation—this fork exists because of that work.

What started as a handful of PRs turned into **full-time active development**. While other forks mostly rebrand the tool, this repo continues to evolve with new features, fixes, and community input. If you want the real deal, you’re in the right place.

---

## Features

* Generates and parses **MediaInfo/BDInfo**.
* Creates and uploads **screenshots** (HDR tone-mapping supported).
* Uses **srrdb** to fix scene names.
* Pulls descriptions from **PTP / BLU / Aither / LST / OE / BHD**.
* Can re-use existing screenshots from descriptions.
* Fetches identifiers from **TMDb / IMDb / MAL / TVDB / TVMaze**.
* Converts absolute → season/episode numbering (anime + non-anime with TVDB).
* Generates clean `.torrent` files (no junk folders/nfos).
* Can re-use existing torrents (qBittorrent v5+ integration).
* Auto-formats names using MediaInfo/BDInfo + TMDb/IMDb (site rules compliant).
* Checks for existing releases before upload.
* Adds torrents to client with **instant seeding** (rtorrent/qBittorrent/deluge/watch folders).
* Works with `.mkv`, `.mp4`, Blu-ray, DVD, HD-DVD.
* Designed for **minimal input**.

---

## Supported Sites

| Name                     | Acronym | Name            | Acronym |
| ------------------------ | ------- | --------------- | ------- |
| Aither                   | AITHER  | Alpharatio      | AR      |
| Amigos Share Club        | ASC     | AnimeLovers     | AL      |
| Anthelion                | ANT     | AsianCinema     | ACM     |
| Beyond-HD                | BHD     | BitHDTV         | BHDTV   |
| BrasilJapão-Share        | BJS     | Blutopia        | BLU     |
| BrasilTracker            | BT      | CapybaraBR      | CBR     |
| Cinematik                | TIK     | DarkPeers       | DP      |
| DigitalCore              | DC      | FearNoPeer      | FNP     |
| FileList                 | FL      | Friki           | FRIKI   |
| hawke-uno                | HUNO    | HDBits          | HDB     |
| HD-Space                 | HDS     | HD-Torrents     | HDT     |
| HomieHelpDesk            | HHD     | ItaTorrents     | ITT     |
| Last Digital Underground | LDU     | Lat-Team        | LT      |
| Locadora                 | LCD     | LST             | LST     |
| MoreThanTV               | MTV     | Nebulance       | NBL     |
| OldToonsWorld            | OTW     | OnlyEncodes+    | OE      |
| PassThePopcorn           | PTP     | Polish Torrent  | PTT     |
| Portugas                 | PT      | PTerClub        | PTER    |
| PrivateHD                | PHD     | Racing4Everyone | R4E     |
| Rastastugan              | RAS     | ReelFLiX        | RF      |
| RetroFlix                | RTF     | Samaritano      | SAM     |
| seedpool                 | SP      | ShareIsland     | SHRI    |
| SkipTheCommericals       | STC     | SpeedApp        | SPD     |
| Swarmazon                | SN      | Toca Share      | TOCA    |
| TorrentHR                | THR     | TorrentLeech    | TL      |
| ToTheGlory               | TTG     | TVChaosUK       | TVC     |
| UHDShare                 | UHD     | ULCX            | ULCX    |
| UTOPIA                   | UTP     | YOiNKED         | YOINK   |
| YUSCENE                  | YUS     |                 |         |

---

## Setup

**Requirements:**

* Python **3.9+** with `pip`
* [Mono](https://www.mono-project.com/) (Linux only, for BDInfo)
* [MediaInfo](https://mediaarea.net/en/MediaInfo)
* [ffmpeg](https://ffmpeg.org/) (must be in PATH on Windows)

**Installation:**

```bash
# Clone the repo
git clone https://github.com/Audionut/Upload-Assistant.git
cd Upload-Assistant

# Fetch release tags
git fetch --all --tags

# Checkout a specific release
git checkout tags/v5.0.0

# Install dependencies
pip3 install --user -U -r requirements.txt
```

If you prefer isolation (or hit “externally managed environment” errors):

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Configuration:**

```bash
python3 config-generator.py
```

*or* copy `data/example-config.py` → `data/config.py` and edit manually.

More details in the [Wiki](https://github.com/Audionut/Upload-Assistant/wiki).

---

## Updating

```bash
cd Upload-Assistant
git fetch --all --tags
git checkout tags/vX.X.X
python3 -m pip install --user -U -r requirements.txt
python3 config-generator.py   # update config with new options
```

---

## Usage

**CLI:**

```bash
python3 upload.py "/path/to/content" --args
```

* Arguments are optional.
* Run `--help` for full list.
* Always wrap paths in quotes.

**Docker:**
See the [Docker wiki guide](https://github.com/Audionut/Upload-Assistant/wiki/Docker).
Or watch this [community video](https://videos.badkitty.zone/ua).

---

## Attributions

* [BDInfoCLI-ng](https://github.com/rokibhasansagar/BDInfoCLI-ng)
* [mkbrr](https://github.com/autobrr/mkbrr)
* [FFmpeg](https://ffmpeg.org/)
* [MediaInfo](https://mediaarea.net/en/MediaInfo)
* [TMDb](https://www.themoviedb.org/)
* [IMDb](https://www.imdb.com/)
* [TheTVDB](https://thetvdb.com/)
* [TVMaze](https://www.tvmaze.com/)
