"""
Unit-testing longest-chain iterator logic, using artificial forks.
"""

import unittest
import numpy as np

from chainscan.scan import LongestChainBlockIterator
from chainscan.parse import bytes2uint32
from chainscan.misc import Bunch
from tests.test_blockiter import BlockIterTest, TOTAL_NUM_BLOCKS
from tests.artificial import gen_artificial_block_rawdata_with_forks

################################################################################

class ArtificialDataIterator:
    
    def __init__(self):
        blob = gen_artificial_block_rawdata_with_forks(TOTAL_NUM_BLOCKS)
        blob = np.frombuffer(memoryview(blob), dtype = 'uint8').copy()
        data = Bunch(blob = blob, filename = None)
        self._iter = iter([ data])
    
    def __next__(self):
        return next(self._iter)
    
    def __iter__(self):
        return self

################################################################################

class ForkTest(BlockIterTest):

    def _get_raw_data_iter(self):
        # Using artificial chain with forks
        return ArtificialDataIterator()

    def test_longestchain2(self):
        # The artificial blocks which belong to longest chain are generated with nonce=height
        for blk in LongestChainBlockIterator(raw_data_iter = self._get_raw_data_iter()):
            self.assertEqual(bytes2uint32(blk.nonce), blk.height)
    
################################################################################

if __name__ == '__main__':
    unittest.main()

################################################################################
