import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class IDSubspace:
    """A subspace of ids, defined by a range of a certain byte (depending on the
    IDFeatures space).

    The restricted byte is the most significant byte that can be used in an IDFeatures
    space. It is guaranteed that the subspace will contain at least `end - begin` ids
    and that the subspace will not overlap if their ranges don't overlap.

    Attributes:
        begin: The first byte value in the range.
        end: The byte value after the last one in the range.
    """

    begin: int = 0
    end: int = 256

    def __post_init__(self):
        if not (0 <= self.begin < self.end <= 256):
            raise ValueError("Invariant violation: 0 <= begin < end <= 256")
        if self.end == 1:
            raise ValueError("A subspace must contain at least one non-zero id")

    def __str__(self) -> str:
        return f"{self.begin}:{self.end}"

    @staticmethod
    def from_string(s: str) -> "IDSubspace":
        """Parses an IDSubspace from a string `begin:end`."""
        if not s:
            return IDSubspace()
        try:
            begin, end = s.split(":")
            begin = int(begin)
            end = int(end)
        except ValueError:
            raise ValueError(f"Invalid format for IDSubspace: '{s}'. Expected format 'begin:end' with integers.")
        return IDSubspace(begin, end)

    def rand_byte(self) -> int:
        """Generates a random byte in the range."""
        return secrets.randbelow(self.end - self.begin) + self.begin

    def rand_nonzero_byte(self) -> int:
        """Generates a random non-zero byte in the range."""
        if self.begin <= 0:
            return secrets.randbelow(self.end - 1) + 1
        return self.rand_byte()

    def all_byte_values(self) -> Iterable[int]:
        """Generates all byte values in the range."""
        return range(self.begin, self.end)

    def all_nonzero_byte_values(self) -> Iterable[int]:
        """Generates all non-zero byte values in the range"""
        if self.begin <= 0:
            return range(1, self.end)
        return range(self.begin, self.end)

    def num_byte_values(self) -> int:
        """Returns the number of byte values in the range."""
        return self.end - self.begin

    def num_nonzero_byte_values(self) -> int:
        """Returns the number of non-zero byte values in the range"""
        if self.begin <= 0:
            return self.end - 1
        return self.end - self.begin

    def contains_byte(self, b: int) -> bool:
        """Returns true if the byte is in the range."""
        return self.begin <= b < self.end

    def split(self, count: int) -> List["IDSubspace"]:
        """Splits the subspace into `count` non-overlapping subspaces of approximately
        equal size. Will raise an error if the subspace is too small to split."""
        if count <= 0:
            raise ValueError("count must be positive")
        if count == 1:
            return [self]
        if self.num_nonzero_byte_values() < count:
            raise ValueError(f"Subspace is too small to split: the number of non-zero byte values {self.num_nonzero_byte_values()} is less than the number of requested sub-subspaces {count}")
        size = self.num_nonzero_byte_values() // count
        remainder = self.num_byte_values() - size * count
        subspaces = []
        for begin in range(self.begin + remainder, self.end, size):
            subspaces.append(IDSubspace(begin, begin + size))
        subspaces[0] = IDSubspace(self.begin, subspaces[0].end)
        return subspaces


@dataclass(frozen=True)
class IDFeatures:
    """The features that can be used to represent an image ID.

    When displaying an image using Unicode placeholders, the image ID may be
    represented with the fg color (24 or 8 bits) and the 3rd diacritic (8 bits).
    Some applications may not support all of the features, so all IDs are broken
    down into non-intersecting IDFeatures spaces, each space contains only IDs
    that can be represented with the given features.

    Note that since we want the IDFeatures spaces to be disjoint, certain bytes
    of the IDs belonging to bigger subspaces may be required to be non-zero.

    Attributes:
        color_bits: The number of color bits. Must be 0, 8 or 24.
        use_3rd_diacritic: Whether to use the 3rd diacritic.
    """

    color_bits: int = 24
    use_3rd_diacritic: bool = True

    def __post_init__(self):
        if self.color_bits == 0 and not self.use_3rd_diacritic:
            raise ValueError(
                "Cannot use 0 color bits and not use the 3rd diacritic at the"
                " same time, because there would be no non-zero ids"
            )
        if self.color_bits not in [0, 8, 24]:
            raise ValueError(
                f"Invalid number of color bits: {self.color_bits}, must be 0, 8"
                " or 24"
            )

    @staticmethod
    def from_id(id: int) -> "IDFeatures":
        """Get the IDFeatures space an image ID belongs to."""
        if id <= 0 or id > 0xFFFFFFFF:
            raise ValueError(f"Invalid id, must be non-zero 32-bit: {id}")
        use_3rd_diacritic = (id & 0xFF000000) != 0
        color_bits = 0
        if (id & 0x00FFFFFF) != 0:
            if (id & 0x00FFFF00) != 0:
                color_bits = 24
            else:
                color_bits = 8
        return IDFeatures(color_bits, use_3rd_diacritic)

    def num_nonzero_bits(self) -> int:
        """Get the number of bits of an ID that may be nonzero in this space."""
        return (8 if self.use_3rd_diacritic else 0) + self.color_bits

    def namespace_name(self) -> str:
        """Get the name of this IDFeatures space that can be used as an
        identifier or a file name."""
        if self.use_3rd_diacritic:
            return f"ids_{self.num_nonzero_bits()}bit_3rd_diacritic"
        else:
            return f"ids_{self.num_nonzero_bits()}bit"

    def contains(self, id: int) -> bool:
        return self.from_id(id) == self

    def contains_and_in_subspace(self, id: int, subspace: IDSubspace) -> bool:
        """Returns true if the id is in this space and also in the given
        subspace."""
        begin, end = self.subspace_masked_range(subspace)
        return self.contains(id) and (begin <= (
            id & self.subspace_byte_mask()
        ) < end)

    def gen_random_id(self, subspace: IDSubspace = IDSubspace()) -> int:
        """Generates a random id in this space that also belongs to the given
        subspace."""
        # We want to use every feature available to us, making id namespaces
        # disjoint.

        byte_0 = 0 # blue or the color index
        byte_1 = 0 # green
        byte_2 = 0 # red
        byte_3 = 0 # 3rd diacritic
        if self.use_3rd_diacritic:
            # If we can use the 3rd diacritic, it must be nonzero, and we apply the
            # subspace to it.
            byte_3 = subspace.rand_nonzero_byte()
            if self.color_bits == 8:
                # If we can use only 8 bit colors, the color must be nonzero.
                byte_0 = secrets.randbelow(255) + 1
            elif self.color_bits == 24:
                # If we can use 24 bit colors, one of the the two bytes in the middle
                # must be non-zero.
                byte_0 = secrets.randbelow(256)
                byte_2 = secrets.randbelow(256)
                if byte_2 == 0:
                    byte_1 = secrets.randbelow(255) + 1
                else:
                    byte_1 = secrets.randbelow(256)
        else:
            # No 3rd diacritic.
            if self.color_bits == 8:
                # If we can use only 8 bit colors, the color must be nonzero and we
                # apply the subspace to it.
                byte_0 = subspace.rand_nonzero_byte()
            elif self.color_bits == 24:
                # If we can use 24 bit colors, one of the two bytes in the middle must
                # be non-zero, and we apply the subspace to the most significant one.
                byte_0 = secrets.randbelow(256)
                byte_2 = subspace.rand_byte()
                if byte_2 == 0:
                    byte_1 = secrets.randbelow(255) + 1
                else:
                    byte_1 = secrets.randbelow(256)
        return (byte_3 << 24) | (byte_2 << 16) | (byte_1 << 8) | byte_0

    def all_ids(self, subspace: IDSubspace = IDSubspace()) -> Iterator[int]:
        """Generates all ids in this space that also belong to the given
        subspace."""
        byte_0 = lambda: [0] # blue or the color index
        byte_1_2 = lambda: [0] # red and green
        byte_3 = lambda: [0] # 3rd diacritic
        if self.use_3rd_diacritic:
            byte_3 = lambda: subspace.all_nonzero_byte_values()
            if self.color_bits == 8:
                byte_0 = lambda: range(1, 256)
            elif self.color_bits == 24:
                byte_0 = lambda: range(0, 256)
                byte_1_2 = lambda: range(1, 256 * 256)
        else:
            # No 3rd diacritic.
            if self.color_bits == 8:
                byte_0 = lambda: subspace.all_nonzero_byte_values()
            elif self.color_bits == 24:
                byte_0 = lambda: range(0, 256)
                byte_1_2 = lambda: ((b2 << 8) | b1 for b2 in subspace.all_byte_values() for b1 in range(1 if b2 == 0 else 0, 256))
        for b3 in byte_3():
            for b12 in byte_1_2():
                for b0 in byte_0():
                    yield (b3 << 24) | (b12 << 8) | b0

    def subspace_size(self, subspace: IDSubspace = IDSubspace()) -> int:
        """Returns the number of ids in this space that also belong to the given
        subspace. This function takes into account that some bytes must not be
        zero."""
        byte_0_cnt = 1
        byte_12_cnt = 1
        byte_3_cnt = 1
        if self.use_3rd_diacritic:
            byte_3_cnt = subspace.num_nonzero_byte_values()
            if self.color_bits == 8:
                byte_0_cnt = 255
            elif self.color_bits == 24:
                byte_0_cnt = 256
                byte_12_cnt = 256 * 256 - 1
        else:
            # No 3rd diacritic.
            if self.color_bits == 8:
                byte_0_cnt = subspace.num_nonzero_byte_values()
            elif self.color_bits == 24:
                byte_0_cnt = 256
                byte_12_cnt = subspace.num_byte_values() * 256
                if subspace.begin <= 0:
                    byte_12_cnt -= 1
        return byte_3_cnt * byte_12_cnt * byte_0_cnt

    def subspace_byte_offset(self) -> int:
        """Returns the offset (in bits) of the byte to which the subspace is applied."""
        if self.use_3rd_diacritic:
            return 24
        if self.color_bits == 24:
            return 16
        return 0

    def subspace_byte_mask(self) -> int:
        """Returns a mask that can be used to get the byte to which the subspace is
        applied."""
        return 0xFF << self.subspace_byte_offset()

    def subspace_masked_range(self, subspace: IDSubspace) -> Tuple[int, int]:
        """Returns the range of IDs from the subspace after applying the byte mask. That
        is, an ID `id` from the space `self` belongs to `subspace` iff the following
        holds:

                begin <= (id & self.subspace_byte_mask()) < end

        where `begin, end = self.subspace_masked_range(subspace)`.
        """
        offset = self.subspace_byte_offset()
        return (subspace.begin << offset, subspace.end << offset)

    @staticmethod
    def all_values() -> Iterator["IDFeatures"]:
        """Generates all IDFeatures spaces."""
        for use_3rd_diacritic in [True, False]:
            for color_bits in [0, 8, 24]:
                if color_bits == 0 and not use_3rd_diacritic:
                    continue
                yield IDFeatures(color_bits, use_3rd_diacritic)


@dataclass
class ImageInfo:
    path: str
    params: str = ""
    mtime: Optional[datetime] = None
    id: Optional[int] = None
    atime: Optional[datetime] = None


@dataclass
class UploadInfo:
    id: int
    path: str
    params: str
    mtime: Optional[datetime]
    upload_time: Optional[datetime]
    terminal: str
    size: int
    bytes_ago: int
    uploads_ago: int


class IDManager:
    def __init__(self, database_file: str, *, max_ids_per_subspace: int = 1024):
        self.conn = sqlite3.connect(database_file, isolation_level=None)
        self.cursor = self.conn.cursor()
        self.max_ids_per_subspace: int = max_ids_per_subspace

        # Make sure we have tables for all ID namespaces.
        for id_features in IDFeatures.all_values():
            namespace = id_features.namespace_name()
            self.cursor.execute(
                f"""
                    CREATE TABLE IF NOT EXISTS {namespace} (
                        id INTEGER PRIMARY KEY,
                        path TEXT NOT NULL,
                        params TEXT NOT NULL,
                        mtime TIMESTAMP NOT NULL,
                        atime TIMESTAMP NOT NULL
                    )
                """
            )
            self.cursor.execute(
                f"""CREATE INDEX IF NOT EXISTS idx_{namespace}_path_parameters
                    ON {namespace} (path, params)
                """
            )
            self.cursor.execute(
                f"""CREATE INDEX IF NOT EXISTS idx_{namespace}_atime
                    ON {namespace} (atime)
                """
            )
        # Make sure we have a table for recent uploads.
        self.cursor.execute(
            f"""
                CREATE TABLE IF NOT EXISTS upload (
                    id INTEGER NOT NULL,
                    path TEXT NOT NULL,
                    params TEXT NOT NULL,
                    mtime TIMESTAMP NOT NULL,
                    size INTEGER NOT NULL,
                    terminal TEXT NOT NULL,
                    upload_time TIMESTAMP NOT NULL,
                    PRIMARY KEY (id, terminal)
                )
            """
        )
        self.cursor.execute(
            f"""CREATE INDEX IF NOT EXISTS idx_upload_upload_time
                ON upload (upload_time)
            """
        )
        self.conn.commit()

    def close(self):
        self.conn.close()

    def get_info(self, id: int) -> Optional[ImageInfo]:
        id_features = IDFeatures.from_id(id)
        namespace = id_features.namespace_name()
        self.cursor.execute(
            f"""SELECT path, params, mtime, atime FROM {namespace}
                WHERE id=?
            """,
            (id,),
        )
        row = self.cursor.fetchone()
        if not row:
            return None
        path, params, mtime, atime = row
        return ImageInfo(
            id=id,
            path=path,
            params=params,
            mtime=datetime.fromisoformat(mtime),
            atime=datetime.fromisoformat(atime),
        )

    def get_all(
        self, id_features: IDFeatures, subspace: IDSubspace = IDSubspace()
    ) -> List[ImageInfo]:
        namespace = id_features.namespace_name()
        begin, end = id_features.subspace_masked_range(subspace)
        self.cursor.execute(
            f"""SELECT id, path, params, mtime, atime FROM {namespace}
                WHERE (id & ?) BETWEEN ? AND ? ORDER BY atime DESC
            """,
            (
                id_features.subspace_byte_mask(),
                begin,
                end - 1,
            ),
        )
        return [
            ImageInfo(
                id=row[0],
                path=row[1],
                params=row[2],
                mtime=datetime.fromisoformat(row[3]),
                atime=datetime.fromisoformat(row[4]),
            )
            for row in self.cursor.fetchall()
        ]

    def count(
        self, id_features: IDFeatures, subspace: IDSubspace = IDSubspace()
    ) -> int:
        namespace = id_features.namespace_name()
        begin, end = id_features.subspace_masked_range(subspace)
        self.cursor.execute(
            f"""SELECT COUNT(*) FROM {namespace}
                WHERE (id & ?) BETWEEN ? AND ? ORDER BY atime DESC
            """,
            (
                id_features.subspace_byte_mask(),
                begin,
                end - 1,
            ),
        )
        return self.cursor.fetchone()[0]

    def set_id(
        self,
        id: int,
        path: str,
        *,
        params: str = "",
        mtime: Optional[datetime] = None,
        atime: Optional[datetime] = None,
    ):
        id_features = IDFeatures.from_id(id)
        namespace = id_features.namespace_name()
        if mtime is None:
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
            except FileNotFoundError:
                mtime = datetime.fromtimestamp(0)
        if atime is None:
            atime = datetime.now()
        # Upsert the row.
        self.cursor.execute(
            f"""INSERT INTO {namespace} (id, path, params, mtime, atime)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    path=excluded.path, params=excluded.params,
                    mtime=excluded.mtime, atime=excluded.atime
            """,
            (id, path, params, mtime.isoformat(), atime.isoformat()),
        )

    def del_id(self, id: int):
        id_features = IDFeatures.from_id(id)
        namespace = id_features.namespace_name()
        with self.conn:
            self.conn.execute("BEGIN")
            self.cursor.execute(f"DELETE FROM {namespace} WHERE id=?", (id,))

    def get_id(
        self,
        path: str,
        id_features: IDFeatures,
        *,
        params: str = "",
        mtime: Optional[datetime] = None,
        subspace: IDSubspace = IDSubspace(),
    ) -> int:
        # If `mtime` is not given, use the modification time of the file, or
        # just some arbitrary time if the file does not exist.
        if mtime is None:
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(path))
            except FileNotFoundError:
                mtime = datetime.fromtimestamp(0)

        namespace = id_features.namespace_name()
        begin, end = id_features.subspace_masked_range(subspace)

        atime = datetime.now()

        with self.conn:
            self.conn.execute("BEGIN")
            # Find the row with the given `path`, `params`, `mtime` and id
            # subspace.
            self.cursor.execute(
                f"""SELECT id FROM {namespace}
                    WHERE path=? AND params=? AND mtime=? AND (id & ?) BETWEEN ? AND ?
                """,
                (
                    path,
                    params,
                    mtime.isoformat(),
                    id_features.subspace_byte_mask(),
                    begin,
                    end - 1,
                ),
            )
            row = self.cursor.fetchone()

            # If there is such a row, update the `atime` and return the `id`.
            if row:
                id = row[0]
                self.cursor.execute(
                    f"UPDATE {namespace} SET atime=? WHERE id=?",
                    (atime.isoformat(), id),
                )
                return id

            subspace_size = id_features.subspace_size(subspace)

            # If the subspace is small enough, we will select all the rows and
            # identify unused IDs.
            if subspace_size <= min(1024, self.max_ids_per_subspace):
                # First check the count of rows in the subspace. If the subspace
                # is full, select the oldest row and update it.
                if self.count(id_features, subspace) >= subspace_size:
                    self.cursor.execute(
                        f"""SELECT id FROM {namespace} WHERE (id & ?) BETWEEN ? AND ?
                            ORDER BY atime ASC LIMIT 1
                        """,
                        (
                            id_features.subspace_byte_mask(),
                            begin,
                            end - 1,
                        ),
                    )
                    id = self.cursor.fetchone()[0]
                    self.set_id(
                        id,
                        path=path,
                        params=params,
                        mtime=mtime,
                        atime=atime,
                    )
                    return id
                self.cursor.execute(
                    f"SELECT id, atime FROM {namespace} WHERE (id & ?) BETWEEN ? AND ?",
                    (
                        id_features.subspace_byte_mask(),
                        begin,
                        end - 1,
                    ),
                )
                available_ids = set(id_features.all_ids(subspace))
                oldest_atime_id: Optional[Tuple[int, datetime]] = None
                for row in self.cursor.fetchall():
                    row_id = row[0]
                    row_atime = datetime.fromisoformat(row[1])
                    available_ids.remove(row_id)
                    if oldest_atime_id is None or row_atime < oldest_atime_id[1]:
                        oldest_atime_id = (row_id, row_atime)
                if available_ids:
                    id = secrets.choice(list(available_ids))
                else:
                    assert(oldest_atime_id is not None)
                    id = oldest_atime_id[0]
                self.set_id(
                    id,
                    path=path,
                    params=params,
                    mtime=mtime,
                    atime=atime,
                )
                return id

        # If the subspace is too large, try rejection sampling. We will try to
        # do it several times, and if we fail, we will do a cleanup and try
        # again. Cleanups are progressively more aggressive.
        for frac in [0.75, 0.6, 0.5, 0]:
            with self.conn:
                self.conn.execute("BEGIN")
                id = None
                # Run rejection sampling.
                for j in range(8):
                    id = id_features.gen_random_id(subspace)
                    self.cursor.execute(f"SELECT id FROM {namespace} WHERE id=?", (id,))
                    if not self.cursor.fetchone():
                        break
                    id = None
                # If it succeeded, insert the row and return the id.
                if id is not None:
                    self.set_id(
                        id,
                        path=path,
                        params=params,
                        mtime=mtime,
                        atime=atime,
                    )
                    return id
            if frac == 0:
                raise RuntimeError(
                    "Failed to find an unused id, row count:"
                    f" {self.count(id_features, subspace)}, subspace size:"
                    f" {subspace_size}"
                )
            # If it failed, try do a cleanup.
            self.cleanup(
                id_features,
                subspace,
                max_ids=min(int(subspace_size * frac), self.max_ids_per_subspace),
            )

    def cleanup(
        self,
        id_features: IDFeatures,
        subspace: IDSubspace = IDSubspace(),
        max_ids: Optional[int] = None,
    ):
        if max_ids is None:
            max_ids = self.max_ids_per_subspace
        namespace = id_features.namespace_name()
        begin, end = id_features.subspace_masked_range(subspace)
        self.cursor.execute(
            f"""DELETE FROM {namespace}
                WHERE id IN (
                    SELECT id FROM {namespace}
                    WHERE (id & ?) BETWEEN ? AND ?
                    ORDER BY atime ASC
                    LIMIT (
                        SELECT MAX(COUNT(*) - ?, 0) FROM {namespace}
                        WHERE (id & ?) BETWEEN ? AND ?
                    )
                )
            """,
            (
                id_features.subspace_byte_mask(),
                begin,
                end - 1,
                max_ids,
                id_features.subspace_byte_mask(),
                begin,
                end - 1,
            ),
        )

    def get_upload_info(self, id: int, terminal: str) -> Optional[UploadInfo]:
        self.cursor.execute(
            """
            SELECT path, params, mtime, upload_time, size FROM upload
            WHERE id=? AND terminal=?
            """,
            (id, terminal),
        )
        row = self.cursor.fetchone()
        if not row:
            return None
        path, params, mtime_str, upload_time_str, size = row
        if size is None:
            size = 0
        self.cursor.execute(
            """
            SELECT COUNT(*), SUM(size) FROM upload
            WHERE terminal = ? AND upload_time > ?
            """,
            (terminal, upload_time_str),
        )
        uploads_ago, bytes_ago = self.cursor.fetchone()
        return UploadInfo(
            id=id,
            path=path,
            params=params,
            mtime=datetime.fromisoformat(mtime_str),
            upload_time=datetime.fromisoformat(upload_time_str),
            terminal=terminal,
            size=size,
            bytes_ago=size + (bytes_ago if bytes_ago else 0),
            uploads_ago=1 + (uploads_ago if uploads_ago else 0),
        )

    def needs_uploading(
        self,
        id: int,
        terminal: str,
        *,
        max_uploads_ago: int = 1024,
        max_bytes_ago: int = 20 * (2**20),
        max_time_ago: timedelta = timedelta(hours=1),
    ) -> bool:
        info = self.get_info(id)
        if info is None:
            return False
        upload_info = self.get_upload_info(id, terminal)
        if upload_info is None:
            return True
        return (
            upload_info.path != info.path
            or upload_info.params != info.params
            or upload_info.mtime != info.mtime
            or upload_info.bytes_ago > max_bytes_ago
            or upload_info.uploads_ago > max_uploads_ago
            or datetime.now() - upload_info.upload_time > max_time_ago
        )

    def mark_uploaded(
        self,
        id: int,
        terminal: str,
        *,
        size: int,
        upload_time: Optional[datetime] = None,
    ):
        if upload_time is None:
            upload_time = datetime.now()
        info = self.get_info(id)
        if info is None:
            return
        self.cursor.execute(
            f"""INSERT INTO upload
                (id, path, params, mtime, size, terminal, upload_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id, terminal) DO UPDATE SET
                    path=excluded.path, params=excluded.params,
                    mtime=excluded.mtime, size=excluded.size,
                    upload_time=excluded.upload_time
            """,
            (
                id,
                info.path,
                info.params,
                info.mtime.isoformat(),
                size,
                terminal,
                upload_time.isoformat(),
            ),
        )

    def cleanup_uploads(
        self,
        max_uploads: int = 1024,
    ):
        self.cursor.execute(
            f"""DELETE FROM upload WHERE (id, terminal) NOT IN (
                    SELECT id, terminal FROM upload
                    ORDER BY upload_time DESC LIMIT ?
                )
            """,
            (max_uploads,),
        )
