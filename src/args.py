# -*- coding: utf-8 -*-
import argparse
import urllib.parse
import os
import datetime
import sys
import re
from src.console import console


class ShortHelpFormatter(argparse.HelpFormatter):
    """
    Custom formatter for short help (-h)
    Only displays essential options.
    """
    def __init__(self, prog):
        super().__init__(prog, max_help_position=40, width=80)

    def format_help(self):
        """
        Customize short help output (only show essential arguments).
        """
        short_usage = "usage: upload.py [path...] [options]\n\n"
        short_options = """
Common options:
  -tmdb, --tmdb              Specify the TMDb id to use with movie/ or tv/ prefix
  -imdb, --imdb              Specify the IMDb id to use
  -tvmaze, --tvmaze          Specify the TVMaze id to use
  -tvdb, --tvdb              Specify the TVDB id to use
  --queue (queue name)       Process an entire folder (including files/subfolders) in a queue
  -mf, --manual_frames       Comma-seperated list of frame numbers to use for screenshots
  -df, --descfile            Path to custom description file
  -serv, --service           Streaming service
  --no-aka                   Remove AKA from title
  -daily, --daily            Air date of a daily type episode (YYYY-MM-DD)
  -c, --category             Category (movie, tv, fanres)
  -t, --type                 Type (disc, remux, encode, webdl, etc.)
  --source                   Source (Blu-ray, BluRay, DVD, WEBDL, etc.)
  -comps, --comparison       Use comparison images from a folder (input folder path): see -comps_index
  -debug, --debug            Prints more information, runs everything without actually uploading

Use --help for a full list of options.
"""
        return short_usage + short_options


class CustomArgumentParser(argparse.ArgumentParser):
    """
    Custom ArgumentParser to handle short (-h) and long (--help) help messages.
    """
    def print_help(self, file=None):
        """
        Show short help for `-h` and full help for `--help`
        """
        if "--help" in sys.argv:
            super().print_help(file)  # Full help
        else:
            short_parser = argparse.ArgumentParser(
                formatter_class=ShortHelpFormatter, add_help=False, usage="upload.py [path...] [options]"
            )
            short_parser.print_help(file)


class Args():
    """
    Parse Args
    """
    def __init__(self, config):
        self.config = config
        pass

    def parse(self, args, meta):
        input = args
        parser = CustomArgumentParser(
            usage="upload.py [path...] [options]",
        )

        parser.add_argument('path', nargs='+', help="Path to file/directory (in single/double quotes is best)")
        parser.add_argument('--queue', nargs=1, required=False, help="(--queue queue_name) Process an entire folder (files/subfolders) in a queue")
        parser.add_argument('-lq', '--limit-queue', dest='limit_queue', nargs=1, required=False, help="Limit the amount of queue files processed", type=int, default=0)
        parser.add_argument('--unit3d', action='store_true', required=False, help="[parse a txt output file from UNIT3D-Upload-Checker]")
        parser.add_argument('-s', '--screens', nargs=1, required=False, help="Number of screenshots", default=int(self.config['DEFAULT']['screens']))
        parser.add_argument('-comps', '--comparison', nargs='+', required=False, help="Use comparison images from a folder (input folder path). See: https://github.com/Audionut/Upload-Assistant/pull/487", default=None)
        parser.add_argument('-comps_index', '--comparison_index', nargs=1, required=False, help="Which of your comparison indexes is the main images (required when comps)", type=int, default=None)
        parser.add_argument('-mf', '--manual_frames', nargs=1, required=False, help="Comma-separated frame numbers to use as screenshots", type=str, default=None)
        parser.add_argument('-c', '--category', nargs=1, required=False, help="Category [MOVIE, TV, FANRES]", choices=['movie', 'tv', 'fanres'])
        parser.add_argument('-t', '--type', nargs=1, required=False, help="Type [DISC, REMUX, ENCODE, WEBDL, WEBRIP, HDTV, DVDRIP]", choices=['disc', 'remux', 'encode', 'webdl', 'web-dl', 'webrip', 'hdtv', 'dvdrip'], dest="manual_type")
        parser.add_argument('--source', nargs=1, required=False, help="Source [Blu-ray, BluRay, DVD, DVD5, DVD9, HDDVD, WEB, HDTV, UHDTV, LaserDisc, DCP]", choices=['Blu-ray', 'BluRay', 'DVD', 'DVD5', 'DVD9', 'HDDVD', 'WEB', 'HDTV', 'UHDTV', 'LaserDisc', 'DCP'], dest="manual_source")
        parser.add_argument('-res', '--resolution', nargs=1, required=False, help="Resolution [2160p, 1080p, 1080i, 720p, 576p, 576i, 480p, 480i, 8640p, 4320p, OTHER]", choices=['2160p', '1080p', '1080i', '720p', '576p', '576i', '480p', '480i', '8640p', '4320p', 'other'])
        parser.add_argument('-tmdb', '--tmdb', nargs=1, required=False, help="TMDb ID (use movie/ or tv/ prefix)", type=str, dest='tmdb_manual')
        parser.add_argument('-imdb', '--imdb', nargs=1, required=False, help="IMDb ID", type=str, dest='imdb_manual')
        parser.add_argument('-mal', '--mal', nargs=1, required=False, help="MAL ID", type=str, dest='mal_manual')
        parser.add_argument('-tvmaze', '--tvmaze', nargs=1, required=False, help="TVMAZE ID", type=str, dest='tvmaze_manual')
        parser.add_argument('-tvdb', '--tvdb', nargs=1, required=False, help="TVDB ID", type=str, dest='tvdb_manual')
        parser.add_argument('-g', '--tag', nargs='*', required=False, help="Group Tag", type=str)
        parser.add_argument('-serv', '--service', nargs='*', required=False, help="Streaming Service", type=str)
        parser.add_argument('-dist', '--distributor', nargs='*', required=False, help="Disc Distributor e.g.(Criterion, BFI, etc.)", type=str)
        parser.add_argument('-edition', '--edition', '--repack', nargs='*', required=False, help="Edition/Repack String e.g.(Director's Cut, Uncut, Hybrid, REPACK, REPACK3)", type=str, dest='manual_edition')
        parser.add_argument('-season', '--season', nargs=1, required=False, help="Season (number)", type=str)
        parser.add_argument('-episode', '--episode', nargs=1, required=False, help="Episode (number)", type=str)
        parser.add_argument('--not-anime', dest='not_anime', action='store_true', required=False, help="This is not an Anime release")
        parser.add_argument('-met', '--manual-episode-title', nargs='*', required=False, help="Set episode title, empty = empty", type=str, dest="manual_episode_title", default=None)
        parser.add_argument('-daily', '--daily', nargs=1, required=False, help="Air date of this episode (YYYY-MM-DD)", type=datetime.date.fromisoformat, dest="manual_date")
        parser.add_argument('--no-season', dest='no_season', action='store_true', required=False, help="Remove Season from title")
        parser.add_argument('--no-year', dest='no_year', action='store_true', required=False, help="Remove Year from title")
        parser.add_argument('--no-aka', dest='no_aka', action='store_true', required=False, help="Remove AKA from title")
        parser.add_argument('--no-dub', dest='no_dub', action='store_true', required=False, help="Remove Dubbed from title")
        parser.add_argument('--no-dual', dest='no_dual', action='store_true', required=False, help="Remove Dual-Audio from title")
        parser.add_argument('--no-tag', dest='no_tag', action='store_true', required=False, help="Remove Group Tag from title")
        parser.add_argument('--no-edition', dest='no_edition', action='store_true', required=False, help="Remove Edition from title")
        parser.add_argument('--dual-audio', dest='dual_audio', action='store_true', required=False, help="Add Dual-Audio to the title")
        parser.add_argument('-ol', '--original-language', dest='manual_language', nargs=1, required=False, help="Set original audio language")
        parser.add_argument('-oil', '--only-if-languages', dest='has_languages',  nargs='*', required=False, help="Require at least one of the languages to upload. Comma separated list e.g. 'English, French, Spanish'", type=str)
        parser.add_argument('-ns', '--no-seed', action='store_true', required=False, help="Do not add torrent to the client")
        parser.add_argument('-year', '--year', dest='manual_year', nargs=1, required=False, help="Override the year found", type=int, default=0)
        parser.add_argument('-ptp', '--ptp', nargs=1, required=False, help="PTP torrent id/permalink", type=str)
        parser.add_argument('-blu', '--blu', nargs=1, required=False, help="BLU torrent id/link", type=str)
        parser.add_argument('-aither', '--aither', nargs=1, required=False, help="Aither torrent id/link", type=str)
        parser.add_argument('-lst', '--lst', nargs=1, required=False, help="LST torrent id/link", type=str)
        parser.add_argument('-oe', '--oe', nargs=1, required=False, help="OE torrent id/link", type=str)
        parser.add_argument('-tik', '--tik', nargs=1, required=False, help="TIK torrent id/link", type=str)
        parser.add_argument('-hdb', '--hdb', nargs=1, required=False, help="HDB torrent id/link", type=str)
        parser.add_argument('-btn', '--btn', nargs=1, required=False, help="BTN torrent id/link", type=str)
        parser.add_argument('-bhd', '--bhd', nargs=1, required=False, help="BHD torrent_id/link", type=str)
        parser.add_argument('-huno', '--huno', nargs=1, required=False, help="HUNO torrent id/link", type=str)
        parser.add_argument('-ulcx', '--ulcx', nargs=1, required=False, help="ULCX torrent id/link", type=str)
        parser.add_argument('-onlyID', '--onlyID', action='store_true', required=False, help="Only grab meta ids (tmdb/imdb/etc) from tracker, not description/image links.", default=None)
        parser.add_argument('--foreign', dest='foreign', action='store_true', required=False, help="Set for TIK Foreign category")
        parser.add_argument('--opera', dest='opera', action='store_true', required=False, help="Set for TIK Opera & Musical category")
        parser.add_argument('--asian', dest='asian', action='store_true', required=False, help="Set for TIK Asian category")
        parser.add_argument('-disctype', '--disctype', nargs=1, required=False, help="Type of disc for TIK (BD100, BD66, BD50, BD25, NTSC DVD9, NTSC DVD5, PAL DVD9, PAL DVD5, Custom, 3D)", type=str)
        parser.add_argument('--untouched', dest='untouched', action='store_true', required=False, help="Set when a completely untouched disc at TIK")
        parser.add_argument('-manual_dvds', '--manual_dvds', nargs=1, required=False, help="Override the default number of DVD's (eg: use 2xDVD9+DVD5 instead)", type=str, dest='manual_dvds', default="")
        parser.add_argument('-pb', '--desclink', nargs=1, required=False, help="Custom Description (link to hastebin/pastebin)")
        parser.add_argument('-df', '--descfile', nargs=1, required=False, help="Custom Description (path to file OR filename in current working directory)")
        parser.add_argument('-ih', '--imghost', nargs=1, required=False, help="Image Host", choices=['imgbb', 'ptpimg', 'imgbox', 'pixhost', 'lensdump', 'ptscreens', 'onlyimage', 'dalexni', 'zipline'])
        parser.add_argument('-siu', '--skip-imagehost-upload', dest='skip_imghost_upload', action='store_true', required=False, help="Skip Uploading to an image host")
        parser.add_argument('-th', '--torrenthash', nargs=1, required=False, help="Torrent Hash to re-use from your client's session directory")
        parser.add_argument('-nfo', '--nfo', action='store_true', required=False, help="Use .nfo in directory for description")
        parser.add_argument('-k', '--keywords', nargs=1, required=False, help="Add comma seperated keywords e.g. 'keyword, keyword2, etc'")
        parser.add_argument('-kf', '--keep-folder', action='store_true', required=False, help="Keep the folder containing the single file. Works only when supplying a directory as input. For uploads with poor filenames, like some scene.")
        parser.add_argument('-reg', '--region', nargs=1, required=False, help="Region for discs")
        parser.add_argument('-a', '--anon', action='store_true', required=False, help="Upload anonymously")
        parser.add_argument('-st', '--stream', action='store_true', required=False, help="Stream Optimized Upload")
        parser.add_argument('-webdv', '--webdv', action='store_true', required=False, help="Contains a Dolby Vision layer converted using dovi_tool (HYBRID)")
        parser.add_argument('-hc', '--hardcoded-subs', action='store_true', required=False, help="Contains hardcoded subs", dest="hardcoded-subs")
        parser.add_argument('-pr', '--personalrelease', action='store_true', required=False, help="Personal Release")
        parser.add_argument('-sdc', '--skip-dupe-check', action='store_true', required=False, help="Pass if you know this is a dupe (Skips dupe check)", dest="dupe")
        parser.add_argument('-debug', '--debug', action='store_true', required=False, help="Debug Mode, will run through all the motions providing extra info, but will not upload to trackers.")
        parser.add_argument('-ffdebug', '--ffdebug', action='store_true', required=False, help="Will show info from ffmpeg while taking screenshots.")
        parser.add_argument('-mps', '--max-piece-size', nargs=1, required=False, help="Set max piece size allowed in MiB for default torrent creation (default 128 MiB)", choices=['2', '4', '8', '16', '32', '64', '128'])
        parser.add_argument('-nh', '--nohash', action='store_true', required=False, help="Don't hash .torrent")
        parser.add_argument('-rh', '--rehash', action='store_true', required=False, help="DO hash .torrent")
        parser.add_argument('-mkbrr', '--mkbrr', action='store_true', required=False, help="Use mkbrr for torrent hashing")
        parser.add_argument('-dr', '--draft', action='store_true', required=False, help="Send to drafts (BHD, LST)")
        parser.add_argument('-mq', '--modq', action='store_true', required=False, help="Send to modQ")
        parser.add_argument('-client', '--client', nargs=1, required=False, help="Use this torrent client instead of default")
        parser.add_argument('-qbt', '--qbit-tag', dest='qbit_tag', nargs=1, required=False, help="Add to qbit with this tag")
        parser.add_argument('-qbc', '--qbit-cat', dest='qbit_cat', nargs=1, required=False, help="Add to qbit with this category")
        parser.add_argument('-rtl', '--rtorrent-label', dest='rtorrent_label', nargs=1, required=False, help="Add to rtorrent with this label")
        parser.add_argument('-tk', '--trackers', nargs=1, required=False, help="Upload to these trackers, comma seperated (--trackers blu,bhd) including manual")
        parser.add_argument('-tpc', '--trackers-pass', dest='trackers_pass', nargs=1, required=False, help="How many trackers need to pass all checks (dupe/banned group/etc) to actually proceed to uploading", type=int)
        parser.add_argument('-rt', '--randomized', nargs=1, required=False, help="Number of extra, torrents with random infohash", default=0)
        parser.add_argument('-entropy', '--entropy', dest='entropy', nargs=1, required=False, help="Use entropy in created torrents. (32 or 64) bits (ie: -entropy 32). Not supported at all sites, you many need to redownload the torrent", type=int, default=0)
        parser.add_argument('-ua', '--unattended', action='store_true', required=False, help=argparse.SUPPRESS)
        parser.add_argument('-uac', '--unattended-confirm', action='store_true', required=False, help=argparse.SUPPRESS)
        parser.add_argument('-vs', '--vapoursynth', action='store_true', required=False, help="Use vapoursynth for screens (requires vs install)")
        parser.add_argument('-dm', '--delete-meta', action='store_true', required=False, dest='delete_meta', help="Delete only meta.json from tmp directory")
        parser.add_argument('-dtmp', '--delete-tmp', action='store_true', required=False, dest='delete_tmp', help="Delete tmp directory for the working file/folder")
        parser.add_argument('-cleanup', '--cleanup', action='store_true', required=False, help="Clean up tmp directory")
        parser.add_argument('-fl', '--freeleech', nargs=1, required=False, help="Freeleech Percentage. Any value 1-100 works, but site search is limited to certain values", default=0, dest="freeleech")
        parser.add_argument('--infohash', nargs=1, required=False, help="V1 Info Hash")
        args, before_args = parser.parse_known_args(input)
        args = vars(args)
        # console.print(args)
        if meta.get('manual_frames') is not None:
            try:
                # Join the list into a single string, split by commas, and convert to integers
                meta['manual_frames'] = [int(time.strip()) for time in meta['manual_frames'].split(',')]
                # console.print(f"Processed manual_frames: {meta['manual_frames']}")
            except ValueError:
                console.print("[red]Invalid format for manual_frames. Please provide a comma-separated list of integers.")
                console.print(f"Processed manual_frames: {meta['manual_frames']}")
                sys.exit(1)
        else:
            meta['manual_frames'] = None  # Explicitly set it to None if not provided
        if len(before_args) >= 1 and not os.path.exists(' '.join(args['path'])):
            for each in before_args:
                args['path'].append(each)
                if os.path.exists(' '.join(args['path'])):
                    if any(".mkv" in x for x in before_args):
                        if ".mkv" in ' '.join(args['path']):
                            break
                    else:
                        break

        if meta.get('tmdb_manual') is not None or meta.get('imdb_manual') is not None:
            meta['tmdb_manual'] = meta['tmdb_id'] = meta['tmdb'] = meta['imdb_id'] = meta['imdb'] = None
        for key in args:
            value = args.get(key)
            if value not in (None, []):
                if isinstance(value, list):
                    value2 = self.list_to_string(value)
                    if key == 'manual_type':
                        meta['manual_type'] = value2.upper().replace('-', '')
                    elif key == 'tag':
                        meta[key] = f"-{value2}"
                    elif key == 'descfile':
                        meta[key] = os.path.abspath(value2)
                    elif key == 'comparison':
                        meta[key] = os.path.abspath(value2)
                    elif key == 'screens':
                        meta[key] = int(value2)
                    elif key == 'season':
                        meta['manual_season'] = value2
                    elif key == 'episode':
                        meta['manual_episode'] = value2
                    elif key == 'manual_date':
                        meta['manual_date'] = value2
                    elif key == 'tmdb_manual':
                        meta['category'], meta['tmdb_manual'] = self.parse_tmdb_id(value2, meta.get('category'))
                    elif key == 'ptp':
                        if value2.startswith('http'):
                            parsed = urllib.parse.urlparse(value2)
                            try:
                                meta['ptp'] = urllib.parse.parse_qs(parsed.query)['torrentid'][0]
                            except Exception:
                                console.print('[red]Your terminal ate  part of the url, please surround in quotes next time, or pass only the torrentid')
                                console.print('[red]Continuing without -ptp')
                        else:
                            meta['ptp'] = value2
                    elif key == 'blu':
                        if value2.startswith('http'):
                            parsed = urllib.parse.urlparse(value2)
                            try:
                                blupath = parsed.path
                                if blupath.endswith('/'):
                                    blupath = blupath[:-1]
                                meta['blu'] = blupath.split('/')[-1]
                            except Exception:
                                console.print('[red]Unable to parse id from url')
                                console.print('[red]Continuing without --blu')
                        else:
                            meta['blu'] = value2
                    elif key == 'aither':
                        if value2.startswith('http'):
                            parsed = urllib.parse.urlparse(value2)
                            try:
                                aitherpath = parsed.path
                                if aitherpath.endswith('/'):
                                    aitherpath = aitherpath[:-1]
                                meta['aither'] = aitherpath.split('/')[-1]
                            except Exception:
                                console.print('[red]Unable to parse id from url')
                                console.print('[red]Continuing without --aither')
                        else:
                            meta['aither'] = value2
                    elif key == 'lst':
                        if value2.startswith('http'):
                            parsed = urllib.parse.urlparse(value2)
                            try:
                                lstpath = parsed.path
                                if lstpath.endswith('/'):
                                    lstpath = lstpath[:-1]
                                meta['lst'] = lstpath.split('/')[-1]
                            except Exception:
                                console.print('[red]Unable to parse id from url')
                                console.print('[red]Continuing without --lst')
                        else:
                            meta['lst'] = value2
                    elif key == 'oe':
                        if value2.startswith('http'):
                            parsed = urllib.parse.urlparse(value2)
                            try:
                                oepath = parsed.path
                                if oepath.endswith('/'):
                                    oepath = oepath[:-1]
                                meta['oe'] = oepath.split('/')[-1]
                            except Exception:
                                console.print('[red]Unable to parse id from url')
                                console.print('[red]Continuing without --oe')
                        else:
                            meta['oe'] = value2
                    elif key == 'ulcx':
                        if value2.startswith('http'):
                            parsed = urllib.parse.urlparse(value2)
                            try:
                                ulcxpath = parsed.path
                                if ulcxpath.endswith('/'):
                                    ulcxpath = ulcxpath[:-1]
                                meta['ulcx'] = ulcxpath.split('/')[-1]
                            except Exception:
                                console.print('[red]Unable to parse id from url')
                                console.print('[red]Continuing without --ulcx')
                        else:
                            meta['ulcx'] = value2
                    elif key == 'hdb':
                        if value2.startswith('http'):
                            parsed = urllib.parse.urlparse(value2)
                            try:
                                meta['hdb'] = urllib.parse.parse_qs(parsed.query)['id'][0]
                            except Exception:
                                console.print('[red]Your terminal ate  part of the url, please surround in quotes next time, or pass only the torrentid')
                                console.print('[red]Continuing without -hdb')
                        else:
                            meta['hdb'] = value2

                    elif key == 'btn':
                        if value2.startswith('http'):
                            parsed = urllib.parse.urlparse(value2)
                            try:
                                meta['btn'] = urllib.parse.parse_qs(parsed.query)['id'][0]
                            except Exception:
                                console.print('[red]Your terminal ate  part of the url, please surround in quotes next time, or pass only the torrentid')
                                console.print('[red]Continuing without -hdb')
                        else:
                            meta['btn'] = value2

                    elif key == 'bhd':
                        if value2.startswith('http'):
                            parsed = urllib.parse.urlparse(value2)
                            try:
                                bhdpath = parsed.path
                                if bhdpath.endswith('/'):
                                    bhdpath = bhdpath[:-1]

                                if '/download/' in bhdpath or '/torrents/' in bhdpath:
                                    torrent_id_match = re.search(r'\.(\d+)$', bhdpath)
                                    if torrent_id_match:
                                        meta['bhd'] = torrent_id_match.group(1)
                                    else:
                                        meta['bhd'] = bhdpath.split('/')[-1]
                                else:
                                    meta['bhd'] = bhdpath.split('/')[-1]

                                console.print(f"[green]Parsed BHD torrent ID: {meta['bhd']}")
                            except Exception as e:
                                console.print(f'[red]Unable to parse id from url: {e}')
                                console.print('[red]Continuing without --bhd')
                        else:
                            meta['bhd'] = value2

                    elif key == 'huno':
                        if value2.startswith('http'):
                            parsed = urllib.parse.urlparse(value2)
                            try:
                                hunopath = parsed.path
                                if hunopath.endswith('/'):
                                    hunopath = hunopath[:-1]
                                meta['huno'] = hunopath.split('/')[-1]
                            except Exception:
                                console.print('[red]Unable to parse id from url')
                                console.print('[red]Continuing without --huno')
                        else:
                            meta['huno'] = value2

                    else:
                        meta[key] = value2
                else:
                    meta[key] = value
            elif key in ("manual_edition"):
                if isinstance(value, list) and len(value) == 1:
                    meta[key] = value[0]
                else:
                    meta[key] = value
            elif key in ("manual_dvds"):
                meta[key] = value
            elif key in ("freeleech"):
                meta[key] = 100
            elif key in ("tag") and value == []:
                meta[key] = ""
            elif key in ["manual_episode_title"] and value == []:
                meta[key] = ""
            elif key in ["manual_episode_title"]:
                meta[key] = value
            elif key in ["tvmaze_manual"]:
                meta[key] = value
            elif key == 'trackers':
                if value:
                    tracker_value = value
                    if isinstance(tracker_value, str):
                        tracker_value = tracker_value.strip('"\'')

                    if isinstance(tracker_value, str) and ',' in tracker_value:
                        meta[key] = [t.strip().upper() for t in tracker_value.split(',')]
                    else:
                        meta[key] = [tracker_value.strip().upper()] if isinstance(tracker_value, str) else [tracker_value.upper()]
                else:
                    meta[key] = []
            else:
                meta[key] = meta.get(key, None)
            # if key == 'help' and value == True:
                # parser.print_help()
        return meta, parser, before_args

    def list_to_string(self, list):
        if len(list) == 1:
            return str(list[0])
        try:
            result = " ".join(list)
        except Exception:
            result = "None"
        return result

    def parse_tmdb_id(self, id, category):
        id = str(id).lower().strip()
        if id.startswith('http'):
            parsed = urllib.parse.urlparse(id)
            path = parsed.path.strip('/')

            if '/' in path:
                parts = path.split('/')
                if len(parts) >= 2:
                    type_part = parts[-2]
                    id_part = parts[-1]

                    if type_part == 'tv':
                        category = 'TV'
                    elif type_part == 'movie':
                        category = 'MOVIE'

                    id = id_part

        if id.startswith('tv'):
            id = id.split('/')[1]
            category = 'TV'
        elif id.startswith('movie'):
            id = id.split('/')[1]
            category = 'MOVIE'
        else:
            id = id

        if isinstance(id, str) and id.isdigit():
            id = int(id)
        else:
            id = 0

        return category, id
