v5.4.0

## RELEASE NOTES
 - Blutopia has a peer scraping issue that resulted in UNIT3D codebase being updated, requiring torrent files to be created site side. See https://github.com/HDInnovations/UNIT3D/pull/4910
 - With the infohash being randomized site side, UA can no longer create valid torrent files for client injection, and instead the torrent file needs to be downloaded for client injection.
 - All UNIT3D based sites have been updated to prevent any issues moving forward as other sites update their UNIT3D codebase.
 - This will cause delay in the upload process, as each torrent file is downloaded from corresponding sites.
