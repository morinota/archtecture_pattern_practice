import shutil
import tempfile
from pathlib import Path

from src.sync import sync


def test_when_a_file_exists_in_the_source_but_not_the_destination():
    src_hashes = {"hash1": "fn1"}
    dst_hashes = {}
    expected_actions = [("COPY", "/src/fn1", "/dst/fn1")]


def test_when_a_file_has_been_renamed_in_the_source():
    src_hashes = {"hash1": "fn1"}
    dst_hashes = {"hash1": "fn2"}
    expected_actions = [("MOVE", "/dst/fn2", "/dst/fn1")]
