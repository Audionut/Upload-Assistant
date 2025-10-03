v6.0.0

## RELEASE NOTES
 - Immense thanks to @wastaken7 for refactoring the unit3d based tracker code. A huge QOL improvement that removed thousands of lines of code.
 - To signify the continued contributions by @wastaken7, this project is now know simply as "Upload Assistant".
 - New package added, run requirements.txt
 - This release contains lengthy refactoring of many code aspects. Many users, with thanks, have been testing the changes and giving feedback.
 - The version bump to v6.0.0 signifies the large code changes, and you should follow an update process suitable for yourself with a major version bump.

## New config options - see example.py
 - FFMPEG related options that may assist those having issues with screenshots.
 - AvistaZ based sites have new options in their site sections.
- "use_italian_title" inside SHRI config, for using Italian titles where available
- Some HDT related config options were updated/changed
- "check_predb" for also checking predb for scene status
- "get_bluray_info" updated to also include getting DVD data
- "qui_proxy_url" inside qbittorrent client config, for supporting qui reverse proxy url

## WHAT'S NEW - some from last release
 - New arg -sort, used for sorting filelist, to ensure UA can run with some anime folders that have allowed smaller files.
 - New arg -rtk, which can be used to process a run, removing specific trackers from your default trackers list, and processing with the remaining trackers in your default list.
 - A significant chunk of the actual upload process has been correctly asynced. Some specific site files still need to be updated and will slow the process.
 - More UNIT3D based trackers have been updated with request searching support.
 - Added support for sending applicable edition to LST api edition endpoint.
 - NoGrp type tags are not removed by default. Use "--no-tag" if desired, and/or report trackers as needed.
