v7.0.1

## RELEASE NOTES
 - Fixed a breaking bug that could validate wrong torrent files.
 - wastaken added an option to delay torrent injection, which helps for sites that take a moment to register the torrent hash.
 - Better proxy handling for the webui.
 - maksii improved the shutdown handling when running the webui.
 - UA now ships with a pre-built bdifno in docker (no more mono), and will download the matching binary for bare metal systems.

## New config options - see example.py
 - inject_delay - time in seconds to delay torrent injection. Can be set at an individual tracker level, inside of the tracker config.
