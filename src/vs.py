# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
import vapoursynth as vs
from awsmfunc import ScreenGen, DynamicTonemap, zresize
import random
import os
from functools import partial

core = vs.core

# core.std.LoadPlugin(path="/usr/local/lib/vapoursynth/libffms2.so")
# core.std.LoadPlugin(path="/usr/local/lib/vapoursynth/libsub.so")
# core.std.LoadPlugin(path="/usr/local/lib/vapoursynth/libimwri.so")


def CustomFrameInfo(clip, text):
    def FrameProps(n, f, clip):
        # Modify the frame properties extraction here to avoid the decode issue
        info = f"Frame {n} of {clip.num_frames}\nPicture type: {f.props['_PictType']}"
        # Adding the frame information as text to the clip
        return core.text.Text(clip, info)

    # Apply FrameProps to each frame
    return core.std.FrameEval(clip, partial(FrameProps, clip=clip), prop_src=clip)


def optimize_images(image, config):
    import platform  # Ensure platform is imported here
    if config.get('optimize_images', True):
        if os.path.exists(image):
            try:
                pyver = platform.python_version_tuple()
                if int(pyver[0]) == 3 and int(pyver[1]) >= 7:
                    import oxipng
                if os.path.getsize(image) >= 16000000:
                    oxipng.optimize(image, level=6)
                else:
                    oxipng.optimize(image, level=3)
            except Exception as e:
                print(f"Image optimization failed: {e}")
    return


def vs_screengn(source, encode=None, filter_b_frames=False, num=5, dir=".", config=None):
    if config is None:
        config = {'optimize_images': True}  # Default configuration

    screens_file = os.path.join(dir, "screens.txt")

    # Check if screens.txt already exists and use it if valid
    if os.path.exists(screens_file):
        with open(screens_file, "r") as txt:
            frames = [int(line.strip()) for line in txt.readlines()]
        if len(frames) == num and all(isinstance(f, int) and 0 <= f for f in frames):
            print(f"Using existing frame numbers from {screens_file}")
        else:
            frames = []
    else:
        frames = []

    # Indexing the source using ffms2 or lsmash for m2ts files
    if str(source).endswith(".m2ts"):
        print(f"Indexing {source} with LSMASHSource... This may take a while.")
        src = core.lsmas.LWLibavSource(source)
    else:
        cachefile = f"{os.path.abspath(dir)}{os.sep}ffms2.ffms2"
        if not os.path.exists(cachefile):
            print(f"Indexing {source} with ffms2... This may take a while.")
        try:
            src = core.ffms2.Source(source, cachefile=cachefile)
        except vs.Error as e:
            print(f"Error during indexing: {str(e)}")
            raise
        if os.path.exists(cachefile):
            print(f"Indexing completed and cached at: {cachefile}")
        else:
            print("Indexing did not complete as expected.")

    # Check if encode is provided
    if encode:
        if not os.path.exists(encode):
            print(f"Encode file {encode} not found. Skipping encode processing.")
            encode = None
        else:
            enc = core.ffms2.Source(encode)

    # Use source length if encode is not provided
    num_frames = len(src)
    start, end = 1000, num_frames - 10000

    # Generate random frame numbers for screenshots if not using existing ones
    if not frames:
        for _ in range(num):
            frames.append(random.randint(start, end))
        frames = sorted(frames)
        frames = [f"{x}\n" for x in frames]

        # Write the frame numbers to a file for reuse
        with open(screens_file, "w") as txt:
            txt.writelines(frames)
        print(f"Generated and saved new frame numbers to {screens_file}")

    # If an encode exists and is provided, crop and resize
    if encode:
        if src.width != enc.width or src.height != enc.height:
            ref = zresize(enc, preset=src.height)
            crop = [(src.width - ref.width) / 2, (src.height - ref.height) / 2]
            src = src.std.Crop(left=crop[0], right=crop[0], top=crop[1], bottom=crop[1])
            if enc.width / enc.height > 16 / 9:
                width = enc.width
                height = None
            else:
                width = None
                height = enc.height
            src = zresize(src, width=width, height=height)

    # Apply tonemapping if the source is HDR
    tonemapped = False
    if src.get_frame(0).props["_Primaries"] == 9:
        tonemapped = True
        src = DynamicTonemap(src, src_fmt=False, libplacebo=True, adjust_gamma=True)
        if encode:
            enc = DynamicTonemap(enc, src_fmt=False, libplacebo=True, adjust_gamma=True)

    # Use the custom FrameInfo function
    if tonemapped:
        src = CustomFrameInfo(src, "Tonemapped")

    # Generate screenshots
    ScreenGen(src, dir, "a")
    if encode:
        enc = CustomFrameInfo(enc, "Encode (Tonemapped)")
        ScreenGen(enc, dir, "b")

    # Optimize images
    for i in range(1, num + 1):
        image_path = os.path.join(dir, f"{str(i).zfill(2)}a.png")
        optimize_images(image_path, config)
