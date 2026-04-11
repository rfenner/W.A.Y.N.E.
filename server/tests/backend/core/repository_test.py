import hashlib
import os
import shutil
from pathlib import Path

import pytest

from config import REPO_DATA_DIR_NAME_OLD, REPO_DATA_DIR_NAME
from core.directory_file_manager import DirectoryFileManager
from core.indexer_ import CodeIndexer
from core.repository import Repository


class TestRepository:
    @pytest.fixture(scope='function', autouse=True)
    def setup_teardown(self):
        self.base_path = '/test_repos/Test_repository'
        os.makedirs(self.base_path)
        git_ignore = Path(f'{self.base_path}/.gitignore')
        with open(git_ignore, 'w') as f:
            f.writelines(['dist'])
        yield
        shutil.rmtree(self.base_path)

    def test_init(self):
        repository = Repository(self.base_path)

        assert repository._repo_path == self.base_path
        assert repository._canonical_path == self.base_path
        assert repository._repo_id == hashlib.sha256(repository._canonical_path.encode('utf-8')).hexdigest()[:8]
        assert repository._repo_name == 'Test_repository'
        assert repository._repo_name_key == 'test_repository'
        assert repository._collection_name == f'wayne_{repository._repo_name}_{repository._repo_id}'
        assert isinstance(repository._indexer, CodeIndexer)
        assert repository._last_index_time == 0
        assert len(repository._ignorers) == 2
        assert isinstance(repository._file_manager, DirectoryFileManager)

        assert repository.metadata == {
            'repo_id':repository._repo_id,
            'repo_name':repository._repo_name,
            'collection_name':repository._collection_name,
            'canonical_path':repository._canonical_path,
        }

        assert repository.path == repository._repo_path
        assert repository.name == repository._repo_name
        assert repository.name_key == repository._repo_name_key
        assert repository.id == repository._repo_id
        assert repository.collection_name == repository._collection_name
        assert repository.canonical_path == repository._canonical_path
        assert repository.indexer == repository._indexer

    def test__get_canonical_path(self):
        repository = Repository(self.base_path)

        repository._repo_path = '~/test'
        assert repository._get_canonical_path() == '/root/test'

        repository._repo_path = 'test'
        assert repository._get_canonical_path() == '/app/test'

        repository._repo_path = '/test'
        assert repository._get_canonical_path() == '/test'

    def test__sanitize_name(self):
        repository = Repository(self.base_path)

        repository._repo_name = 'T#est__Repo%%1-'
        assert repository._sanitize_name() == 'T_est_Repo_1-'

    def test_migrate_old_data_dir(self):
        repository = Repository(self.base_path)
        repo_pilot_dir = Path(f'{self.base_path}/{REPO_DATA_DIR_NAME_OLD}')
        repo_pilot_dir.touch()
        assert os.path.exists(repo_pilot_dir.as_posix()) is True

        wayne_data_dir = Path(f'{self.base_path}/{REPO_DATA_DIR_NAME}')
        assert os.path.exists(wayne_data_dir.as_posix()) is False

        repository._migrate_old_data_dir()
        assert os.path.exists(repo_pilot_dir.as_posix()) is False
        assert os.path.exists(wayne_data_dir.as_posix()) is True
