config = {
    "DEFAULT": {

        # ------ READ THIS ------
        # Any lines starting with the # symbol are commented and will not be used.
        # If you change any of these options, remove the #
        # -----------------------

        # will print a notice if an update is available
        "update_notification": True,
        # will print the changelog if an update is available
        "verbose_notification": False,

        # tmdb api key
        # visit "https://www.themoviedb.org/settings/api" copy api key and insert below
        "tmdb_api": "tmdb_api key",

        # tvdb api key
        # visit "https://www.thetvdb.com/dashboard/account/apikey" copy api key and insert below
        "tvdb_api": "",
        # visit "https://thetvdb.github.io/v4-api/#/Login/post_login" enter api key, generate token and insert token below
        # the pin in the login form is not needed (don't modify), only enter your api key
        "tvdb_token": "",

        # btn api key for infohash parsing
        "btn_api": "btn_api key",
        # bhd api/rss keys for infohash parsing and auto torrent id/filename searching
        "bhd_api": "bhd api key",
        "bhd_rss_key": "bhd rss key",

        # image host api keys
        "imgbb_api": "imgbb api key",
        "ptpimg_api": "ptpimg api key",
        "lensdump_api": "lensdump api key",
        "ptscreens_api": "ptscreens api key",
        "oeimg_api": "oeimg api key",
        "dalexni_api": "dalexni api key",
        # custom zipline url
        "zipline_url": "zipline URL",
        "zipline_api_key": "zipline API KEY",

        # Order of image hosts, and backup image hosts
        "img_host_1": "imgbb",
        "img_host_2": "ptpimg",
        "img_host_3": "imgbox",
        "img_host_4": "pixhost",
        "img_host_5": "lensdump",
        "img_host_6": "ptscreens",
        "img_host_7": "oeimg",
        "img_host_8": "dalexni",
        "img_host_9": "zipline",

        # Whether to add a logo for the show/movie from TMDB to the top of the description
        "add_logo": False,

        # Logo image size
        "logo_size": "420",

        # Accepted logo language (ISO 639-1)
        # If a logo with this language cannot be found, English will be used instead
        "logo_language": "en",

        # Number of screenshots to capture
        "screens": "6",

        # Add some overlay details to the screenshots
        # Frame number/type and Tonemapped if applicable
        "frame_overlay": False,
        # Overlay text size, scales with resolution
        "overlay_text_size": "18",

        # Tonemap HDR screenshots
        "tone_map": False,
        # Tonemap HDR screenshots with the following settings
        # See https://ayosec.github.io/ffmpeg-filters-docs/7.1/Filters/Video/tonemap.html
        "algorithm": "mobius",
        "desat": "10.0",

        # Number of cutoff screenshots
        # If there are at least this many screenshots already, perhaps pulled from existing
        # description, skip creating and uploading any further screenshots.
        "cutoff_screens": "3",

        # MULTI PROCESSING
        # The optimization task is resource intensive, it can and will break linux terminals
        # Find a balance of the options below that give the best performace without
        # breaking your terminal. Windows doesn't care, even when spawing 200+ threads.

        # When optimizing images, limit to this many concurrent workers.
        # Each worker is a fresh python.exe instance.
        # The final value used will be the lowest value of either 'number of screens'
        # or this value.
        # defaults to 1 if not set. Uncomment line below and set a value
        # "process_limit": "1",

        # When optimizing images, limit to this many threads spawned by each worker above
        # On the authors windows box, each python instance is 8 threads (including background wait
        # threads that self terminate with time), thus while this value sets the number of threads
        # used for each optimization worker, the total amount of threads spawned equals:
        # (8) + threads * ('process_limit' OR 'screens')
        # Defaults to 1 if not set. Uncomment line before and set a value
        # "threads": "1",

        # Providing the option to change the size of the screenshot thumbnails where supported.
        # Default is 350, ie [img=350]
        "thumbnail_size": "350",

        # Number of screenshots to use for each (ALL) disc/episode when uploading packs to supported sites.
        # 0 equals old behavior where only the original description and images are added.
        # This setting also effect PTP, however PTP requries at least 2 images for each.
        # PTP will always use a *minimum* of 2, regardless of what is set here.
        "multiScreens": "2",

        # The below options for packed content do not effect PTP. PTP has a set standard.

        # When uploading packs, you can specifiy a different screenshot thumbnail size, default 300.
        "pack_thumb_size": "300",

        # Description character count (including bbcode) cutoff for UNIT3D sites when **season packs only**.
        # After hitting this limit, only filenames and screenshots will be used for any ADDITIONAL files
        # still to be added to the description. You can set this small like 50, to only ever
        # print filenames and screenshots for each file, no mediainfo will be printed.
        # UNIT3D sites have a hard character limit for descriptions. A little over 17000
        # worked fine in a forum post at BLU. If the description is at 1 < charLimit, the next full
        # description will be added before respecting this cutoff.
        "charLimit": "14000",

        # How many files in a season pack will be added to the description before using an additional spoiler tag.
        # Any other files past this limit will be hidden/added all within a spoiler tag.
        "fileLimit": "2",

        # Absolute limit on processed files in packs.
        # You might not want to process screens/mediainfo for 40 episodes in a season pack.
        "processLimit": "5",

        # Providing the option to add a header, in bbcode, above the screenshot section where supported
        # "screenshot_header": "[center] SCREENSHOTS [/center]",

        # Enable lossless PNG Compression (True/False)
        "optimize_images": True,

        # The name of your default torrent client, set in the torrent client sections below
        "default_torrent_client": "Client1",

        # Play the bell sound effect when asking for confirmation
        "sfx_on_prompt": True,

        # How many trackers need to pass successfull checking to continue with the upload process
        # Default = 1. If 1 (or more) tracker/s pass banned_group, content and dupe checking, uploading will continue
        # If less than the number of trackers pass the checking, exit immediately.
        "tracker_pass_checks": "1",

        # Set to true to always just use the largest playlist on a blu-ray, without selection prompt.
        "use_largest_playlist": False,

        # set true to only grab meta id's from trackers, not descriptions and images
        "only_id": False,

        # set true to use mkbrr for torrent creation
        "mkbrr": False,

        # set true to use argument overrides from data/templates/user-args.json
        "user_overrides": False,

        # set true to add episode overview to description
        "episode_overview": False,

        # set true to skip automated client torrent searching
        'skip_auto_torrent': False,

        # NOT RECOMMENDED UNLESS YOU KNOW WHAT YOU ARE DOING
        # set true to not delete existing meta.json file before running
        "keep_meta": False,

    },

    # these are used for DB links on AR
    "IMAGES": {
        "imdb_75": 'https://i.imgur.com/Mux5ObG.png',
        "tmdb_75": 'https://i.imgur.com/r3QzUbk.png',
        "tvdb_75": 'https://i.imgur.com/UWtUme4.png',
        "tvmaze_75": 'https://i.imgur.com/ZHEF5nE.png',
        "mal_75": 'https://i.imgur.com/PBfdP3M.png'
    },

    "TRACKERS": {
        # Which trackers do you want to upload to?
        # Available tracker: ACM, AITHER, AL, ANT, AR, BHD, BHDTV, BLU, CBR, DP, FNP, FRIKI, HDB, HDT, HUNO, ITT, LCD, LST, LT, MTV, NBL, OE, OTW, PSS, PTER, PTP, PTT, R4E, RAS, RF, RTF, SAM, SN, STC, THR, TIK, TL, TOCA, UHD, ULCX, UTP, YOINK, YUS
        # Remove the trackers from the default_trackers list that are not used, to save being asked everytime about tracker you do not have access too.
        "default_trackers": "ACM, AITHER, AL, ANT, AR, BHD, BHDTV, BLU, CBR, DP, FNP, FRIKI, HDB, HDT, HUNO, ITT, LCD, LST, LT, MTV, NBL, OE, OTW, PSS, PTER, PTP, PTT, R4E, RAS, RF, RTF, SAM, SN, STC, THR, TIK, TL, TOCA, UHD, ULCX, UTP, YOINK, YUS",

        "ACM": {
            "api_key": "ACM api key",
            "announce_url": "https://eiga.moi/announce/customannounceurl",
            # "anon" : False,

            # FOR INTERNAL USE ONLY:
            # "internal" : True,
            # "internal_groups" : ["What", "Internal", "Groups", "Are", "You", "In"],
        },
        "AITHER": {
            "useAPI": False,  # Set to True if using Aither for automatic ID searching or description parsing
            "api_key": "AITHER api key",
            "announce_url": "https://aither.cc/announce/customannounceurl",
            # "anon" : False,
            # "modq" : False  ## Not working yet
        },
        "AL": {
            "api_key": "AL api key",
            "announce_url": "https://animelovers.club/announce/customannounceurl",
            # "anon" : False
        },
        "ANT": {
            "api_key": "ANT api key",
            "announce_url": "https://anthelion.me/announce/customannounceurl",
            # "anon" : False
        },
        "AR": {
            "username": "<USERNAME>",
            "password": "<PASSWORD>",
            "announce_url": "http://tracker.alpharatio.cc:2710/PASSKEY/announce",
            # anon is not an option when uplaoding you need to change your privacy settings.
            # "anon" : "False"
        },
        "BHD": {
            # set api/rss keys above if using BHD for automatic ID searching or torrent_id searching
            "useAPI": False,  # Set to True if using BHD for automatic file/foldername searching
            "api_key": "BHD api key",
            "announce_url": "https://beyond-hd.me/announce/customannounceurl",
            "draft_default": "True",  # Send to drafts
            # "anon" : False
        },
        "BHDTV": {
            "api_key": "found under https://www.bit-hdtv.com/my.php",
            "announce_url": "https://trackerr.bit-hdtv.com/announce",
            # passkey found under https://www.bit-hdtv.com/my.php
            "my_announce_url": "https://trackerr.bit-hdtv.com/passkey/announce",
            # "anon" : "False"
        },
        "BLU": {
            "useAPI": False,  # Set to True if using BLU for automatic ID searching or description parsing
            "api_key": "BLU api key",
            "announce_url": "https://blutopia.cc/announce/customannounceurl",
            # "anon" : False,
            # "modq" : False  ## Not working yet
        },
        "CBR": {
            "api_key": "CBR api key",
            "announce_url": "https://capybarabr.com/announce/customannounceurl",
            # "anon" : False
        },
        "DP": {
            "api_key": "DP api key",
            "announce_url": "https://darkpeers.org/announce/customannounceurl",
            # "anon" : False
        },
        "FL": {
            "username": "FL username",
            "passkey": "FL passkey",
            "uploader_name": "https://filelist.io/Custom_Announce_URL",
            # "anon": False,
        },
        "FNP": {
            "api_key": "FNP api key",
            "announce_url": "https://fearnopeer.com/announce/customannounceurl",
            # "anon" : "False"
        },
        "FRIKI": {
            "api_key": "FRIKI API KEY",
            "announce_url": "https://frikibar.com/announce/<PASSKEY>",
        },
        # for HDB you must have been granted uploading approval via Offers
        "HDB": {
            "useAPI": False,  # Set to True if using HDB for automatic ID searching or description parsing
            "username": "HDB username",
            "passkey": "HDB passkey",
            "announce_url": "https://hdbits.org/announce/Custom_Announce_URL",
            # "anon": False,
            "img_rehost": True,
        },
        # for HDT to work you need to export cookies from https://hd-torrent.net/ using https://addons.mozilla.org/en-US/firefox/addon/export-cookies-txt/.
        # cookies need to be in netscape format and need to be in data/cookies/HDT.txt
        "HDT": {
            "username": "username",
            "password": "password",
            "my_announce_url": "https://hdts-announce.ru/announce.php?pid=<PASS_KEY/PID>",
            # "anon" : "False"
            "announce_url": "https://hdts-announce.ru/announce.php",  # DO NOT EDIT THIS LINE
        },
        "HUNO": {
            "api_key": "HUNO api key",
            "announce_url": "https://hawke.uno/announce/customannounceurl",
            # "anon" : False
        },
        "ITT": {
            "api_key": "ITT api key",
            "announce_url": "https://itatorrents.xyz/announce/customannounceurl",
            # "anon" : False
        },
        "LCD": {
            "api_key": "LCD api key",
            "announce_url": "https://locadora.cc/announce/customannounceurl",
            # "anon" : False
        },
        "LST": {
            "useAPI": False,  # Set to True if using LST for automatic ID searching or description parsing
            "api_key": "LST api key",
            "announce_url": "https://lst.gg/announce/customannounceurl",
            # "anon" : False,
            # "modq" : False,  # Send to modq for staff approval
            # "draft" : False  # Send to drafts
        },
        "LT": {
            "api_key": "LT api key",
            "announce_url": "https://lat-team.com/announce/customannounceurl",
            # "anon" : False
        },
        "MTV": {
            'api_key': 'get from security page',
            'username': '<USERNAME>',
            'password': '<PASSWORD>',
            'announce_url': "get from https://www.morethantv.me/upload.php",
            # 'anon': False,
            # 'otp_uri' : 'OTP URI, read the following for more information https://github.com/google/google-authenticator/wiki/Key-Uri-Format'
            'skip_if_rehash': False,  # Skip uploading to MTV if it would require a torrent rehash because existing piece size > 8 MiB
            'prefer_mtv_torrent': False,  # Iterate over found torrents and prefer MTV suitable torrents if found.
        },
        "NBL": {
            "api_key": "NBL api key",
            "announce_url": "https://tracker.nebulance.io/insertyourpasskeyhere/announce",
        },
        "OE": {
            "useAPI": False,  # Set to True if using OE for automatic ID searching or description parsing
            "api_key": "OE api key",
            "announce_url": "https://onlyencodes.cc/announce/customannounceurl",
            # "anon" : False
        },
        "OTW": {
            "api_key": "OTW api key",
            "announce_url": "https://oldtoons.world/announce/customannounceurl",
            # "anon" : False
        },
        "PSS": {
            "api_key": "PSS api key",
            "announce_url": "https://privatesilverscreen.cc/announce/customannounceurl",
            # "anon" : False
        },
        "PTER": {  # Does not appear to be working at all
            "passkey": 'passkey',
            "img_rehost": False,
            "username": "",
            "password": "",
            "ptgen_api": "",
            # "anon": True,
        },
        "PTP": {
            "useAPI": False,  # Set to True if using PTP for automatic ID searching or description parsing
            "add_web_source_to_desc": True,
            "ApiUser": "ptp api user",
            "ApiKey": 'ptp api key',
            "username": "",
            "password": "",
            "announce_url": ""
        },
        "PTT": {
            "api_key": "PTT api key",
            "announce_url": "https://polishtorrent.top/announce/customannounceurl",
            # "anon" : False,
        },
        "R4E": {
            "api_key": "R4E api key",
            "announce_url": "https://racing4everyone.eu/announce/customannounceurl",
            # "anon" : False
        },
        "RAS": {
            "api_key": "RAS api key",
            "announce_url": "https://rastastugan.org/announce/customannounceurl",
            # "anon" : False
        },
        "RF": {
            "api_key": "RF api key",
            "announce_url": "https://reelflix.xyz/announce/customannounceurl",
            # "anon" : False
        },
        "RTF": {
            "username": "username",
            "password": "password",
            "api_key": 'get_it_by_running_/api/ login command from https://retroflix.club/api/doc',
            "announce_url": "get from upload page",
            # "anon": True
        },
        "SAM": {
            "api_key": "Samaritano API KEY",
            "announce_url": "https://samaritano.cc/announce/<PASSKEY>",
            # "anon" : False,
        },
        "SHRI": {
            "api_key": "SHRI api key",
            "announce_url": "https://shareisland.org/announce/customannounceurl",
            # "anon" : "False"
        },
        "SN": {
            "api_key": "SN",
            "announce_url": "https://tracker.swarmazon.club:8443/<YOUR_PASSKEY>/announce",
        },
        "SP": {
            "api_key": "SeedPool API KEY",
            "announce_url": "https://seedpool.org/announce/<PASSKEY>",
        },
        "SPD": {
            "api_key": "SPEEDAPP API KEY",
            "announce_url": "https://ramjet.speedapp.io/<PASSKEY>/announce",
        },
        "STC": {
            "api_key": "STC",
            "announce_url": "https://skipthecommericals.xyz/announce/customannounceurl",
            # "anon" : False
        },
        "THR": {
            "username": "username",
            "password": "password",
            "img_api": "get this from the forum post",
            "announce_url": "http://www.torrenthr.org/announce.php?passkey=yourpasskeyhere",
            "pronfo_api_key": "pronfo api key",
            "pronfo_theme": "pronfo theme code",
            "pronfo_rapi_id": "pronfo remote api id",
            # "anon" : False
        },
        "TIK": {
            "useAPI": False,  # Set to True if using TIK for automatic ID searching, won't work great until folder searching is added to UNIT3D API
            "api_key": "TIK api key",
            "announce_url": "https://cinematik.net/announce/",
            # "anon": False,
            # "modq": True, # Not working for now, ignored unless correct class
        },
        "TL": {
            "announce_key": "TL announce key",
        },
        "TOCA": {
            "api_key": "TOCA api key",
            "announce_url": "https://tocashare.biz/announce/customannounceurl",
            # "anon" : False
        },
        "TTG": {
            "username": "username",
            "password": "password",
            "login_question": "login_question",
            "login_answer": "login_answer",
            "user_id": "user_id",
            "announce_url": "https://totheglory.im/announce/",
            # "anon" : False
        },
        "TVC": {
            "api_key": "TVC API Key",
            "announce_url": "https://tvchaosuk.com/announce/<PASSKEY>",
            # "anon": "False"
        },
        "UHD": {
            "api_key": "UHDshare API KEY",
            "announce_url": "https://uhdshare.com/announce/<PASSKEY>",
            # "anon" : False,
        },
        "ULCX": {
            "api_key": "ULCX api key",
            "announce_url": "https://upload.cx/announce/customannounceurl",
            # "anon" : False,
        },
        # "UNIT3D_TEMPLATE": {
        #    "api_key": "UNIT3D_TEMPLATE api key",
        #    "announce_url": "https://domain.tld/announce/customannounceurl",
        #    # "anon" : False,
        #    # "modq" : False  ## Not working yet
        # },
        "UTP": {
            "api_key": "UTP api key",
            "announce_url": "https://UTP/announce/customannounceurl",
            # "anon" : False
        },
        "YOINK": {
            "api_key": "YOINK api key",
            "announce_url": "https://yoinked.org/announce/customannounceurl",
            # "anon" : "False"
        },
        "YUS": {
            "api_key": "YUS api key",
            "announce_url": "https://yu-scene.net/announce/customannounceurl",
            # "anon" : "False"
        },
    },

    # enable_search to True will automatically try and find a suitable hash to save having to rehash when creating torrents
    # If you find issue, especially in local/remote path mapping, use the "--debug" argument to print out some related details
    "TORRENT_CLIENTS": {
        # Name your torrent clients here, for example, this example is named "Client1" and is set as default_torrent_client above
        # All options relate to the webui, make sure you have the webui secured if it has WAN access
        # **DO NOT** modify torrent_client name, eg: "qbit"
        # See https://github.com/Audionut/Upload-Assistant/wiki
        "Client1": {
            "torrent_client": "qbit",
            "enable_search": True,
            "qbit_url": "http://127.0.0.1",
            "qbit_port": "8080",
            "qbit_user": "username",
            "qbit_pass": "password",
            # only set qBitTorrent torrent_storage_dir if API searching does not work
            # "torrent_storage_dir": "path/to/BT_backup folder"  ## use double-backslash on windows eg: "C:\\client\\backup"

            # here you can chose to use either symbolic or hard links, or leave uncommented to use original path
            # this will disable any automatic torrent management if set
            # use either "symlink" or "hardlink"
            # on windows, symlinks needs admin privs, hardlinks need ntfs/refs filesytem (and same drive)
            # "linking": "symlink",

            # A folder or list of folders that will contain the linked content
            # if using hardlinking, the linked folder must be on the same drive/volume as the original contnt,
            # with UA mapping the correct location if multiple paths are specified.
            # Use local paths, remote path mapping will be handled.
            # "linked_folder": ["D:\\MY_UA_LINKS", "E:\\MY_OTHER_UA_LINKS"]


            # Remote path mapping (docker/etc.) CASE SENSITIVE
            # "local_path": "/LocalPath",
            # "remote_path": "/RemotePath"
        },
        "qbit_sample": {
            "torrent_client": "qbit",
            "enable_search": True,
            "qbit_url": "http://127.0.0.1",
            "qbit_port": "8080",
            "qbit_user": "username",
            "qbit_pass": "password",
            # "torrent_storage_dir": "path/to/BT_backup folder"
            # "qbit_tag": "tag",
            # "qbit_cat": "category"
            # "use_tracker_as_tag": False,

            # Content Layout for adding .torrents: "Original"(recommended)/"Subfolder"/"NoSubfolder"
            "content_layout": "Original"

            # Enable automatic torrent management if listed path(s) are present in the path
            # Linking does not work with ATM. ATM will be disbaled if linking is enabled.
            # If using remote path mapping, use remote path
            # For using multiple paths, use a list ["path1", "path2"]
            # "automatic_management_paths" : ""
            # Remote path mapping (docker/etc.) CASE SENSITIVE
            # "local_path" : "E:\\downloads\\tv",
            # "remote_path" : "/remote/downloads/tv"

            # Set to False to skip verify certificate for HTTPS connections; for instance, if the connection is using a self-signed certificate.
            # "VERIFY_WEBUI_CERTIFICATE" : True
        },

        "rtorrent_sample": {
            "torrent_client": "rtorrent",
            "rtorrent_url": "https://user:password@server.host.tld:443/username/rutorrent/plugins/httprpc/action.php",
            # "torrent_storage_dir" : "path/to/session folder",
            # "rtorrent_label" : "Add this label to all uploads"

            # "linking": "hardlink",  # use either "symlink" or "hardlink"
            # "linked_folder": ["/path/to/linked/folder", "/path/to/other/linked/folder"]

            # Remote path mapping (docker/etc.) CASE SENSITIVE
            # "local_path" : "/LocalPath",
            # "remote_path" : "/RemotePath"

        },
        "deluge_sample": {
            "torrent_client": "deluge",
            "deluge_url": "localhost",
            "deluge_port": "8080",
            "deluge_user": "username",
            "deluge_pass": "password",
            # "torrent_storage_dir" : "path/to/session folder",

            # Remote path mapping (docker/etc.) CASE SENSITIVE
            # "local_path" : "/LocalPath",
            # "remote_path" : "/RemotePath"
        },

        "transmission_sample": {
            "torrent_client": "transmission",
            "transmission_protocol": "http",  # http or https
            "transmission_username": "username",
            "transmission_password": "password",
            "transmission_host": "localhost",
            "transmission_port": 9091,

            # "transmission_path" : "/transmission/rpc"
            # "torrent_storage_dir" : "path/to/config/torrents folder",
            # "transmission_label" : "Add this label to all uploads"

            # Remote path mapping (docker/etc.) CASE SENSITIVE
            # "local_path" : "/LocalPath",
            # "remote_path" : "/RemotePath"
        },

        "watch_sample": {
            "torrent_client": "watch",
            "watch_folder": "/Path/To/Watch/Folder"
        },

    },

    "DISCORD": {
        "discord_bot_token": "discord bot token",
        "discord_bot_description": "L4G's Upload Assistant",
        "command_prefix": "!",
        "discord_channel_id": "discord channel id for use",
        "admin_id": "your discord user id",

        "search_dir": "Path/to/downloads/folder/   this is used for search",
        # Alternatively, search multiple folders:
        # "search_dir" : [
        #   "/downloads/dir1",
        #   "/data/dir2",
        # ]
        "discord_emojis": {
            "BLU": "💙",
            "BHD": "🎉",
            "AITHER": "🛫",
            "STC": "📺",
            "ACM": "🍙",
            "MANUAL": "📩",
            "UPLOAD": "✅",
            "CANCEL": "🚫"
        }
    }
}
