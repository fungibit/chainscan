"""
Tools for reading raw serialized blockchain data from blk*.dat files on disk.
"""

import os
import sys
import glob
import click
#import mmap
import numpy as np

from .defs import DEFAULT_DATA_DIR, RAW_FILES_GLOB_PATTERN
from .misc import Bunch

from .loggers import get_logger
logger = get_logger('io', 'info')
   
################################################################################

class RawFilesIterator:
    """
    An iterator over blk*.dat files found in bitcoin's "blocks" directory.
    
    This iterator generates filesystem paths to the files.
    
    :note: This iterator is resumable and refreshable.
    """

    DEFAULT_DATA_DIR = DEFAULT_DATA_DIR
    RAW_FILES_GLOB_PATTERN = RAW_FILES_GLOB_PATTERN
    

    def __init__(self, data_dir = None, raw_files_glob_pattern = None, refresh = True, show_progressbar = False):
        if data_dir is None:
            data_dir = self.DEFAULT_DATA_DIR
        self.data_dir = data_dir
        if raw_files_glob_pattern is None:
            raw_files_glob_pattern = self.RAW_FILES_GLOB_PATTERN
        self.raw_files_glob_pattern = raw_files_glob_pattern
        self.refresh = refresh
        self.show_progressbar = show_progressbar

        self._prev_file = None
        self._init()

    def _init(self):

        # files and state
        self._files = self._find_files()
        self._iter = iter(self._files)

        # progress bar
        if self.show_progressbar and self._files:
            self.progressbar = _make_progressbar(self._files)
            self.progressbar_ctx = self.progressbar.__enter__()
            self._iter = self.progressbar
        else:
            self.progressbar = None
            self.progressbar_ctx = None
    
    def _find_files(self):
        glob_pattern = os.path.expanduser(os.path.join(self.data_dir, self.RAW_FILES_GLOB_PATTERN))
        files = sorted(glob.glob(glob_pattern))
        if self._prev_file is not None:
            # only files not already used
            files = [ f for f in files if f > self._prev_file ]
            if files:
                logger.debug('found %d new raw files' % len(files))
        return files

    def _raw_next(self):
        self._prev_file = next(self._iter)
        return self._prev_file

    def __next__(self):
        try:
            return self._raw_next()
        except StopIteration:
            # done iterating over self._files.

            if self.progressbar_ctx is not None:
                self.progressbar_ctx.__exit__(None, None, None)
            
            # refresh: check if new files appeared since we started
            if self.refresh:
                self._init()
                if self._files:
                    return self._raw_next()
            
            raise
        
        except:
            # some other error occurred
            if self.progressbar_ctx is not None:
                self.progressbar_ctx.__exit__(*sys.exc_info())
            raise

    def __iter__(self):
        return self

class RawDataIterator:
    """
    An iterator over `blk*.dat` files, generating their raw binary data.

    Element type is an object with attributes blob (of type `bytes`) and filename.
    
    :note: This iterator is resumable and refreshable.
    """
    
    def __init__(self, raw_files_iter = None, use_mmap = True, **kwargs):
        """
        :param raw_files_iter: a `RawFilesIterator`
        :note: `use_mmap` is currently ignored. We currently don't use mmap
            due to a cython bug, until it is fixed or we find a way to bypass it.
        """
        if raw_files_iter is None:
            raw_files_iter = RawFilesIterator(**kwargs)
        self.raw_files_iter = raw_files_iter
        self.use_mmap = use_mmap

    def __next__(self):
        raw_file = next(self.raw_files_iter)
        return self.get_data(raw_file)

    def get_data(self, raw_file):
        blob = self._get_blob(raw_file)
        return Bunch(
            blob = blob,
            filename = raw_file,
        )

    def _get_blob(self, raw_file):
        logger.debug('reading: %s', raw_file)

        # Due to a cython bug, we must return a writable buffer (despite the fact
        # we're not going to write to it).
        # The easiest way to do that is using numpy.  It is somewhat slower than
        # using mmap.

        #if self.use_mmap:
        #    F = open(raw_file, 'rb')  # close it somewhere?
        #    blob = mmap.mmap(F.fileno(), 0, prot = mmap.PROT_READ)
        #else:
        #    with open(raw_file, 'rb') as F:
        #        blob = F.read()
        #return memoryview(blob)
        
        buf = np.fromfile(raw_file, dtype = np.uint8)
        return buf
    
    def __iter__(self):
        return self

    @property
    def refresh(self):
        return self.raw_files_iter.refresh

################################################################################

def _make_progressbar(iterable, **kwargs):
    return click.progressbar(iterable, show_percent = True, show_eta = True, width = 0, **kwargs)
    
################################################################################
