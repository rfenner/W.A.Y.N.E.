import os

import pathspec

from core.directory_file_manager import FileObjectIgnorer


class WayneIgnorer(FileObjectIgnorer):
    """
    Handles ignore files that wayne should not index using
    gitignore style patterns
    """
    def __init__(self, repo_path:str):
        self._repo_path = repo_path
        self._checker = None
        ignore_file = f'{repo_path}/.wayne_ignore'
        lines = []
        if os.path.exists(ignore_file):
            with open(ignore_file, 'r') as f:
                lines += f.readlines()
            self._checker = pathspec.PathSpec.from_lines('gitignore', lines)

    def file_ignored(self, file_path: str) -> bool:
        if self._checker is None:
            return False
        return self._checker.match_file(file_path)