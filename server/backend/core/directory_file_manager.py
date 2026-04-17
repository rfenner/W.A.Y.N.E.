import os
import weakref
from abc import ABC, abstractmethod
from typing import Callable

from watchdog.events import FileSystemEventHandler, DirModifiedEvent, FileModifiedEvent
from watchdog.observers import Observer


class FileObjectIgnorer(ABC):
    """
    Interface to check if a file is ignored or not
    Abstract so we can create different rule sets for ignoring files
    so the DirectoryFileManager doesn't have to have that logic.
    """
    @abstractmethod
    def file_ignored(self, file_path: str) -> bool:
        pass

class WayneFileSystemEventHandler(FileSystemEventHandler):
    """
    Handles file system updates so we keep can track file changes in realtime
    """
    def __init__(self, dir_man:weakref.ref['DirectoryFileManager']) -> None:
        self._dir_man = dir_man

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        dir_man = self._dir_man()
        if dir_man is None:
            return

        if event.is_directory:
            return

        dir_man.file_update(event.src_path, int(os.path.getmtime(event.src_path)))

    def on_moved(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        dir_man = self._dir_man()
        if dir_man is None:
            return

        if event.is_directory:
            dir_man.directory_moved(event.src_path, event.dest_path)
            return

        dir_man.file_update(event.src_path, removed=True)
        dir_man.file_update(event.dest_path, int(os.path.getmtime(event.dest_path)))

    def on_created(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        dir_man = self._dir_man()
        if dir_man is None:
            return

        if event.is_directory:
            return

        dir_man.file_update(event.src_path, int(os.path.getmtime(event.src_path)))

    def on_deleted(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        dir_man = self._dir_man()
        if dir_man is None:
            return

        if event.is_directory:
            dir_man.directory_removed(event.src_path)
            return

        dir_man.file_update(event.src_path, removed=True)


class DirectoryFileManager:
    """
    Manages the files in a directory, and it's subdirectories tracking the files
    modified time so indexing can we can reindex only those files that changed
    Uses watchdog to watch for file system changes to keep the list updated.

    """
    def __init__(self, base_directory: str, ignorers:list[FileObjectIgnorer]|None=None, change_callback:Callable[[],None]|None=None) -> None:
        self._base_directory = base_directory
        self._ignorers = ignorers if ignorers is not None else []
        self._file_list  = {}
        self._notifier = change_callback

        if change_callback is not None:
            self._watchdog = Observer()
            local_watchdog = self._watchdog
            weakref.finalize(self, DirectoryFileManager.cleanup_observers, local_watchdog)
            self._watchdog.schedule(WayneFileSystemEventHandler(weakref.ref(self)), self._base_directory, recursive=True)

    @staticmethod
    def cleanup_observers(watchdog):
        if watchdog.is_alive():
            watchdog.stop()
            watchdog.join()

    @property
    def base_directory(self) -> str:
        return self._base_directory

    @property
    def file_list(self) -> dict[str, int]:
        return self._file_list

    def _file_ignored(self, file_path: str) -> bool:
        for ignorer in self._ignorers:
            if ignorer.file_ignored(file_path):
                return True
        return False

    def _scan_dir(self, dir_path, file_last_mod:dict[str, int]|None=None)->dict[str, int]:
        files = {}
        with os.scandir(dir_path) as it:
            for entry in it:
                if self._file_ignored(entry.path):
                    continue
                if entry.is_dir():
                    files.update(self._scan_dir(entry.path, file_last_mod))
                if entry.is_file():
                    if file_last_mod is None:
                        files[entry.path] = int(entry.stat().st_mtime)
                    else:
                        mtime = int(entry.stat().st_mtime)
                        if entry.path in file_last_mod and file_last_mod[entry.path] == mtime:
                            continue
                        files[entry.path] = mtime


        return files

    def scan_directory(self):
        self._file_list = self._scan_dir(self._base_directory)
        if self._notifier is not None:
            self._notifier()

        if self._notifier and not self._watchdog.is_alive():
            self._watchdog.start()

    def file_update(self, file:str,mtime:int|None=None,removed:bool=False)->None:
        """
        Updates our file list for a file
        """
        changed = False

        if removed:
            if file in self._file_list:
                changed = True
                del self._file_list[file]
        else:
            self._file_list[file] = mtime
            changed = True

        if changed and self._notifier is not None:
            self._notifier()

    def directory_removed(self, dir_path:str)->None:
        """
        Removes all files that start with dir_path
        """
        changed = False
        for file in list(self._file_list.keys()):
            if file.startswith(dir_path):
                changed = True
                del self._file_list[file]

        if changed and self._notifier is not None:
            self._notifier()

    def directory_moved(self, src_path:str, dest_path)->None:
        """
        Moves all files that start with dir_path
        """
        changed = False
        for file in list(self._file_list.keys()):
            if file == src_path:
                # if the moved file escaped the base_directory remove it instead
                if not dest_path.startswith(self.base_directory):
                    del self._file_list[file]
                    continue
                changed = True
                new_file = file.replace(src_path, dest_path, 1)
                self._file_list[new_file] = self._file_list[file]
                del self._file_list[file]

        if changed and self._notifier is not None:
            self._notifier()
