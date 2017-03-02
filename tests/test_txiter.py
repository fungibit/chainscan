"""
Unit-testing the various tx-iterators, including spending-tracking.
"""

import unittest

from chainscan.scan import TxIterator
from chainscan.track import TrackedSpendingTxIterator, UtxoSet

################################################################################

TOTAL_NUM_TXS = 50000

################################################################################

class TxIterTest(unittest.TestCase):

    def test_txiter(self):
        self._test_txiter()
        
    def test_txiter_block_context(self):
        self._test_txiter(include_block_context = True, check_blocks = True)
        
    def _test_txiter(self, check_blocks = False, **kwargs):
        last_block_height = 0
        # test txs are generated in order, by making sure each tx is only spending outputs which
        # are already seen
        txid_to_num_outputs = {}
        for i, tx in enumerate(TxIterator(**kwargs)):
            if not tx.is_coinbase:
                for input in tx.inputs:
                    self.assertIn(input.spent_txid, txid_to_num_outputs, 'spent_txid not yet seen for tx %s' % tx)
                    spent_tx_num_outputs = txid_to_num_outputs[input.spent_txid]
                    self.assertLessEqual(0, input.spent_output_idx)
                    self.assertLess(input.spent_output_idx, spent_tx_num_outputs)
                
            txid_to_num_outputs[tx.txid] = len(tx.outputs)

            if check_blocks:
                block_height = tx.block.height
                self.assertGreaterEqual(block_height, last_block_height)
                last_block_height = block_height

            if i >= TOTAL_NUM_TXS:
                break

        # make sure not all block heights are 0
        if check_blocks:
            self.assertGreaterEqual(last_block_height, 1000)

    def test_tracked(self):
        self._test_tracked()
        
    def test_tracked_scripts(self):
        self._test_tracked(utxoset = UtxoSet(include_scripts = True), check_scripts = True)
        
    def test_tracked_block_context(self):
        self._test_tracked(check_blocks = True, include_block_context = True)
        
    def _test_tracked(self, check_scripts = False, check_blocks = False, **kwargs):
        last_block_height = 0
        # test that each input has an output set on it
        for i, tx in enumerate(TrackedSpendingTxIterator(**kwargs)):
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
                    if check_scripts:
                        # output_script is just an alias to input.spent_output.script
                        self.assertIsNotNone(input.output_script)
                        self.assertIsNotNone(spent_output.script)
            
                if check_blocks:
                    for input in tx.inputs:
                        # can only spent outputs from past blocks
                        spent_block_height = input.spending_info.block_height
                        tx_block_height = tx.block.height
                        self.assertGreaterEqual(tx_block_height, spent_block_height)
                        self.assertGreaterEqual(tx_block_height, last_block_height)
                        last_block_height = max(tx_block_height, last_block_height)
            
            if i >= TOTAL_NUM_TXS:
                break

        # make sure not all block heights are 0
        if check_blocks:
            self.assertGreaterEqual(last_block_height, 1000)
        
    
################################################################################

if __name__ == '__main__':
    unittest.main()

################################################################################
