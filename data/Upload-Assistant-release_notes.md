v6.1.0

## RELEASE NOTES
 - Some large refactoring of description type handling for some sites, to speed the upload process.
 - The actual ffmpeg process now respects "process_limit" set via config.py.
 - The author has seen some issues with latest ffmpeg versions. August based releases work fine here.

## New config options - see example.py
 - "prefer_max_16_torrent" which will choose an 16 MiB torrent or lower when finding a suitable existing torrent file to use.
 - "full_mediainfo" in some tracker sections, to choose whether to use the full mediainfo or not.
