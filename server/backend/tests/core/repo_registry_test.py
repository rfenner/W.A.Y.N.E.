import asyncio
import datetime

import pytest

class TestRepoRegistry:
    @pytest.mark.asyncio
    async def test_load_repositories(self, monkeypatch):
        base_path= '/app/tests/test_data/repo_registry_test'
        # patch the var first
        # now import the repository registry so it uses it
        from core.repo_registry import RepositoryRegistry
        RepositoryRegistry.load_repositories(base_path)

        assert len(RepositoryRegistry._repositories) == 1
        assert len(RepositoryRegistry._indexing) == 1
        print(RepositoryRegistry._indexing)


        # wait for the task to finish it's scan
        task = RepositoryRegistry._indexing['repo']
        start = datetime.datetime.now().timestamp()
        while not task.done():
            if datetime.datetime.now().timestamp() - start >= 10:
                assert False
            await asyncio.sleep(.5)

        # wait for the background task that removes completed indexing tasks
        start = datetime.datetime.now().timestamp()
        while len(RepositoryRegistry._indexing) != 0:
            if datetime.datetime.now().timestamp() - start >= 10:
                assert False
            await asyncio.sleep(.5)
