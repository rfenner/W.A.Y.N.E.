"""
Repo Registry — deterministic per-repo identification for WAYNE.

Each repository gets a unique, stable ID derived from its canonical
absolute path. This ID is used to create isolated Qdrant collections
so that multiple repos never pollute each other's vector stores.
"""
import asyncio
import logging
import os
from typing import TYPE_CHECKING

from core.connection_manager import WSConnectionManager
from core.repository import Repository

if TYPE_CHECKING:
    from core.user import User

logger = logging.getLogger(__name__)


class RepositoryRegistry:
    """
    Singleton class that tracks all the repositories
    that we cloned or are in the repository directory
    """
    _repositories = {}
    _indexing = {}

    @classmethod
    def load_repositories(cls, repositories_path:str):
        """
        Scans the repertoires directory and loads any it finds.
        The loading is done asynchronously.
        """
        with os.scandir(repositories_path) as entries:
            for entry in entries:
                if not entry.is_dir():
                    continue

                git_dir = f'{entry.path}/.git'
                if not os.path.exists(git_dir):
                    continue
                ignore = f'{entry.path}/.wayne_skip'
                if os.path.exists(ignore):
                    continue
                cls.index_repository(entry.path)

        asyncio.create_task(cls._check_indexing())

    @classmethod
    def get_repository(cls, repo_name: str) -> Repository | None:
        """
        checks the passed name and returns the repository if it is one
        """
        if repo_name in cls._repositories:
            return cls._repositories[repo_name]
        return None

    @classmethod
    async def _check_indexing(cls):
        """
        Task that runs in the background that checks indexing and
        clears out done tasks
        """

        for repo_name in list(cls._indexing):
            repo_task = cls._indexing[repo_name]
            if repo_task.done():
                exception = repo_task.exception()
                if exception is not None:
                    logging.exception(exception)
                else:
                    WSConnectionManager.broadcast(
                        f"I've completed indexing repository {cls._repositories[repo_name].name}")

                del cls._indexing[repo_name]

    @classmethod
    def index_repository(cls, repo_path: str):
        repo = Repository(repo_path)
        cls._repositories[repo.name_key] = repo
        cls._indexing[repo.name_key] = asyncio.create_task(repo.index_repository())

    @classmethod
    def get_indexing_status(cls, client: 'User'):
        """
        send the indexing status to the client
        """
        indexing = ""
        failed = ""
        done = ""
        for repo_name in cls._indexing.keys():
            repo_task = cls._indexing[repo_name]
            if repo_task.done():
                exception = repo_task.exception()
                if exception is None:
                    done += repo_task.result()
                else:
                    failed += f"{cls._repositories[repo_name].name}\n"
            else:
                indexing += f"{cls._repositories[repo_name].name}\n"

        response = ""
        if done != "":
            response += "I've completed indexing the following repositories:\n" + done

        if indexing != "":
            response += "I'm still indexing the following repositories:\n" + indexing

        if failed != "":
            response += "I encountered an error while indexing these repositories:\n" + failed

        if response != "":
            client.send_output("I encountered an error while indexing these repositories:\n" + failed)

    @classmethod
    def list_repositories(cls, client: 'User'):
        """
        Sends a list of repositories to the client minus ones that are indexing
        """
        response = 'I know about the following repositories:\n'
        indexing = False
        for repo in cls._repositories.values():
            if repo.name_key in cls._indexing:
                indexing = True
                continue
            response += f"{repo.name}\n"
        response += """Just tell me which one to use and i'll base my answers on that repository.\n
         You can switch repositories by telling me to use another one.\n"""

        if indexing:
            response += "I'm still indexing some repositories so they are not listed.\nI'll let you know when their done."

        client.send_output(response)
