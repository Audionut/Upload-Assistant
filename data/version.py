__version__ = "v5.2.1"

"""
Release Notes for version v5.2.1 (2025-07-30):

# ## What's Changed
# 
# * fix no_subs meta by @Audionut in 86f2bcf
# * Robust id from mediainfo (#645) by @Audionut in 9c43584
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v5.2.0...v5.2.1
"""


"""
Release Notes for version v5.2.0 (2025-07-29):

# ## What's Changed
# 
# * hc subs language handling by @Audionut in 762eed8
# * pack check also being cat by @Audionut in 9279b8e
# * CBR - bdmv language check by @Audionut in de461fb
# * set hc_language meta object by @Audionut in 0bd92d7
# * LT Spanish catches by @Audionut in ac9dc35
# * Revert LT Spanish catches by @Audionut in 51c64f2
# * remove verbose print by @Audionut in fc3d1b8
# * LT.py SUBS parser failed Spanish (AR) (#626) by @Hielito in 7b6292e
# * clarify image size else print by @Audionut in a13211b
# * fix tvmaze returning None ids by @Audionut in 0769997
# * move tvdb search outside tv_pack by @Audionut in 6573337
# * get_tracker_data.py - lower HUNO priority (#629) by @wastaken7 in 8156bc8
# * ASC - type mapping and description fix (#628) by @wastaken7 in f0defc9
# * debug status message by @Audionut in 26038d4
# * OE - DS4K in name by @Audionut in 84e7517
# * Update languages.py (#633) by @wastaken7 in ae963ab
# * Add option to use entropy by @Audionut in dbba7f0
# * queue update by @Audionut in 9b1775d
# * don't add useless folders to queue by @Audionut in 63113d6
# * ffmpeg only video stream by @Audionut in 049697a
# * Merge branch 'queue-update' by @Audionut
# * group check dvd by @Audionut in 7b68370
# * Better matching of files against foldered torrents by @Audionut in 6af32a9
# * Add linux option to use custom ffmpeg binary by @Audionut in 3baa389
# * Give screenshots some spaces to breathe (#639) by @Khoa Pham in aba0bb6
# * Merge branch 'ffmpeg' by @Audionut
# * ASC - strengthen the description against NoneType errors (#638) by @wastaken7 in c2cdba6
# * CBR - handle no_dual by @Audionut in 7133915
# * CBR also remove the dual-audio by @Audionut in f62247f
# * set dual-audio meta by @Audionut in afb8175
# * mkbrr - only wanted binary by @Audionut in 57d9c5d
# * correct call by @Audionut in d005b37
# * Note about ffmpeg linux binary by @Audionut in f792c56
# * TL - add http upload option (#627) by @wastaken7 in 5d27d27
# * Merge branch 'auto-torrent-searching' by @Audionut
# * clarify usage in arg by @Audionut in 639328e
# * Merge branch 'entropy' by @Audionut
# * Prioritize arg descriptions by @Audionut in c11c3a4
# * fix id from mi by @Audionut in 694c331
# * docker mkbrr binary by @Audionut in 9077df6
# * correct filename by @Audionut in 6a6e8e8
# * Merge branch 'mkbrr-binaries' by @Audionut
# * Correct versioning in releases (#644) by @Audionut in a279a6a
# * Improve metadata finding (#636) by @Audionut in 9e32eaa
# * correct base_dir by @Audionut in 9bb68fd
# * fix docker do not tag manual as latest by @Audionut in f373286
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.1.5.2...v5.2.0
"""


"""
Changelog for version 5.1.5.2 (2025-07-19):

## What's Changed
* Update README to include supported trackers list by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/619
* Get correct discord config in upload.py by @ppkhoa in https://github.com/Audionut/Upload-Assistant/pull/621
* DC - Remove file extensions from upload filename before torrent upload by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/622
* Fixed a DC edition check
* Fixed a tracker status check

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.1.5.1...5.1.5.2
"""

__version__ = "5.1.5.1"

"""
Changelog for version 5.1.5.1 (2025-07-19):

- Language bases fixes.

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.1.5...5.1.5.1
"""

__version__ = "5.1.5"

"""
Changelog for version 5.1.5 (2025-07-18):

## What's Changed
* Fix LT edit name by @Hielito2 in https://github.com/Audionut/Upload-Assistant/pull/595
* HUNO encode checks by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/600
* Update ULCX Banned Release Groups by @backstab5983 in https://github.com/Audionut/Upload-Assistant/pull/601
* Fix filenames in Description when uploading TV [ ] by @Hielito2 in https://github.com/Audionut/Upload-Assistant/pull/603
* Handles None imdb_id string by @jacobcxdev in https://github.com/Audionut/Upload-Assistant/pull/606
* Fix variable reuse by @moontime-goose in https://github.com/Audionut/Upload-Assistant/pull/607
* Add image restriction to DigitalCore by @PythonCoderAS in https://github.com/Audionut/Upload-Assistant/pull/609
* Dp banned groups by @OrbitMPGH in https://github.com/Audionut/Upload-Assistant/pull/611
* centralized language handling by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/604
* Add randomness to image taking function and cleanup by @Hielito2 in https://github.com/Audionut/Upload-Assistant/pull/608
* ASC - remove dependency on tracker API by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/610
* BT - remove dependency on tracker API by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/612
* Add LDU support by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/613
* Other fixes here and there.

## New Contributors
* @jacobcxdev made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/606
* @moontime-goose made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/607
* @PythonCoderAS made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/609
* @OrbitMPGH made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/611

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.1.4.1...5.1.5
"""

__version__ = "5.1.4.1"

"""
Changelog for version 5.1.4.1 (2025-07-11):

* Fix: string year for replacement.

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.1.4...5.1.4.1
"""

__version__ = "5.1.4"

"""
Changelog for version 5.1.4 (2025-07-10):

## What's Changed
* DP - remove image host requirements by @jschavey in https://github.com/Audionut/Upload-Assistant/pull/593
* Fixed torf torrent creation when a single file from folder
* Fixed some year matching regex that was regressing title searching
* Fixed torrent id searching from support sites
* Updated ULCX banned groups and naming standards
* Updated BLU to use name as per IMDb

## New Contributors
* @jschavey made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/593

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.1.3.1...5.1.4
"""

__version__ = "5.1.3.1"

"""
Changelog for version 5.1.3.1 (2025-07-08):

* Fixed disc based torrent creation

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.1.3...5.1.3.1
"""

__version__ = "5.1.3"

"""
Changelog for version 5.1.3 (2025-07-08):

* Fixed en checking in audio
* Fixed torrent links

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.1.2.4...5.1.3
"""

__version__ = "5.1.2.4"

"""
Changelog for version 5.1.2.4 (2025-07-08):

## What's Changed
* Update example-config.py by @backstab5983 in https://github.com/Audionut/Upload-Assistant/pull/589
* Correct mediainfo validation


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.1.2.3...5.1.2.4
"""

__version__ = "5.1.2.3"

"""
Changelog for version 5.1.2.3 (2025-07-07):

## What's Changed
* region.py - add Pluto TV by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/583
* Onlyimage by @edge20200 in https://github.com/Audionut/Upload-Assistant/pull/582
* ASC - changes and fixes by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/581
* Print cleaning and sanitation by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/580
* HDS - description tweaks by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/585
* (Update) ULCX banned groups by @AnabolicsAnonymous in https://github.com/Audionut/Upload-Assistant/pull/586
* ASC - add custom layout config by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/584
* Added support for DigitalCore by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/577
* Fix upload to UTP by @IevgenSobko in https://github.com/Audionut/Upload-Assistant/pull/587
* Fix torrent creation for foldered content to properly exclude bad files
* Validate Unique ID in mediainfo
* Cleaned up the UA presentation in console (see below)
* Refactored the dual/dubbed/bloated audio handling to catch some edge cases
* Fix linux dvd handling. maybe......
* Updated auto torrent matching to catch more matches
* Run an auto config updater for edge's image host change
* Added a catch for incorrect tmdb id from BHD. Instead of allowing only an int for tmdb id, BHD changed to a string movie or tv/id arrangement, which means all manner of *plainly incorrect* ids can be returned from their API. 
* Added language printing handling in descriptions using common.py, when language is not in mediainfo
* Added non-en dub warning, and skips for BHD/ULCX
* Changed -fl to be set at 100% by default
* Better auto IMDb edition handling
* Fixed an OE existing search bug that's been in the code since day dot
* Other little tweaks

## Notes
Some large changes to the UA feedback during processing. Much more streamlined.
Two new config options:
* print_tracker_messages: False, - controls whether to print site api/html feedback on upload.
* print_tracker_links: True, - controls whether to print direct uploaded torrent links where possible.

Even in debug mode, the console should now be sanitized of private details. There may be some edge cases, please report.

## New Contributors
* @IevgenSobko made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/587

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.1.1...5.1.2
"""

__version__ = "5.1.1"

"""
Changelog for version 5.1.1 (2025-06-28):

## What's Changed
* HDT - screens and description changes by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/575
* HDS - load custom descriptions by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/576
* fix DVD processing on linux by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/574
* ASC - improve fallback data by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/578
* is_scene - Fix crash when is_all_lowercase is not defined by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/579
* fixed the test run prints in the readme
* OTW - add resolution to name with DVD type sources
* BHD - nfo file uploads
* ULCX - fix search_year: aka - year in title when tv and condition met
* PTP - move the youtube check so that it only asks when actually uploading


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.1.0...5.1.1
"""

__version__ = "5.1.0"

"""
Changelog for version 5.1.0 (2025-06-22):

## What's Changed
* Updated get category function by @b-igu in https://github.com/Audionut/Upload-Assistant/pull/536
* Set default value for FrameRate by @minicoz in https://github.com/Audionut/Upload-Assistant/pull/555
* Update LCD.py by @a1Thiago in https://github.com/Audionut/Upload-Assistant/pull/562
* DP - Fix: Subtitle language check ignores English by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/561
* refactor id handling by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/548
* make discord bot work by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/551
* Added support for HD-Space by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/568
* Added support for BrasilTracker by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/569
* Added support for ASC by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/560
* Properly restore  key to original value by @ppkhoa in https://github.com/Audionut/Upload-Assistant/pull/573
* OTW - update naming for DVD and REMUX
* Fixed an outlier is DVD source handling
* Fixed the discord bot to only load when being used and skip when debug
* Fixed existing image handling from PTP when not single files
* Added feedback when trackers were being skipped because of language checks
* Better dupe check handling for releases that only list DV when they're actually DV+HDR
* Fixed manual tag handling when anime
* Fixed only_id arg handling
* Fixed an aka bug from the last release that could skip aka
* Fixed double HC in HUNO name
* Added language checking for CBR
* Fixed only use tvdb if valid credentials

## New Contributors
* @minicoz made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/555

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.0.5.1...5.1.0
"""

__version__ = "5.0.5.1"

"""
Changelog for version 5.0.5.1 (2025-06-02):

* Ensure proper category sets from sites

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.0.5...5.0.5.1
"""

__version__ = "5.0.5"

"""
Changelog for version 5.0.5 (2025-06-02):

## What's Changed
* CBR - Initial modq setup by @a1Thiago in https://github.com/Audionut/Upload-Assistant/pull/546
* Remove 'pyrobase' requirement by @ambroisie in https://github.com/Audionut/Upload-Assistant/pull/547
* DP - fixed to allow when en subs
* fixed cat set from auto unit3d
* updated AR naming to take either scene name or folder/file name.
* changed the aka diff check to only allow (automated) aka when difference is greater than 70%
* protect screenshots from ptp through bbcode shenanigans
* added some filtering for automated imdb edition handling

## New Contributors
* @a1Thiago made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/546
* @ambroisie made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/547

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.0.4.2...5.0.5
"""

__version__ = "5.0.4.2"

"""
Changelog for version 5.0.4.2 (2025-05-30):

* Fix the validation check when torrent_storage_dir

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.0.4.1...5.0.4.2
"""

__version__ = "5.0.4.1"

"""
Changelog for version 5.0.4.1 (2025-05-30):

* Fixed an issue from the last release that broke existing torrent validation in qbittorent
* DP - added modq option
* Better handling of REPACK detection
* Console cleaning
* Add Hybrid to filename detection 

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.0.4...5.0.4.1
"""

__version__ = "5.0.4"

"""
Changelog for version 5.0.4 (2025-05-28):

## What's Changed
* Add additional arr instance support by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/544
* fixed anon arg
* fixed tvdb season/episode naming at HUNO
* fixed python title handling for edition and added some bad editions to skip
* fixed blank BHD descriptions also skipping images
* HDT - added quick skip for non-supported resolutions
* more tag regex shenanigans
* PTT - use only Polish name when original language is Polish (no aka)
* arr handling fixes
* PTP - if only_id, then skip if imdb_id != 0
* reduced is_scene to one api all


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.0.3.3...5.0.4
"""

__version__ = "5.0.3.3"

"""
Changelog for version 5.0.3.3 (2025-05-27):

* Fix unnecessary error feedback on empty aither claims
* implement same for banned groups detection
* fix DVD error

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.0.3.2...5.0.3.3
"""

__version__ = "5.0.3.2"

"""
Changelog for version 5.0.3.2 (2025-05-26):

* Fix arr always return valid data

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.0.3.1...5.0.3.2
"""

__version__ = "5.0.3.1"

"""
Changelog for version 5.0.3.1 (2025-05-26):

* Fixed a bad await breaking HUNO

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.0.3...5.0.3.1
"""

__version__ = "5.0.3"

"""
Changelog for version 5.0.3 (2025-05-26):

## What's Changed
* update mediainfo by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/514
* HUNO - naming update by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/535
* add arr support by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/538
* Tracker specific custom link_dir and linking fallback by @brah in https://github.com/Audionut/Upload-Assistant/pull/537
* Group tagging fixes
* Updated PTP url checking to catch old PTP torrent comments with non-ssl addy. (match more torrents)
* Whole bunch of console print cleaning
* Changed Limit Queue to only limit based on successful uploads
* Fixed PTP to not grab description in instances where it was not needed
* Set the TMP directory in docker to ensure description editing works in all cases
* Other little tweaks and fixes

## NOTES
* Added specific mediainfo binary for DVD's. Update pymediainfo to use latest mediainfo for everything else. Defaulting to user installation because normal site-packages is not writeable
Collecting pymediainfo
  Downloading pymediainfo-7.0.1-py3-none-manylinux_2_27_x86_64.whl.metadata (9.0 kB)
Downloading pymediainfo-7.0.1-py3-none-manylinux_2_27_x86_64.whl (6.0 MB)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 6.0/6.0 MB 100.6 MB/s eta 0:00:00
Installing collected packages: pymediainfo
Successfully installed pymediainfo-7.0.1
* With arr support, if the file is in your sonarr/radarr instance, it will pull data from the arr.
* Updated --webdv as the HYBRID title set. Works better than using --edition

## New configs
*  for tracker specific linking directory name instead of tracker acronym.
*  to use original folder client injection model if linking failure.
*  to keep description images when  is True

## New Contributors
* @brah made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/537

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.0.2...5.0.3
"""

__version__ = "5.0.2"

"""
Changelog for version 5.0.2 (2025-05-20):

- gather tmdb tasks to speed process
- add backup config to git ignore

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.0.1...5.0.2
"""

__version__ = "5.0.1"

"""
Changelog for version 5.0.1 (2025-05-19):

* Fixes DVD
* Fixes BHD description handling

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/5.0.0...5.0.1
"""

__version__ = "5.0.0"

"""
Changelog for version 5.0.0 (2025-05-19):

## A major version bump given some significant code changes

## What's Changed
* Get edition from IMDB by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/519
* Update LT.py by @Aerglonus in https://github.com/Audionut/Upload-Assistant/pull/520
* (Add) mod queue opt-in option to OTW tracker by @AnabolicsAnonymous in https://github.com/Audionut/Upload-Assistant/pull/524
* Add test run action by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/525
* Prep is getting out of hand by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/518
* Config generator and updater by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/522
* Image rehosting use os.chdir as final fallback by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/529
* Get edition from IMDB by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/519
* Added a fallback to cover issue that causes glob to not find images when site rehosting images
* Fixed an issue that send dubbed as dual audio to MTV
* Fixed an issue when HDB descriptions returned None from bbcode cleaning
* Stopped using non-English names from TVDB when original language is not English
* Caught an error when TMDB is None from BHD
* Added function so that series packs can get TVDB name
* Other little tweaks and fixes

## NOTES
- There is now a config generator and updater. config-generator.py. Usage is in the readme and docker wiki. As the name implies, you can generate new configs and update existing configs.
- If you are an existing user wanting to use the config-generator, I highly recommend to update your client names to match those set in the example-config https://github.com/Audionut/Upload-Assistant/blob/5f27e01a7f179e0ea49796dcbcae206718366423/data/example-config.py#L551
- The names that match what you set as the default_torrent_client https://github.com/Audionut/Upload-Assistant/blob/5f27e01a7f179e0ea49796dcbcae206718366423/data/example-config.py#L140
- This will make your experience with the config-generator much more pleasurable.
- BHD api/rss keys for BHD id/description parsing are now located with the BHD tracker settings and not within the DEFAULT settings section. It will continue to work with a notice being printed for the meantime, but please update your configs as I will permanently retire the old settings in time.
- modq for UNIT3D sites has been fixed in the UNIT3D source thanks to @AnabolicsAnonymous let me know if a site you use has updated to the latest UNIT3D source code with modq api fix, and it can be added to that sites UA file.
- You may notice that the main landing page now contains some Test Run passing displays. This does some basic checking that won't catch every error, but it may be useful for those who update directly from master branch. I'll keep adding to this over time to better catch any errors, If this display shows error, probably don't git pull.

## New Contributors
* @Aerglonus made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/520

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.2.4.1...5.0.0
"""

__version__ = "4.2.4.1"

"""
Changelog for version 4.2.4.1 (2025-05-10):

## What's Changed
* Make search imdb not useless by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/517
* Remove brackets from TVDB titles
* Fix PTP adding group.


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.2.4...4.2.4.1
"""

__version__ = "4.2.4"

"""
Changelog for version 4.2.4 (2025-05-10):

## What's Changed
* Update PTT.py by @btTeddy in https://github.com/Audionut/Upload-Assistant/pull/511
* Update OTW banned release groups by @backstab5983 in https://github.com/Audionut/Upload-Assistant/pull/512
* tmdb from imdb updates by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/515
* Use TVDB title by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/516
* HDB descriptions by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/498
* Fixed manual frame code changes breaking packed images handling
* DP - removed nordic from name per their request
* Fixed PTP groupID not being set in meta
* Added a config option for screenshot header when tonemapping


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.2.3.1...4.2.4
"""

__version__ = "4.2.3.1"

"""
Changelog for version 4.2.3.1 (2025-05-05):

* Fix cat call

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.2.3...4.2.3.1
"""

__version__ = "4.2.3"

"""
Changelog for version 4.2.3 (2025-05-05):

## What's Changed
* Update PSS banned release groups by @backstab5983 in https://github.com/Audionut/Upload-Assistant/pull/504
* Add BR streaming services by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/505
* Fixed PTP manual concert type
* Fixed PTP trump/subs logic (again)
* Fixed PT that I broke when fixing PTT
* Catch imdb str id from HUNO
* Skip auto PTP searching if TV - does not effect manual ID or client searching


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.2.2...4.2.3
"""

__version__ = "4.2.2"

"""
Changelog for version 4.2.2 (2025-05-03):

## What's Changed
* Update Service Mapping NOW by @yoyo292949158 in https://github.com/Audionut/Upload-Assistant/pull/494
* (Add) mod queue opt-in option to ULCX tracker by @AnabolicsAnonymous in https://github.com/Audionut/Upload-Assistant/pull/491
* Fix typo in HDB comps by @GizmoBal in https://github.com/Audionut/Upload-Assistant/pull/492
* Check lowercase names against srrdb for proper tag by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/495
* Additional bbcode editing on PTP/HDB/BHD/BLU by @GizmoBal in https://github.com/Audionut/Upload-Assistant/pull/493
* Further bbcode conversions by @GizmoBal in https://github.com/Audionut/Upload-Assistant/pull/496
* Stop convert_comparison_to_centered to crush spaces in names by @GizmoBal in https://github.com/Audionut/Upload-Assistant/pull/500
* TOCA remove EUR as region by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/501
* CBR - add dvdrip by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/502
* CBR - aka and year updats for name by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/503
* Added validation to BHD description images
* Fixed an issue with PTP/THR when no IMDB
* BHD/AR graceful error handling
* Fix PTT tracker setup
* Added 'hd.ma.5.1' as a bad group tag to skip

## New Contributors
* @AnabolicsAnonymous made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/491

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.2.1...4.2.2
"""

__version__ = "4.2.1"

"""
Changelog for version 4.2.1 (2025-04-29):

## What's Changed
* Update RAS.py by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/483
* Add support for Portugas by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/482
* OTW - use year in TV title by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/481
* Adding ADN as a provider by @ppkhoa in https://github.com/Audionut/Upload-Assistant/pull/484
* Allow '-s 0' option when uploading to HDB by @GizmoBal in https://github.com/Audionut/Upload-Assistant/pull/485
* CBR: Refactor get_audio function to handle multiple languages by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/488
* Screens handling updates by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/486
* Add comparison images by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/487
* Should be improvements to PTP hardcoded subs handling
* Corrected AR imdb url
* Fixed an issue in a tmdb episode pathway that would fail without tvdb
* Cleaned more private details from debug prints
* Fixed old BHD code to respect only supported BDMV regions
* Update OE against their image hosts rule
* Added passtheima.ge support

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.2.0.1...4.2.1
"""

__version__ = "4.2.0.1"

"""
Changelog for version 4.2.0.1 (2025-04-24):

- OE - only allow with English subs if not English audio
- Fixed the bad copy/paste that missed the ULCX torrent url
- Added the new trackers args auto api to example config
- Fixed overwriting custom descriptions with bad data
- Updated HDR check to find  and correctly check for relevant strings.

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.2.0...4.2.0.1
"""

__version__ = "4.2.0"

"""
Changelog for version 4.2.0 (2025-04-24):

## What's Changed
* store and use any found torrent data by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/452
* Automated bluray region-distributor parsing by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/471
* add image upload retry logic by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/472
* TVC Allow 1080p HEVC by @yoyo292949158 in https://github.com/Audionut/Upload-Assistant/pull/478
* Small fixes to AL title formatting by @b-igu in https://github.com/Audionut/Upload-Assistant/pull/477
* fixed a bug that skipped tvdb episode data handling
* made THR work

## Config additions
* A bunch of new config options starting here: https://github.com/Audionut/Upload-Assistant/blob/b382ece4fde22425dd307d1098198fb3fc9e0289/data/example-config.py#L183

## New Contributors
* @yoyo292949158 made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/478

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.9...4.2.0
"""

__version__ = "4.1.9"

"""
Changelog for version 4.1.9 (2025-04-20):

## What's Changed
* PTP. Do not ask if files with en-GB subs are trumpable. by @GizmoBal in https://github.com/Audionut/Upload-Assistant/pull/459
* Add tag for releases without a group name (PSS) by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/461
* In PTP descriptions, do not replace [code] by [quote]. by @GizmoBal in https://github.com/Audionut/Upload-Assistant/pull/463
* In HDB descriptions, do not replace [code] by [quote]. by @GizmoBal in https://github.com/Audionut/Upload-Assistant/pull/466
* handle cleanup on mac os without termination by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/465
* Refactor CBR.py by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/467
* Description Customization by @zercsy in https://github.com/Audionut/Upload-Assistant/pull/468
* Fixed THR
* Added an option that allows sites to skip upload when content does not contain English
* Fixed cleanup on Mac OS
* Fixed an error causing regenerated torrents to fail being added to client
* Added fallback search for HDB when no IMDB
* Other minor fixes

## New Contributors
* @zercsy made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/468

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.8.1...4.1.9
"""

__version__ = "4.1.8.1"

"""
Changelog for version 4.1.8.1 (2025-04-15):

* Fixed a quote bug

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.8...4.1.8.1
"""

__version__ = "4.1.8"

"""
Changelog for version 4.1.8 (2025-04-14):

## What's Changed
* Correct typo to enable UA to set the 'Internal' tag on HDB. by @GizmoBal in https://github.com/Audionut/Upload-Assistant/pull/456
* Updated AL upload by @b-igu in https://github.com/Audionut/Upload-Assistant/pull/457
* Run cleaning between items in a queue - fixes terminal issue when running a queue
* Fixed an error when imdb returns no results
* Fixes image rehosting was overwriting main image_list

## New Contributors
* @b-igu made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/457

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.7...4.1.8
"""

__version__ = "4.1.7"

"""
Changelog for version 4.1.7 (2025-04-13):

## What's Changed
* Fix missing HHD config in example-config.py by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/455
* Updated mkbrr including fix for BDMV torrent and symlink creation
* Fixed manual source with BHD
* Added nfo file upload support for DP
* Changed logo handling so individual sites can pull language specific logos
* Fixed an error with adding mkbrr regenerated torrents to client
* Refactored Torf torrent creation to be quicker


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.6...4.1.7
"""

__version__ = "4.1.6"

"""
Changelog for version 4.1.6 (2025-04-12):

## What's Changed
* qBittorrent Option: Include Tracker as Tag - New sites SAM and UHD by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/454
* fixed image retaking
* fixed pack images to be saved in unique file now that meta is deleted by default
* updated OE to check all mediainfo when language checking
* updated OTW to include resolution with DVD
* updated DP rule compliance


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.5...4.1.6
"""

__version__ = "4.1.5"

"""
Changelog for version 4.1.5 (2025-04-10):

## What's Changed
* Clean existing meta by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/451
* Added frame overlays to disc based content
* Refactored ss_times


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.4.1...4.1.5
"""

__version__ = "4.1.4.1"

"""
Changelog for version 4.1.4.1 (2025-04-09):

## What's Changed
* Minor fixes in TIK.py by @GizmoBal in https://github.com/Audionut/Upload-Assistant/pull/449
* Fixed year getting inserted into incorrect TV


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.4...4.1.4.1
"""

__version__ = "4.1.4"

"""
Changelog for version 4.1.4 (2025-04-08):

## What's Changed
* Update SP.py to replace   with . per upload guidelines by @tubaboy26 in https://github.com/Audionut/Upload-Assistant/pull/435
* HUNO - remove region from name by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/441
* Correct absolute episode number lookup by @ppkhoa in https://github.com/Audionut/Upload-Assistant/pull/447
* add more args overrides options by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/437
* add rTorrent linking support by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/390
* Accept both relative and absolute path for the description filename. by @GizmoBal in https://github.com/Audionut/Upload-Assistant/pull/448
* Updated dupe checking - mainly to allow uploads when more than 1 of a content is allowed
* Added an argument  which cleans just the tmp directory for the current pathed content
* Hide some not important console prints behind debug
* Fixed HDR tonemapping
* Added config option to overlay some details on screenshots (currently only files)
* Adjust font size of screenshot overlays to match the resolution. by @GizmoBal in https://github.com/Audionut/Upload-Assistant/pull/442
* Fixed manual year
* Other minor fixes

## New Contributors
* @GizmoBal made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/442

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.3...4.1.4
"""

__version__ = "4.1.3"

"""
Changelog for version 4.1.3 (2025-04-02):

- All torrent creation issues should now be fixed
- Site upload issues are gracefully handled
- tvmaze episode title fallback
- Fix web/hdtv dupe handling

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.2...4.1.3
"""

__version__ = "4.1.2"

"""
Changelog for version 4.1.2 (2025-03-30):

## What's Changed
* Added support for DarkPeers and Rastastugan by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/431
* fixed HDB missing call for torf regeneration
* fixed cutoff screens handling when taking images
* fixed existing image timeout error causing UA to hard crash
* tweaked  pathway to ensure no duplicate api calls
* fixed a duplicate import in PTP that could cause some python versions to hard error
* removed JPTV

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.1...4.1.2
"""

__version__ = "4.1.1"

"""
Changelog for version 4.1.1 (2025-03-30):

## What's Changed
* add argument --not-anime by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/430
* fixed linking on linux when volumes have the same mount
* fixed torf torrent regeneration in MTV
* added null language check for tmdb logo (mostly useful for movies)
* fixed 
* fixed ssrdb release matching print
* fixed tvdb season matching under some conditions (wasn't serious)

Check v4.1.0 release notes if not already https://github.com/Audionut/Upload-Assistant/releases/tag/4.1.0

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.0.2...4.1.1
"""

__version__ = "4.1.0.2"

"""
Changelog for version 4.1.0.2 (2025-03-29):

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.0.1...4.1.0.2

4..1.0 release notes:

## New config options
See example-config.py
-  and  - add tv series logo to top of descriptions with size control
-  - from the last release, adds tv series overview to description. Now includes season name and details if applicable, see below
-  (qBitTorrent v5+ only) - don't automatically try and find a matching torrent from just the path
-  and  for tvdb data support

## Notes
- UA will now try and automatically find a torrent from qBitTorrent (v5+ only) that matches any site based argument. If it finds a matching torrent, for instance from PTP, it will automatically set . In other words, you no longer need to set a site argument ( or  or --whatever (or  and/or ) as UA will now do this automatically if the path matches a torrent in client. Use the applicable config option to disable this default behavior.

- TVDB requires token to be initially inputted, after which time it will be auto generated as needed.
- Automatic Absolute Order to Aired Order season/episode numbering with TVDB.
- BHD now supports torrent id instead of just hash.
- Some mkbrr updates, including support for  and rehashing for sites as needed.
- TMDB searching should be improved.


See examples below for new logo and episode data handling.
<img src=https://github.com/user-attachments/assets/b2dc4a64-236d-4b77-af32-abe9b1b4fb44 width=400> <img src=https://github.com/user-attachments/assets/19011997-977b-4e19-b45b-51db598aba17 width=346>


## What's Changed
* BHD torrent id parsing by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/417
* Better title/year parsing for tmdb searching by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/416
* feat: pull logo from tmdb by @markhc in https://github.com/Audionut/Upload-Assistant/pull/425
* fix: logo displayed as None by @markhc in https://github.com/Audionut/Upload-Assistant/pull/427
* Update region.py by @ikitub3 in https://github.com/Audionut/Upload-Assistant/pull/429
* proper mkbrr handling by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/397
* TVDB support by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/423
* qBitTorrent auto torrent grabing and rTorrent infohash support by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/428

## New Contributors
* @markhc made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/425
* @ikitub3 made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/429

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.0.6...4.1.0
"""

__version__ = "4.1.0.1"

"""
Changelog for version 4.1.0.1 (2025-03-29):

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.1.0...4.1.0.1

From 4.1.0

## New config options
See example-config.py
-  and  - add tv series logo to top of descriptions with size control
-  - from the last release, adds tv series overview to description. Now includes season name and details if applicable, see below
-  (qBitTorrent v5+ only) - don't automatically try and find a matching torrent from just the path
-  and  for tvdb data support

## Notes
- UA will now try and automatically find a torrent from qBitTorrent (v5+ only) that matches any site based argument. If it finds a matching torrent, for instance from PTP, it will automatically set . In other words, you no longer need to set a site argument ( or  or --whatever (or  and/or ) as UA will now do this automatically if the path matches a torrent in client. Use the applicable config option to disable this default behavior.

- TVDB requires token to be initially inputted, after which time it will be auto generated as needed.
- Automatic Absolute Order to Aired Order season/episode numbering with TVDB.
- BHD now supports torrent id instead of just hash.
- Some mkbrr updates, including support for  and rehashing for sites as needed.
- TMDB searching should be improved.


See examples below for new logo and episode data handling.
<img src=https://github.com/user-attachments/assets/b2dc4a64-236d-4b77-af32-abe9b1b4fb44 width=400> <img src=https://github.com/user-attachments/assets/19011997-977b-4e19-b45b-51db598aba17 width=346>


## What's Changed
* BHD torrent id parsing by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/417
* Better title/year parsing for tmdb searching by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/416
* feat: pull logo from tmdb by @markhc in https://github.com/Audionut/Upload-Assistant/pull/425
* fix: logo displayed as None by @markhc in https://github.com/Audionut/Upload-Assistant/pull/427
* Update region.py by @ikitub3 in https://github.com/Audionut/Upload-Assistant/pull/429
* proper mkbrr handling by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/397
* TVDB support by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/423
* qBitTorrent auto torrent grabing and rTorrent infohash support by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/428

## New Contributors
* @markhc made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/425
* @ikitub3 made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/429

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.0.6...4.1.0
"""

__version__ = "4.1.0"

"""
Changelog for version 4.1.0 (2025-03-29):

## New config options
See example-config.py
-  and  - add tv series logo to top of descriptions with size control
-  - from the last release, adds tv series overview to description. Now includes season name and details if applicable, see below
-  (qBitTorrent v5+ only) - don't automatically try and find a matching torrent from just the path
-  and  for tvdb data support

## Notes
- UA will now try and automatically find a torrent from qBitTorrent (v5+ only) that matches any site based argument. If it finds a matching torrent, for instance from PTP, it will automatically set . In other words, you no longer need to set a site argument ( or  or --whatever (or  and/or ) as UA will now do this automatically if the path matches a torrent in client. Use the applicable config option to disable this default behavior.

- TVDB requires token to be initially inputted, after which time it will be auto generated as needed.
- Automatic Absolute Order to Aired Order season/episode numbering with TVDB.
- BHD now supports torrent id instead of just hash.
- Some mkbrr updates, including support for  and rehashing for sites as needed.
- TMDB searching should be improved.


See examples below for new logo and episode data handling.
<img src=https://github.com/user-attachments/assets/b2dc4a64-236d-4b77-af32-abe9b1b4fb44 width=400> <img src=https://github.com/user-attachments/assets/19011997-977b-4e19-b45b-51db598aba17 width=346>


## What's Changed
* BHD torrent id parsing by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/417
* Better title/year parsing for tmdb searching by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/416
* feat: pull logo from tmdb by @markhc in https://github.com/Audionut/Upload-Assistant/pull/425
* fix: logo displayed as None by @markhc in https://github.com/Audionut/Upload-Assistant/pull/427
* Update region.py by @ikitub3 in https://github.com/Audionut/Upload-Assistant/pull/429
* proper mkbrr handling by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/397
* TVDB support by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/423
* qBitTorrent auto torrent grabing and rTorrent infohash support by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/428

## New Contributors
* @markhc made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/425
* @ikitub3 made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/429

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.0.6...4.1.0
"""

__version__ = "4.0.6"

"""
Changelog for version 4.0.6 (2025-03-25):

## What's Changed
* update to improve 540 detection by @swannie-eire in https://github.com/Audionut/Upload-Assistant/pull/413
* Update YUS.py by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/414
* BHD - file/folder searching by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/415
* Allow some hardcoded user overrides by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/411
* option episode overview in description by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/418
* Catch HUNO BluRay naming requirement by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/419
* group tag regex by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/420
* OTW - stop pre-filtering image hosts
* revert automatic episode title

BHD auto searching does not currently return description/image links


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.0.5...4.0.6
"""

__version__ = "4.0.5"

"""
Changelog for version 4.0.5 (2025-03-21):

## What's Changed
* Refactor TOCA.py by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/410
* fixed an imdb search returning bad results
* don't run episode title checks on season packs or episode == 0
* cleaned PTP mediainfo in packed content (scrubbed by PTP upload parser anyway)
* fixed some sites duplicating episode title
* docker should only pull needed mkbrr binaries, not all of them
* removed private details from some console prints
* fixed handling in ptp mediainfo check
* fixed  arg work with no value
* removed rehosting from OTW, they seem fine with ptpimg now.

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.0.4...4.0.5
"""

__version__ = "4.0.4"

"""
Changelog for version 4.0.4 (2025-03-19):

## What's Changed
* get episode title from tmdb by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/403
* supporting 540p by @swannie-eire in https://github.com/Audionut/Upload-Assistant/pull/404
* LT - fix no distributor api endpoint by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/406
* reset terminal fix
* ULCX content checks
* PTP - set EN sub flag when trumpable for HC's English subs
* PTP - fixed an issue where description images were not being parsed correctly
* Caught an IMDB issue when no IMDB is returned by metadata functions
* Changed the banned groups/claims checking to daily

## Episode title data change
Instead of relying solely on guessit to catch episode titles, UA now pulls episode title information from TMDB. There is some pre-filtering to catch placeholder title information like 'Episode 2', but you should monitor your TV uploads. Setting  with an empty space will clear the episode title.

Conversely (reminder of already existing functionality), setting met with some title  will force that episode title.


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.0.3.1...4.0.4
"""

__version__ = "4.0.3.1"

"""
Changelog for version 4.0.3.1 (2025-03-17):

- Fix erroneous AKA in title when AKA empty

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.0.3...4.0.3.1
"""

__version__ = "4.0.3"

"""
Changelog for version 4.0.3 (2025-03-17):

## What's Changed
* Update naming logic for SP Anime Uploads by @tubaboy26 in https://github.com/Audionut/Upload-Assistant/pull/399
* Fix ITT torrent comment by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/400
* Fix --cleanup without path
* Fix tracker casing
* Fix AKA

## New Contributors
* @tubaboy26 made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/399

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.0.2...4.0.3
"""

__version__ = "4.0.2"

"""
Changelog for version 4.0.2 (2025-03-15):

## What's Changed
* Update CBR.py by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/392
* Update ITT.py by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/393
* Added support for TocaShare by @wastaken7 in https://github.com/Audionut/Upload-Assistant/pull/394
* Force auto torrent management to false when using linking

## New Contributors
* @wastaken7 made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/392

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.0.1...4.0.2
"""

__version__ = "4.0.1"

"""
Changelog for version 4.0.1 (2025-03-14):

- fixed a tracker handling error when answering no to title confirmation
- fixed imdb from srrdb
- strip matching distributor from title and add to meta object
- other little fixes

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.0.0.3...4.0.1
"""

__version__ = "4.0.0.3"

"""
Changelog for version 4.0.0.3 (2025-03-13):

- added platform to docker building
- fixed anime titling
- fixed aither dvdrip naming

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.0.0.2...4.0.0.3

## Version 4 release notes:
## Breaking change
* When using trackers argument,  or , you must now use a comma separated list.

## Linking support in qBitTorrent
### This is not fully tested. 
It seems to be working fine on this windows box, but you absolutely should test with the  argument to make sure it works on your system before putting it into production.
* You can specify to use symbolic or hard links
* 
* Add one or many (local) paths which you want to contain the links, and UA will map the correct drive/volume for hardlinks.

## Reminder
* UA has mkbrr support 
* You can specify an argument  or set the config 
* UA loads binary files for the supported mkbrr OS. If you find mkbrr slower than the original torf implementation when hashing torrents, the mkbrr devs are likely to be appreciative of any reports.
"""

__version__ = "4.0.0.2"

"""
Changelog for version 4.0.0.2 (2025-03-13):

- two site files manually imported tmdbsimple.
- fixed R4E by adding the want tmdb data from the main tmdb api call, which negates the need to make a needless api call when uploading to R4E, and will shave around 2 seconds from the time it takes to upload.
- other site file will be fixed when I get around to dealing with that mess.

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.0.0.1...4.0.0.2

## Version 4 release notes:
## Breaking change
* When using trackers argument,  or , you must now use a comma separated list.

## Linking support in qBitTorrent
### This is not fully tested. 
It seems to be working fine on this windows box, but you absolutely should test with the  argument to make sure it works on your system before putting it into production.
* You can specify to use symbolic or hard links
* 
* Add one or many (local) paths which you want to contain the links, and UA will map the correct drive/volume for hardlinks.

## Reminder
* UA has mkbrr support 
* You can specify an argument  or set the config 
* UA loads binary files for the supported mkbrr OS. If you find mkbrr slower than the original torf implementation when hashing torrents, the mkbrr devs are likely to be appreciative of any reports.
"""

__version__ = "4.0.0.1"

"""
Changelog for version 4.0.0.1 (2025-03-13):

- fix broken trackers handling
- fix client inject when not using linking.

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/4.0.0...4.0.0.1

## Version 4 release notes:
## Breaking change
* When using trackers argument,  or , you must now use a comma separated list.

## Linking support in qBitTorrent
### This is not fully tested. 
It seems to be working fine on this windows box, but you absolutely should test with the  argument to make sure it works on your system before putting it into production.
* You can specify to use symbolic or hard links
* 
* Add one or many (local) paths which you want to contain the links, and UA will map the correct drive/volume for hardlinks.

## Reminder
* UA has mkbrr support 
* You can specify an argument  or set the config 
* UA loads binary files for the supported mkbrr OS. If you find mkbrr slower than the original torf implementation when hashing torrents, the mkbrr devs are likely to be appreciative of any reports.
"""

__version__ = "4.0.0"

"""
Changelog for version 4.0.0 (2025-03-13):

Pushing this as v4 given some significant code changes.

## Breaking change
* When using trackers argument,  or , you must now use a comma separated list.

## Linking support in qBitTorrent
### This is not fully tested. 
It seems to be working fine on this windows box, but you absolutely should test with the  argument to make sure it works on your system before putting it into production.
* You can specify to use symbolic or hard links
* 
* Add one or many (local) paths which you want to contain the links, and UA will map the correct drive/volume for hardlinks.

## Reminder
* UA has mkbrr support 
* You can specify an argument  or set the config 
* UA loads binary files for the supported mkbrr OS. If you find mkbrr slower than the original torf implementation when hashing torrents, the mkbrr devs are likely to be appreciative of any reports.

## What's Changed
* move cleanup to file by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/384
* async metadata calls by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/382
* add initial linking support by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/380
* Refactor args parsing by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/383


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/3.6.5...4.0.0
"""

__version__ = "3.6.5"

"""
Changelog for version 3.6.5 (2025-03-12):

## What's Changed
* bunch of id related issues fixed
* if using , take that moment to validate and export the torrent file
* some prettier printing with torf torrent hashing
* mkbrr binary files by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/381


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/3.6.4...3.6.5
"""

__version__ = "3.6.4"

"""
Changelog for version 3.6.4 (2025-03-09):

- Added option to use mkbrr https://github.com/autobrr/mkbrr (). About 4 times faster than torf for a file in cache . Can be set via config
- fixed empty HDB file/folder searching giving bad feedback print

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/3.6.3.1...3.6.4
"""

__version__ = "3.6.3.1"

"""
Changelog for version 3.6.3.1 (2025-03-09):

- Fix BTN ID grabbing

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/3.6.3...3.6.3.1
"""

__version__ = "3.6.3"

"""
Changelog for version 3.6.3 (2025-03-09):

## Config changes
* As part of the effort to fix unresponsive terminals on unix systems, a new config option has been added , and an existing config option , now has a default setting even if commented out/not preset.
* Non-unix users (or users without terminal issue) should uncomment and modify these settings to taste
* https://github.com/Audionut/Upload-Assistant/blob/de7689ff36f76d7ba9b92afe1175b703a59cda65/data/example-config.py#L53

## What's Changed
* Create YUS.py by @fiftieth3322 in https://github.com/Audionut/Upload-Assistant/pull/373
* remote_path as list by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/365
* Correcting PROPER number namings in title by @Zips-sipZ in https://github.com/Audionut/Upload-Assistant/pull/378
* Save extracted description images to disk (can be useful for rehosting to save the capture/optimization step)
* Updates/fixes to ID handling across the board
* Catch session interruptions in AR to ensure session is closed
* Work around a bug that sets empty description to None, breaking repeated processing with same meta
* Remote paths now accept list
* More effort to stop unix terminals shitting the bed

## New Contributors
* @fiftieth3322 made their first contribution in https://github.com/Audionut/Upload-Assistant/pull/373

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/3.6.2...3.6.3
"""

__version__ = "3.6.2"

"""
Changelog for version 3.6.2 (2025-03-04):

## Update Notification
This release adds some new config options relating to update notifications: https://github.com/Audionut/Upload-Assistant/blob/a8b9ada38323c2f05b0f808d1d19d1d79c2a9acf/data/example-config.py#L9

## What's Changed
* Add proper2 and proper3 support by @Kha-kis in https://github.com/Audionut/Upload-Assistant/pull/371
* added update notification
* HDB image rehosting updates
* updated srrdb handling
* other minor fixes


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/3.6.1...3.6.2
"""

__version__ = "3.6.1"

"""
Changelog for version 3.6.1 (2025-03-01):

- fix manual package screens uploading
- switch to subprocess for setting stty sane
- print version to console
- other minor fixes

**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/3.6.0...3.6.1
"""

__version__ = "3.6.0"

"""
Changelog for version 3.6.0 (2025-02-28):

## What's Changed
* cleanup tasks by @Audionut in https://github.com/Audionut/Upload-Assistant/pull/364


**Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/3.5.3.3...3.6.0
"""

__version__ = "3.5.3.1"
