"""Image downloading utility with optional scaling.

This module provides utilities for downloading images from URLs and optionally
scaling them to a target size.
"""

import os
import shutil
import sys
import tempfile
import urllib.request
from typing import Optional, Tuple

from PIL import Image

import ikup

USER_AGENT = f"ikup/{ikup.__version__} (github.com/sergei-grechanik/ikup)"


def _download_and_scale(
    url: str,
    output_path: str,
    target_size: Optional[Tuple[int, int]] = None,
    user_agent: Optional[str] = None,
    verbose: bool = False,
):
    """Download an image and optionally resize it to an exact size.

    Args:
        url: URL to download the image from.
        output_path: Path where the final image should be saved.
        target_size: Optional (width, height) tuple. If provided, the image will
            be resized to exactly this size.
        user_agent: Optional user agent string. Defaults to ikup's user agent.
    Returns:
        True if the image was resized, False otherwise.
    """
    if user_agent is None:
        user_agent = USER_AGENT

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "*/*",
        },
    )

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name
        try:
            if verbose:
                print(f"Downloading image: {url}", file=sys.stderr)
            with urllib.request.urlopen(req) as resp:
                shutil.copyfileobj(resp, tmp)
            tmp.flush()

            if not _is_valid_image(tmp_path):
                raise ValueError(f"URL did not return a valid image: {url}")

            if target_size is None:
                shutil.move(tmp_path, output_path)
            else:
                img = Image.open(tmp_path)
                if target_size == img.size:
                    shutil.move(tmp_path, output_path)
                else:
                    if verbose:
                        print(
                            f"Resizing image to {target_size}: {output_path}",
                            file=sys.stderr,
                        )
                    output_format = img.format or "PNG"
                    resized_img = img.resize(target_size, Image.Resampling.LANCZOS)
                    resized_img.save(output_path, format=output_format)
                    os.unlink(tmp_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise


def download_image(
    url: str,
    output_path: str,
    target_size: Optional[Tuple[int, int]] = None,
    user_agent: Optional[str] = None,
    verbose: bool = False,
) -> str:
    """Download an image if it doesn't already exist or is invalid.

    This function checks if the image already exists at the output path and is
    valid (correct format and size) before attempting to download. If the file
    exists and is valid, the download is skipped.

    Args:
        url: URL to download the image from.
        output_path: Path where the final image should be saved.
        target_size: Optional (width, height) tuple for scaling.
        user_agent: Optional user agent string.
        verbose: Whether to print progress messages.

    Returns:
        The absolute path to the image.
    """
    output_path = os.path.abspath(output_path)

    if os.path.exists(output_path):
        if _is_valid_image(output_path, target_size):
            if verbose:
                print(f"Using existing image: {output_path}", file=sys.stderr)
            return output_path
        os.unlink(output_path)

    _download_and_scale(url, output_path, target_size, user_agent, verbose=verbose)
    return output_path


def _is_valid_image(path: str, expected_size: Optional[Tuple[int, int]] = None) -> bool:
    """Check if a file is a valid image with the expected size.

    Args:
        path: Path to the image file.
        expected_size: Optional (width, height) tuple. If provided, the image
            must fit within this size (i.e., both dimensions must be <= the
            expected dimensions).
    """
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            if expected_size is not None:
                w, h = img.size
                if w != expected_size[0] or h != expected_size[1]:
                    return False
        return True
    except Exception:
        return False
