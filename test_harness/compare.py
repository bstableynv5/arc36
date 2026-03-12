# from typing import Protocol
import hashlib
from hashlib import md5 as hashfunc
from pathlib import Path
from typing import Optional

import fiona
import geopandas as gp


def _get_hash(p: Path, hash: Optional['hashlib._Hash'] = None) -> bytes:
    """Gets the bytes digest of the contents of a path. If path is a single
    file, the hash is of its content. If path is a directory, the hash is of
    the content of all files within the tree rooted at `p` (ie recursive).

    Args:
        p (Path): a file or directory to hash
        hash (Optional[hashlib._Hash], optional): a hash object from
            hashlib. If None, a default hash function will be used.
            Defaults to None.

    Returns:
        bytes: the digest of the hash. this can be compared with other digests.
    """
    if hash is None:
        hash = hashfunc()

    if p.is_file():
        with p.open("rb") as file:
            hash.update(file.read())
    else:
        for item in p.iterdir():
            _get_hash(item, hash)

    return hash.digest()


def compare_hash(path_a: Path, path_b: Path) -> bool:
    """Compares two paths for equal content based on their hashes. So paths
    will be equal only if they're exactly the same.

    Args:
        path_a (Path): a path to a file or directory
        path_b (Path): a path to a file or directory

    Returns:
        bool: True if the paths are the same according to their
           hashes; False otherwise.
    """
    return _get_hash(path_a) == _get_hash(path_b)


def compare_featureclass(path_a: Path, path_b: Path) -> bool:
    df_a = gp.read_file(path_a.parent, layer=path_a.name)
    df_b = gp.read_file(path_b.parent, layer=path_b.name)
    return df_a.equals(df_b)  # seems to account for geometry and crs


def compare_gdb(path_a: Path, path_b: Path) -> bool:
    fcs_a = sorted(set(fiona.listlayers(path_a)))
    fcs_b = sorted(set(fiona.listlayers(path_b)))
    if fcs_a != fcs_b:
        return False

    fcs_same = []
    for fc_a, fc_b in zip(fcs_a, fcs_b):
        a = path_a / fc_a
        b = path_b / fc_b
        fcs_same.append(compare_featureclass(a, b))

    return all(fcs_same)


def compare(path_a: Path, path_b: Path) -> bool:
    same = compare_hash(path_a, path_b)
    if not same and path_a.suffix.lower() == ".gdb" and path_b.suffix.lower() == ".gdb":
        same = compare_gdb(path_a, path_b)
    return same
