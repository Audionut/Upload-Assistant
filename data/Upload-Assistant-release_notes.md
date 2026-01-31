v7.0.0

## RELEASE NOTES
 - Pushing this release as version 7, given the significant code changes.
 - The webui have received a large overhaul, see below.
 - Given the tvdb handling to ensure the correct data for all use cases, some content, particularly daily shows, could page many requests for data. UA now caches multi-page tvdb data and checks this cached data before making further api requests.
 - Fixed an issue that broke ANT torrent injection in the last release, and wastaken has updated ANT to work with some changes.
 - Updated STC to work with site revival.
 - Removed AL
 - When uploading to any sites with specific image host requirements, UA will now find the best host to use before uploading any images.
 - Fixed an issue with unit3d based upload timeout handling. Given that UA can now run each tracker upload independently, it defers to having a longer timeout period for slow responding trackers.
 - Moved a complete season pack check into a function that always runs, instead of only running when rehashing torrents. The function now also includes a group tag check, which will warn if a season pack has different group tagged files.
 - Added Aither/LST semi-automated trump handling, using their new api endpoint (thanks both of you). See further notes below.
 - richardr1126 added arm64 support for docker.
 - CptCherry added TOS support. TOS has some specific support for using NFO files, as is required by their rules. See help for --keep-nfo
 
 ## SECURITY
 - There have been a number of changes in the UA coding process, with the specific intent of improving security.
 - Some of the changes protect against malicious attacks that could have occurred, under quite specific circumstances, such as attacks via downloaded binaries. These would likely have never occurred, but are now mitigated against.
 - There have been significant updates to the webui, see below.

## CONFIG VALIDATION
- UA now performs some config validation, and gives better feedback on hard loading errors. Did you accidentally edit out a pesky little comma.....
- Alternatively, for users new to Upload Assistant, the config editing in the webui will be useful.

## New config options - see example.py
 - suppress_warnings - which will suppress config validation warnings.
 - Sharex image host.
 - rehash_cooldown - set in seconds. adds that specified small delay to trackers needing specific torrent rehashing, which allows all of the other tracker uploads to process, before resources are consumed by rehashing.

## New command argument
- -ddc or --double-dupe-check, if you want to race uploads, but tend to lose, this arg will perform a secondary dupe check right before the actual upload process.
 
## Aither/LST trump processing
- For the initial rollout, this will only work in full manual mode.
- If a torrent has an existing trump report (Aither only), you will not be allowed to file a new report.
- When filing a trump report, there are some manual input options, but otherwise, UA will upload your content, and automate the report of the existing torrent site side.
- During a dupe check, if an existing torrent is marked as trumpable, you will now have the option of filing a trump report for that torrent.
- If your upload is an exact match for an existing upload, you will have a trumpable option.
- Those options are permitted for anyone.
- If you're uploading a season pack, you will have the option to report single episodes.
- UA will preference a single episode that has matching group tag.
- Internal release episodes cannot be trump reported by standard users. Internal groups can trump their own single episodes, with the same config used for internal uploads.
- Pay attention, you must pass a few prompts to be able to trump, so the onus is on you to only file correct reports.
- In debug mode. it will do everything except actually file the report.
- This process will be streamlined in the future, to further increase automation and reduce prompting.

## WEBUI
- User who have previously run the webui, should take particular note at the changes.
- https://github.com/Audionut/Upload-Assistant/blob/master/docs/web-ui-basic.md
- Docker builds with the -webui moniker have been retired, with the existing docker entrypoint handling being retained moving forward.
- See other docs in https://github.com/Audionut/Upload-Assistant/tree/master/docs
- Expect some further refinement on the config pages.