"""
Unit-testing the various block-iterators.
"""

import unittest

from chainscan.defs import GENESIS_PREV_BLOCK_HASH
from chainscan.scan import RawFileBlockIterator, TopologicalBlockIterator, LongestChainBlockIterator

################################################################################

TOTAL_NUM_BLOCKS = 1000

################################################################################

class BlockIterTest(unittest.TestCase):

    def _get_raw_data_iter(self):
        # Using the default, i.e. RawDataIterator, i.e. reading from real blk.dat files
        return None

    def test_rawblock(self):
        # test there are no errors when iterating. nothing else.
        blkiter = RawFileBlockIterator(raw_data_iter = self._get_raw_data_iter())
        self._consume(blkiter, TOTAL_NUM_BLOCKS)
    
    def test_block(self):
        # test a block only appears after its "prev", and that the height is set correctly
        height_by_hash = { GENESIS_PREV_BLOCK_HASH: -1 }
        for blk in TopologicalBlockIterator(raw_data_iter = self._get_raw_data_iter()):
            height = blk.height
            self.assertIn(blk.prev_block_hash, height_by_hash, 'prev block not yet seen for block %s' % blk)
            prev_blk_height = height_by_hash[blk.prev_block_hash]
            self.assertEqual(height, prev_blk_height + 1)
            height_by_hash[blk.block_hash] = height
            if height >= TOTAL_NUM_BLOCKS:
                break
            
    def test_longestchain(self):
        # test blocks appear by order of height, and that prev_block_hash agrees
        prev_blk_hash = GENESIS_PREV_BLOCK_HASH
        prev_blk_height = -1
        for blk in LongestChainBlockIterator(raw_data_iter = self._get_raw_data_iter()):
            height = blk.height
            self.assertEqual(height, prev_blk_height + 1)
            self.assertEqual(blk.prev_block_hash, prev_blk_hash)
            prev_blk_hash = blk.block_hash
            prev_blk_height = height
            if height >= TOTAL_NUM_BLOCKS:
                break
        
    def _consume(self, iter, n):
        res = []
        while len(res) < n:
            res.append(next(iter))
        return res

################################################################################

if __name__ == '__main__':
    unittest.main()

################################################################################
