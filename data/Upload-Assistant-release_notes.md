v5.3.0

## NOTES
 - From the previous release, screenshots in description were modified. Check the options in the example-config to handle to taste, particulary https://github.com/Audionut/Upload-Assistant/blob/f45e4dd87472ab31b79569f97e3bea62e27940e0/data/example-config.py#L70


## RELEASE NOTES
 - UA will no longer, 'just pick the top result suggested by TMDb'.
 - Instead, title parsing has been sgnificantly improved. Now UA will use a weight based system that relies on the title name, AKA name `if present` and year `if present`.
 - Old scene releases such as `groupname-reduced title name.1080p.mkv` will easily defeat the title parsing, however these releases will get an IMDB ID from srrdb, negating this issue. Poorly named P2P releases are exactly that.
 - Unfortunately, not only are there many, many releases that have exactly matching names, and release years, TMDb's own sorting algorithm doesn't perfectly return the correct result, as the first result, always.
 - This means that a prompt is required. UA will display a shortened list of results for you to select, an allows manual entry of the correct TMDb ID, such as `tv/1234`/`movie/1234`.
 - Given that UA would have just selected the first result previously, which could have been incorrect, some percentage of time, the net result should be a better overall user experience, since the wrong return previously required manual intervention in any event, and may have been missed previously, leading to lack luster results.
 - As always, feeding the correct ID's into UA always leads to a better experience. There are many options to accomplish this task automatically, and users should familirize themselves with the options outlined in the example.config, and/or user-args.json