import os
import shutil
from pathlib import Path

import pytest
from pathspec import PathSpec

from tools.wayne_ignorer import WayneIgnorer


class TestWayneIgnorer:
    @pytest.fixture(scope='function', autouse=True)
    def setup_teardown(self):
        self.base_path = '/test_wayne_ignorer'
        os.makedirs(self.base_path)
        yield
        shutil.rmtree(self.base_path)

    def test_init_no_ignore(self):
        ignorer = WayneIgnorer(self.base_path)
        assert ignorer._repo_path == self.base_path
        assert ignorer._checker is None

        assert ignorer.file_ignored(f'{self.base_path}/test.txt') is False

    def test_init_ignore_file(self):
        ignore_file = Path(f'{self.base_path}/.wayne_ignore')
        ignore_file.touch()
        with open(ignore_file, 'w') as f:
            f.writelines(['dist'])

        ignorer = WayneIgnorer(str(self.base_path))

        assert ignorer._repo_path == self.base_path
        assert isinstance(ignorer._checker, PathSpec)

        assert ignorer.file_ignored(f'{self.base_path}/dist') is True
        assert ignorer.file_ignored(f'{self.base_path}/test.txt') is False
