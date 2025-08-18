import os
import sqlite3
import secrets
import logging
import shutil
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from typing import (
    List,
    Optional,
    Tuple,
    TYPE_CHECKING,
)

from ikup.image_optimizer import optimize_image_to_size, convert_image

# PIL is expensive to import, we import it only when needed or when type checking.
if TYPE_CHECKING:
    from PIL import Image


# Set up logger for the conversion cache
logger = logging.getLogger("ikup.conversion_cache")


@dataclass
class CachedConvertedImage:
    path: str  # The full path
    name: str  # The unique ID, usually a relative path
    width: int  # The converted width
    height: int  # The converted height
    format: str  # The format of the converted image
    size_bytes: int  # The size of the converted image file in bytes
    atime: datetime  # The last access time of the converted image
    is_biggest: bool = False  # Whether it is the biggest image for the src and format


@dataclass
class CachedSourceImage:
    path: str
    mtime: datetime
    converted_images: List[CachedConvertedImage]


class _ImageConversionRequest:
    """A request to convert an image to a specific size and format. This class is used
    as a helper to verify and impute parameters.
    """

    def __init__(
        self,
        *,
        src_path: str,
        src_mtime: Optional[datetime],
        src_image_object: Optional["Image.Image"] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        max_size_bytes: Optional[int] = None,
        format: Optional[str] = None,
        tolerance: Optional[float] = None,
        image_object_may_be_destroyed: bool = False,
        default_tolerance: float,
    ):
        if src_path.startswith("~"):
            src_path = os.path.expanduser(src_path)
        if os.path.exists(src_path):
            src_path = os.path.abspath(src_path)
        self.src_path: str = src_path

        if src_mtime is None:
            if not os.path.exists(src_path):
                raise FileNotFoundError(f"Source image file does not exist: {src_path}")
            src_mtime = datetime.fromtimestamp(os.path.getmtime(src_path))
        self.src_mtime: datetime = src_mtime

        self.src_image_object: Optional["Image.Image"] = src_image_object
        self.image_object_may_be_destroyed: bool = image_object_may_be_destroyed
        self.tolerance = tolerance if tolerance is not None else default_tolerance

        if (
            width is None
            and height is None
            and max_size_bytes is None
            and format is None
        ):
            raise ValueError("No conversion parameters specified")
        if max_size_bytes is not None and (width is not None or height is not None):
            raise ValueError("Cannot specify both max_size_bytes and width/height")

        # Impute missing parameters from the source image if needed.
        if format is None:
            format = self.get_src_image_object().format or "PNG"
        # If no resize is requested, use the original size.
        if width is None and height is None and max_size_bytes is None:
            width, height = self.get_src_image_object().size
        # If only width or height is specified, calculate the other dimension assuming
        # we want to keep the aspect ratio of the original image.
        if width is not None and height is None:
            image_object = self.get_src_image_object()
            height = max(1, int(image_object.height * width / image_object.width))
        if height is not None and width is None:
            image_object = self.get_src_image_object()
            width = max(1, int(image_object.width * height / image_object.height))

        self.width: Optional[int] = width
        self.height: Optional[int] = height
        self.max_size_bytes: Optional[int] = max_size_bytes
        self.format: str = format.upper() if format else "PNG"

    def get_src_image_object(self) -> "Image.Image":
        """Get the source image object, loading it from file if not provided."""
        if self.src_image_object is None:
            from PIL import Image

            self.src_image_object = Image.open(self.src_path)
            self.image_object_may_be_destroyed = True
        return self.src_image_object

    def __str__(self) -> str:
        return (
            "_ImageConversionRequest("
            f"src_path={self.src_path}, "
            f"src_mtime={self.src_mtime}, "
            f"width={self.width}, "
            f"height={self.height}, "
            f"max_size_bytes={self.max_size_bytes}, "
            f"format={self.format}, "
            f"tolerance={self.tolerance})"
        )


class ConversionCache:
    """A manager of resized/converted images stored on disk."""

    def __init__(
        self,
        cache_directory: str,
        tolerance: float = 0.2,
        max_images: int = 4096,
        max_total_size_bytes: int = 300 * 1024 * 1024,
    ):
        os.makedirs(cache_directory, exist_ok=True)
        self.cache_directory = cache_directory
        self.database_file = os.path.join(cache_directory, "conversion_cache.db")
        self.tolerance = tolerance
        self.max_images = max_images
        self.max_total_size_bytes = max_total_size_bytes
        self.conn = sqlite3.connect(self.database_file, isolation_level=None)
        self._init_database()

    def _init_database(self):
        """Initialize database tables and indexes."""
        with closing(self.conn.cursor()) as cursor:
            # Set some options.
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout = 30000")

            # Create a table for images
            cursor.execute(
                """
                    CREATE TABLE IF NOT EXISTS conversion_cache (
                        src_path TEXT NOT NULL,
                        src_mtime TIMESTAMP NOT NULL,
                        dst_format TEXT NOT NULL,
                        dst_width INTEGER NOT NULL,
                        dst_height INTEGER NOT NULL,
                        dst_is_biggest INTEGER NOT NULL,
                        dst_name TEXT NOT NULL UNIQUE,
                        dst_size_bytes INTEGER NOT NULL,
                        dst_atime TIMESTAMP NOT NULL,
                        PRIMARY KEY (src_path, src_mtime, dst_format,
                                     dst_width, dst_height)
                    )
                """
            )

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_src_lookup ON conversion_cache(src_path, src_mtime)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_cleanup ON conversion_cache(dst_atime)"
            )

    def convert(
        self,
        image_path: str,
        *,
        image_object: Optional["Image.Image"] = None,
        mtime: Optional[datetime] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        max_size_bytes: Optional[int] = None,
        format: Optional[str] = None,
        tolerance: Optional[float] = None,
    ) -> CachedConvertedImage:
        """Convert an image to the given format and size, and cache it, or get it
        from the cache if it has already been converted.

        If only width or height is specified, the other dimension will be calculated
        automatically to maintain the aspect ratio of the original image.

        If `max_size_bytes` is specified, the image will be resized to fit within that
        size, and width and height will not be used. The resized image file may be
        smaller than the specified size (within `tolerance`), but will not exceed it,
        unless compressing to that size is impossible (in which case a 1x1 image will be
        returned).

        Args:
            image_path: The _FULL_ path to the source image file.
            mtime: The modification time of the image file. Will be read from
                the actual file if None.
            image_object: An optional PIL Image object for the source image. If None,
                the image may be read from the file at `image`.
            width: The desired width of the converted image.
            height: The desired height of the converted image.
            max_size_bytes: The maximum size of the converted image in bytes.
                If specified, width and height must not be specified and
                will be computed automatically.
            format: The format to convert the image to. If not specified, the
                original format of the image will be used.
            tolerance: The maximum allowed relative difference between the resulting
                file size and `max_size_bytes`. If None, the default tolerance of the
                conversion cache will be used.

        Returns:
            A CachedConvertedImage object containing the info about the converted image.
        """
        request = _ImageConversionRequest(
            src_path=image_path,
            src_mtime=mtime,
            src_image_object=image_object,
            width=width,
            height=height,
            max_size_bytes=max_size_bytes,
            format=format,
            tolerance=tolerance,
            default_tolerance=self.tolerance,
        )

        # Try to find a cached image that matches the request.
        with self.conn, closing(self.conn.cursor()) as cursor:
            cursor.execute("BEGIN IMMEDIATE")
            cached_image = self._find_cached_image(cursor, request)
        if cached_image:
            return cached_image

        # The match is not found or it was stale, need to create a new cached image. We
        # do it outside of the transaction, so we will need to check again if another
        # process has created the same image in the meantime.
        if max_size_bytes is not None:
            dst_name, dst_path, width, height, is_biggest = (
                self._create_cached_image_with_max_size(request)
            )
        else:
            width, height = request.width, request.height
            dst_name, dst_path, is_biggest = self._create_cached_image_with_dimensions(
                request
            )

        assert width is not None and height is not None

        # Insert the new image into the database. If there is already an entry,
        # don't insert a new one, use the old one and delete the new file.
        with self.conn, closing(self.conn.cursor()) as cursor:
            cursor.execute("BEGIN IMMEDIATE")
            # Try to find a cached image with the same parameters. Set the exact width
            # and height of the new image.
            request.max_size_bytes = None
            request.width = width
            request.height = height
            cached_image = self._find_cached_image(cursor, request)
            if cached_image is not None:
                # Someone else has already created this image, return it and delete the
                # file we just created.
                logger.debug("Found existing entry, deleting new file %s", dst_path)
                os.remove(dst_path)
                return cached_image

            res = CachedConvertedImage(
                path=dst_path,
                name=dst_name,
                width=width,
                height=height,
                format=request.format,
                size_bytes=os.path.getsize(dst_path),
                atime=datetime.now(),
                is_biggest=is_biggest,
            )
            logger.debug("Inserting new entry %s", res)

            # Insert the new cached image into the database.
            cursor.execute(
                """
                INSERT INTO conversion_cache
                (src_path, src_mtime, dst_format, dst_width, dst_height, dst_name,
                dst_size_bytes, dst_atime, dst_is_biggest)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.src_path,
                    request.src_mtime,
                    request.format,
                    width,
                    height,
                    dst_name,
                    res.size_bytes,
                    res.atime,
                    int(is_biggest),
                ),
            )

            return res

    def find_cached_image(
        self,
        image_path: str,
        *,
        image_object: Optional["Image.Image"] = None,
        mtime: Optional[datetime] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        max_size_bytes: Optional[int] = None,
        format: Optional[str] = None,
        tolerance: Optional[float] = None,
        update_atime: bool = True,
        remove_if_missing: bool = True,
    ) -> Optional[CachedConvertedImage]:
        """Returns a cached converted image if it exists, or None if not.

        If width or height is specified, searches for an exact match for those
        dimensions.

        If `max_size_bytes` is specified, returns the biggest image that does not
        exceed that size and is within the specified `tolerance`.

        Args:
            image_path: The _FULL_ path to the source image file.
            mtime: The modification time of the image file. Will be read from
                the actual file if None.
            image_object: An optional PIL Image object for the source image. If None,
                the image may be read from the file at `image`.
            width: The width of the converted image.
            height: The height of the converted image.
            max_size_bytes: The maximum size of the converted image in bytes.
                If specified, width and height must not be specified.
            format: The format to convert the image to. If not specified, the
                original format of the image will be used.
            tolerance: The maximum allowed relative difference between the resulting
                file size and `max_size_bytes`. If None, the default tolerance of the
                conversion cache will be used.
            update_atime: If true, update the access time of the cached image to the
                current time if found.
            remove_if_missing: If true, remove the cached image entry if the file
                does not exist on disk.

        Returns:
            A CachedConvertedImage object if a cached image is found, or None if not.
        """
        request = _ImageConversionRequest(
            src_path=image_path,
            src_mtime=mtime,
            src_image_object=image_object,
            width=width,
            height=height,
            max_size_bytes=max_size_bytes,
            format=format,
            tolerance=tolerance,
            default_tolerance=self.tolerance,
        )

        with self.conn, closing(self.conn.cursor()) as cursor:
            cursor.execute("BEGIN IMMEDIATE")
            return self._find_cached_image(cursor, request)

    def _find_cached_image(
        self,
        cursor: sqlite3.Cursor,
        request: _ImageConversionRequest,
        update_atime: bool = True,
        remove_if_missing: bool = True,
    ) -> Optional[CachedConvertedImage]:
        """See `find_cached_image`. This is a helper to run within a transaction after
        imputing arguments. It updates the atime and removes the entry if the file
        doesn't exist."""
        logger.debug("_find_cached_image: %s", request)
        if request.max_size_bytes is not None:
            best_match = self._find_best_cached_match_by_file_size(cursor, request)
        else:
            best_match = self._find_best_cached_match_by_dimensions(cursor, request)

        logger.debug("_find_cached_image result: %s", best_match)

        if best_match is None:
            return None

        if os.path.exists(best_match.path):
            logger.debug("File exists: %s", best_match.path)
            if update_atime:
                self._update_access_time(cursor, best_match.name)
            return best_match

        if remove_if_missing:
            # Remove the stale database entry for the missing file
            logger.debug("File doesn't exist, removing entry: %s", best_match.path)
            cursor.execute(
                "DELETE FROM conversion_cache WHERE dst_name = ?", (best_match.name,)
            )
        return None

    def _find_best_cached_match_by_file_size(
        self,
        cursor: sqlite3.Cursor,
        request: _ImageConversionRequest,
    ) -> Optional[CachedConvertedImage]:
        """Find the best matching cached image for max-bytes constraint."""
        assert request.max_size_bytes is not None
        cursor.execute(
            """
            SELECT
                dst_name, dst_width, dst_height, dst_size_bytes, dst_atime,
                dst_is_biggest
            FROM conversion_cache
            WHERE src_path = ? AND src_mtime = ? AND dst_format = ?
              AND (dst_size_bytes <= ? OR (dst_width = 1 AND dst_height = 1))
              AND (dst_size_bytes >= ? OR dst_is_biggest = 1)
            ORDER BY dst_size_bytes DESC
            LIMIT 1
            """,
            (
                request.src_path,
                request.src_mtime,
                request.format,
                request.max_size_bytes,
                int(request.max_size_bytes * (1 - request.tolerance)),
            ),
        )

        row = cursor.fetchone()
        if not row:
            return None

        dst_name, dst_width, dst_height, dst_size, dst_atime, dst_is_biggest = row
        dst_path = os.path.join(self.cache_directory, dst_name)
        return CachedConvertedImage(
            path=dst_path,
            name=dst_name,
            width=dst_width,
            height=dst_height,
            format=request.format,
            size_bytes=dst_size,
            atime=datetime.fromisoformat(dst_atime),
            is_biggest=bool(dst_is_biggest),
        )

    def _find_best_cached_match_by_dimensions(
        self,
        cursor: sqlite3.Cursor,
        request: _ImageConversionRequest,
    ) -> Optional[CachedConvertedImage]:
        """Find the matching cached image with the given dimensions."""
        assert request.width is not None and request.height is not None
        cursor.execute(
            """
            SELECT
                dst_name, dst_width, dst_height, dst_size_bytes, dst_atime,
                dst_is_biggest
            FROM conversion_cache
            WHERE src_path = ? AND src_mtime = ? AND dst_format = ? AND
                  dst_width = ? AND dst_height = ?
            ORDER BY dst_size_bytes ASC
            LIMIT 1
            """,
            (
                request.src_path,
                request.src_mtime,
                request.format,
                request.width,
                request.height,
            ),
        )

        row = cursor.fetchone()
        if not row:
            return None

        dst_name, dst_width, dst_height, dst_size, dst_atime, dst_is_biggest = row
        dst_path = os.path.join(self.cache_directory, dst_name)
        return CachedConvertedImage(
            path=dst_path,
            name=dst_name,
            width=dst_width,
            height=dst_height,
            format=request.format,
            size_bytes=dst_size,
            atime=datetime.fromisoformat(dst_atime),
            is_biggest=bool(dst_is_biggest),
        )

    def _update_access_time(self, cursor: sqlite3.Cursor, dst_name: str):
        """Update the access time for a cached image."""
        cursor.execute(
            "UPDATE conversion_cache SET dst_atime = ? WHERE dst_name = ?",
            (datetime.now(), dst_name),
        )

    def _create_cached_image_with_dimensions(
        self,
        request: _ImageConversionRequest,
    ) -> Tuple[str, str, bool]:
        """Create a new cached image with specific dimensions.

        The image is created in the cache directory, but it's not inserted into the
        database. The caller must insert it into the database after this call or delete
        the file if it fails to insert.

        Returns:
            A tuple containing:
                - dst_name: The name of the cached image file.
                - dst_path: The full path to the cached image file.
                - is_biggest: Whether the created image matches the original size
                    and format (i.e. it's the biggest non-upscaled version).
        """
        assert request.width is not None and request.height is not None
        image_object = request.get_src_image_object()
        orig_format = image_object.format or "UNKNOWN"

        dst_name = self._generate_cache_filename(request.format)
        dst_path = os.path.join(self.cache_directory, dst_name)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)

        # If the size and the format match the original image, we can just copy it (if
        # it exists, sometimes we only have an object, but the path is fake).
        if (
            image_object.size == (request.width, request.height)
            and orig_format.upper() == request.format.upper()
            and os.path.exists(request.src_path)
        ):
            shutil.copyfile(request.src_path, dst_path)
        else:
            converted_data, _ = convert_image(
                image_object,
                width=request.width,
                height=request.height,
                format=request.format,
            )
            with open(dst_path, "wb") as f:
                f.write(converted_data.getvalue())

        return dst_name, dst_path, image_object.size == (request.width, request.height)

    def _create_cached_image_with_max_size(
        self,
        request: _ImageConversionRequest,
    ) -> Tuple[str, str, int, int, bool]:
        """Create a new cached image that fits within max_size_bytes.

        Returns:
            A tuple containing:
                - dst_name: The name of the cached image file.
                - dst_path: The full path to the cached image file.
                - width: The width of the created image.
                - height: The height of the created image.
                - is_biggest: Whether the created image is the biggest non-upscaled
                    version of this image and format.
        """
        assert request.max_size_bytes is not None
        image_object = request.get_src_image_object()

        dst_name = self._generate_cache_filename(request.format)
        dst_path = os.path.join(self.cache_directory, dst_name)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)

        # If the format of the original image matches the target format and the size is
        # smaller than the target, use it (as the biggest one) by copying the file if
        # possible.
        if (image_object.format or "").upper() == request.format and os.path.exists(
            request.src_path
        ):
            orig_size = os.path.getsize(request.src_path)
            if orig_size <= request.max_size_bytes:
                shutil.copyfile(request.src_path, dst_path)
                return dst_name, dst_path, image_object.width, image_object.height, True

        # Build a list of samples for size estimation.
        samples: List[Tuple[int, int, int]] = []  # (width, height, size_bytes)

        # Get images of the same format and closest sizes to the target size.
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(
                """
                SELECT dst_width, dst_height, dst_size_bytes
                FROM conversion_cache
                WHERE src_path = ? AND src_mtime = ? AND dst_format = ?
                ORDER BY ABS(dst_size_bytes - ?) ASC
                LIMIT 2
                """,
                (
                    request.src_path,
                    request.src_mtime,
                    request.format,
                    request.max_size_bytes,
                ),
            )

            for row in cursor.fetchall():
                width, height, size_bytes = row
                samples.append((width, height, size_bytes))

        # If there are not enough images of the same format, but the original image has the same
        # format and exists as a file, use it as a sample.
        if (
            not samples
            and (image_object.format or "").upper() == request.format
            and os.path.exists(request.src_path)
        ):
            orig_size = os.path.getsize(request.src_path)
            samples.append((image_object.width, image_object.height, orig_size))

        # Call the function to minimize the image.
        converted_data, converted_image_object = optimize_image_to_size(
            image_object,
            format=request.format,
            max_size_bytes=request.max_size_bytes,
            tolerance=request.tolerance,
            samples=samples,
        )
        # Save it to a file and return.
        with open(dst_path, "wb") as f:
            f.write(converted_data.getvalue())
        return (
            dst_name,
            dst_path,
            converted_image_object.width,
            converted_image_object.height,
            converted_image_object.size == image_object.size,
        )

    def _generate_cache_filename(self, format: str) -> str:
        random_name = secrets.token_hex(16)
        extension = format.lower()

        subdir = random_name[:2]
        filename = f"{random_name[2:]}.{extension}"

        return os.path.join(subdir, filename)

    def cleanup(
        self,
        max_images: Optional[int] = None,
        max_total_size_bytes: Optional[int] = None,
    ):
        """Clean up the cache by removing old images.

        Args:
            max_images: The maximum number of images to keep in the cache.
                If None, use the default from the conversion cache.
            max_total_size_bytes: The maximum total size of the cache in bytes.
                If None, use the default from the conversion cache.
        """
        if max_images is None:
            max_images = self.max_images
        if max_total_size_bytes is None:
            max_total_size_bytes = self.max_total_size_bytes

        with self.conn, closing(self.conn.cursor()) as cursor:
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT COUNT(*), SUM(dst_size_bytes) FROM conversion_cache")
            current_count, current_size = cursor.fetchone()
            current_size = current_size or 0

            if current_count <= max_images and current_size <= max_total_size_bytes:
                return

            cursor.execute(
                """
                SELECT dst_name, dst_size_bytes FROM conversion_cache
                ORDER BY dst_atime ASC
                """
            )

            to_remove = []
            remaining_count = current_count
            remaining_size = current_size

            for dst_name, dst_size_bytes in cursor.fetchall():
                if (
                    remaining_count <= max_images
                    and remaining_size <= max_total_size_bytes
                ):
                    break

                to_remove.append(dst_name)
                remaining_count -= 1
                remaining_size -= dst_size_bytes

            for dst_name in to_remove:
                dst_path = os.path.join(self.cache_directory, dst_name)
                if os.path.exists(dst_path):
                    os.remove(dst_path)

                cursor.execute(
                    "DELETE FROM conversion_cache WHERE dst_name = ?", (dst_name,)
                )

    def get_cached_images(self) -> List[CachedSourceImage]:
        """Returns all cached images grouped by the source image."""
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(
                """
                SELECT src_path, src_mtime, dst_name, dst_width, dst_height,
                       dst_format, dst_size_bytes, dst_atime, dst_is_biggest
                FROM conversion_cache
                ORDER BY src_path, src_mtime
                """
            )

            result = []
            current_source = None
            current_converted = []

            for row in cursor.fetchall():
                (
                    src_path,
                    src_mtime,
                    dst_name,
                    dst_width,
                    dst_height,
                    dst_format,
                    dst_size_bytes,
                    dst_atime,
                    dst_is_biggest,
                ) = row

                src_mtime_converted = datetime.fromisoformat(src_mtime)

                if current_source is None or (src_path, src_mtime_converted) != (
                    current_source.path,
                    current_source.mtime,
                ):
                    if current_source is not None:
                        result.append(current_source)

                    current_source = CachedSourceImage(
                        path=src_path, mtime=src_mtime_converted, converted_images=[]
                    )
                    current_converted = current_source.converted_images

                converted_image = CachedConvertedImage(
                    path=os.path.join(self.cache_directory, dst_name),
                    name=dst_name,
                    width=dst_width,
                    height=dst_height,
                    format=dst_format,
                    size_bytes=dst_size_bytes,
                    atime=datetime.fromisoformat(dst_atime),
                    is_biggest=bool(dst_is_biggest),
                )
                current_converted.append(converted_image)

            if current_source is not None:
                result.append(current_source)

            return result

    def remove_cached_images(
        self,
        image_path: str,
        mtime: Optional[datetime] = None,
        format: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> int:
        """Remove cached images matching the specified criteria.

        Args:
            image_path: Path to the source image
            mtime: Modification time of the source image (auto-detected if None)
            format: Format to remove (removes all formats if None)
            width: Width to remove (removes all widths if None)
            height: Height to remove (removes all heights if None)

        Returns:
            Number of cached images removed
        """
        if mtime is None:
            mtime = datetime.fromtimestamp(os.path.getmtime(image_path))

        with self.conn, closing(self.conn.cursor()) as cursor:
            cursor.execute("BEGIN IMMEDIATE")
            # Build WHERE clause based on provided parameters
            conditions = ["src_path = ?", "src_mtime = ?"]
            params = [image_path, mtime]

            if format is not None:
                conditions.append("dst_format = ?")
                params.append(format)
            if width is not None:
                conditions.append("dst_width = ?")
                params.append(width)
            if height is not None:
                conditions.append("dst_height = ?")
                params.append(height)

            # Find matching entries
            cursor.execute(
                "SELECT dst_name FROM conversion_cache WHERE "
                f"{' AND '.join(conditions)}",
                params,
            )

            removed_count = 0
            for row in cursor.fetchall():
                dst_name = row[0]
                dst_path = os.path.join(self.cache_directory, dst_name)

                # Remove file if it exists
                if os.path.exists(dst_path):
                    os.remove(dst_path)

                # Remove from database
                cursor.execute(
                    "DELETE FROM conversion_cache WHERE dst_name = ?", (dst_name,)
                )
                removed_count += 1

            return removed_count

    def remove_by_cached_path(self, cached_path: str) -> bool:
        """Remove a cached image by its cached file path.

        Args:
            cached_path: Path to the cached image file

        Returns:
            True if the image was found and removed, False otherwise
        """
        # Extract relative path from cache directory
        if not cached_path.startswith(self.cache_directory):
            # Try to make it relative to cache directory
            cached_path = os.path.abspath(cached_path)
            if not cached_path.startswith(self.cache_directory):
                return False

        dst_name = os.path.relpath(cached_path, self.cache_directory)

        with self.conn, closing(self.conn.cursor()) as cursor:
            cursor.execute("BEGIN IMMEDIATE")
            # Check if entry exists
            cursor.execute(
                "SELECT dst_name FROM conversion_cache WHERE dst_name = ?",
                (dst_name,),
            )
            if not cursor.fetchone():
                return False

            # Remove file if it exists
            if os.path.exists(cached_path):
                os.remove(cached_path)

            # Remove from database
            cursor.execute(
                "DELETE FROM conversion_cache WHERE dst_name = ?", (dst_name,)
            )
            return True

    def remove_all_cached_images(self) -> int:
        """Remove all cached images and clear the cache completely.

        Returns:
            Number of cached images removed
        """
        with self.conn, closing(self.conn.cursor()) as cursor:
            cursor.execute("BEGIN IMMEDIATE")

            # Get all cached file paths first
            cursor.execute("SELECT dst_name FROM conversion_cache")
            all_cached_files = cursor.fetchall()

            removed_count = 0

            # Remove all physical files
            for row in all_cached_files:
                dst_name = row[0]
                dst_path = os.path.join(self.cache_directory, dst_name)

                if os.path.exists(dst_path):
                    os.remove(dst_path)
                    removed_count += 1

            # Clear the database
            cursor.execute("DELETE FROM conversion_cache")

            return removed_count

    def close(self):
        """Close the database connection."""
        self.conn.close()
