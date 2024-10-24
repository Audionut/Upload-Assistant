config = {
    "DEFAULT": {

        # ------ READ THIS ------
        # Any lines starting with the # symbol are commented and will not be used.
        # If you change any of these options, remove the #
        # -----------------------

        "tmdb_api": "tmdb_api key",
        "imgbb_api": "imgbb api key",
        "ptpimg_api": "ptpimg api key",
        "lensdump_api": "lensdump api key",
        "ptscreens_api": "ptscreens api key",
        "oeimg_api": "oeimg api key",

        # Order of image hosts, and backup image hosts
        "img_host_1": "imgbb",
        "img_host_2": "ptpimg",
        "img_host_3": "imgbox",
        "img_host_4": "pixhost",
        "img_host_5": "lensdump",
        "img_host_6": "ptscreens",
        "img_host_7": "oeimg",

        # Number of screenshots to capture
        "screens": "6",

        # Providing the option to change the size of the thumbnails where supported, default is 350
        "thumbnail_size": "350",

        # Providing the option to add a header, in bbcode, above the screenshot section where supported
        # "screenshot_header": "[centers] SCREENSHOTS [/center]"

        # Enable lossless PNG Compression (True/False)
        "optimize_images": True,

        # Use only half available CPU cores to avoid memory allocation errors
        # Only when usig lossless compression
        "shared_seedbox": False,

        # The name of your default torrent client, set in the torrent client sections below
        "default_torrent_client": "Client1",

        # Play the bell sound effect when asking for confirmation
        "sfx_on_prompt": True,

        # Run an API search after upload to find the permalink and insert as comment in torrent
        # Needs a 5 second wait to ensure the API is updated
        "get_permalink": False,

    },

    "TRACKERS": {
        # Which trackers do you want to upload to?
        # Available tracker: BLU, BHD, AITHER, STC, STT, SN, THR, R4E, HP, ACM, PTP, LCD, LST, PTER, NBL, ANT, MTV, CBR, RTF, HUNO, BHDTV, LT, PTER, TL, TDC, HDT, OE, RF, OTW, FNP, UTP, AL, HDB, TIK, PSS, ULCX
        # Remove the trackers from the default_trackers list that are not used, to save being asked everytime
        "default_trackers": "BLU, BHD, AITHER, STC, STT, SN, THR, R4E, HP, ACM, PTP, LCD, LST, PTER, NBL, ANT, MTV, CBR, RTF, HUNO, BHDTV, LT, PTER, TL, TDC, HDT, OE, RF, OTW, FNP, UTP, AL, HDB, TIK, PSS, ULCX",

        "BLU": {
            "useAPI": False,  # Set to True if using BLU
            "api_key": "BLU api key",
            "announce_url": "https://blutopia.cc/announce/customannounceurl",
            # "anon" : False,
            # "modq" : False  ## Not working yet
        },
        "BHD": {
            "api_key": "BHD api key",
            "announce_url": "https://beyond-hd.me/announce/customannounceurl",
            "draft_default": "True",
            # "anon" : False
        },
        "BHDTV": {
            "api_key": "found under https://www.bit-hdtv.com/my.php",
            "announce_url": "https://trackerr.bit-hdtv.com/announce",
            # passkey found under https://www.bit-hdtv.com/my.php
            "my_announce_url": "https://trackerr.bit-hdtv.com/passkey/announce",
            # "anon" : "False"
        },
        "PTP": {
            "useAPI": False,  # Set to True if using PTP
            "add_web_source_to_desc": True,
            "ApiUser": "ptp api user",
            "ApiKey": 'ptp api key',
            "username": "",
            "password": "",
            "announce_url": ""
        },
        "AITHER": {
            "useAPI": False,  # Set to True if using Aither
            "api_key": "AITHER api key",
            "announce_url": "https://aither.cc/announce/customannounceurl",
            # "anon" : False,
            # "modq" : False  ## Not working yet
        },
        "R4E": {
            "api_key": "R4E api key",
            "announce_url": "https://racing4everyone.eu/announce/customannounceurl",
            # "anon" : False
        },
        "HUNO": {
            "api_key": "HUNO api key",
            "announce_url": "https://hawke.uno/announce/customannounceurl",
            # "anon" : False
        },
        "MTV": {
            'api_key': 'get from security page',
            'username': '<USERNAME>',
            'password': '<PASSWORD>',
            'announce_url': "get from https://www.morethantv.me/upload.php",
            'anon': False,
            # 'otp_uri' : 'OTP URI, read the following for more information https://github.com/google/google-authenticator/wiki/Key-Uri-Format'
        },
        "STC": {
            "api_key": "STC",
            "announce_url": "https://skipthecommericals.xyz/announce/customannounceurl",
            # "anon" : False
        },
        "STT": {
            "api_key": "STC",
            "announce_url": "https://stt.xyz/announce/customannounceurl",
            # "anon" : False
        },
        "SN": {
            "api_key": "SN",
            "announce_url": "https://tracker.swarmazon.club:8443/<YOUR_PASSKEY>/announce",
        },
        "HP": {
            "api_key": "HP",
            "announce_url": "https://hidden-palace.net/announce/customannounceurl",
            # "anon" : False
        },
        "ACM": {
            "api_key": "ACM api key",
            "announce_url": "https://asiancinema.me/announce/customannounceurl",
            # "anon" : False,

            # FOR INTERNAL USE ONLY:
            # "internal" : True,
            # "internal_groups" : ["What", "Internal", "Groups", "Are", "You", "In"],
        },
        "NBL": {
            "api_key": "NBL api key",
            "announce_url": "https://nebulance.io/customannounceurl",
        },
        "ANT": {
            "api_key": "ANT api key",
            "announce_url": "https://anthelion.me/announce/customannounceurl",
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
        "LCD": {
            "api_key": "LCD api key",
            "announce_url": "https://locadora.cc/announce/customannounceurl",
            # "anon" : False
        },
        "CBR": {
            "api_key": "CBR api key",
            "announce_url": "https://capybarabr.com/announce/customannounceurl",
            # "anon" : False
        },
        "LST": {
            "useAPI": False,  # Set to True if using LST
            "api_key": "LST api key",
            "announce_url": "https://lst.gg/announce/customannounceurl",
            # "anon" : False,
            # "modq" : False,
            # "draft" : False
        },
        "LT": {
            "api_key": "LT api key",
            "announce_url": "https://lat-team.com/announce/customannounceurl",
            # "anon" : False
        },
        "PTER": {
            "passkey": 'passkey',
            "img_rehost": False,
            "username": "",
            "password": "",
            "ptgen_api": "",
            "anon": True,
        },
        "TL": {
            "announce_key": "TL announce key",
        },
        "TDC": {
            "api_key": "TDC api key",
            "announce_url": "https://thedarkcommunity.cc/announce/customannounceurl",
            # "anon" : "False"
        },
        "HDT": {
            "username": "username",
            "password": "password",
            "my_announce_url": "https://hdts-announce.ru/announce.php?pid=<PASS_KEY/PID>",
            # "anon" : "False"
            "announce_url": "https://hdts-announce.ru/announce.php",  # DO NOT EDIT THIS LINE
        },
        "OE": {
            "useAPI": False,  # Set to True if using OE
            "api_key": "OE api key",
            "announce_url": "https://onlyencodes.cc/announce/customannounceurl",
            # "anon" : False
        },
        "RTF": {
            "username": "username",
            "password": "password",
            "api_key": 'get_it_by_running_/api/ login command from https://retroflix.club/api/doc',
            "announce_url": "get from upload page",
            "anon": True
        },
        "RF": {
            "api_key": "RF api key",
            "announce_url": "https://reelflix.xyz/announce/customannounceurl",
            # "anon" : False
        },
        "OTW": {
            "api_key": "OTW api key",
            "announce_url": "https://oldtoons.world/announce/customannounceurl",
            # "anon" : False
        },
        "FNP": {
            "api_key": "FNP api key",
            "announce_url": "https://fearnopeer.com/announce/customannounceurl",
            # "anon" : "False"
        },
        "UTP": {
            "api_key": "UTP api key",
            "announce_url": "https://UTP/announce/customannounceurl",
            # "anon" : False
        },
        "AL": {
            "api_key": "AL api key",
            "announce_url": "https://animelovers.club/announce/customannounceurl",
            # "anon" : False
        },
        "HDB": {
            "useAPI": False,
            "username": "HDB username",
            "passkey": "HDB passkey",
            "announce_url": "https://hdbits.org/announce/Custom_Announce_URL",
            "anon": False,
        },
        "SHRI": {
            "api_key": "SHRI api key",
            "announce_url": "https://shareisland.org/announce/customannounceurl",
            # "anon" : "False"
        },
        "SPD": {
            "api_key": "SPEEDAPP API KEY",
            "announce_url": "https://ramjet.speedapp.io/<PASSKEY>/announce",
            # "anon" : "False"
        },
        "TIK": {
            "useAPI": False,  # Set to True if using TIK
            "api_key": "",
            "announce_url": "https://cinematik.net/announce/",
            "anon": False,
            "modq": True,
        },
        "TVC": {
            "api_key": "TVC API Key",
            "announce_url": "https://tvchaosuk.com/announce/<PASSKEY>",
            "anon" : "False"
        },
        "PSS": {
            "api_key": "PSS api key",
            "announce_url": "https://privatesilverscreen.cc/announce/customannounceurl",
            # "anon" : False
        },
        "ULCX": {
            "api_key": "ULCX api key",
            "announce_url": "https://upload.cx/announce/customannounceurl",
            # "anon" : False,
        },
        "MANUAL": {
            # Uncomment and replace link with filebrowser (https://github.com/filebrowser/filebrowser) link to the Upload-Assistant directory, this will link to your filebrowser instead of uploading to uguu.se
            # "filebrowser" : "https://domain.tld/filebrowser/files/Upload-Assistant/"
        },
    },

    # enable_search to True will automatically try and find a suitable hash to save having to rehash when creating torrents
    # Should use the qbit API, but will also use the torrent_storage_dir to find suitable hashes
    # If you find issue, use the "--debug" argument to print out some related details
    "TORRENT_CLIENTS": {
        # Name your torrent clients here, for example, this example is named "Client1" and is set as default_torrent_client above
        # All options relate to the webui, make sure you have the webui secured if it has WAN access
        # See https://github.com/Audionut/Upload-Assistant/wiki
        "Client1": {
            "torrent_client": "qbit",
            # "enable_search": True,
            "qbit_url": "http://127.0.0.1",
            "qbit_port": "8080",
            "qbit_user": "username",
            "qbit_pass": "password",
            # "torrent_storage_dir": "path/to/BT_backup folder"  ## use double-backslash on windows eg: "C:\\client\\backup"

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

            # Content Layout for adding .torrents: "Original"(recommended)/"Subfolder"/"NoSubfolder"
            "content_layout": "Original"

            # Enable automatic torrent management if listed path(s) are present in the path
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
