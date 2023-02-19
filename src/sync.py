import hashlib
import os
import shutil
from pathlib import Path

BLOCKSIZE = 65536


def hash_file(path: Path) -> str:
    """指定したファイルからユニークなハッシュを生成する."""
    hasher = hashlib.sha1()
    with path.open("rb") as file:
        buf = file.read(BLOCKSIZE)
        while buf:
            hasher.update(buf)
            buf = file.read(BLOCKSIZE)
    return hasher.hexdigest()


def sync(source, dest):
    # imperative shell step 1, gather inputs
    source_hashes = read_paths_and_hashes(source)  1
    dest_hashes = read_paths_and_hashes(dest)  1

    # step 2: call functional core
    actions = determine_actions(source_hashes, dest_hashes, source, dest)  2

    # imperative shell step 3, apply outputs
    for action, *paths in actions:
        if action == 'copy':
            shutil.copyfile(*paths)
        if action == 'move':
            shutil.move(*paths)
        if action == 'delete':
            os.remove(paths[0])
