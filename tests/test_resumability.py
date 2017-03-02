"""
Unit-testing resumability of block- and tx-iterators.
"""

import unittest
import pickle

from chainscan.scan import RawFileBlockIterator, TopologicalBlockIterator, LongestChainBlockIterator, TxIterator
from chainscan.track import TrackedSpendingTxIterator

################################################################################

TOTAL_NUM_BLOCKS = 1000
RESUME_EVERY_BLOCKS = 100

TOTAL_NUM_TXS = 50000
RESUME_EVERY_TXS = 500

################################################################################

class ResumabilityTest(unittest.TestCase):

    def test_resumability_rawblock(self):
        self._test_resumability_blk(RawFileBlockIterator, lambda elem: elem.block)
        
    def test_resumability_block(self):
        self._test_resumability_blk(TopologicalBlockIterator)
        
    def test_resumability_longestchain(self):
        self._test_resumability_blk(LongestChainBlockIterator)
    
    def test_resumability_tx(self):
        self._test_resumability_tx(TxIterator)
    
    # TBD: UtxoSet currently does not support pickle, so not resumable.
    #def test_resumability_tx_tracked(self):
    #    self._test_resumability_tx(TrackedSpendingTxIterator)
    
    def _test_resumability_blk(self, make_iter, elem_to_block = lambda x: x):
        N = TOTAL_NUM_BLOCKS
        blkiter0 = make_iter()
        all_blks = [ elem_to_block(b) for b in self._consume(blkiter0, N) ]
        del blkiter0
        
        blkiter1 = make_iter()
        for i in range(N):
            blk = next(blkiter1)
            blk = elem_to_block(blk)
            self.assertBlockEqual(blk, all_blks[i])
            # abort and resume:
            if i % RESUME_EVERY_BLOCKS == 0:
                blkiter1 = pickle.loads(pickle.dumps(blkiter1))

    def _test_resumability_tx(self, make_iter):
        N = TOTAL_NUM_TXS
        txiter0 = make_iter()
        all_txs = self._consume(txiter0, N)
        del txiter0
        
        txiter1 = make_iter()
        for i in range(N):
            tx = next(txiter1)
            self.assertTxEqual(tx, all_txs[i])
            # abort and resume:
            if i % RESUME_EVERY_TXS == 0:
                txiter1 = pickle.loads(pickle.dumps(txiter1))
    
    def assertBlockEqual(self, b1, b2):
        self.assertEqual(b1.height, b2.height)
        self.assertEqual(b1.block_hash, b2.block_hash)
    
    def assertTxEqual(self, tx1, tx2):
        self.assertEqual(tx1.txid, tx2.txid)
    
    def _consume(self, iter, n):
        res = []
        while len(res) < n:
            res.append(next(iter))
        return res

################################################################################

if __name__ == '__main__':
    unittest.main()

################################################################################
