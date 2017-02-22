"""
Some block-related classes.

These are here instead of in `block.py` in order to avoid circular-imoprting.
This module is imported from `_block_c.pyx`.
"""

from .misc import deserialize_varlen_integer
from .tx import TxInBlock, deserialize_tx

################################################################################
# BLOCK TXS
################################################################################

class BlockTxsIterator:
    """
    An iterator over the transactions contained in a block.
    
    It deserializes block's tx-blob on the fly.
    
    :note: This iterator is resumable.
    """
    
    def __init__(self, blob, num_txs, block, include_block_context = False, include_tx_blob = False):
        self.blob = blob
        self.block = block
        self.num_txs = num_txs
        self.include_block_context = include_block_context
        self.include_tx_blob = include_tx_blob
        # state
        self._offset = 0
        self._tx_idx = 0
        
    def __next__(self):
        tx_idx = self._tx_idx
        blob = self.blob[self._offset : ]
        if tx_idx >= self.num_txs:
            assert self._offset == len(self.blob), (self._offset, len(self.blob))
            raise StopIteration
        tx = self._make_tx(blob, tx_idx)
        self._tx_idx += 1
        self._offset += tx.rawsize
        return tx
        
    def _make_tx(self, blob, idx_in_block):
        tx = deserialize_tx(blob, include_blob = self.include_tx_blob)
        if self.include_block_context:
            tx = TxInBlock(tx, self.block, index = idx_in_block)
        return tx
    
    def __iter__(self):
        return self
    
    # pickle support
    
    def __getstate__(self):
        # self.blob is a memoryview. convert it, so it can be pickled
        state = dict(self.__dict__)
        state['blob'] = bytearray(state['blob'])
        return state
    
    def __setstate__(self, state):
        self.__dict__.update(state)


class BlockTxs:
    """
    Represents the set of transactions in a block.
    """
    
    BlockTxsIterator = BlockTxsIterator
    
    def __init__(self, block):
        self.block = block

    @property
    def blob(self):
        return self.block._txs_blob

    @property
    def num_txs(self):
        return self.block.num_txs

    def __len__(self):
        return self.num_txs

    def __iter__(self):
        return self.iter_txs()
    
    def iter_txs(self, include_block_context = False, **kwargs):
        txs_blob = self.blob
        num_txs, consumed = deserialize_varlen_integer(txs_blob)
        return self.BlockTxsIterator(  
            txs_blob[consumed:], num_txs, self.block,
            include_block_context = include_block_context,
            **kwargs)

    def iter_txs_in_block(self, **kwargs):
        """
        Same as `iter_txs`, but generates `TxInBlock` objects instead of `Tx` objects.
        """
        return self.iter_txs(include_block_context = True)

    def __repr__(self):
        return '<%s (%d txs)>' % (type(self).__name__, len(self))

################################################################################
