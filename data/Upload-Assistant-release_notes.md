v6.0.0

## RELEASE NOTES
 - Immense thanks to @wastaken7 for refactoring the unit3d based tracker code. A huge QOL improvement that removed thousands of lines of code.
 - New package added, run requirements.txt

## WHAT'S NEW - some from last release
 - Some new config options in example-config.py.
 - FFMPEG related options that may assist those having issues with screenshots.
 - AvistaZ based sites have new options in their site sections.
 - New arg -sort, used for sorting filelist, to ensure UA can run with some anime folders that have allowed smaller files.
 - New arg -rtk, which can be used to process a run, removing specific trackers from your default trackers list, and processing with the remaining trackers in your default list.
 - A significant chunk of the actual upload process has been correctly asynced. Some specific site files still need to be updated and will slow the process.
 - More UNIT3D based trackers have been updated with request searching support.
