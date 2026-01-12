v7.0.0

## RELEASE NOTES
 - Pushing this release as version 7, given the significant code changes.
 - Given the tvdb handling to ensure the correct data for all use cases, some content, particularly daily shows, could page many requests for the data. UA now caches multi-page tvdb data and checks this cached data before making further api requests.
 - Fixed an issue that broke ANT torrent injection in the last release.
 - Updated STC to work with site revival.
 - Removed AL
 - When uploading to any sites with specific image host requirements, UA will now find the best host to use before uploading any images.
 - Fixed an issue with unit3d based upload timeout handling. Given that UA can now run each tracker upload independently, it defers to having a longer timeout period for slow responding trackers.
 - Moved a complete season pack check into a function that always runs, instead of only when rehashing torrents. Also includes a group tag check which will warn if a season pack has different group tagged files.
 - Added Aither semi-automated trump handling, using their new api endpoint (thanks you). See further notes below.
 
 ## SECURITY
 - There have been a number of changes in the UA coding process, with the specific intent of improving security.
 - Some of the changes protect against malicious attacks that could have occurred, under quite specific circstances, such as attacks via downloaded binaries. These would likely have never occurred, but are now mitigated against.
 - It as been brought to my attention, that many users running the docker webui, having been exposing their ui to the web. You should not expose to the web unless strictly necessary.
 - I've added some basic auth, but users should put the webui behind a reverse proxy with auth management. See updated docs https://github.com/Audionut/Upload-Assistant/tree/master/docs

## CONFIG VALIDATION
- UA now performs some config validation, and gives better feedback on hard loading errors. Did you accidentally edit out a pesky little comma.....

## New config options - see example.py
 - suppress_warnings which will suppress config validation warnings.
 - Sharex image host.

## New command argument
- -ddc or --double-dupe-check, if you want to race uploads, but tend to lose, this arg will perform a secondary dupe check right before the actual upload process.
 
## Aither trump processing
- For the initial rollout, this only work in full manual mode.
- If a torrent has an existing trump report, you will not be allowed to file a new report.
- When filing a trump report, there is some manual input options, but otherwise, UA will upload your content, and automate the report of the existing torrent.
- During a dupe check, if an existing torrent is marked as trumpable, you will now have the option of filing a trump report for that torrent.
- If your upload is an exact match for an existing upload, you will have a trumpable option.
- Those options are permitted for anyone.
- If you're uploading a season pack, you will have the option to report single episodes. Aither's internal trump process will automatically select all applicable single episodes to be reported, UA only needs to pick one.
- UA will preference a single episode that has matching group tag.
- Internal release episodes cannot be trump reported by standard users. Internal groups can trump their own single episodes, with the same config used for internal uploads.
- Pay attention, you must pass a few prompts to be able to trump, so the onus is on you to only file correct reports.