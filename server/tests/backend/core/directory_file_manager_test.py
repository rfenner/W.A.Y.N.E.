import gc
import os
import shutil
from pathlib import Path
from time import sleep, time

import pytest
from watchdog.observers import Observer

from core.directory_file_manager import DirectoryFileManager, FileObjectIgnorer

import debug.debugger

class IgnoreFileTester(FileObjectIgnorer):
    def file_ignored(self, file_path: str) -> bool:
        if 'ignore_me' in file_path:
            return True
        return False


class TestDirectoryFileManager:
    @pytest.fixture(scope='function',autouse=True)
    def setup_teardown(self):
        self.manager = None
        self.base_path = '/test_dir'
        os.makedirs(f'{self.base_path}/one/two')
        self.one_path = f'{self.base_path}/one'
        self.two_path = f'{self.one_path}/two'

        self.test_file1 = Path(f'{self.base_path}/test1.txt')
        self.test_file1.touch()
        self.test_file2 = Path(f'{self.one_path}/test2.txt')
        self.test_file2.touch()
        self.test_file3 = Path(f'{self.two_path}/test3.txt')
        self.test_file3.touch()
        self.test_ignore = Path(f'{self.two_path}/ignore_me.txt')
        self.test_ignore.touch()

        self.ignorer = IgnoreFileTester()
        self.was_notified = False
        yield
        shutil.rmtree(f'{self.base_path}')

    def callback_test(self):
        self.was_notified = True

    def wait_for_file_event(self):
        start = time()
        while not self.was_notified:
            sleep(.5)
            if time() - start > 3:
                assert False
        # allow updates to propagate as file list for main thread
        # was not updating once notified was set.
        sleep(.5)
    # by default pytest runs tests in the order as defined in the class
    def test_init(self):
        self.manager = DirectoryFileManager(self.base_path, ignorers=[self.ignorer], change_callback=self.callback_test)
        assert self.manager._base_directory == self.base_path
        assert self.manager._ignorers == [self.ignorer]
        assert self.manager._file_list == {}
        assert self.manager._notifier == self.callback_test
        assert isinstance(self.manager._watchdog, Observer)

        #properties
        assert self.manager.base_directory == self.base_path
        assert self.manager.file_list == {}

    def test_scan_directory(self):
        self.manager = DirectoryFileManager(self.base_path, ignorers=[self.ignorer], change_callback=self.callback_test)
        self.manager.scan_directory()

        assert self.was_notified is True
        assert len(self.manager.file_list) == 3
        assert str(self.test_file1) in self.manager.file_list
        assert str(self.test_file2) in self.manager.file_list
        assert str(self.test_file3) in self.manager.file_list
        assert str(self.test_ignore) not in self.manager.file_list
        assert self.manager._watchdog.is_alive()

    def test_scan_directory_no_ignores(self):
        self.manager = DirectoryFileManager(self.base_path, change_callback=self.callback_test)
        self.manager.scan_directory()

        assert len(self.manager.file_list) == 4
        assert str(self.test_ignore) in self.manager.file_list

    def test_file_monitoring(self):
        self.manager = DirectoryFileManager(self.base_path, ignorers=[self.ignorer], change_callback=self.callback_test)
        self.manager.scan_directory()

        # test created
        test_file = Path(f'{self.base_path}/test_create.txt')
        test_file.touch()
        self.wait_for_file_event()

        assert self.was_notified is True
        assert len(self.manager.file_list) == 4
        assert str(test_file) in self.manager.file_list

        modified_time = self.manager.file_list[str(test_file.absolute())]

        # test file updated
        self.manager.was_notified = False
        # sleep fro a second to allow modified to change
        sleep(1)
        test_file.touch()
        self.wait_for_file_event()

        assert self.was_notified is True
        assert modified_time != self.manager.file_list[str(test_file)]

        # test file renamed
        self.was_notified = False
        new_name = Path(f'{self.base_path}/test_renamed.txt')
        os.rename(test_file, new_name)
        self.wait_for_file_event()

        assert self.was_notified is True
        assert len(self.manager.file_list) == 4
        assert str(new_name) in self.manager.file_list
        assert str(test_file) not in self.manager.file_list

        test_file = new_name

        # test file removed
        self.was_notified = False
        os.unlink(test_file)
        self.wait_for_file_event()

        assert self.was_notified is True
        assert len(self.manager.file_list) == 3
        assert str(test_file) not in self.manager.file_list

        # test directory renamed
        self.was_notified = False
        test_new_dir = f'{self.base_path}/three'
        new_test_file_3 = f'{test_new_dir}/test3.txt'
        os.rename(self.two_path, test_new_dir)
        self.wait_for_file_event()

        assert self.was_notified is True
        assert self.test_file3 not in self.manager.file_list
        assert new_test_file_3 in self.manager.file_list

        # test directory removed
        self.was_notified = False
        shutil.rmtree(f'{test_new_dir}')
        self.wait_for_file_event()

        assert self.was_notified is True
        assert new_test_file_3 not in self.manager.file_list

        # test files escaped the base directory
        self.was_notified = False
        new_one_dir = '/escaped'
        os.rename(self.one_path, new_one_dir)
        self.wait_for_file_event()

        assert self.was_notified is True
        assert len(self.manager.file_list) == 1
        assert self.test_file2 not in self.manager.file_list

    def test_finalizer(self):
        manager = DirectoryFileManager(self.base_path, ignorers=[self.ignorer], change_callback=self.callback_test)
        manager.scan_directory()

        watchdog = manager._watchdog
        ref = gc.get_referrers(manager)
        del manager
        gc.collect()
        assert watchdog.is_alive() is False




