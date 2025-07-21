config = {
    "DEFAULT": {
        # will print a notice if an update is available
        "update_notification": True,
        # will print the changelog if an update is available
        "verbose_notification": False,

        # tmdb api key **REQUIRED**
        # visit "https://www.themoviedb.org/settings/api" copy api key and insert below
        "tmdb_api": "",

        # tvdb api key
        # visit "https://www.thetvdb.com/dashboard/account/apikey" copy api key and insert below
        "tvdb_api": "",

        # visit "https://thetvdb.github.io/v4-api/#/Login/post_login" enter api key, generate token and insert token below
        # the pin in the login form is not needed (don't modify), only enter your api key
        "tvdb_token": "",

        # btn api key used to get details from btn
        "btn_api": "",

        # Order of image hosts. primary host as first with others as backup
        # Available image hosts: imgbb, ptpimg, imgbox, pixhost, lensdump, ptscreens, onlyimage, dalexni, zipline, passtheimage
        "img_host_1": "",
        "img_host_2": "",
        "img_host_3": "",
        "img_host_4": "",
        "img_host_5": "",

        # image host api keys
        "imgbb_api": "",
        "ptpimg_api": "",
        "lensdump_api": "",
        "ptscreens_api": "",
        "onlyimage_api": "",
        "dalexni_api": "",
        "passtheima_ge_api": "",
        # custom zipline url
        "zipline_url": "",
        "zipline_api_key": "",

        # Whether to add a logo for the show/movie from TMDB to the top of the description
        "add_logo": False,

        # Logo image size
        "logo_size": "300",

        # logo language (ISO 639-1) - default is 'en' (English)
        # If a logo with this language cannot be found, English will be used instead
        "logo_language": "",

        # set true to add episode overview to description
        "episode_overview": False,

        # Number of screenshots to capture
        "screens": "4",

        # Number of cutoff screenshots
        # If there are at least this many screenshots already, perhaps pulled from existing
        # description, skip creating and uploading any further screenshots.
        "cutoff_screens": "4",

        # Providing the option to change the size of the screenshot thumbnails where supported.
        # Default is 350, ie [img=350]
        "thumbnail_size": "350",

        # Number of screenshots per row in the description. Default is single row.
        # Only for sites that use common description for now
        "screens_per_row": "",

        # Overlay Frame number/type and "Tonemapped" if applicable to screenshots
        "frame_overlay": False,

        # Overlay text size (scales with resolution)
        "overlay_text_size": "18",

        # Tonemap HDR - DV+HDR screenshots
        "tone_map": True,

        # Tonemap screenshots with the following settings
        # See https://ayosec.github.io/ffmpeg-filters-docs/7.1/Filters/Video/tonemap.html
        "algorithm": "mobius",
        "desat": "10.0",

        # Add this header above screenshots in description when screens have been tonemapped (in bbcode)
        "tonemapped_header": "[center][code] Screenshots have been tonemapped for reference [/code][/center]",

        # MULTI PROCESSING
        # The optimization task is resource intensive.
        # The final value used will be the lowest value of either 'number of screens'
        # or this value. Recommended value is enough to cover your normal number of screens.
        # If you're on a shared seedbox you may want to limit this to avoid hogging resources.
        "process_limit": "4",

        # When optimizing images, limit to this many threads spawned by each process above.
        # Recommended value is the number of logical processesors on your system.
        # This is equivalent to the old shared_seedbox setting, however the existing process
        # only used a single process. You probably need to limit this to 1 or 2 to avoid hogging resources.
        "threads": "10",

        # Set true to limit the amount of CPU when running ffmpeg.
        "ffmpeg_limit": False,

        # Number of screenshots to use for each (ALL) disc/episode when uploading packs to supported sites.
        # 0 equals old behavior where only the original description and images are added.
        # This setting also affects PTP, however PTP requries at least 2 images for each.
        # PTP will always use a *minimum* of 2, regardless of what is set here.
        "multiScreens": "2",

        # The next options for packed content do not effect PTP. PTP has a set standard.
        # When uploading packs, you can specifiy a different screenshot thumbnail size, default 300.
        "pack_thumb_size": "300",

        # Description character count (including bbcode) cutoff for UNIT3D sites when **season packs only**.
        # After hitting this limit, only filenames and screenshots will be used for any ADDITIONAL files
        # still to be added to the description. You can set this small like 50, to only ever
        # print filenames and screenshots for each file, no mediainfo will be printed.
        # UNIT3D sites have a hard character limit for descriptions. A little over 17000
        # worked fine in a forum post at AITHER. If the description is at 1 < charLimit, the next full
        # description will be added before respecting this cutoff.
        "charLimit": "14000",

        # How many files in a season pack will be added to the description before using an additional spoiler tag.
        # Any other files past this limit will be hidden/added all within a spoiler tag.
        "fileLimit": "2",

        # Absolute limit on processed files in packs.
        # You might not want to process screens/mediainfo for 40 episodes in a season pack.
        "processLimit": "10",

        # Providing the option to add a description header, in bbcode, at the top of the description section
        # where supported
        "custom_description_header": "",

        # Providing the option to add a header, in bbcode, above the screenshot section where supported
        "screenshot_header": "",

        # Enable lossless PNG Compression (True/False)
        "optimize_images": True,

        # Which client are you using.
        "default_torrent_client": "qbittorrent",

        # Play the bell sound effect when asking for confirmation
        "sfx_on_prompt": True,

        # How many trackers need to pass successfull checking to continue with the upload process
        # Default = 1. If 1 (or more) tracker/s pass banned_group, content and dupe checking, uploading will continue
        # If less than the number of trackers pass the checking, exit immediately.
        "tracker_pass_checks": "1",

        # Set to true to always just use the largest playlist on a blu-ray, without selection prompt.
        "use_largest_playlist": False,

        # Set False to skip getting images from tracker descriptions
        "keep_images": True,

        # set true to only grab meta id's from trackers, not descriptions
        "only_id": False,

        # set true to use sonarr for tv show searching
        "use_sonarr": False,
        "sonarr_url": "http://localhost:8989",
        "sonarr_api_key": "",

        # details for a second sonarr instance
        # additional sonarr instances can be added by adding more sonarr_url_x and sonarr_api_key_x entries
        "sonarr_url_1": "http://my-second-instance:8989",
        "sonarr_api_key_1": "",

        # set true to use radarr for movie searching
        "use_radarr": False,
        "radarr_url": "http://localhost:7878",
        "radarr_api_key": "",

        # details for a second radarr instance
        # additional radarr instances can be added by adding more radarr_url_x and radarr_api_key_x entries
        "radarr_url_1": "http://my-second-instance:7878",
        "radarr_api_key_1": "",

        # set true to use mkbrr for torrent creation
        "mkbrr": True,

        # set true to use argument overrides from data/templates/user-args.json
        "user_overrides": False,

        # set true to skip automated client torrent searching
        # this will search qbittorrent clients for matching torrents
        # and use found torrent id's for existing hash and site searching
        'skip_auto_torrent': False,

        # If there is no region/distributor ids specified, we can use existing torrents to check
        # This will use data from matching torrents in qBitTorrent/RuTorrent to find matching site ids
        # and then try and find region/distributor ids from those sites
        # Requires "skip_auto_torrent" to be set to False
        "ping_unit3d": False,

        # If processing a bluray disc, get bluray information from bluray.com
        # This will set region and distribution info
        # Must have imdb id to work
        "get_bluray_info": False,

        # Add bluray.com link to description
        # Requires "get_bluray_info" to be set to True
        "add_bluray_link": False,

        # Add cover/back/slip images from bluray.com to description if available
        # Requires "get_bluray_info" to be set to True
        "use_bluray_images": False,

        # Size of bluray.com cover images.
        # bbcode is width limited, cover images are mostly hight dominant
        # So you probably want a smaller size than screenshots for instance
        "bluray_image_size": "250",

        # A release with 100% score will have complete matching details between bluray.com and bdinfo
        # Each missing Audio OR Subtitle track will reduce the score by 5
        # Partial matched audio tracks have a 2.5 score penalty
        # If only a single bdinfo audio/subtitle track, penalties are doubled
        # Video codec/resolution and disc size mismatches have huge penalities
        # Only useful in unattended mode. If not unattended you will be prompted to confirm release
        # Final score must be greater than this value to be considered a match
        "bluray_score": 94.5,

        # If there is only a single release on bluray.com, you may wish to relax the score a little
        "bluray_single_score": 89.5,

        # NOT RECOMMENDED UNLESS YOU KNOW WHAT YOU ARE DOING
        # set true to not delete existing meta.json file before running
        "keep_meta": False,

        # Set true to print the tracker api messages from uploads
        "print_tracker_messages": False,

        # Whether or not to print direct torrent links for the uploaded content
        "print_tracker_links": True,

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
        # Available tracker: ACM, AITHER, AL, ANT, AR, ASC, BHD, BHDTV, BLU, BT, CBR, DC, DP, FNP, FRIKI, HDB, HDS, HDT, HHD, HUNO, ITT, LCD, LDU, LST, LT, MTV, NBL, OE, OTW, PSS, PT, PTER, PTP, PTT, R4E, RAS, RF, RTF, SAM, SN, STC, THR, TIK, TL, TOCA, UHD, ULCX, UTP, YOINK, YUS
        # Only add the trackers you want to upload to on a regular basis
        "default_trackers": "",

        "ACM": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://eiga.moi/announce/customannounceurl",
            "anon": False,
        },
        "AITHER": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            # "useAPI": False,  Set to True if using this tracker for automatic ID searching or description parsing
            "useAPI": False,
            "api_key": "",
            "announce_url": "https://aither.cc/announce/customannounceurl",
            "anon": False,
            # Send uploads to Aither modq for staff approval
            "modq": False,
        },
        "AL": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://animelovers.club/announce/customannounceurl",
            "anon": False,
        },
        "ANT": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://anthelion.me/announce/customannounceurl",
            "anon": False,
        },
        "AR": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            # anon is not an option when uploading you need to change your privacy settings.
            "username": "",
            "password": "",
            "announce_url": "http://tracker.alpharatio.cc:2710/PASSKEY/announce",
        },
        "ASC": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            # Set uploader_status to True if you have uploader permissions to automatically approve your uploads
            "uploader_status": False,
            # The custom layout default is 2
            # If you have a custom layout, you'll need to inspect the element on the upload page to find the correct layout value
            # Don't change it unless you know what you're doing
            "custom_layout": '2',
            # anon is not an option when uploading to ASC
            # for ASC to work you need to export cookies from https://cliente.amigos-share.club/ using https://addons.mozilla.org/en-US/firefox/addon/export-cookies-txt/
            # cookies need to be in netscape format and need to be in data/cookies/ASC.txt
            "announce_url": "https://amigos-share.club/announce.php?passkey=PASSKEY",
        },
        "BHD": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            # "useAPI": False,  Set to True if using this tracker for automatic ID searching or description parsing
            "useAPI": False,
            "api_key": "",
            "bhd_rss_key": "",
            "announce_url": "https://beyond-hd.me/announce/customannounceurl",
            # Send uploads to BHD drafts
            "draft_default": "False",
            "anon": False,
        },
        "BHDTV": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "found under https://www.bit-hdtv.com/my.php",
            "announce_url": "https://trackerr.bit-hdtv.com/announce",
            # passkey found under https://www.bit-hdtv.com/my.php
            "my_announce_url": "https://trackerr.bit-hdtv.com/passkey/announce",
            "anon": False,
        },
        "BLU": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            # "useAPI": False,  Set to True if using this tracker for automatic ID searching or description parsing
            "useAPI": False,
            "api_key": "",
            "announce_url": "https://blutopia.cc/announce/customannounceurl",
            "anon": False,
        },
        "BT": {
            "link_dir_name": "",
            # for BT to work you need to export cookies from https://brasiltracker.org/ using https://addons.mozilla.org/en-US/firefox/addon/export-cookies-txt/.
            # cookies need to be in netscape format and need to be in data/cookies/BT.txt
            "announce_url": "https://t.brasiltracker.org/<PASSKEY>/announce",
            "anon": False,
        },
        "CBR": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://capybarabr.com/announce/customannounceurl",
            "anon": False,
            # Send uploads to CBR modq for staff approval
            "modq": False,
        },
        "DC": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "username": "",
            "password": "",
            "announce_url": "https://digitalcore.club/tracker.php/<PASSKEY>/announce",
            "anon": False,
        },
        "DP": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://darkpeers.org/announce/customannounceurl",
            "anon": False,
            # Send uploads to DP modq for staff approval
            "modq": False,
        },
        "FL": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "username": "",
            "passkey": "",
            "uploader_name": "https://filelist.io/Custom_Announce_URL",
            "anon": False,
        },
        "FNP": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://fearnopeer.com/announce/customannounceurl",
            "anon": False,
        },
        "FRIKI": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://frikibar.com/announce/<PASSKEY>",
        },
        "HDB": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            # "useAPI": False,  Set to True if using this tracker for automatic ID searching or description parsing
            "useAPI": False,
            # for HDB you **MUST** have been granted uploading approval via Offers, you've been warned
            # for HDB to work you need to export cookies from https://hdbits.org/ using https://addons.mozilla.org/en-US/firefox/addon/export-cookies-txt/.
            # cookies need to be in netscape format and need to be in data/cookies/HDB.txt
            "username": "",
            "passkey": "",
            "announce_url": "https://hdbits.org/announce/Custom_Announce_URL",
            "img_rehost": True,
        },
        "HDS": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            # for HDS to work you need to export cookies from https://hd-space.org/ using https://addons.mozilla.org/en-US/firefox/addon/export-cookies-txt/.
            # cookies need to be in netscape format and need to be in data/cookies/HDS.txt
            "announce_url": "http://hd-space.pw/announce.php?pid=<PASSKEY>",
            "anon": False,
        },
        "HDT": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            # for HDT to work you need to export cookies from https://hd-torrent.net/ using https://addons.mozilla.org/en-US/firefox/addon/export-cookies-txt/.
            # cookies need to be in netscape format and need to be in data/cookies/HDT.txt
            "username": "",
            "password": "",
            "my_announce_url": "https://hdts-announce.ru/announce.php?pid=<PASS_KEY/PID>",
            "anon": False,
            # DO NOT EDIT THIS LINE
            "announce_url": "https://hdts-announce.ru/announce.php",
        },
        "HHD": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://homiehelpdesk.net/announce/customannounceurl",
            "anon": False,
        },
        "HUNO": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "useAPI": False,
            "api_key": "",
            "announce_url": "https://hawke.uno/announce/customannounceurl",
            "anon": False,
        },
        "ITT": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://itatorrents.xyz/announce/customannounceurl",
            "anon": False,
        },
        "LCD": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://locadora.cc/announce/customannounceurl",
            "anon": False,
        },
        "LDU": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://theldu.to/announce/customannounceurl",
            "anon": False,
        },
        "LST": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            # "useAPI": False,  Set to True if using this tracker for automatic ID searching or description parsing
            "useAPI": False,
            "api_key": "",
            "announce_url": "https://lst.gg/announce/customannounceurl",
            "anon": False,
            # Send uploads to LST modq for staff approval
            "modq": False,
            # Send uploads to LST drafts
            "draft": False,
        },
        "LT": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://lat-team.com/announce/customannounceurl",
            "anon": False,
        },
        "MTV": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            'api_key': 'get from security page',
            'username': '',
            'password': '',
            'announce_url': "get from https://www.morethantv.me/upload.php",
            'anon': False,
            # read the following for more information https://github.com/google/google-authenticator/wiki/Key-Uri-Format
            'otp_uri': 'OTP URI,',
            # Skip uploading to MTV if it would require a torrent rehash because existing piece size > 8 MiB
            'skip_if_rehash': False,
            # Iterate over found torrents and prefer MTV suitable torrents if found.
            'prefer_mtv_torrent': False,
        },
        "NBL": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://tracker.nebulance.io/insertyourpasskeyhere/announce",
        },
        "OE": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            # "useAPI": False,  Set to True if using this tracker for automatic ID searching or description parsing
            "useAPI": False,
            "api_key": "",
            "announce_url": "https://onlyencodes.cc/announce/customannounceurl",
            "anon": False,
        },
        "OTW": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://oldtoons.world/announce/customannounceurl",
            # Send uploads to OTW modq for staff approval
            "modq": False,
            "anon": False,
        },
        "PT": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://portugas.org/announce/customannounceurl",
            "anon": False,
        },
        "PSS": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://privatesilverscreen.cc/announce/customannounceurl",
            "anon": False,
        },
        "PTER": {  # Does not appear to be working at all
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "passkey": 'passkey',
            "img_rehost": False,
            "username": "",
            "password": "",
            "ptgen_api": "",
            "anon": True,
        },
        "PTP": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            # "useAPI": False,  Set to True if using this tracker for automatic ID searching or description parsing
            "useAPI": False,
            "add_web_source_to_desc": True,
            "ApiUser": "ptp api user",
            "ApiKey": 'ptp api key',
            "username": "",
            "password": "",
            "announce_url": "",
        },
        "PTT": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://polishtorrent.top/announce/customannounceurl",
            "anon": False,
        },
        "R4E": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://racing4everyone.eu/announce/customannounceurl",
            "anon": False,
        },
        "RAS": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://rastastugan.org/announce/customannounceurl",
            "anon": False,
        },
        "RF": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://reelflix.xyz/announce/customannounceurl",
            "anon": False,
        },
        "RTF": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "username": "",
            "password": "",
            # get_it_by_running_/api/ login command from https://retroflix.club/api/doc
            "api_key": '',
            "announce_url": "get from upload page",
            "anon": True,
        },
        "SAM": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://samaritano.cc/announce/<PASSKEY>",
            "anon": False,
        },
        "SHRI": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://shareisland.org/announce/customannounceurl",
            "anon": False,
        },
        "SN": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://tracker.swarmazon.club:8443/<YOUR_PASSKEY>/announce",
        },
        "SP": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://seedpool.org/announce/<PASSKEY>",
        },
        "SPD": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://ramjet.speedapp.io/<PASSKEY>/announce",
        },
        "STC": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://skipthecommericals.xyz/announce/customannounceurl",
            "anon": False,
        },
        "THR": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "username": "",
            "password": "",
            "img_api": "get this from the forum post",
            "announce_url": "http://www.torrenthr.org/announce.php?passkey=yourpasskeyhere",
            "pronfo_api_key": "",
            "pronfo_theme": "pronfo theme code",
            "pronfo_rapi_id": "pronfo remote api id",
            "anon": False,
        },
        "TIK": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://cinematik.net/announce/",
            "anon": False,
        },
        "TL": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            # Set to False if you don't have access to the API (e.g., if you're a trial uploader). Note: this may not work sometimes due to Cloudflare restrictions.
            # If you are not going to use the API, you will need to export cookies from https://www.torrentleech.org/ using https://addons.mozilla.org/en-US/firefox/addon/export-cookies-txt/.
            # cookies need to be in netscape format and need to be in data/cookies/TL.txt
            "api_upload": True,
            "announce_key": "TL announce key",
        },
        "TOCA": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://tocashare.biz/announce/customannounceurl",
            "anon": False,
        },
        "TTG": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "username": "",
            "password": "",
            "login_question": "",
            "login_answer": "",
            "user_id": "",
            "announce_url": "https://totheglory.im/announce/",
            "anon": False,
        },
        "TVC": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://tvchaosuk.com/announce/<PASSKEY>",
            "anon": False,
        },
        "UHD": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://uhdshare.com/announce/<PASSKEY>",
            "anon": False,
        },
        "ULCX": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            # "useAPI": False,  Set to True if using this tracker for automatic ID searching or description parsing
            "useAPI": False,
            "api_key": "",
            "announce_url": "https://upload.cx/announce/customannounceurl",
            "anon": False,
            # Send to modq for staff approval
            "modq": False,
        },
        "UTP": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://UTP/announce/customannounceurl",
            "anon": False,
        },
        "YOINK": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://yoinked.org/announce/customannounceurl",
            "anon": False,
        },
        "YUS": {
            # Instead of using the tracker acronym for folder name when sym/hard linking, you can use a custom name
            "link_dir_name": "",
            "api_key": "",
            "announce_url": "https://yu-scene.net/announce/customannounceurl",
            "anon": False,
        },
        "MANUAL": {
            # Replace link with filebrowser (https://github.com/filebrowser/filebrowser) link to the Upload-Assistant directory, this will link to your filebrowser instead of uploading to uguu.se
            "filebrowser": "",
        },
    },

    # enable_search to True will automatically try and find a suitable hash to save having to rehash when creating torrents
    # If you find issue, especially in local/remote path mapping, use the "--debug" argument to print out some related details
    "TORRENT_CLIENTS": {
        # Name your torrent clients here, for example, this example is named "qbittorrent" and is set as default_torrent_client above
        # All options relate to the webui, make sure you have the webui secured if it has WAN access
        # **DO NOT** modify torrent_client name, eg: "qbit"
        # See https://github.com/Audionut/Upload-Assistant/wiki
        "qbittorrent": {
            "torrent_client": "qbit",
            # enable_search to True will automatically try and find a suitable hash to save having to rehash when creating torrents
            "enable_search": True,
            "qbit_url": "http://127.0.0.1",
            "qbit_port": "8080",
            "qbit_user": "",
            "qbit_pass": "",
            # Use the UA tracker acronym as a tag in qBitTorrent
            "use_tracker_as_tag": False,
            "qbit_tag": "",
            "qbit_cat": "",
            "content_layout": "Original",
            # here you can chose to use either symbolic or hard links, or None to use original path
            # this will disable any automatic torrent management if set
            # use either "symlink" or "hardlink"
            # on windows, symlinks needs admin privs, both link types need ntfs/refs filesytem (and same drive)
            "linking": "",
            # Allow fallback to inject torrent into qBitTorrent using the original path
            # when linking error. eg: unsupported file system.
            "allow_fallback": True,
            # A folder or list of folders that will contain the linked content
            # if using hardlinking, the linked folder must be on the same drive/volume as the original contnt,
            # with UA mapping the correct location if multiple paths are specified.
            # Use local paths, remote path mapping will be handled.
            # only single \ on windows, path will be handled by UA
            "linked_folder": [""],
            # Remote path mapping (docker/etc.) CASE SENSITIVE
            "local_path": [""],
            "remote_path": [""],
            # only set qBitTorrent torrent_storage_dir if API searching does not work
            # use double-backslash on windows eg: "C:\\client\\backup"
            # "torrent_storage_dir": "path/to/BT_backup folder",

            # Set to False to skip verify certificate for HTTPS connections; for instance, if the connection is using a self-signed certificate.
            # "VERIFY_WEBUI_CERTIFICATE": True,
        },
        "rtorrent": {
            "torrent_client": "rtorrent",
            "rtorrent_url": "https://user:password@server.host.tld:443/username/rutorrent/plugins/httprpc/action.php",
            # path/to/session folder
            "torrent_storage_dir": "",
            "rtorrent_label": "",
            # here you can chose to use either symbolic or hard links, or leave uncommented to use original path
            # use either "symlink" or "hardlink"
            "linking": "",
            "linked_folder": [""],
            # Remote path mapping (docker/etc.) CASE SENSITIVE
            "local_path": [""],
            "remote_path": [""],
        },
        "deluge": {
            "torrent_client": "deluge",
            "deluge_url": "localhost",
            "deluge_port": "8080",
            "deluge_user": "username",
            "deluge_pass": "password",
            # path/to/session folder
            "torrent_storage_dir": "",
            # Remote path mapping (docker/etc.) CASE SENSITIVE
            "local_path": [""],
            "remote_path": [""],
        },
        "transmission": {
            "torrent_client": "transmission",
            # http or https
            "transmission_protocol": "http",
            "transmission_username": "username",
            "transmission_password": "password",
            "transmission_host": "localhost",
            "transmission_port": 9091,
            "transmission_path": "/transmission/rpc",
            #  path/to/config/torrents folder
            "torrent_storage_dir": "",
            "transmission_label": "",
            # Remote path mapping (docker/etc.) CASE SENSITIVE
            "local_path": [""],
            "remote_path": [""],
        },
        "watch": {
            "torrent_client": "watch",
            # /Path/To/Watch/Folder
            "watch_folder": "",
        },
    },
    "DISCORD": {
        # Set to True to enable Discord bot functionality
        "use_discord": False,
        # Set to True to only run the bot in unattended mode
        "only_unattended": True,
        "discord_bot_token": "",
        "discord_channel_id": "",
        "discord_bot_description": "",
        "command_prefix": "!"
    },
}
