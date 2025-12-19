# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
config = {
    "DEFAULT": {

        # WAVES HAND.........
        # This is not the config file you are looking for

        # This is the config file for github action testing only

        # will print a notice if an update is available
        "update_notification": True,
        # will print the changelog if an update is available
        "verbose_notification": False,

        # tmdb api key **REQUIRED**
        # visit "https://www.themoviedb.org/settings/api" copy api key and insert below
        "tmdb_api": "${API_KEY}",

        # tvdb api key
        # visit "https://www.thetvdb.com/dashboard/account/apikey" copy api key and insert below
        "tvdb_api": "",

        # visit "https://thetvdb.github.io/v4-api/#/Login/post_login" enter api key, generate token and insert token below
        # the pin in the login form is not needed (don't modify), only enter your api key
        "tvdb_token": "",

        # btn api key used to get details from btn
        "btn_api": "",

        # image host api keys
        "imgbb_api": "",
        "ptpimg_api": "",
        "lensdump_api": "",
        "ptscreens_api": "",
        "oeimg_api": "",
        "dalexni_api": "",
        "passtheima_ge_api": "",

        # custom zipline url
        "zipline_url": "",
        "zipline_api_key": "",

        # Order of image hosts. primary host as first with others as backup
        # Available image hosts: imgbb, ptpimg, imgbox, pixhost, lensdump, ptscreens, oeimg, dalexni, zipline, passtheimage
        "img_host_1": "imgbb",
        "img_host_2": "imgbox",

        # Whether to add a logo for the show/movie from TMDB to the top of the description
        "add_logo": True,

        # Logo image size
        "logo_size": "300",

        # logo language (ISO 639-1)
        # If a logo with this language cannot be found, en (English) will be used instead
        "logo_language": "",

        # Number of screenshots to capture
        "screens": "4",

        # Number of screenshots per row in the description. Default is single row.
        # Only for sites that use common description for now
        "screens_per_row": "",

        # Overlay Frame number/type and "Tonemapped" if applicable to screenshots
        "frame_overlay": True,

        # Overlay text size (scales with resolution)
        "overlay_text_size": "18",

        # Tonemap HDR - DV+HDR screenshots
        "tone_map": True,

        # Tonemap HDR screenshots with the following settings
        # See https://ayosec.github.io/ffmpeg-filters-docs/7.1/Filters/Video/tonemap.html
        "algorithm": "mobius",
        "desat": "10.0",

        # Add this header above screenshots in description when screens have been tonemapped (in bbcode)
        "tonemapped_header": "",

        # Number of cutoff screenshots
        # If there are at least this many screenshots already, perhaps pulled from existing
        # description, skip creating and uploading any further screenshots.
        "cutoff_screens": "4",

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
        "threads": "4",

        # Providing the option to change the size of the screenshot thumbnails where supported.
        # Default is 350, ie [img=350]
        "thumbnail_size": "350",

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

        # set true to only grab meta id's from trackers, not descriptions and images
        "only_id": False,

        # set true to use mkbrr for torrent creation
        "mkbrr": True,

        # set true to use argument overrides from data/templates/user-args.json
        "user_overrides": False,

        # set true to add episode overview to description
        "episode_overview": True,

        # set true to skip automated client torrent searching
        # this will search qbittorrent clients for matching torrents
        # and use found torrent id's for existing hash and site searching
        'skip_auto_torrent': True,

        # NOT RECOMMENDED UNLESS YOU KNOW WHAT YOU ARE DOING
        # set true to not delete existing meta.json file before running
        "keep_meta": False,

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
        "default_trackers": "TL",
        "TL": {
            "announce_key": "test",
        },
    },

    # enable_search to true will automatically try and find a suitable hash to save having to rehash when creating torrents
    # Should use the qbit API, but will also use the torrent_storage_dir to find suitable hashes
    # If you find issue, use the "--debug" command option to print out some related details
    "TORRENT_CLIENTS": {
        # Name your torrent clients here, for example, this example is named "Client1" and is set as default_torrent_client above
        # All options relate to the webui, make sure you have the webui secured if it has WAN access
        # See https://github.com/Audionut/Upload-Assistant/wiki
        "qbittorrent": {
            "torrent_client": "qbit",
            "enable_search": False,
            "qbit_url": "http://127.0.0.1",
            "qbit_port": "8080",
            "qbit_user": "",
            "qbit_pass": "",
        }
    }
}
