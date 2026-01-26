"""Compatibility shim for legacy image777 uploader.

SSD expects an `upload_image` function but the original module isn't present in
this repository. Provide a safe fallback that keeps the uploader running even
when an external image host isn't configured.
"""
from __future__ import annotations

import os
from typing import Optional


def upload_image(image_path: str) -> Optional[str]:
    """Best-effort upload placeholder.

    Returns None to signal the caller to use the original image URL when no
    uploader is configured.
    """
    if not image_path or not os.path.isfile(image_path):
        return None
    return None
