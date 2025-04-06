import heapq
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Iterator, List, Optional, Tuple
from contextlib import closing


@dataclass(frozen=True)
class IDSubspace:
    """A subspace of ids, defined by a range of a certain byte (depending on the
    IDSpace space).

    The restricted byte is the most significant byte that can be used in an IDSpace
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
            raise ValueError(
                f"Invalid format for IDSubspace: '{s}'. Expected format 'begin:end' with integers."
            )
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
            raise ValueError(
                f"Subspace is too small to split: the number of non-zero byte values {self.num_nonzero_byte_values()} is less than the number of requested sub-subspaces {count}"
            )
        size = self.num_nonzero_byte_values() // count
        remainder = self.num_byte_values() - size * count
        subspaces = []
        for begin in range(self.begin + remainder, self.end, size):
            subspaces.append(IDSubspace(begin, begin + size))
        subspaces[0] = IDSubspace(self.begin, subspaces[0].end)
        return subspaces


@dataclass(frozen=True)
class IDSpace:
    """A space of image IDs described as the features that can be used to represent an
    image ID.

    When displaying an image using Unicode placeholders, the image ID may be represented
    with the fg color (24 or 8 bits) and the 3rd diacritic (8 bits). Some applications
    may not support all of the features, so all IDs are broken down into
    non-intersecting IDSpace spaces, each space contains only IDs that can be
    represented with the given features.

    Note that since we want the IDSpace spaces to be disjoint, certain bytes of the IDs
    belonging to bigger subspaces may be required to be non-zero.

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

    def __str__(self) -> str:
        bits = self.num_nonzero_bits()
        if bits == 8 and self.use_3rd_diacritic:
            return "8bit_diacritic"
        return f"{bits}bit"

    @staticmethod
    def from_string(s: str) -> "IDSpace":
        """Parses an IDSpace from a string."""
        if s in ("32", "32bit"):
            return IDSpace(24, True)
        if s in ("24", "24bit"):
            return IDSpace(24, False)
        if s in ("8d", "8bit_diacritic"):
            return IDSpace(0, True)
        if s in ("8", "8bit", "256"):
            return IDSpace(8, False)
        if s in ("16", "16d", "16bit", "16bit_diacritic"):
            return IDSpace(8, True)
        raise ValueError(f"Invalid IDSpace string: {s}")

    @staticmethod
    def from_id(id: int) -> "IDSpace":
        """Get the IDSpace space an image ID belongs to."""
        if id <= 0 or id > 0xFFFFFFFF:
            raise ValueError(f"Invalid id, must be non-zero 32-bit: {id}")
        use_3rd_diacritic = (id & 0xFF000000) != 0
        color_bits = 0
        if (id & 0x00FFFFFF) != 0:
            if (id & 0x00FFFF00) != 0:
                color_bits = 24
            else:
                color_bits = 8
        return IDSpace(color_bits, use_3rd_diacritic)

    def num_nonzero_bits(self) -> int:
        """Get the number of bits of an ID that may be nonzero in this space."""
        return (8 if self.use_3rd_diacritic else 0) + self.color_bits

    def namespace_name(self) -> str:
        """Get the name of this IDSpace space that can be used as an
        identifier or a file name."""
        if self.use_3rd_diacritic:
            return f"ids_{self}"
        else:
            return f"ids_{self}"

    def contains(self, id: int) -> bool:
        return self.from_id(id) == self

    def contains_and_in_subspace(self, id: int, subspace: IDSubspace) -> bool:
        """Returns true if the id is in this space and also in the given
        subspace."""
        begin, end = self.subspace_masked_range(subspace)
        return self.contains(id) and (begin <= (id & self.subspace_byte_mask()) < end)

    def gen_random_id(self, subspace: IDSubspace = IDSubspace()) -> int:
        """Generates a random id in this space that also belongs to the given
        subspace."""
        # We want to use every feature available to us, making id namespaces
        # disjoint.

        byte_0 = 0  # blue or the color index
        byte_1 = 0  # green
        byte_2 = 0  # red
        byte_3 = 0  # 3rd diacritic
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
        byte_0 = lambda: [0]  # blue or the color index
        byte_1_2 = lambda: [0]  # red and green
        byte_3 = lambda: [0]  # 3rd diacritic
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
                byte_1_2 = lambda: (
                    (b2 << 8) | b1
                    for b2 in subspace.all_byte_values()
                    for b1 in range(1 if b2 == 0 else 0, 256)
                )
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
    def get_subspace_byte(id: int) -> int:
        """Returns the byte to which the subspace is applied in the given ID."""
        offset = IDSpace.from_id(id).subspace_byte_offset()
        return (id >> offset) & 0xFF

    @staticmethod
    def all_values() -> Iterator["IDSpace"]:
        """Generates all IDSpace spaces."""
        for use_3rd_diacritic in [True, False]:
            for color_bits in [0, 8, 24]:
                if color_bits == 0 and not use_3rd_diacritic:
                    continue
                yield IDSpace(color_bits, use_3rd_diacritic)


@dataclass
class ImageInfo:
    description: str
    id: int
    atime: datetime


@dataclass
class UploadInfo:
    id: int
    description: str
    upload_time: datetime
    terminal: str
    size: int
    bytes_ago: int
    uploads_ago: int

    def needs_uploading(
        self,
        *,
        max_uploads_ago: int = 1024,
        max_bytes_ago: int = 20 * (2**20),
        max_time_ago: timedelta = timedelta(hours=1),
    ) -> bool:
        return (
            self.bytes_ago > max_bytes_ago
            or self.uploads_ago > max_uploads_ago
            or datetime.now() - self.upload_time > max_time_ago
        )


class IDManager:
    def __init__(self, database_file: str, *, max_ids_per_subspace: int = 1024):
        self.database_file = database_file
        directory = os.path.dirname(database_file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.conn = sqlite3.connect(database_file, isolation_level=None)
        self.max_ids_per_subspace: int = max_ids_per_subspace

        with closing(self.conn.cursor()) as cursor:
            # Set some options.
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout = 30000")
            # Make sure we have tables for all ID namespaces.
            for id_space in IDSpace.all_values():
                namespace = id_space.namespace_name()
                cursor.execute(
                    f"""
                        CREATE TABLE IF NOT EXISTS {namespace} (
                            id INTEGER PRIMARY KEY,
                            description TEXT NOT NULL,
                            atime TIMESTAMP NOT NULL
                        )
                    """
                )
                cursor.execute(
                    f"""CREATE INDEX IF NOT EXISTS idx_{namespace}_path_parameters
                        ON {namespace} (description)
                    """
                )
                cursor.execute(
                    f"""CREATE INDEX IF NOT EXISTS idx_{namespace}_atime
                        ON {namespace} (atime)
                    """
                )
            # Make sure we have a table for recent uploads.
            cursor.execute(
                f"""
                    CREATE TABLE IF NOT EXISTS upload (
                        id INTEGER NOT NULL,
                        description TEXT NOT NULL,
                        size INTEGER NOT NULL,
                        terminal TEXT NOT NULL,
                        upload_time TIMESTAMP NOT NULL,
                        PRIMARY KEY (id, terminal)
                    )
                """
            )
            cursor.execute(
                f"""CREATE INDEX IF NOT EXISTS idx_upload_upload_time
                    ON upload (upload_time)
                """
            )
            self.conn.commit()

    def close(self):
        self.conn.close()

    def get_info(self, id: int) -> Optional[ImageInfo]:
        id_space = IDSpace.from_id(id)
        namespace = id_space.namespace_name()
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(
                f"""SELECT description, atime FROM {namespace}
                    WHERE id=?
                """,
                (id,),
            )
            row = cursor.fetchone()
        if not row:
            return None
        description, atime = row
        return ImageInfo(
            id=id,
            description=description,
            atime=datetime.fromisoformat(atime),
        )

    def get_all(
        self,
        id_space: Optional[IDSpace] = None,
        subspace: IDSubspace = IDSubspace(),
    ) -> List[ImageInfo]:
        if id_space is None:
            spaces = [self.get_all(s, subspace) for s in IDSpace.all_values()]
            return list(heapq.merge(*spaces, key=lambda x: x.atime, reverse=True))

        namespace = id_space.namespace_name()
        begin, end = id_space.subspace_masked_range(subspace)
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(
                f"""SELECT id, description, atime FROM {namespace}
                    WHERE (id & ?) BETWEEN ? AND ? ORDER BY atime DESC
                """,
                (
                    id_space.subspace_byte_mask(),
                    begin,
                    end - 1,
                ),
            )
            return [
                ImageInfo(
                    id=row[0],
                    description=row[1],
                    atime=datetime.fromisoformat(row[2]),
                )
                for row in cursor.fetchall()
            ]

    def count(
        self,
        id_space: Optional[IDSpace] = None,
        subspace: IDSubspace = IDSubspace(),
    ) -> int:
        if id_space is None:
            return sum(self.count(s, subspace) for s in IDSpace.all_values())

        namespace = id_space.namespace_name()
        begin, end = id_space.subspace_masked_range(subspace)
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(
                f"""SELECT COUNT(*) FROM {namespace}
                    WHERE (id & ?) BETWEEN ? AND ?
                """,
                (
                    id_space.subspace_byte_mask(),
                    begin,
                    end - 1,
                ),
            )
            return cursor.fetchone()[0]

    def set_id(
        self,
        id: int,
        description: str,
        *,
        atime: Optional[datetime] = None,
    ):
        id_space = IDSpace.from_id(id)
        namespace = id_space.namespace_name()
        if atime is None:
            atime = datetime.now()
        with closing(self.conn.cursor()) as cursor:
            # Upsert the row.
            cursor.execute(
                f"""INSERT INTO {namespace} (id, description, atime)
                    VALUES (?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        description=excluded.description,
                        atime=excluded.atime
                """,
                (id, description, atime.isoformat()),
            )

    def del_id(self, id: int):
        id_space = IDSpace.from_id(id)
        namespace = id_space.namespace_name()
        with self.conn:
            with closing(self.conn.cursor()) as cursor:
                self.conn.execute("BEGIN IMMEDIATE")
                cursor.execute(f"DELETE FROM {namespace} WHERE id=?", (id,))

    def get_id(
        self,
        description: str,
        id_space: IDSpace,
        *,
        subspace: IDSubspace = IDSubspace(),
    ) -> int:
        namespace = id_space.namespace_name()
        begin, end = id_space.subspace_masked_range(subspace)

        atime = datetime.now()

        with self.conn:
            with closing(self.conn.cursor()) as cursor:
                cursor.execute("BEGIN IMMEDIATE")
                # Find the row with the given `description` and id subspace.
                cursor.execute(
                    f"""SELECT id FROM {namespace}
                        WHERE description=? AND (id & ?) BETWEEN ? AND ?
                    """,
                    (
                        description,
                        id_space.subspace_byte_mask(),
                        begin,
                        end - 1,
                    ),
                )
                row = cursor.fetchone()

                # If there is such a row, update the `atime` and return the `id`.
                if row:
                    id = row[0]
                    cursor.execute(
                        f"UPDATE {namespace} SET atime=? WHERE id=?",
                        (atime.isoformat(), id),
                    )
                    return id

                subspace_size = id_space.subspace_size(subspace)

                # If the subspace is small enough, we will select all the rows and
                # identify unused IDs.
                if subspace_size <= min(1024, self.max_ids_per_subspace):
                    # First check the count of rows in the subspace. If the subspace
                    # is full, select the oldest row and update it.
                    if self.count(id_space, subspace) >= subspace_size:
                        cursor.execute(
                            f"""SELECT id FROM {namespace} WHERE (id & ?) BETWEEN ? AND ?
                                ORDER BY atime ASC LIMIT 1
                            """,
                            (
                                id_space.subspace_byte_mask(),
                                begin,
                                end - 1,
                            ),
                        )
                        id = cursor.fetchone()[0]
                        self.set_id(
                            id,
                            description=description,
                            atime=atime,
                        )
                        return id
                    cursor.execute(
                        f"SELECT id, atime FROM {namespace} WHERE (id & ?) BETWEEN ? AND ?",
                        (
                            id_space.subspace_byte_mask(),
                            begin,
                            end - 1,
                        ),
                    )
                    available_ids = set(id_space.all_ids(subspace))
                    oldest_atime_id: Optional[Tuple[int, datetime]] = None
                    for row in cursor.fetchall():
                        row_id = row[0]
                        row_atime = datetime.fromisoformat(row[1])
                        available_ids.remove(row_id)
                        if oldest_atime_id is None or row_atime < oldest_atime_id[1]:
                            oldest_atime_id = (row_id, row_atime)
                    if available_ids:
                        id = secrets.choice(list(available_ids))
                    else:
                        assert oldest_atime_id is not None
                        id = oldest_atime_id[0]
                    self.set_id(
                        id,
                        description=description,
                        atime=atime,
                    )
                    return id

        # If the subspace is too large, try rejection sampling. We will try to
        # do it several times, and if we fail, we will do a cleanup and try
        # again. Cleanups are progressively more aggressive.
        for frac in [0.75, 0.6, 0.5, 0]:
            with self.conn:
                self.conn.execute("BEGIN IMMEDIATE")
                id = None
                with closing(self.conn.cursor()) as cursor:
                    # Run rejection sampling.
                    for j in range(8):
                        id = id_space.gen_random_id(subspace)
                        cursor.execute(f"SELECT id FROM {namespace} WHERE id=?", (id,))
                        if not cursor.fetchone():
                            break
                        id = None
                    # If it succeeded, insert the row and return the id.
                    if id is not None:
                        self.set_id(
                            id,
                            description=description,
                            atime=atime,
                        )
                        return id
            if frac == 0:
                break
            # If it failed, try do a cleanup.
            self.cleanup(
                id_space,
                subspace,
                max_ids=min(int(subspace_size * frac), self.max_ids_per_subspace),
            )

        raise RuntimeError(
            "Failed to find an unused id, row count:"
            f" {self.count(id_space, subspace)}, subspace size:"
            f" {subspace_size}"
        )

    def cleanup(
        self,
        id_space: IDSpace,
        subspace: IDSubspace = IDSubspace(),
        max_ids: Optional[int] = None,
    ):
        if max_ids is None:
            max_ids = self.max_ids_per_subspace
        namespace = id_space.namespace_name()
        begin, end = id_space.subspace_masked_range(subspace)
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(
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
                    id_space.subspace_byte_mask(),
                    begin,
                    end - 1,
                    max_ids,
                    id_space.subspace_byte_mask(),
                    begin,
                    end - 1,
                ),
            )

    def get_upload_info(self, id: int, terminal: str) -> Optional[UploadInfo]:
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(
                """
                SELECT description, upload_time, size FROM upload
                WHERE id=? AND terminal=?
                """,
                (id, terminal),
            )
            row = cursor.fetchone()
            if not row:
                return None
            description, upload_time_str, size = row
            if size is None:
                size = 0
            cursor.execute(
                """
                SELECT COUNT(*), SUM(size) FROM upload
                WHERE terminal = ? AND upload_time > ?
                """,
                (terminal, upload_time_str),
            )
            uploads_ago, bytes_ago = cursor.fetchone()
        return UploadInfo(
            id=id,
            description=description,
            upload_time=datetime.fromisoformat(upload_time_str),
            terminal=terminal,
            size=size,
            bytes_ago=size + (bytes_ago if bytes_ago else 0),
            uploads_ago=1 + (uploads_ago if uploads_ago else 0),
        )

    def get_upload_infos(self, id: int) -> List[UploadInfo]:
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(
                """
                SELECT terminal FROM upload
                WHERE id=?
                """,
                (id,),
            )
            res = []
            for row in cursor.fetchall():
                terminal = row[0]
                upload_info = self.get_upload_info(id, terminal)
                if upload_info:
                    res.append(upload_info)
            return res

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
            upload_info.description != info.description
            or upload_info.needs_uploading(
                max_uploads_ago=max_uploads_ago,
                max_bytes_ago=max_bytes_ago,
                max_time_ago=max_time_ago,
            )
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
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(
                f"""INSERT INTO upload
                    (id, description, size, terminal, upload_time)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id, terminal) DO UPDATE SET
                        description=excluded.description,
                        size=excluded.size,
                        upload_time=excluded.upload_time
                """,
                (
                    id,
                    info.description,
                    size,
                    terminal,
                    upload_time.isoformat(),
                ),
            )

    def cleanup_uploads(
        self,
        max_uploads: int = 1024,
    ):
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(
                f"""DELETE FROM upload WHERE (id, terminal) NOT IN (
                        SELECT id, terminal FROM upload
                        ORDER BY upload_time DESC LIMIT ?
                    )
                """,
                (max_uploads,),
            )

    def get_all_with_upload_info(
        self, id_space: IDSpace, subspace: IDSubspace = IDSubspace()
    ) -> List[ImageInfo]:
        namespace = id_space.namespace_name()
        begin, end = id_space.subspace_masked_range(subspace)
        with closing(self.conn.cursor()) as cursor:
            cursor.execute(
                f"""SELECT id, description, atime FROM {namespace}
                    WHERE (id & ?) BETWEEN ? AND ? ORDER BY atime DESC
                """,
                (
                    id_space.subspace_byte_mask(),
                    begin,
                    end - 1,
                ),
            )
            return [
                ImageInfo(
                    id=row[0],
                    description=row[1],
                    atime=datetime.fromisoformat(row[4]),
                )
                for row in cursor.fetchall()
            ]
