__version__ = "v6.3.2"

"""
Release Notes for version v6.3.2 (2025-12-31):

# ## What's Changed
# 
# * fix: docker tagging by @Audionut in cda7a2c
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v6.3.1...v6.3.2
"""


"""
Release Notes for version v6.3.1 (2025-12-30):

# 
# ## RELEASE NOTES
#  - Updated the docker builds to have standard latest tag, and latest-webui specifically for the webui builds. This should assist those who were experiencing issues with the last release that defaulted to have the webui changes.
#  - Added cross-seeding support. If you attempt to upload to site XYZ, and the exact filename is found at that site during the dupe checking, UA can now download and add that torrent to the client (follows any hard/symlinking).
#  - wastaken refactored the unit3d torrent handling to skip functions that were no longer needed with torrent downloading.
#  - wastaken added an option to log the time it takes each individual tracker to upload.
#  - I refactored the major async blockers in the upload and inject process, which allows each individual site upload/injection into client, to process immediately as it's finished, regardless of what any other tracker upload is doing.
#  - For example, you can upload to 10 x unit3d based sites, and be uploaded and injected into client, and seeding, whilst MTV might still be rehashing to satisfy their 8 MiB piece size constraint.
# 
# ## New config options - see example.py
#  - cross-seeding related options.
#  - Seedpool added their imagehost as an option.
#  
# 
# ---
# 
# ## What's Changed
# 
# * TVC: fix python f-string by @Audionut in 603ccb4
# * ACM: fix name return by @Audionut in df3a9d3
# * ACM: fix description by @Audionut in 0064917
# * refactor anime/anilist handling by @Audionut in 994eba2
# * Update banned groups in DP.py (#1055) by @FortKnox1337 in 9fae288
# * LT: release naming for spanish variants (#1052) by @Caleb Contreras in 482184b
# * fix: set VP9, AV1 and VC-1 (#1050) by @cucaracha7126378 in 2abe5c5
# * fix: some bdinfo going though dual audio checking by @Audionut in 4738b02
# * fix NBLA service from filename by @Audionut in d9ab112
# * use existing mi json for dvd type source handling by @Audionut in 865663c
# * improve group tagging by @Audionut in 7f49621
# * PTP: send dvdrips with other resolution by @Audionut in e23e54e
# * PTP: tag scene by @Audionut in 135fab4
# * PTP: remove scene nfo from descriptions by @Audionut in 63af9a7
# * strip TBA from episode titles by @Audionut in 98ca55e
# * Add support for disc menu images (#1051) by @wastaken7 in 2719211
# * docker, default to running upload.py by @Audionut in 929beb8
# * fix: use cleaned summary for BDInfo parsing and meta (#1062) by @wastaken7 in 28c3784
# * ping tv metadata sites when tv movie by @Audionut in 3fac3d8
# * Merge branch 'docker-exec' by @Audionut
# * add cross-seeding support (#1029) by @Audionut in 392d06b
# * Add seedpool cdn support  (#1058) by @tetrahydroc in 8df1424
# * fix tv handling by @Audionut in bb2b51f
# * fix indentation by @Audionut in 9c41e1c
# * SHRI: catch unknown locales by @Audionut in 4d832bb
# * clarify linking setup for rtorrent by @Audionut in 431da41
# * feat(THR): add documentary category detection (#1066) by @cucaracha7126378 in 4c78baa
# * fix(ptscreens): status code error (#1073) by @Caleb Contreras in a9fa020
# * refactor: improve duplicate search in selected supported trackers (#1071) by @wastaken7 in e85eb1d
# * PTP: add HDT to banned groups by @Audionut in 86f5c9b
# * improve sat torrent matching by @Audionut in bae0499
# * add tvmovie to type detection by @Audionut in e29859e
# * MTV: ua handling for 4K releases by @Audionut in fef236f
# * refactor: stop modifying the torrent file if it is downloaded (#1067) by @wastaken7 in 2f7e149
# * Process screenshots in paths with special characters for HDB (#1070) by @Khoa Pham in 4e9b054
# * SP: only 1080+ by @Audionut in e6e05b7
# * SP: add porn catch by @Audionut in 2e78343
# * dupe checking: source mismatches by @Audionut in 4027486
# * convert tv overview html by @Audionut in a523342
# * fix: don't put discs through dual audio handling by @Audionut in 5fef312
# * fix: use double quotes in client type defaults by @Audionut in 6cc8a05
# * requests debugging by @Audionut in 0fae58e
# * DC: set upload torrent file (#1077) by @Audionut in f951701
# * Fix condition for BluRay source mismatch check (#1079) by @FortKnox1337 in 6de3161
# * FNP: Add request search support. (#1082) by @FortKnox1337 in 5e18b0b
# * ANT: dupe filename feedbackl by @Audionut in f7815c7
# * CBR: add multi tag support (#1081) by @wastaken7 in 26e70ca
# * Enhance BDMV MediaInfo generation with character limit fallback (#1080) by @wastaken7 in 40f0ce6
# * HDB: fix indentation by @Audionut in 4122a8d
# * Remove unnecessary time.sleep (#1041) by @WOSSFOSS in cb3ffdd
# * Docker building - specific webui builds (#1085) by @Audionut in a197129
# * release notes by @Audionut in 09bede4
# * allow setting 0 for some ids by @Audionut in 2c307c0
# * Revert "allow setting 0 for some ids" by @Audionut in 49247a7
# * BJS: Handle image URL validation and error reporting (#1089) by @wastaken7 in 9d0f244
# * CBR, SAM: do not add DUAL/MULTI to the title when it is a full disc (#1088) by @wastaken7 in 7e337ce
# * Add upload duration tracking for each tracker upload (#1087) by @wastaken7 in dd46b8c
# * fix existing tracker check for cross-seeding by @Audionut in 5c76671
# * fix some tracker id searches by @Audionut in c384c08
# * add tracker flags for HDR type dupe matching by @Audionut in 2a79d0f
# * unit3d: gather 1080p and 1080i in existing search by @Audionut in 8184253
# * catch unit3d 520 error by @Audionut in e27b77c
# * unit3d: add upload retries by @Audionut in 1e3620b
# * RAS and ULCX: update the language handling by @Audionut in de648ab
# * unit3d: handle torrent download on error by @Audionut in 8de7a23
# * remove async blockers from upload process by @Audionut in 0265fc5
# * qbit: add an arg to force a recheck before uploading by @Audionut in ec9a827
# * unit3d: bump the perpage search results by @Audionut in 019046f
# * mkbrr: bump to v1.18.0 by @Audionut in d0e9aad
# * Refactor is_scene to use httpx for async requests and implement caching for srrDB searches (#1086) by @wastaken7 in 78239b9
# * PTP: fix announce url replacement by @Audionut in 8a488a6
# * PTP: use the updated announce url for torrent creation by @Audionut in 12a8458
# * PTP: add plaintext url warnings by @Audionut in 49448fd
# * Implement bloated audio track check with tracker-specific language allowances (#1084) by @wastaken7 in 181e248
# * release notes by @Audionut in 9c84fa4
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v6.3.0...v6.3.1
"""


"""
Release Notes for version v6.3.0 (2025-12-15):

# 
# ## RELEASE NOTES
#  - This release was slower than usual. Some notable changes....
#  - Added TLZ, IHD, TTR
#  - Added support for multiple client injecting.
#  - Improved the image host handling for sites that have banned hosts.
#  - Improved the year detection for RTF when uploading TV content.
#  - Fixed a bug with DVD mediainfo handling.
#  - Fixed audio track handling that could cause missed dual-audio type handling.
#  - Fixed image compression when using image overlay.
#  - Fixed some mal id handling.
#  - Added support for detecting ATMOS height channels.
#  - Fixed auto torrent searching to only search valid trackers in config.
#  - Added a webui for docker.
#  - wastaken7 done a bunch of further refactoring.
# 
# ## New config options - see example.py
#  - Multiple injecion clients can be added.
#  - Removed the need for passkey from SPD and DC.
#  - Added modq support for LT.
# 
# ## Special shout out
# - blueberry, who is banned from UA github, and from a bunch of sites, due to invite begging/trading, and begging for internal status. It takes a special kind of stupid to modify a handful of lines and claim something as your own.
# 
# ---
# 
# ## What's Changed
# 
# * docker pr building by @Audionut in 4a56b81
# * build from fork by @Audionut in d10bff9
# * fix some args parse quirks by @Audionut in fa05ca5
# * prints behind debug by @Audionut in c1050f2
# * BT: fix internal (#955) by @wastaken7 in d852726
# * fix: don't sanitize meta early by @Audionut in 46346cd
# * add new tracker URLs to match_tracker_url function (#957) by @wastaken7 in f45b9af
# * refactor: remove UHD tracker (#958) by @wastaken7 in 339ba64
# * feat: add support for super-seed mode (#956) by @wastaken7 in 0db8ed8
# * PTP: upload error handling by @Audionut in 2c04770
# * handle domain changes in unit3d descriptions by @Audionut in fb12db1
# * TIK: videoformat update by @Audionut in 569740f
# * image host validation updates by @Audionut in 3ab8bc5
# * refactor(ASC): move internal flag setting to a separate method (#959) by @wastaken7 in 058b4cb
# * fix uploaded images success check by @Audionut in 089f127
# * feat: Docker GUI for front end.  (#954) by @IPGPrometheus in ca87495
# * AR: Improve genre tag compilation logic (#965) by @cza in 6271ded
# * refactor(SPD): remove passkey usage, update upload logic, add banned groups API (#963) by @wastaken7 in b019965
# * HDB - Refine granulometry of thumbnail size in comps (#968) by @GizmoBal in c342712
# * webui example args by @Audionut in 93330c2
# * UHD: Remove from available trackers list in example-config.py (#970) by @FortKnox1337 in 03c2fda
# * Add Torrenteros support (#971) by @wastaken7 in 170a43a
# * TVDB/TVMaze improvements (#978) by @Audionut in bdd164f
# * README: Add CinemaZ to the list of supported sites. (#974) by @FortKnox1337 in 1718e3c
# * refactor(DC): remove passkey handling, update API endpoint usage, and improve upload logic (#976) by @wastaken7 in 7a8cb9c
# * reverse linux bdinfo checking by @Audionut in 10eca14
# * unattended no imdb by @Audionut in 5224894
# * fix imdb search params by @Audionut in e51421a
# * SHRI: BBCode description generation (#980) by @TheDarkMan in 80fe158
# * feat(SHRI): add customization and conditional sections (#983) by @TheDarkMan in 7c9ced7
# * Scan type detection for empty ScanType value (#982) by @TheDarkMan in ed49e65
# * Minor THR improvements (#987) by @cucaracha7126378 in 13ba722
# * fix(SHRI): handle MediaInfo Language dict and improve logo extraction (#988) by @TheDarkMan in 27d2143
# * Improve qui searching (#967) by @Audionut in 7eb838e
# * validate specific trackers by @Audionut in a4b5af3
# * improve existing torrent search by @Audionut in 5598e24
# * RTF: fix year check by @Audionut in 1f729ae
# * BLU: Update banned release groups list (#990) by @FortKnox1337 in a5c6ecf
# * fix(THR): replace unsupported bbcode tags and fix NFO content alignment (#993) by @cucaracha7126378 in 06c7e86
# * fix(SHRI): improve REMUX detection and codec identification (#992) by @TheDarkMan in 7f45b58
# * print error when no audio by @Audionut in c169279
# * ANT: prohibit bloated by @Audionut in d3c5528
# * handle height channels (#985) by @Audionut in df76e53
# * fix(CZ): change BDinfo summary file (#996) by @wastaken7 in df4a4cb
# * ASC: fix localized data (#994) by @Audionut in f2a6513
# * catch bdinfo errors by @Audionut in 614bbc0
# * Fix empty status_message after upload failure (#1000) by @wastaken7 in 1120f4a
# * fix(LT.py): fix origin_country check, modQ option added (#1002) by @Caleb Contreras in 752072d
# * fix getting BTN ids by @Audionut in d244af5
# * parse scene nfo for service by @Audionut in 751253c
# * PHD: Add banned release groups (#1004) by @FortKnox1337 in b22a07e
# * fix group checking for banned groups by @Audionut in 7060e34
# * fix double screens print by @Audionut in fe5ee82
# * refactor infohash by @Audionut in d758027
# * fix(FF): follow the site's naming conventions (#1006) by @wastaken7 in 1e6b27a
# * RTV: refactor tv year handling by @Audionut in a325fb3
# * cleanup bluray com handling by @Audionut in da2fff2
# * ULCX: refactor aka handling by @Audionut in 9b38b2d
# * fixed mal handling by @Audionut in e7e4e48
# * refactor(DC): remove logo and screenshot header from description (#1018) by @wastaken7 in dc6f057
# * fix(SHRI): improve language handling for Italian and English (#1013) by @TheDarkMan in f5d4a42
# * add site uploading from site check log (#995) by @Audionut in 4f166d4
# * always attempt mal by @Audionut in 3915ed9
# * Add IHD support by @Audionut in a4d1df4
# * licensing (#1022) by @Audionut in e2d2531
# * IHD: fix language checking by @Audionut in a259e3d
# * add extra tags catch by @Audionut in 458f48f
# * unit3d internal flag debugging by @Audionut in a08b887
# * Revert "unit3d internal flag debugging" by @Audionut in 23e1b08
# * fix: screens compression when image overlay by @Audionut in 66dcc2b
# * Add further support for IHD tracker (#1027) by @FortKnox1337 in f0a13f4
# * Refactor UNIT3D description handling (#1007) by @wastaken7 in 9949c1e
# * description fixes by @Audionut in 1d13584
# * mps support 1 MiB by @Audionut in 8d328b5
# * fix audio track counting by @Audionut in ce4529a
# * allow override scene imdb by @Audionut in f988749
# * fix search_imdb by @Audionut in bfbc68f
# * cleanup HDB description handling by @Audionut in a9b20a5
# * RTF: get all the years by @Audionut in 37836f7
# * fix(SHRI) ignores akas titles with "attributes" (alternative titles) (#1032) by @braingremlin in 0823f78
# * TL: fix unbound variable 'torrent_id' (#1034) by @wastaken7 in a533425
# * check image hosts before async upload (#1033) by @Audionut in 4fc63d8
# * refactor(DC): streamline torrent naming convention and remove duplicate title check (#1036) by @wastaken7 in ebb0d78
# * Fix list formatting on different websites (#1038) by @wastaken7 in 3295781
# * add support for multi-client injection (#1037) by @wastaken7 in 02865c7
# * BHD: adjust size bbcode for new site fix by @Audionut in 5c69c2b
# * Update eMuwarez base url (#1040) by @Jesús José Maldonado Arroyo in bf6ecaa
# * refactor language checks to use common method across trackers (#1030) by @wastaken7 in 66d7a05
# * rehosting: Use listdir instead of glob for PNG files (#1035) by @WOSSFOSS in e382ed9
# * fix qui searching by @Audionut in d6757cc
# * filter empty injection clients by @Audionut in 9f1f616
# * Update LT.py (#1044) by @Hielito in a4ecf7e
# * fix: remove space before 'AKA' in anime title formatting (#1042) by @wastaken7 in dc3397d
# * fix qui url by @Audionut in 4e7c4b2
# * ANT: all type ids by @Audionut in a2471d0
# * remove debugger by @Audionut in a237d6a
# * Add language-data optional to langcodes (#1046) by @WOSSFOSS in 2d82858
# * BHD: exclude 2160p by default when framestor and hdr release by @Audionut in 2066f68
# * dupe checking: fix remux check by @Audionut in f47307e
# * unit3d: fix existing search when edition by @Audionut in 70cc612
# * fix DVD mediainfo use ifo by @Audionut in a795bc8
# * fix bdinfo progress output by @Audionut in 55ca8cf
# * Add TLZ support (#1048) by @FortKnox1337 in a98eb50
# * ACM: fix multi-disc bdinfo by @Audionut in 25647d4
# * TL: fix NFO upload with cookie method (#1049) by @wastaken7 in 9faaf47
# * Refactor TVC tracker with enhanced metadata handling and description generation (#1025) by @Lusephur in e2ba3a7
# * 6.3 release notes by @Audionut in 65f2f55
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v6.2.3...v6.3.0
"""

__version__ = "v6.2.3"

"""
Release Notes for version v6.2.3 (2025-10-27):

# ## What's Changed
# 
# * set torrent_properties by @Audionut in 96d41b8
# * discparse.py - Use BDInfo on PATH if available (Linux) (#952) by @noobiangodd in bd52996
# * tvdb improvements by @Audionut in 5891db5
# * BT: add internal upload support (#953) by @wastaken7 in daeadbe
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v6.2.2...v6.2.3
"""


"""
Release Notes for version v6.2.2 (2025-10-26):

# ## What's Changed
# 
# * fix tvdb pagination by @Audionut in 1c4f9b6
# * S/E overrides by @Audionut in 84787af
# * tvdb safe settings by @Audionut in d4de654
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v6.2.1...v6.2.2
"""


"""
Release Notes for version v6.2.1 (2025-10-26):

# ## What's Changed
# 
# * fix: prevent error with missing config by @Audionut in 1398458
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v6.2.0...v6.2.1
"""


"""
Release Notes for version v6.2.0 (2025-10-26):

# 
# ## RELEASE NOTES
#  - New site support - ImmortalSeed, Emuwarez.
#  - New modules required, update with requirements.txt.
#  - Linux specific mediainfo binaries for DVD support. Uninstall existing 'pymediainfo' before running requirements.txt.
#  - Removed oxipng support, using ffmpeg based compression instead.
#  - TVDB for all.
#  - Refactored cookie/site validation processing, to speed processing.
#  - New feature, site checking. Use as 'python3 upload.py path_to_movie_folder --queue a_queue_name -sc -ua'. Append trackers as needed. You can also append '-req' (or config option). This will find all matching content from the input directory, that can be uploaded to each tracker (and list any request). Log files for each tracker will be created in the UA tmp directory.
#  - Alternatively, you can remove '-sc' from the above example, and let UA just upload content from the input directory instead of logging. You may wish to append '-lq' with a numeric value to limit the amount of successful uploads processed.
# 
# ## New config options - see example.py
#  - Multiple client searching for existing torrent files.
#  - Specific injection client.
#  - ffmpeg based compression option.
# 
# ---
# 
# ## What's Changed
# 
# * Add banned groups to CBR tracker: DragsterPS, DRENAN, S74Ll10n (#885) by @franzopl in 5c7db2b
# * linux specific mi binaries (#886) by @Audionut in f838eff
# * force mediainfo by @Audionut in 01fc6c9
# * fix: args key (#889) by @GizmoBal in 1a94f57
# * catch exceptions by @Audionut in 1c82a9e
# * unit3d description handling update by @Audionut in b292887
# * add prompt for ANT ids by @Audionut in c60328e
# * Refactor SHRI (#888) by @TheDarkMan in a129a0e
# * feat(SHRI): improve audio string cleaning in SHRI tracker (#893) by @TheDarkMan in 968d575
# * OE-OTW rules compliance by @Audionut in ffb3424
# * fixing imgur issue with TVC and making some improvements (#894) by @swannie-eire in 5b7ebf4
# * Fix race condition in get_mediainfo_section by removing unnecessary asyncio usage (#895) by @wastaken7 in abdfee7
# * SHRI: handle bitrate conversion errors in audio track processing (#896) by @TheDarkMan in b783158
# * feat: add site checking by @Audionut in 83718c0
# * feat: injection client by @Audionut in 68ca252
# * wrap child process kill by @Audionut in 28a99f2
# * PTP: fix missing import by @Audionut in 289e9b4
# * SHRI: improve encoding detection (#902) by @TheDarkMan in 73deae4
# * ITT: add naming conventions and request research (#900) by @wastaken7 in 2dedf50
# * add EMUW tracker support (#898) by @Kaiser in 98ec8ec
# * fix(ITT): missing mapping_only (#903) by @wastaken7 in 3884b89
# * always regenerate mi by @Audionut in 04c70a8
# * SHRI: handle list sources  (#905) by @TheDarkMan in 0014260
# * distributor from edition only when is_disc by @Audionut in 6283beb
# * UNIT3D: catch upload permission & incorrect API key (#904) by @wastaken7 in 2b27633
# * Add Nebula streaming service (#906) by @WOSSFOSS in a2cd15d
# * rules compliance updates by @Audionut in aafc3b0
# * update -sc handling to work as only a tracker search by @Audionut in 22e912d
# * DP: enable request search (#912) by @wastaken7 in b897ff2
# * better -sc handling by @Audionut in 269d810
# * YUS: disabled request searching by @Audionut in bad14bc
# * remove print by @Audionut in 1c0c03c
# * log requests by @Audionut in 27ee1d5
# * fix logging only sucessfull trackers by @Audionut in c1f04c3
# * site_searching: save aither trumpables by @Audionut in d6e487a
# * site_searching: always request search by @Audionut in d6293c9
# * fix(SHRI): normalize Blu-ray to BluRay for non-DISC types (#914) by @TheDarkMan in 1faa0a6
# * AITHER: add request support by @Audionut in 3941841
# * site_check: cleanup queue printing by @Audionut in 9b82a6c
# * fix(SHRI): correct WEB-DL vs WEBRip detection logic (#916) by @TheDarkMan in c05bbc9
# * feat: cache qbit login (#918) by @WOSSFOSS in 25755f5
# * banned groups update on CBR.py (#920) by @franzopl in 63c3f67
# * fix(SHRI): improve release group tag extraction (#921) by @TheDarkMan in e37c36e
# * blu, remove webdv by @Audionut in b1888e6
# * HHD: no dvdrip by @Audionut in 517247e
# * BJS, ASC: add missing internal group detection (#923) by @wastaken7 in d516502
# * fix(SHRI): detect GPU encodes via empty BluRay metadata (#924) by @TheDarkMan in 6dffda3
# * ANT: adult screens by @Audionut in c039dce
# * OTW: naming fixes by @Audionut in 8c4c75d
# * use combined genre check by @Audionut in 6211f21
# * LT: enhance category detection and add Spanish language checks (#925) by @wastaken7 in e954f12
# * ULCX: fail safe with adult screens by @Audionut in fb1c61f
# * BT: add scene flag (#927) by @wastaken7 in a2e6527
# * HUNO: correct HFR placement by @Audionut in cbb3bef
# * ANT: flagchange adult screens by @Audionut in d30290b
# * ANT: useragent by @Audionut in 43a3795
# * SHRI: improve type detection for DV profile encodes (#929) by @TheDarkMan in f83f0b8
# * Slice upload of comparison screenshots on HDB. (#930) by @GizmoBal in 58d0793
# * BHD: remove screensperrow handling by @Audionut in b544769
# * HUNO: replace dubbed by @Audionut in 58be987
# * BLU: fix webdv name replacement by @Audionut in 4895d64
# * TL: Fix wrong syntax (#932) by @WOSSFOSS in 3f54319
# * TL: fix unbound error in torrent edit (#933) by @WOSSFOSS in c4685da
# * RF: domain change by @Audionut in e62fd96
# * adult content handling by @Audionut in 04d8c4a
# * better matching against adult content by @Audionut in 373bbb4
# * fix(SHRI): improve hybrid detection logic in SHRI tracker (#937) by @TheDarkMan in a6b8c5f
# * Center ordinary screens on HDB (#936) by @GizmoBal in df0b521
# * refactor: centralize cookie validation and upload logic (#883) by @wastaken7 in 76daec4
# * fix setting BHD id's by @Audionut in 131849b
# * ASC: Fix anime related issues (#939) by @wastaken7 in fb57fb3
# * CZ: add client matching (#945) by @FortKnox1337 in 06339ae
# * Added support for ImmortalSeed (#942) by @wastaken7 in 644e0ad
# * raise exceptions by @Audionut in 81619c4
# * Use ffmpeg compression instead of oxipng (#946) by @Audionut in 79130f9
# * refactor tvdb (#941) by @Audionut in f0b70dc
# * feat: multiple searching client support (#913) by @Audionut in 06c04a3
# * release notes by @Audionut in dad66b6
# * patch qui torrent comments by @Audionut in 0892720
# * HUNO text size by @Audionut in eac97c6
# * HUNO: screens per row fix by @Audionut in 624a825
# * fix args parsing by @Audionut in a21cebc
# * fix missing key set by @Audionut in ed0f1c4
# * fix(SHRI): web and remux handling (#947) by @TheDarkMan in 194e4ab
# * unit3d follow redirects by @Audionut in 8ef665c
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v6.1.1...v6.2.0
"""


"""
Release Notes for version v6.1.1 (2025-10-11):

# ## What's Changed
# 
# * fix(BJS): NoneType error (#880) by @wastaken7 in 88e7f40
# * fix: ASC IMDb link, signatures (#884) by @wastaken7 in f555acf
# * fix: anime tagging by @Audionut in 1ebb00c
# * fix: skip checking AV1 encode settings by @Audionut in 4741097
# * tvmaze episode data use meta objects by @Audionut in d805d85
# * tvmaze - rely on meta object for additional check by @Audionut in f82babf
# * set meta object by @Audionut in 968cee7
# * unit3d bbcode parser, white space handling by @Audionut in 55f636c
# * BHD fix empty returns by @Audionut in 63d49d1
# * Revert "unit3d bbcode parser, white space handling" by @Audionut in b22b12d
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v6.1.0...v6.1.1
"""


"""
Release Notes for version v6.1.0 (2025-10-10):

# 
# ## RELEASE NOTES
#  - Some large refactoring of description type handling for some sites, to speed the upload process.
#  - The actual ffmpeg process now respects process_limit set via config.py.
#  - The author has seen some issues with latest ffmpeg versions. August based releases work fine here.
# 
# ## New config options - see example.py
#  - prefer_max_16_torrent which will choose an 16 MiB torrent or lower when finding a suitable existing torrent file to use.
#  - full_mediainfo in some tracker sections, to choose whether to use the full mediainfo or not.
# 
# ---
# 
# ## What's Changed
# 
# * fix(BLU): derived handling not needed any longer by @Audionut in ca2f507
# * fix: frame overlay by @Audionut in b40094f
# * remove tags from arrs by @Audionut in 9c90277
# * BLU: fix double aka by @Audionut in d93805c
# * allow debug without apikey by @Audionut in bd27a55
# * BLU : rule compliance by @Audionut in 9d8a2b8
# * BLU: correct group capitalization by @Audionut in 1a020d2
# * PTP: fix getting groupID when multiple search results by @Audionut in e39b95c
# * fx: sticky id args through functions by @Audionut in 7a018b1
# * fix: custom link dir name by @Audionut in bbcd94f
# * Update to ULCX banned groups (#858) by @Zips-sipZ in ebef94b
# * fix tracker search return by @Audionut in edb10d0
# * unattended skip by @Audionut in 4dfab79
# * ACM fix description by @Audionut in e9f1627
# * fix: don't guessit tags from files by @Audionut in 3c27387
# * catch arr type file renames by @Audionut in 98ac5c6
# * refactor bdmv MI handling (#853) by @Audionut in 966158d
# * fix: site based language handling by @Audionut in 3592157
# * fix(AVISTAZ): torrent naming conventions, media code search, tokens (#862) by @wastaken7 in 46c8ee0
# * fix(AVISTAZ): ensure year is converted to string when modifying upload name (#863) by @wastaken7 in 92731d2
# * ULCX: aka is aka except when it's not aka because other aka is aka by @Audionut in aecb72e
# * AL: return empty string for mal_rating (#866) by @WOSSFOSS in 087d7a1
# * feat: add region and distributor information to get_confirmation (#868) by @wastaken7 in b2701a5
# * Update banned groups in DP.py (#870) by @emb3r in 0502d68
# * Both [code] and [quote] should coexist in PTP descriptions (#869) by @GizmoBal in df22996
# * fix: IMDb returns title as aka by @Audionut in 417c932
# * BLU IMDb naming by @Audionut in f519e23
# * fix warmup config by @Audionut in d15a7de
# * wrap capture task in semaphore by @Audionut in 3a4c5f7
# * some tracker specific in torrent creation by @Audionut in 91fe360
# * fix: piece size preference in auto torrent and add 16 MiB option by @Audionut in 9a6ce33
# * TVC: restrict image hosts by @Audionut in 838fc4b
# * fix torrent validation logic by @Audionut in 3de9fa6
# * remove pointless print by @Audionut in 240f828
# * fix(BJS): remove unnecessary raise_for_status call in response handling (#873) by @wastaken7 in 76431f9
# * validate encode settings (#871) by @Audionut in 2f804c6
# * HUNO: fix internal state by @Audionut in 5d2e8da
# * feature: add configurable disc requirements per tracker (#878) by @TheDarkMan in d1b18bf
# * feat(SAM): add name processing and add additional checks for Portuguese audio/subtitle tracks (#879) by @wastaken7 in 1f2c41a
# * Simplify tracker specific torrent recreation by @Audionut in 65b62d7
# * fix: region when None by @Audionut in e52b4ff
# * print tracker name changes by @Audionut in eefa20c
# * Enhance metadata handling, description building, and refactor tracker integrations (#860) by @wastaken7 in ee1885b
# * fix versioning by @Audionut in 00eae1c
# * release notes by @Audionut in 1e59d0d
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v6.0.1...v6.1.0
"""


"""
Release Notes for version v6.0.1 (2025-10-04):

# ## What's Changed
# 
# * fix version file by @Audionut in c8ccf5a
# * erroneous v in version file by @Audionut in 5428927
# * Fix YUS get_type_id (#850) by @oxidize9779 in 25591e0
# * fix: LCD and UNIT3D upload (#852) by @wastaken7 in f5d11b8
# * Update banned release groups of various trackers (#848) by @flowerey in 9311996
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v6.0.0...v6.0.1
"""


"""
Changelog for version v6.0.0 (2025-10-03):

# ## RELEASE NOTES
# - Immense thanks to @wastaken7 for refactoring the unit3d based tracker code. A huge QOL improvement that removed thousands of lines of code.
# - To signify the continued contributions by @wastaken7, this project is now know simply as "Upload Assistant".
# - New package added, run requirements.txt
# - This release contains lengthy refactoring of many code aspects. Many users, with thanks, have been testing the changes and giving feedback.
# - The version bump to v6.0.0 signifies the large code changes, and you should follow an update process suitable for yourself with a major version bump.

## New config options - see example.py
# - FFMPEG related options that may assist those having issues with screenshots.
# - AvistaZ based sites have new options in their site sections.
# - "use_italian_title" inside SHRI config, for using Italian titles where available
# - Some HDT related config options were updated/changed
# - "check_predb" for also checking predb for scene status
# - "get_bluray_info" updated to also include getting DVD data
# - "qui_proxy_url" inside qbittorrent client config, for supporting qui reverse proxy url

# ## WHAT'S NEW - some from last release
# - New arg -sort, used for sorting filelist, to ensure UA can run with some anime folders that have allowed smaller files.
# - New arg -rtk, which can be used to process a run, removing specific trackers from your default trackers list, and processing with the remaining trackers in your default list.
# - A significant chunk of the actual upload process has been correctly asynced. Some specific site files still need to be updated and will slow the process.
# - More UNIT3D based trackers have been updated with request searching support.
# - Added support for sending applicable edition to LST api edition endpoint.
# - NoGrp type tags are not removed by default. Use "--no-tag" if desired, and/or report trackers as needed.

# ## What's Changed
# 
# * fix(GPW) - do not print empty descriptions (#805) by @wastaken7 in 07e8334
# * SHRI - Check group tag and Italian title handling (#803) by @Tiberio in 054ce4f
# * fix(HDS) - use [pre] for mediainfo to correctly use monospaced fonts (#810) by @wastaken7 in aa62941
# * fix(BT) - status code, post data, torrent id (#808) by @wastaken7 in 5ff6249
# * feat(UNIT3D) - refactor UNIT3D websites to reuse common code base (#801) by @wastaken7 in 03c8ffd
# * ANT - fix trying to call lower on dict by @Audionut in 9772b0a
# * SHRI - Remove 'Dubbed', add [SUBS] tag (#815) by @Tiberio in 788be1c
# * graceful exit by @Audionut in ddbd135
# * updated unit3d trackers - request support by @Audionut in a680692
# * release notes by @Audionut in 49efdca
# * Update FNP resolution id (#818) by @oxidize9779 in 48fa975
# * refactor(HDT) (#821) by @wastaken7 in 2365937
# * more async (#819) by @Audionut in b7aea98
# * print in debug by @Audionut in 9b68819
# * set screens from manual frames by @Audionut in b9ef753
# * more debugging by @Audionut in 5ad4fce
# * more debugging by @Audionut in 7902066
# * Refine dual-audio detection for zxx (#822) by @GizmoBal in ab27990
# * fix extended bluray parsing by @Audionut in cae1c38
# * feat: Improve duplicate search functionality (#820) by @wastaken7 in 3b59c03
# * remove dupe requirement by @Audionut in 5ebdc86
# * disable filename match by @Audionut in 63adf3c
# * fix unit3d flags by @Audionut in 3555d12
# * exact filename fix by @Audionut in 69aa3fa
# * Improve NFO downloading robustness (#827) by @noobiangodd in 09bc878
# * PTP redact token by @Audionut in eec5d60
# * enable predb by @Audionut in a073247
# * qbit retries and async calls by @Audionut in 9146011
# * add sleeps to pack processing by @Audionut in ed7eda9
# * add DOCPLAY by @Audionut in aa97763
# * fix unit3d flags api by @Audionut in 506ea47
# * LST edition ids by @Audionut in df7769a
# * more parsers to lxml by @Audionut in e62e819
# * fix pack image creation by @Audionut in 220c5f2
# * fix request type checking by @Audionut in a06c1dd
# * Fix crash when no edit args provided (handle no/empty input safely) (#826) by @ca1m985 in 4cbebc4
# * catch keyboard interruptions in cli_ui by @Audionut in ca76801
# * don't remove nogrp type tags by default by @Audionut in 25b5f09
# * AZ network fixes by @Audionut in 50595c2
# * fix: only print overlay info if relevant by @Audionut in 4e6a5ce
# * add(meta): video container (#831) by @wastaken7 in c55094a
# * fix: frame overlay check tracker list check by @Audionut in 6d7fa3c
# * fix use_libplacebo false by @Audionut in d1044c9
# * fix: improve container detection for different disc types (#835) by @wastaken7 in 073126c
# * set safe debugging languages by @Audionut in bfe964a
# * print automated ffmpeg tonemap checking failure by @Audionut in bebe17c
# * fix: don't overwrite ids from mediainfo by @Audionut in f3fa16c
# * HDT - auth token availability (#839) by @Audionut in 57af870
# * Add support for bluray.com scraping for DVDs (#828) by @9Oc in 6274db1
# * Update config-generator.py (#846) by @AzureBelmont in 070062c
# * fix(ANT): add type and audioformat to post data (#845) by @wastaken7 in 3424794
# * refactor: replace UploadException with tracker_status handling, where applicable (#840) by @wastaken7 in 502e40d
# * cleanup handling for android by @Audionut in 1702d3d
# * add support for qui reverse proxy (#833) by @Audionut in 9a9b3c4
# * improvement: avoid re-executing validate_credentials by temporarily saving tokens in meta (#834) by @wastaken7 in ff99d08
# * release notes by @Audionut in a924df4
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v5.4.3...v6.0.0
"""

__version__ = "5.4.3"

"""
Release Notes for version v5.4.3 (2025-09-19):

# ## What's Changed
# 
# * category regex tweak by @Audionut in f7c02d1
# * Fix HUNO UHD remux (#767) by @oxidize9779 in 1bb0ae8
# * Update to banned groups ULCX.py (#770) by @Zips-sipZ in dd0fdd9
# * fix(HDT): update base URL (#766) by @wastaken7 in bb16dc3
# * fix(BJS): Remove Ultrawide tag detection from remaster tags (#768) by @wastaken7 in 99e1788
# * Added support for AvistaZ (#769) by @wastaken7 in 5bdf3cd
# * TL - api upload update by @Audionut in 341248a
# * add tonemapping header to more sites by @Audionut in 307ba71
# * fix existing tonemapped status by @Audionut in 4950b08
# * HDB - fix additional space in name when atmos by @Audionut in 8733c65
# * fix bad space by @Audionut in 9165411
# * set df encoding by @Audionut in 323a365
# * TL api tweaks by @Audionut in 9fbde8f
# * TL - fix search existing option when api by @Audionut in 534ece7
# * TL - add debugging by @Audionut in ab37785
# * fix bad copy/paste by @Audionut in 6d25afd
# * TL - login update by @Audionut in 677cee8
# * git username mapping by @Audionut in 60ed690
# * FNP - remove a group for banned release groups (#775) by @flowerey in ab4f79a
# * Added support for CinemaZ, refactor Z sites to reuse common codebase (#777) by @wastaken7 in f14066f
# * Update titles of remux for HDB (#778) by @GizmoBal in b9473cb
# * Added support for GreatPosterWall (#779) by @wastaken7 in 4dc1b65
# * SHRI - language handling in name by @Audionut in 5ee449f
# * fix(GPW) - timeout, screenshots, check available slots (#789) by @wastaken7 in 5862df4
# * fix(AvistaZ sites) - languages, resolution, naming, rules (#782) by @wastaken7 in 10bf73f
# * add argument trackers remove by @Audionut in 1b0c549
# * add(region.py) - Kocowa+ (#790) by @wastaken7 in da0b39a
# * fix(CBR.py) - UnboundLocalError when uploading a full disc (#791) by @wastaken7 in dbe3964
# * Fix HUNO bit rate detection (#792) by @oxidize9779 in da1b891
# * SHRI - remove dual audio by @Audionut in 5f94385
# * add argument -sort (#796) by @Audionut in 0d0f1a4
# * add config options for ffmpeg (#798) by @Audionut in 0dc4275
# * add venv to .gitignore (#797) by @Tiberio in 5edfbeb
# * strip multiple spaces from bdinfo (#786) by @Audionut in 38a09aa
# * fix SHRI dual audio brain fart by @Audionut in 8623b18
# * BHD - request search support (#773) by @Audionut in f0f5685
# * can't spell by @Audionut in 159fc0f
# * update DP ban list (#800) by @emb3r in 42dd363
# * fix(Avistaz) - add XviD/DivX to meta (#793) by @wastaken7 in a797844
# * Remove TOCASHARE from supported sites (#802) by @wastaken7 in cf25142
# * conform to GPW description image rules (#804) by @GuillaumedeVolpiano in 24c625e
# * add(get_name.py) - year for DVD's, audio for DVDRip's (#799) by @wastaken7 in adfb263
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v5.4.2...v5.4.3
"""


"""
Release Notes for version v5.4.2 (2025-09-03):

# ## What's Changed
# 
# * enhance(PHD): add search requests option, tags and other changes (#749) by @wastaken7 in 1c970ce
# * enhance(BT): use tmdb cache file and other changes (#750) by @wastaken7 in a793060
# * enhance(HDS): add search requests option and other changes (#751) by @wastaken7 in b0f88e3
# * python does python things by @Audionut in 057d2be
# * FNP - fix banned groups (#753) by @flower in 54c5c32
# * more python quoting fixes by @Audionut in d8a6779
# * MOAR quotes by @Audionut in 7a62585
# * chore: fix incompatible f-strings with python 3.9  (#754) by @wastaken7 in 9a8f190
# * fix(HUNO) - add multi audio, UHD BluRay naming (#756) by @wastaken7 in 5b41f4d
# * fix default tracker list through edit process by @Audionut in 354e9c1
# * move sanatize meta definition by @Audionut in 9d2991b
# * catch mkbrr config error by @Audionut in 34e05f9
# * Added HDT (HD-Torrents) to client.py to allow tracker removal (#760) by @FortKnox1337 in 6c5bbc5
# * fix(PHD): add BD resolution, basic description, remove aka from title (#761) by @wastaken7 in 8459a45
# * fix(DC): Resize images in description generation (#762) by @wastaken7 in 41d7173
# * add(client.py): skip more trackers (#763) by @wastaken7 in 61dfd4a
# * HUNO - unit3d torrent download by @Audionut in 637a145
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v5.4.1...v5.4.2
"""


"""
Release Notes for version v5.4.1 (2025-09-02):

# ## What's Changed
# 
# * fix missing trackers for language processing (#747) by @wastaken7 in 34d0b4b
# * add missing function to common by @Audionut in 33d5aec
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v5.4.0...v5.4.1
"""


"""
Release Notes for version v5.4.0 (2025-09-02):

# 
# ## RELEASE NOTES
#  - Blutopia has a peer scraping issue that resulted in UNIT3D codebase being updated, requiring torrent files to be created site side. See https://github.com/HDInnovations/UNIT3D/pull/4910
#  - With the infohash being randomized site side, UA can no longer create valid torrent files for client injection, and instead the torrent file needs to be downloaded for client injection.
#  - All UNIT3D based sites have been updated to prevent any issues moving forward as other sites update their UNIT3D codebase.
#  - This will cause small slowdown in the upload process, as each torrent file is downloaded from corresponding sites.
#  - Announce URLS for the supported sites are no longer needed in config, check example-config.py for the removed announce urls.
# 
# ## WHAT'S NEW
#  - UA can now search for related requests for the uploaded content, allowing you to quickly and easily see which requests can be filled by your upload.
#  - Request checking via config option (see example-config) or new arg (see --help)
#  - Only ASC, BJS and ULCX supported currently
#  - Added a new arg to skip auto torrent searching
# 
# ---
# 
# ## What's Changed
# 
# * Added support for PTSKIT (#730) by @wastaken7 in 19ccbe5
# * add missing site details (#731) by @wastaken7 in e96cd15
# * LCD - fix region, mediainfo, naming (#732) by @wastaken7 in de38dba
# * SPD - fix and changes (#727) by @wastaken7 in 16d310c
# * BLU - update torrent injection (#736) by @wastaken7 in a2d14af
# * Fix BHD tracker matching (#740) by @backstab5983 in 80b4337
# * fix(SPD): send description to BBCode-compatible field (#738) by @wastaken7 in 95e5ab7
# * Update HDB.py to clean size bbcode (#734) by @9Oc in 8d15765
# * Update existing client-tracker search to add 3 more trackers (#728) by @FortKnox1337 in 3dcbb7c
# * correct screens track mapping and timeout by @Audionut in c9d5466
# * skip auto torrent as arg by @Audionut in b78bb0a
# * fix queue handling when all trackers already in client by @Audionut in aae803f
# * skip pathed torrents when edit mode by @Audionut in eafb38c
# * preserve sat true by @Audionut in ffaddd4
# * ULCX - remove hybrid from name by @Audionut in 1f02274
# * fix existing torrent search when not storage directory and not qbit by @Audionut in 85e653f
# * DP - no group tagging by @Audionut in f4e236d
# * HDB - music category by @Audionut in 6a12335
# * Option - search tracker requests (#718) by @Audionut in 2afce5b
# * add tracker list debug by @Audionut in 5418f05
# * enhance(ASC): add localized TMDB data and search requests option (#743) by @wastaken7 in e2a3963
# * refactor unit3d torrent handling (#741) by @Audionut in 56b3b14
# * enhance(DC): httpx, MediaInfo for BDs, and upload split (#744) by @wastaken7 in de98c6e
# * PT- ensure audio_pt and legenda_pt flags only apply to European Portuguese (#725) by @Thiago in f238fc9
# * fix TAoE banned group checking by @Audionut in 1e8633c
# * enhance(BJS): add localized TMDB data and search requests option (#746) by @wastaken7 in e862496
# * redact passkeys from debug prints by @Audionut in 89809bb
# * clarify request usage by @Audionut in 5afafc0
# * BJS also does request searching by @Audionut in d87f060
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v5.3.6...v5.4.0
"""


"""
Release Notes for version v5.3.6 (2025-08-22):

# ## What's Changed
# 
# * fix docker mkbrr version by @Audionut in 69a1384
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v5.3.5...v5.3.6
"""


"""
Release Notes for version v5.3.5 (2025-08-22):

# ## What's Changed
# 
# * TL - cleanup torrent file handling (#714) by @wastaken7 in 011d588
# * ANT tag reminder by @Audionut in fbb8c2f
# * Added support for FunFile (#717) by @wastaken7 in 6436d34
# * ULCX - aka check by @Audionut in 3b30132
# * ANT - manual commentary flag (#720) by @wastaken7 in d8fd725
# * [FnP] Fix resolutions, types and add banned release groups (#721) by @flower in 5e38b0e
# * Revert "Dockerfile Improvements (#710)" by @Audionut in c85e83d
# * fix release script by @Audionut in d86999d
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v5.3.4...v5.3.5
"""


"""
Release Notes for version v5.3.4 (2025-08-18):

# 
# ## RELEASE NOTES
#  - UA can now tonemap Dolby Vision profile 5 and HLG files.
#  - Requires a compatible ffmpeg (get latest), see https://github.com/Audionut/Upload-Assistant/pull/706
#  - Adjust the related ffmpeg option in config, if you have a suitable ffmpeg installed, in order to skip the automated check
# 
# ---
# 
# ## What's Changed
# 
# * RF - now needs 2fa enabled to upload by @Audionut in e731e27
# * TL - fix outdated attribute (#701) by @wastaken7 in ebabb5d
# * Fix typo in source flag when uploading to SHRI (#703) by @backstab5983 in 0e5bb28
# * Catch conformance error from mediainfo and warn users (#704) by @Khoa Pham in febe0f1
# * Add correct country get to IMDb (#708) by @Audionut in e09dbf2
# * catch empty array from btn by @Audionut in 77b539a
# * highlight tracker removal by @Audionut in 95a9e54
# * Fix img_host and None types (#707) by @frenchcutgreenbean in c34e6be
# * Option - libplacebo tonemapping (#706) by @Audionut in 3fc3c1a
# * fix docker tagging by @Audionut in 0071c71
# * clean empty bbcode from descriptions by @Audionut in 73b40b9
# * require api key to search by @Audionut in ce7bec6
# * Dockerfile Improvements (#710) by @Slikkster in 0b50d36
# * restore docker apt update by @Audionut in a57e514
# * PHD - fix region logic (#709) by @wastaken7 in 5e1c541
# * fix unit3d trackers not accept valid tvdb by @Audionut in 309c54e
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v5.3.3...v5.3.4
"""


"""
Release Notes for version v5.3.3 (2025-08-14):

# 
# ## RELEASE NOTES
#  - New module added requiring update via requirements.txt. See README for instructions.
# 
# ---
# 
# ## What's Changed
# 
# * use all of result when specific is NoneType by @Audionut in 15faaad
# * don't print guessit error in imdb by @Audionut in 3b21998
# * add support for multiple announce links (#691) by @wastaken7 in 4a623d7
# * Added support for PHD (#689) by @wastaken7 in 1170f46
# * pass meta to romaji by @Audionut in 6594f2c
# * DC - API update (#695) by @wastaken7 in 14380f2
# * remove trackers found in client (#683) by @Audionut in 3207fd3
# * Add service Chorki (#690) by @razinares in fa16ebf
# * fix docker mediainfo install (#699) by @Audionut in aa84c07
# * Option - send upload urls to discord (#694) by @Audionut in 29fbcf5
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v5.3.2...v5.3.3
"""


"""
Release Notes for version v5.3.2 (2025-08-11):

# ## What's Changed
# 
# * AR - catch multiple dots in name by @Audionut in 5d5164b
# * correct meta object before inputting data by @Audionut in 166a1a5
# * guessit fallback by @Audionut in eccef19
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v5.3.1...v5.3.2
"""


"""
Release Notes for version v5.3.1 (2025-08-10):

# ## What's Changed
# 
# * TVDB series name not nonetype by @Audionut in 1def355
# * remove compatibility tracks from dupe/dubbed checking by @Audionut in 48e922e
# * fix onlyID (#677) by @Audionut in 29b8caf
# * BT & BJS - fix language, add user input (#678) by @wastaken7 in 51d89c5
# * fix: update SP category logic (#679) by @groggy9788 in 9ed3b2d
# * update mkbrr and add threading control (#680) by @Audionut in 316afe1
# * add tv support for emby (#681) by @Audionut in 0de649b
# * add service XUMO by @Audionut in 633f151
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v5.3.0...v5.3.1
"""


"""
Release Notes for version v5.3.0 (2025-08-08):

# 
# ## NOTES
#  - From the previous release, screenshots in description were modified. Check the options in the example-config to handle to taste, particularly https://github.com/Audionut/Upload-Assistant/blob/f45e4dd87472ab31b79569f97e3bea62e27940e0/data/example-config.py#L70
# 
# 
# ## RELEASE NOTES
#  - UA will no longer, 'just pick the top result suggested by TMDb'.
#  - Instead, title parsing has been significantly improved. Now UA will use a weight based system that relies on the title name, AKA name  and year .
#  - Old scene releases such as  will easily defeat the title parsing, however these releases will get an IMDB ID from srrdb, negating this issue. Poorly named P2P releases are exactly that.
#  - Unfortunately, not only are there many, many releases that have exactly matching names, and release years, TMDb's own sorting algorithm doesn't perfectly return the correct result, as the first result, always.
#  - This means that a prompt is required. UA will display a shortened list of results for you to select, an allows manual entry of the correct TMDb ID, such as /.
#  - Given that UA would have just selected the first result previously, which could have been incorrect, some percentage of time, the net result should be a better overall user experience, since the wrong return previously required manual intervention in any event, and may have been missed previously, leading to lack luster results.
#  - As always, feeding the correct ID's into UA always leads to a better experience. There are many options to accomplish this task automatically, and users should familiarize themselves with the options outlined in the example.config, and/or user-args.json
#  - Overall SubsPlease handling should be greatly increased......if you have TVDB login details.
# 
#  ## NOTEWORTHY UPDATES
#   - Two new trackers, BT and BJS have been added thanks to @wastaken7
#   - PSS was removed as offline
#   - The edit pathway, when correcting Information, should now correctly handle existing args thanks to @ppkhoa
#   - Some additional context has been added regarding ffmpeg screen capture issues, particularly on seedboxes, also see https://github.com/Audionut/Upload-Assistant/wiki/ffmpeg---max-workers-issues
#   - Additional trackers have been added for getting existing ids, but they are currently only available via auto torrent searching
#   - Getting data from trackers now has a cool off period. This should not be noticed under normal circumstances. PTP has a 60 second cool off period, which was chosen to minimize interference with other tools.
# 
# ---
# 
# ## What's Changed
# 
# * update install/update instructions by @Audionut in 6793709
# * TMDB retry (#646) by @Audionut in 84554d8
# * fix missing tvdb credential checks by @Audionut in 28b0561
# * cleanup ptp description/images handling by @Audionut in 271fc5f
# * fix bad copy/paste by @Audionut in d075a11
# * set the ptp_imagelist by @Audionut in 3905248
# * add option to select specific new files for queue (#648) by @Audionut in 8de31e3
# * TMDB retry, set object by @Audionut in 12436ff
# * robust framerate by @Audionut in 955be6d
# * add clarity of max workers issues on seedboxes by @Audionut in d38f265
# * add linux ffmpeg check by @Audionut in 89bf550
# * ffmpeg - point to wiki by @Audionut in 6d6246b
# * generic max workers error print by @Audionut in 71d00c0
# * handle specific ffmpeg complex error by @Audionut in 6e104ea
# * frame overlay print behind debug by @Audionut in 72804de
# * Log_file - save debug logs (#653) by @Audionut in 482dce5
# * SPD - fix imdb in search existing (#656) by @Audionut in a640da6
# * Skip torrents for AL if they don't have a MAL ID (#651) by @PythonCoderAS in 045bb71
# * overrides - import at top by @Audionut in bb662e2
# * ignore mkbrr binaries by @Audionut in 37f3d1c
# * Don't discard original args, override them (#660) by @Khoa Pham in 9554f21
# * remove PSS (#663) by @Audionut in 31a6c57
# * ULCX - remove erroneous space in name by @Audionut in 5bb5806
# * fix subplease service check by @Audionut in 9fa53ba
# * fix tmdb secondary title search by @Audionut in bf77018
# * imdb - get more crew info (#665) by @wastaken7 in 208f65c
# * Added support for BJS (#649) by @wastaken7 in 61fb607
# * BJS - add internal flag (#668) by @wastaken7 in 3cb93f5
# * BT - refactor (#669) by @wastaken7 in d1c6d83
# * BJS - safe string handling of description file by @Audionut in 7c1ef78
# * BT - safe string handling of description file by @Audionut in 67b1fce
# * rTorrent debugging by @Audionut in fb31951
# * Update release notes handling (#671) by @Audionut in f45e4dd
# * Fix manual tracker mode (#673) by @Audionut in fdf3b54
# * BT and BJS fixes (#672) by @wastaken7 in c478149
# * fix: python compatibility in BJS (#674) by @wastaken7 in 9535259
# * Add arg, skip-dupe-asking (#675) by @Audionut in 7844ce6
# * BHD - fix tracker found match by @Audionut in 4a82aed
# * TL - fix description uploading in api mode by @Audionut in d36002e
# * ffmpeg - only first video streams by @Audionut in 85fc9ca
# * Get language from track title (#676) by @Audionut in 013aed1
# * TMDB/IMDB searching refactor and EMBY handling (#637) by @Audionut in f68625d
# * Other minor updates and improvements
# 
# **Full Changelog**: https://github.com/Audionut/Upload-Assistant/compare/v5.2.1...v5.3.0
"""


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
