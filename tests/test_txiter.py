"""
Unit-testing the various tx-iterators, including spending-tracking.
"""

import unittest

from chainscan.scan import TxIterator
from chainscan.track import TrackedSpendingTxIterator

################################################################################

TOTAL_NUM_TXS = 50000

################################################################################

class TxIterTest(unittest.TestCase):

    def test_txiter(self):
        # test txs are generated in order, by making sure each tx is only spending outputs which
        # are already seen
        txid_to_num_outputs = {}
        for i, tx in enumerate(TxIterator()):
            if not tx.is_coinbase:
                for input in tx.inputs:
                    self.assertIn(input.spent_txid, txid_to_num_outputs, 'spent_txid not yet seen for tx %s' % tx)
                    spent_tx_num_outputs = txid_to_num_outputs[input.spent_txid]
                    self.assertLessEqual(0, input.spent_output_idx)
                    self.assertLess(input.spent_output_idx, spent_tx_num_outputs)
            txid_to_num_outputs[tx.txid] = len(tx.outputs)
            if i >= TOTAL_NUM_TXS:
                break
            
    def test_tracked_txiter(self):
        # test that each input has an output set on it
        for i, tx in enumerate(TrackedSpendingTxIterator()):
            if tx.is_coinbase:
                self.assertEqual(len(tx.inputs), 1)
                input = tx.inputs[0]
                self.assertTrue(input.is_coinbase)
                self.assertIsNone(input.spent_output)
            else:
                self.assertTrue(tx.inputs)
                for input in tx.inputs:
                    self.assertFalse(input.is_coinbase)
                    spent_output = input.spent_output
                    self.assertIsNotNone(spent_output)
            if i >= TOTAL_NUM_TXS:
                break
        
    
################################################################################

if __name__ == '__main__':
    unittest.main()

################################################################################
