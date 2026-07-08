import os

import pathspec

from core.directory_file_manager import FileObjectIgnorer

# Common junk directories and files to ignore
IGNORE_DIRS = [
    "node_modules",
    ".git",
    "venv",
    "build",
    "dist",
    "__pycache__",
    ".idea",
    ".vscode",
    ".repopilot_index",
    ".pytest_cache",
    ".venv",
    "env",
    ".env",
    "htmlcov",
    ".coverage",
    "site-packages",
    ".tox",
    ".eggs",
    "*.egg-info",
    "target",
    ".gradle",
    "vendor",
    "deps",
    "tmp",
]

IGNORE_FILES = [
    ".DS_Store",
    ".gitignore",
    ".gitattributes",
    "thumbs.db",
    ".wayne_skip",
    ".wayne_ignore",
]

class RepositoryIgnorer(FileObjectIgnorer):
    """
    Loads the .gitignore files to skip indexing those files in
    a git repository
    """
    def __init__(self, repo_path: str):
        self._repo_path = repo_path
        self._checker = None
        ignore_file = f'{repo_path}/.gitignore'
        lines = IGNORE_FILES + IGNORE_DIRS
        if os.path.exists(ignore_file):
            with open(ignore_file) as f:
                lines += f.readlines()
        self._checker = pathspec.PathSpec.from_lines('gitignore', lines)

    def file_ignored(self, file_path: str) -> bool:
        if self._checker is None:
            return False
        return self._checker.match_file(file_path)
