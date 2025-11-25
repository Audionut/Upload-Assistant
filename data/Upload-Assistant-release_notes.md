v6.2.0

## RELEASE NOTES
 - New site support - ImmortalSeed, Emuwarez.
 - New modules required, update with requirements.txt.
 - Linux specific mediainfo binaries for DVD support. Uninstall existing 'pymediainfo' before running requirements.txt.
 - Removed oxipng support, using ffmpeg based compression instead.
 - TVDB for all.
 - Refactored cookie/site validation processing, to speed processing.
 - New feature, site checking. Use as 'python3 upload.py "path_to_movie_folder" --queue a_queue_name -sc -ua'. Append trackers as needed. You can also append '-req' (or config option). This will find all matching content from the input directory, that can be uploaded to each tracker (and list any request). Log files for each tracker will be created in the UA tmp directory.
 - Alternatively, you can remove '-sc' from the above example, and let UA just upload content from the input directory instead of logging. You may wish to append '-lq' with a numeric value to limit the amount of successful uploads processed.

## New config options - see example.py
 - Multiple client searching for existing torrent files.
 - Specific injection client.
 - ffmpeg based compression option.
