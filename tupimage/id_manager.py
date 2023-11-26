from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Iterator, List
import secrets
import sqlite3
import os


def _randbits_nonzero(bits: int) -> int:
    if bits <= 1:
        return 1
    else:
        x = 0
        while x == 0:
            x = secrets.randbits(bits)
        return x


def _randbits(bits: int, nonzero: bool) -> int:
    if nonzero:
        return _randbits_nonzero(bits)
    else:
        return secrets.randbits(bits)


@dataclass(frozen=True)
class IDSubspace:
    fixed_bits: int = 0
    value: int = 0

    def __post_init__(self):
        if self.fixed_bits < 0 or self.fixed_bits > 6:
            raise ValueError(
                "The number of fixed bits must be between 0 and 6, got:"
                f" {self.fixed_bits}"
            )
        if self.value < 0 or self.value >= 1 << self.fixed_bits:
            raise ValueError(f"Invalid value: {self.value}")

    def _modify_byte(self, id: int) -> int:
        return (id & ~self._mask()) | self.value

    def _mask(self) -> int:
        return (1 << self.fixed_bits) - 1

    def _rand_nonzero_byte(self) -> int:
        b = (
            _randbits(8 - self.fixed_bits, nonzero=self.value == 0)
            << self.fixed_bits
        )
        return self._modify_byte(b)

    def _all_nonzero_bytes(self) -> Iterator[int]:
        for b in range(1 << (8 - self.fixed_bits)):
            if b != 0 or self.value != 0:
                yield (b << self.fixed_bits) | self.value

    def _all_bytes(self) -> Iterator[int]:
        for b in range(1 << (8 - self.fixed_bits)):
            yield (b << self.fixed_bits) | self.value


@dataclass(frozen=True)
class IDFeatures:
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

    def num_bits(self) -> int:
        return (8 if self.use_3rd_diacritic else 0) + self.color_bits

    def namespace_name(self) -> str:
        if self.use_3rd_diacritic:
            return f"ids_{self.num_bits()}bit_3rd_diacritic"
        else:
            return f"ids_{self.num_bits()}bit"

    def contains(self, id: int) -> bool:
        return self.from_id(id) == self

    def contains_and_in_subspace(self, id: int, subspace: IDSubspace) -> bool:
        return self.contains(id) and (
            id & self.subspace_mask(subspace)
        ) == self.subspace_masked_value(subspace)

    def gen_random_id(self, subspace: IDSubspace = IDSubspace()) -> int:
        # We want to use every feature available to us, making id namespaces
        # disjoint.

        # If we can't use any color bits, we must use the 3rd diacritic and
        # apply the subspace to it.
        if self.color_bits == 0:
            return subspace._rand_nonzero_byte() << 24

        byte_0 = 0
        byte_1_2 = 0
        byte_3 = 0
        if self.use_3rd_diacritic:
            # If we can use the 3rd diacritic, it must be nonzero.
            byte_3 = _randbits_nonzero(8)
        if self.color_bits == 8:
            # If we can use only 8 bit colors, the color must be nonzero and we
            # apply the subspace to it.
            byte_0 = subspace._rand_nonzero_byte()
        elif self.color_bits == 24:
            # If we can use 24 bit colors, the two bytes in the middle must be
            # non-zero, but the least significant byte may be zero.
            byte_0 = subspace._modify_byte(secrets.randbits(8))
            byte_1_2 = _randbits_nonzero(16)
        return (byte_3 << 24) | (byte_1_2 << 8) | byte_0

    def all_ids(self, subspace: IDSubspace = IDSubspace()) -> Iterator[int]:
        if self.color_bits == 0:
            for b in subspace._all_nonzero_bytes():
                yield b << 24
            return

        byte3_gen = lambda: range(1, 256) if self.use_3rd_diacritic else [0]

        if self.color_bits == 8:
            byte0_gen = lambda: subspace._all_nonzero_bytes()
            byte12_gen = lambda: [0]
        elif self.color_bits == 24:
            byte0_gen = lambda: subspace._all_bytes()
            byte12_gen = lambda: range(1, 1 << 16)

        for byte3 in byte3_gen():
            for byte12 in byte12_gen():
                for byte0 in byte0_gen():
                    yield (byte3 << 24) | (byte12 << 8) | byte0

    def subspace_size(self, subspace: IDSubspace = IDSubspace()) -> int:
        num_zero_ids = 1 if subspace.value == 0 else 0
        if self.color_bits == 0:
            return (1 << (8 - subspace.fixed_bits)) - num_zero_ids

        byte3_count = 255 if self.use_3rd_diacritic else 1

        if self.color_bits == 8:
            byte0_count = (1 << (8 - subspace.fixed_bits)) - num_zero_ids
            byte12_count = 1
        elif self.color_bits == 24:
            byte0_count = 256
            byte12_count = (1 << 16) - 1

        return byte3_count * byte12_count * byte0_count

    def subspace_mask(self, subspace: IDSubspace) -> int:
        if self.color_bits == 0:
            return subspace._mask() << 24
        else:
            return subspace._mask()

    def subspace_masked_value(self, subspace: IDSubspace) -> int:
        if self.color_bits == 0:
            return subspace.value << 24
        else:
            return subspace.value

    @staticmethod
    def all_values() -> Iterator["IDFeatures"]:
        for use_3rd_diacritic in [True, False]:
            for color_bits in [0, 8, 24]:
                if color_bits == 0 and not use_3rd_diacritic:
                    continue
                yield IDFeatures(color_bits, use_3rd_diacritic)


@dataclass
class ImageInfo:
    path: str
    parameters: str = ""
    mtime: Optional[datetime] = None
    id: Optional[int] = None
    atime: Optional[datetime] = None


class IDManager:
    def __init__(self, database_file: str, max_ids_per_subspace: int = 1024):
        self.conn = sqlite3.connect(database_file, isolation_level=None)
        self.cursor = self.conn.cursor()
        self.max_ids_per_subspace: int = max_ids_per_subspace

        # Make sure we have tables for all ID namespaces.
        for id_features in IDFeatures.all_values():
            namespace = id_features.namespace_name()
            self.cursor.execute(f"""CREATE TABLE IF NOT EXISTS {namespace} (
                        id INTEGER PRIMARY KEY,
                        path TEXT,
                        parameters TEXT,
                        mtime TIMESTAMP,
                        atime TIMESTAMP
                    )
                """)
            self.cursor.execute(
                f"""CREATE INDEX IF NOT EXISTS idx_{namespace}_path_parameters
                    ON {namespace} (path, parameters)
                """
            )
            self.cursor.execute(
                f"""CREATE INDEX IF NOT EXISTS idx_{namespace}_atime
                    ON {namespace} (atime)
                """
            )
        self.conn.commit()

    def get_info(self, id: int) -> Optional[ImageInfo]:
        id_features = IDFeatures.from_id(id)
        namespace = id_features.namespace_name()
        self.cursor.execute(
            f"""SELECT path, parameters, mtime, atime FROM {namespace}
                WHERE id=?
            """,
            (id,),
        )
        row = self.cursor.fetchone()
        if not row:
            return None
        path, parameters, mtime, atime = row
        return ImageInfo(
            id=id,
            path=path,
            parameters=parameters,
            mtime=datetime.fromisoformat(mtime),
            atime=datetime.fromisoformat(atime),
        )

    def get_all(
        self, id_features: IDFeatures, subspace: IDSubspace = IDSubspace()
    ) -> List[ImageInfo]:
        namespace = id_features.namespace_name()
        self.cursor.execute(
            f"""SELECT id, path, parameters, mtime, atime FROM {namespace}
                WHERE id & ? = ? ORDER BY atime DESC
            """,
            (
                id_features.subspace_mask(subspace),
                id_features.subspace_masked_value(subspace),
            ),
        )
        return [
            ImageInfo(
                id=row[0],
                path=row[1],
                parameters=row[2],
                mtime=datetime.fromisoformat(row[3]),
                atime=datetime.fromisoformat(row[4]),
            )
            for row in self.cursor.fetchall()
        ]

    def count(
        self, id_features: IDFeatures, subspace: IDSubspace = IDSubspace()
    ) -> int:
        namespace = id_features.namespace_name()
        self.cursor.execute(
            f"SELECT COUNT(*) FROM {namespace} WHERE id & ? = ?",
            (
                id_features.subspace_mask(subspace),
                id_features.subspace_masked_value(subspace),
            ),
        )
        return self.cursor.fetchone()[0]

    def set_id(
        self,
        id: int,
        path: str,
        parameters: str = "",
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
            f"""INSERT INTO {namespace} (id, path, parameters, mtime, atime)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    path=excluded.path, parameters=excluded.parameters,
                    mtime=excluded.mtime, atime=excluded.atime
            """,
            (id, path, parameters, mtime.isoformat(), atime.isoformat()),
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
        parameters: str = "",
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

        atime = datetime.now()

        with self.conn:
            self.conn.execute("BEGIN")
            # Find the row with the given `path`, `parameters`, `mtime` and id
            # subspace.
            self.cursor.execute(
                f"""SELECT id FROM {namespace}
                    WHERE path=? AND parameters=? AND mtime=? AND id & ? = ?
                """,
                (
                    path,
                    parameters,
                    mtime.isoformat(),
                    id_features.subspace_mask(subspace),
                    id_features.subspace_masked_value(subspace),
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
            if subspace_size <= min(256, self.max_ids_per_subspace):
                # First check the count of rows in the subspace. If the subspace
                # is full, select the oldest row and update it.
                if self.count(id_features, subspace) >= subspace_size:
                    self.cursor.execute(
                        f"""SELECT id FROM {namespace} WHERE id & ? = ?
                            ORDER BY atime ASC LIMIT 1
                        """,
                        (
                            id_features.subspace_mask(subspace),
                            id_features.subspace_masked_value(subspace),
                        ),
                    )
                    id = self.cursor.fetchone()[0]
                    self.set_id(
                        id,
                        path=path,
                        parameters=parameters,
                        mtime=mtime,
                        atime=atime,
                    )
                    return id
                self.cursor.execute(
                    f"SELECT id, atime FROM {namespace} WHERE id & ? = ?",
                    (
                        id_features.subspace_mask(subspace),
                        id_features.subspace_masked_value(subspace),
                    ),
                )
                available_ids = set(id_features.all_ids(subspace))
                oldest_atime_id: Optional[Tuple[int, datetime]] = None
                for row in self.cursor.fetchall():
                    row_id = row[0]
                    row_atime = datetime.fromisoformat(row[1])
                    available_ids.remove(row_id)
                    if (
                        oldest_atime_id is None
                        or row_atime < oldest_atime_id[1]
                    ):
                        oldest_atime_id = (row_id, row_atime)
                if available_ids:
                    id = secrets.choice(list(available_ids))
                else:
                    id = oldest_atime_id[0]
                self.set_id(
                    id,
                    path=path,
                    parameters=parameters,
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
                    self.cursor.execute(
                        f"SELECT id FROM {namespace} WHERE id=?", (id,)
                    )
                    if not self.cursor.fetchone():
                        break
                    id = None
                # If it succeeded, insert the row and return the id.
                if id is not None:
                    self.set_id(
                        id,
                        path=path,
                        parameters=parameters,
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
                max_ids=min(
                    int(subspace_size * frac), self.max_ids_per_subspace
                ),
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
        self.cursor.execute(
            f"""DELETE FROM {namespace}
                WHERE id IN (
                    SELECT id FROM {namespace}
                    WHERE id & ? = ?
                    ORDER BY atime ASC
                    LIMIT (
                        SELECT MAX(COUNT(*) - ?, 0) FROM {namespace}
                        WHERE id & ? = ?
                    )
                )
            """,
            (
                id_features.subspace_mask(subspace),
                id_features.subspace_masked_value(subspace),
                max_ids,
                id_features.subspace_mask(subspace),
                id_features.subspace_masked_value(subspace),
            ),
        )

    def close(self):
        self.conn.close()
