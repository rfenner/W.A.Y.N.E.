import hashlib
import os
import re

from config import REPO_DATA_DIR_NAME_OLD, REPO_DATA_DIR_NAME
from core.directory_file_manager import DirectoryFileManager
from core.indexer_ import CodeIndexer
from tools.repository_ignorer import RepositoryIgnorer
from tools.wayne_ignorer import WayneIgnorer


class Repository:
    """
    Handles managing a git repository for wayne
    """

    def __init__(self, repo_path: str):
        self._repo_path = repo_path
        self._canonical_path = self._get_canonical_path()
        self._repo_id = self._generate_repo_id()
        self._repo_name = self._get_repo_name()
        self._repo_name_key = self._repo_name.lower()
        self._collection_name = self._generate_collection_name()

        self._indexer = CodeIndexer(self._collection_name)

        self._last_index_time = 0

        self._ignorers = [
            RepositoryIgnorer(repo_path),
            WayneIgnorer(repo_path)
        ]

        self._migrate_old_data_dir()

        self._file_manager = DirectoryFileManager(self._repo_path, self._ignorers, self._reindex_repo)

    @property
    def metadata(self) -> dict:
        """
        Return full metadata for a repo, useful for logging and debugging.
        """
        return {
            "repo_id": self._repo_id,
            "repo_name": self._repo_name,
            "collection_name": self._collection_name,
            "canonical_path": self._canonical_path,
        }

    @property
    def path(self):
        return self._repo_path

    @property
    def name(self):
        return self._repo_name

    @property
    def name_key(self):
        return self._repo_name_key

    @property
    def id(self):
        return self._repo_id

    @property
    def collection_name(self):
        return self._collection_name

    @property
    def canonical_path(self):
        return self._canonical_path

    @property
    def indexer(self):
        return self._indexer

    @property
    def repository_files(self):
        return self._file_manager.file_list

    def _get_canonical_path(self) -> str:
        """Resolve a repo path to its canonical form for stable hashing."""
        return os.path.realpath(os.path.abspath(os.path.expanduser(self._repo_path)))

    def _generate_repo_id(self) -> str:
        """
        Generate a deterministic 8-char hex ID from the repo's canonical path.

        This matches the naming scheme already used in .repopilot_indexes/
        (e.g. claim-verifier_5eaca942).
        """
        return hashlib.sha256(self._canonical_path.encode("utf-8")).hexdigest()[:8]

    def _sanitize_name(self) -> str:
        """
        Sanitize a repo name for use in Qdrant collection names.
        Qdrant allows alphanumeric, hyphens, and underscores.
        """
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", self._repo_name)
        # Collapse multiple underscores
        sanitized = re.sub(r"_+", "_", sanitized).strip("_")
        return sanitized[:40]  # keep it short

    def _get_repo_name(self) -> str:
        return os.path.basename(os.path.normpath(self._repo_path))

    def _generate_collection_name(self):
        """
        Generate a unique Qdrant collection name for a repository.

        Format: wayne_{sanitized_repo_name}_{hash8}
        Example: wayne_claim-verifier_5eaca942
        """
        sanitized = self._sanitize_name()
        return f"wayne_{sanitized}_{self._repo_id}"

    def _migrate_old_data_dir(self):
        old_file_name = f'{self._canonical_path}/{REPO_DATA_DIR_NAME_OLD}'
        if os.path.exists(old_file_name):
            new_name = f'{self._canonical_path}/{REPO_DATA_DIR_NAME}'
            os.rename(old_file_name, new_name)

    def _reindex_repo(self):
        self._indexer.build_index(self._file_manager.file_list)

    async def index_repository(self):
        self._file_manager.scan_directory()
        self._reindex_repo()
