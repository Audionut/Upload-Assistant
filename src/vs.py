# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
from __future__ import annotations

import os
import random
from functools import partial
from typing import Any, cast

import awsmfunc as awsmfunc  # pyright: ignore[reportMissingImports]
import vapoursynth as vs  # pyright: ignore[reportMissingImports]

vs = cast(Any, vs)  # pyright: ignore[reportUnnecessaryCast]
awsmfunc = cast(Any, awsmfunc)  # pyright: ignore[reportUnnecessaryCast]
core: Any = vs.core
DynamicTonemap: Any = awsmfunc.DynamicTonemap
ScreenGen: Any = awsmfunc.ScreenGen
zresize: Any = awsmfunc.zresize

# core.std.LoadPlugin(path="/usr/local/lib/vapoursynth/libffms2.so")
# core.std.LoadPlugin(path="/usr/local/lib/vapoursynth/libsub.so")
# core.std.LoadPlugin(path="/usr/local/lib/vapoursynth/libimwri.so")


def CustomFrameInfo(clip: Any, text: str) -> Any:
    def FrameProps(n: int, f: Any, clip: Any) -> Any:
        # Modify the frame properties extraction here to avoid the decode issue
        info = f"Frame {n} of {clip.num_frames}\nPicture type: {f.props['_PictType']}"
        # Adding the frame information as text to the clip
        return core.text.Text(clip, info)

    # Apply FrameProps to each frame
    return core.std.FrameEval(clip, partial(FrameProps, clip=clip), prop_src=clip)


def optimize_images(image: str, config: dict[str, Any]) -> None:
    import platform  # Ensure platform is imported here
    if config.get('optimize_images', True) and os.path.exists(image):
        oxipng: Any | None
        try:
            pyver = platform.python_version_tuple()
            if int(pyver[0]) == 3 and int(pyver[1]) >= 7:
                import oxipng  # pyright: ignore[reportMissingImports]
                oxipng = oxipng
            else:
                oxipng = None
            if oxipng is None:
                return
            if os.path.getsize(image) >= 16000000:
                oxipng.optimize(image, level=6)
            else:
                oxipng.optimize(image, level=3)
        except Exception as e:
            print(f"Image optimization failed: {e}")
    return


def vs_screengn(source: str, encode: str | None = None, num: int = 5, dir: str = ".", config: dict[str, Any] | None = None) -> None:
    if config is None:
        config = {'optimize_images': True}  # Default configuration

    screens_file = os.path.join(dir, "screens.txt")

    # Check if screens.txt already exists and use it if valid
    if os.path.exists(screens_file):
        with open(screens_file) as txt:
            frames: list[int] = [int(line.strip()) for line in txt.readlines()]
        if len(frames) == num and all(f >= 0 for f in frames):
            print(f"Using existing frame numbers from {screens_file}")
        else:
            frames = []
    else:
        frames = []

    # Indexing the source using ffms2 or lsmash for m2ts files
    if str(source).endswith(".m2ts"):
        print(f"Indexing {source} with LSMASHSource... This may take a while.")
        src: Any = core.lsmas.LWLibavSource(source)
    else:
        cachefile = f"{os.path.abspath(dir)}{os.sep}ffms2.ffms2"
        if not os.path.exists(cachefile):
            print(f"Indexing {source} with ffms2... This may take a while.")
        try:
            src = core.ffms2.Source(source, cachefile=cachefile)
        except Exception as e:
            print(f"Error during indexing: {str(e)}")
            raise
        if os.path.exists(cachefile):
            print(f"Indexing completed and cached at: {cachefile}")
        else:
            print("Indexing did not complete as expected.")

    # Check if encode is provided
    enc: Any | None = None
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
            frames.append(random.randint(start, end))  # nosec B311
        frames = sorted(frames)
        frame_lines = [f"{x}\n" for x in frames]

        # Write the frame numbers to a file for reuse
        with open(screens_file, "w") as txt:
            txt.writelines(frame_lines)
        print(f"Generated and saved new frame numbers to {screens_file}")

    # If an encode exists and is provided, crop and resize
    if encode and enc is not None and (src.width != enc.width or src.height != enc.height):
        ref: Any = zresize(enc, preset=src.height)
        crop: list[float] = [(src.width - ref.width) / 2, (src.height - ref.height) / 2]
        src = src.std.Crop(left=crop[0], right=crop[0], top=crop[1], bottom=crop[1])
        width: int | None
        height: int | None
        if enc.width / enc.height > 16 / 9:
            width = enc.width
            height = None
        else:
            width = None
            height = enc.height
        src = zresize(src, width=width, height=height)

    # Apply tonemapping if the source is HDR
    tonemapped = False
    frame: Any = src.get_frame(0)
    if frame.props["_Primaries"] == 9:
        tonemapped = True
        src = DynamicTonemap(src, src_fmt=False, libplacebo=True, adjust_gamma=True)
        if encode and enc is not None:
            enc = DynamicTonemap(enc, src_fmt=False, libplacebo=True, adjust_gamma=True)

    # Use the custom FrameInfo function
    if tonemapped:
        src = CustomFrameInfo(src, "Tonemapped")

    # Generate screenshots
    ScreenGen(src, dir, "a")
    if encode and enc is not None:
        enc = CustomFrameInfo(enc, "Encode (Tonemapped)")
        ScreenGen(enc, dir, "b")

    # Optimize images
    for i in range(1, num + 1):
        image_path = os.path.join(dir, f"{str(i).zfill(2)}a.png")
        optimize_images(image_path, config)
