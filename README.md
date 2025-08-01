[![Create and publish a Docker image](https://github.com/Audionut/Upload-Assistant/actions/workflows/docker-image.yml/badge.svg?branch=master)](https://github.com/Audionut/Upload-Assistant/actions/workflows/docker-image.yml) [![Test run (Master Branch)](https://img.shields.io/github/actions/workflow/status/Audionut/Upload-Assistant/test-run.yaml?branch=master&label=Test%20run%20(Master%20Branch%202025-07-04%2006:06%20UTC))](https://github.com/Audionut/Upload-Assistant/actions/workflows/test-run.yaml?query=branch%3Amaster) [![Test run (5.1.5.2)](https://img.shields.io/github/actions/workflow/status/Audionut/Upload-Assistant/test-run.yaml?branch=5.1.5.2&label=Test%20run%20(5.1.5.2%202025-07-19%2014:24%20UTC))](https://github.com/Audionut/Upload-Assistant/actions/workflows/test-run.yaml?query=branch%3A5.1.5.2)

Discord support https://discord.gg/QHHAZu7e2A

# Audionut's Upload Assistant

A simple tool to take the work out of uploading.

This project is a fork of the original work of L4G https://github.com/L4GSP1KE/Upload-Assistant
Immense thanks to him for establishing this project. Without his (and supporters) time and effort, this fork would not be a thing.
What started as simply pushing some pull requests to keep the main repo inline, as L4G seemed busy with IRL, has since snowballed into full time development, bugs and all.

Many other forks exist, most are simply a rebranding of this fork without any credit whatsoever.
Better just to be on this fork and bug me about my bugs, rather than bugging someone who can ctrl+c/ctrl+v, but likely can't fix the bugs.

## What It Can Do:
  - Generates and Parses MediaInfo/BDInfo.
  - Generates and Uploads screenshots. HDR tonemapping if config.
  - Uses srrdb to fix scene names used at sites.
  - Can grab descriptions from PTP/BLU/Aither/LST/OE/BHD (with config option automatically on filename match, or using arg).
  - Can strip and use existing screenshots from descriptions to skip screenshot generation and uploading.
  - Obtains TMDb/IMDb/MAL/TVDB/TVMAZE identifiers.
  - Converts absolute to season episode numbering for Anime. Non-Anime support with TVDB credentials
  - Generates custom .torrents without useless top level folders/nfos.
  - Can re-use existing torrents instead of hashing new.
  - Can automagically search qBitTorrent version 5+ clients for matching existing torrent.
  - Generates proper name for your upload using Mediainfo/BDInfo and TMDb/IMDb conforming to site rules.
  - Checks for existing releases already on site.
  - Adds to your client with fast resume, seeding instantly (rtorrent/qbittorrent/deluge/watch folder).
  - ALL WITH MINIMAL INPUT!
  - Currently works with .mkv/.mp4/Blu-ray/DVD/HD-DVDs.

## Supported Sites:
<table>
  <tr>
    <td align="center"><b>Name</b></td><td align="center"><b>Acronym</b></td>
    <td align="center"><b>Name</b></td><td align="center"><b>Acronym</b></td>
  </tr>
  <tr><td>Aither</td><td>AITHER</td><td>Alpharatio</td><td>AR</td></tr>
  <tr><td>Amigos Share Club</td><td>ASC</td><td>AnimeLovers</td><td>AL</td></tr>
  <tr><td>Anthelion</td><td>ANT</td><td>AsianCinema</td><td>ACM</td></tr>
  <tr><td>Beyond-HD</td><td>BHD</td><td>BitHDTV</td><td>BHDTV</td></tr>
  <tr><td>Blutopia</td><td>BLU</td><td>BrasilTracker</td><td>BT</td></tr>
  <tr><td>CapybaraBR</td><td>CBR</td><td>Cinematik</td><td>TIK</td></tr>
  <tr><td>DarkPeers</td><td>DP</td><td>DigitalCore</td><td>DC</td></tr>
  <tr><td>FearNoPeer</td><td>FNP</td><td>FileList</td><td>FL</td></tr>
  <tr><td>Friki</td><td>FRIKI</td><td>hawke-uno</td><td>HUNO</td></tr>
  <tr><td>HDBits</td><td>HDB</td><td>HD-Space</td><td>HDS</td></tr>
  <tr><td>HD-Torrents</td><td>HDT</td><td>HomieHelpDesk</td><td>HHD</td></tr>
  <tr><td>ItaTorrents</td><td>ITT</td><td>Last Digital Underground</td><td>LDU</td></tr>
  <tr><td>Lat-Team</td><td>LT</td><td>Locadora</td><td>LCD</td></tr>
  <tr><td>LST</td><td>LST</td><td>MoreThanTV</td><td>MTV</td></tr>
  <tr><td>Nebulance</td><td>NBL</td><td>OldToonsWorld</td><td>OTW</td></tr>
  <tr><td>OnlyEncodes+</td><td>OE</td><td>PassThePopcorn</td><td>PTP</td></tr>
  <tr><td>Polish Torrent</td><td>PTT</td><td>Portugas</td><td>PT</td></tr>
  <tr><td>PrivateSilverScreen</td><td>PSS</td><td>PTerClub</td><td>PTER</td></tr>
  <tr><td>Racing4Everyone</td><td>R4E</td><td>Rastastugan</td><td>RAS</td></tr>
  <tr><td>ReelFLiX</td><td>RF</td><td>RetroFlix</td><td>RTF</td></tr>
  <tr><td>Samaritano</td><td>SAM</td><td>seedpool</td><td>SP</td></tr>
  <tr><td>Shareisland</td><td>SHRI</td><td>SkipTheCommericals</td><td>STC</td></tr>
  <tr><td>SpeedApp</td><td>SPD</td><td>Swarmazon</td><td>SN</td></tr>
  <tr><td>Toca Share</td><td>TOCA</td><td>TorrentHR</td><td>THR</td></tr>
  <tr><td>TorrentLeech</td><td>TL</td><td>ToTheGlory</td><td>TTG</td></tr>
  <tr><td>TVChaosUK</td><td>TVC</td><td>UHDShare</td><td>UHD</td></tr>
  <tr><td>ULCX</td><td>ULCX</td><td>UTOPIA</td><td>UTP</td></tr>
  <tr><td>YOiNKED</td><td>YOINK</td><td>YUSCENE</td><td>YUS</td></tr>
</table>

## **Setup:**
   - **REQUIRES AT LEAST PYTHON 3.9 AND PIP3**
   - Needs [mono](https://www.mono-project.com/) on linux systems for BDInfo
   - Also needs MediaInfo and ffmpeg installed on your system
      - On Windows systems, ffmpeg must be added to PATH (https://windowsloop.com/install-ffmpeg-windows-10/)
      - On linux systems, get it from your favorite package manager
      - If you have issues with ffmpeg, such as `max workers` errors, see this [wiki](https://github.com/Audionut/Upload-Assistant/wiki/ffmpeg---max-workers-issues)
   - Get the source:
      - Clone the repo to your system `git clone https://github.com/Audionut/Upload-Assistant.git`
      - Fetch all of the release tags `git fetch --all --tags`
      - Check out the specifc release: see [releases](https://github.com/Audionut/Upload-Assistant/releases)
      - `git checkout tags/tagname` where `tagname` is the release name, eg `v5.0.0`
      - or download a zip of the source from the releases page and create/overwrite a local copy.
   - Install necessary python modules `pip3 install --user -U -r requirements.txt`
      - `sudo apt install pip` if needed
  - If you receive an error about externally managed environment, or otherwise wish to keep UA python separate:
      - Install virtual python environment `python3 -m venv venv`
      - Activate the virtual environment `source venv/bin/activate`
      - Then install the requirements `pip install -r requirements.txt`
   - From the installation directory, run `python3 config-generator.py`
   - OR
   - Copy and Rename `data/example-config.py` to `data/config.py`
   - Edit `config.py` to use your information (more detailed information in the [wiki](https://github.com/Audionut/Upload-Assistant/wiki))
      - tmdb_api key can be obtained from https://www.themoviedb.org/settings/api
      - image host api keys can be obtained from their respective sites
     
   **Additional Resources are found in the [wiki](https://github.com/Audionut/Upload-Assistant/wiki)**
   
   Feel free to contact me if you need help, I'm not that hard to find.

## **Updating:**
  - To update first navigate into the Upload-Assistant directory: `cd Upload-Assistant`
  - `git fetch --all --tags`
  - `git checkout tags/tagname`
  - Or download a fresh zip from the releases page and overwrite existing files
  - Run `python3 -m pip install --user -U -r requirements.txt` to ensure dependencies are up to date
  - Run `python3 config-generator.py` and select to grab new UA config options.

## **CLI Usage:**
  
  `python3 upload.py "/path/to/content" --args`
  
  Args are OPTIONAL and ALWAYS follow path, for a list of acceptable args, pass `--help`.
  Path works best in quotes.

## **Docker Usage:**
  Visit our wonderful [docker usage wiki page](https://github.com/Audionut/Upload-Assistant/wiki/Docker)

  Also see this excellent video put together by a community memeber https://videos.badkitty.zone/ua

## **Attributions:**

Built with updated BDInfoCLI from https://github.com/rokibhasansagar/BDInfoCLI-ng

<p>
  <a href="https://github.com/autobrr/mkbrr"><img src="https://github.com/autobrr/mkbrr/blob/main/.github/assets/mkbrr-dark.png?raw=true" alt="mkbrr" height="40px;"></a>&nbsp;&nbsp;
  <a href="https://ffmpeg.org/"><img src="https://i.postimg.cc/xdj3BS7S/FFmpeg-Logo-new-svg.png" alt="FFmpeg" height="40px;"></a>&nbsp;&nbsp;
  <a href="https://mediaarea.net/en/MediaInfo"><img src="https://i.postimg.cc/vTkjXmHh/Media-Info-Logo-svg.png" alt="Mediainfo" height="40px;"></a>&nbsp;&nbsp;
  <a href="https://www.themoviedb.org/"><img src="https://i.postimg.cc/1tpXHx3k/blue-square-2-d537fb228cf3ded904ef09b136fe3fec72548ebc1fea3fbbd1ad9e36364db38b.png" alt="TMDb" height="40px;"></a>&nbsp;&nbsp;
  <a href="https://www.imdb.com/"><img src="https://i.postimg.cc/CLVmvwr1/IMDb-Logo-Rectangle-Gold-CB443386186.png" alt="IMDb" height="40px;"></a>&nbsp;&nbsp;
  <a href="https://thetvdb.com/"><img src="https://i.postimg.cc/Hs1KKqsS/logo1.png" alt="TheTVDB" height="40px;"></a>&nbsp;&nbsp;
  <a href="https://www.tvmaze.com/"><img src="https://i.postimg.cc/2jdRzkJp/tvm-header-logo.png" alt="TVmaze" height="40px"></a>
</p>
