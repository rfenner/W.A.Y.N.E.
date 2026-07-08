import os
import shutil
from pathlib import Path

import pytest
from pathspec import PathSpec

from core.repository_ignorer import RepositoryIgnorer


class TestRepositoryIgnorer:
    @pytest.fixture(scope='function', autouse=True)
    def setup_teardown(self):
        self.base_path = '/test_repository_ignorer'
        os.makedirs(self.base_path)
        yield
        shutil.rmtree(self.base_path)

    def test_init_no_ignore(self):
        ignorer = RepositoryIgnorer(self.base_path)
        assert ignorer._repo_path == self.base_path
        assert isinstance(ignorer._checker, PathSpec)

        assert ignorer.file_ignored(f'{self.base_path}/test.txt') is False

    def test_init_ignore_file(self):
        ignore_file = Path(f'{self.base_path}/.gitignore')
        ignore_file.touch()
        with open(ignore_file, 'w') as f:
            f.writelines(['dist'])

        ignorer = RepositoryIgnorer(str(self.base_path))

        assert ignorer._repo_path == self.base_path
        assert isinstance(ignorer._checker, PathSpec)

        assert ignorer.file_ignored(f'{self.base_path}/dist') is True
        assert ignorer.file_ignored(f'{self.base_path}/test.txt') is False
