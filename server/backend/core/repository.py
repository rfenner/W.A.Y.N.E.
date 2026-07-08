import hashlib
import json
import os
import re
from pathlib import Path

from config import REPO_DATA_DIR_NAME_OLD, REPO_DATA_DIR_NAME
from core.directory_file_manager import DirectoryFileManager
from core.indexer_ import CodeIndexer
from core.repository_ignorer import RepositoryIgnorer
from core.wayne_ignorer import WayneIgnorer
from llm import get_system_llm
from llm.local_llm_client import LocalLLMClient


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

        self._readme_file_path = None
        self._readme_summary = ""
        self._readme_last_modified = 0

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

    @property
    def summary(self):
        return self._readme_summary

    @property
    def summary_file(self):
        return self._readme_file_path
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
        readme =  str(Path(self._canonical_path) / Path('Readme.md'))
        if readme in self._file_manager.file_list:
            if self._file_manager.file_list[readme] != self._readme_last_modified:
                self._summarize_readme(readme)
        self._indexer.build_index(self._file_manager.file_list)

    def _load_readme_summary(self):
        readme_summary =  Path(self._canonical_path)/Path(REPO_DATA_DIR_NAME) / Path('Readme_summary.json')
        if os.path.exists(readme_summary):
            with open(readme_summary, 'r') as f:
                summary = f.read()
                try:
                    summary = json.loads(summary)
                    # check if the stored file still exists
                    if os.path.exists(summary['file_path']):
                        # if the readme hasn't been modified then use it
                        if self._file_manager.file_list[summary['file_path']] == summary['last_summarized']:
                            self._readme_summary = summary['summary']
                            self._readme_last_modified = summary['last_summarized']
                            self._readme_file_path = summary['file_path']
                            return
                except json.decoder.JSONDecodeError:
                    # just fall out and regenerate the file
                    pass
            # need to summarize the readme
            self._summarize_readme()

    def _summarize_readme(self):
        modified  = None
        if self._readme_file_path is None:
            for file in self._file_manager.file_list.keys():
                if 'readme' in file.lower():
                    if file.replace(self._canonical_path, '').lower().startswith('readme'):
                        modified = self._file_manager.file_list[file]
                        self._readme_file_path = file
                        break

        # if we didn't find a readme then nothing to do
        if self._readme_file_path is None:
            return

        with open(self._readme_file_path, 'r', encoding='utf-8') as f:
            text = f.read().strip()

            if not text:
                return

            llm = get_system_llm()

            summary = llm.generate_system_text(
                prompt=f"Project README Content:\n\n{text}",
                system_prompt=(
                    "You are an expert workspace router. Summarize the provided project README file "
                    "into a highly dense, concise summary. State the exact core purpose of the codebase "
                    "and its complete tech stack. Limit your entire response to a maximum of 3 short sentences. "
                    "Do not include conversational pleasantries."
                ),
                temperature=0.1
            ).strip()

            if not summary:
                return

            readme_summary = Path(self._canonical_path) / Path(REPO_DATA_DIR_NAME) / Path('Readme_summary.json')
            summary_str = json.dumps({
                'summary': summary,
                'last_summarized': modified,
                'file_path': self._readme_file_path,
            })
            with open(readme_summary, 'w', encoding='utf-8') as f:
                f.write(summary_str)
            self._readme_summary = summary
            self._readme_last_modified = modified

    async def index_repository(self):
        self._file_manager.scan_directory()
        self._load_readme_summary()
        self._reindex_repo()
