# from typing import Protocol
from pathlib import Path
import hashlib
from hashlib import md5 as hashfunc
from typing import Optional


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


def compare(path_a: Path, path_b: Path) -> bool:
    same_content = compare_hash(path_a, path_b)
    return same_content
