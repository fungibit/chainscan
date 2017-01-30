"""
Basic bitcoin entities (block, transaction, input, output).

:note: The units of all BTC values are satoshis (type int). You can use `satoshi2float`
    or `satoshi2decimal` to convert to conventional "human" units.
"""

from .misc import bytes_to_hash_hex
from .parse import (
    bytes2uint32, parse_varlen_integer, datetime_from_timestamp, block_hash_from_blob,
    parse_block, parse_block_txs, parse_tx
    )

# The following entities are defined using cython for efficiency.
# We use them here, and also make them importable from here.
from .cyt import TxOutput, TxInput, CoinbaseTxInput


################################################################################
# Tx

class Tx:
    """
    A bitcoin transaction.
    """
    
    __slots__ = [ 'version', 'inputs', 'outputs', 'locktime', 'txid', 'rawsize', 'blob' ]
    
    TxOutput = TxOutput
    TxInput = TxInput
    CoinbaseTxInput = CoinbaseTxInput
    
    
    def __init__(self, version, inputs, outputs, locktime, txid, rawsize, blob = None):
        """
        :param inputs, outputs: a list of `TxInput`s / `TxOutput`s.
        :param rawsize: size of the serialized tx in bytes.
        """
        self.version = version
        self.inputs = inputs
        self.outputs = outputs
        self.locktime = locktime
        self.txid = txid
        self.rawsize = rawsize
        self.blob = blob

    @classmethod
    def from_blob(cls, blob, **kwargs):
        """
        Create a `Tx` from serialized raw data.
        """
        return parse_tx(cls, blob, **kwargs)

    #===================================================================================================================
    # Additional tx attributes
    #===================================================================================================================

    @property
    def is_coinbase(self):
        return self.inputs[0].is_coinbase

    def get_total_output_value(self):
        return sum( o.value for o in self.outputs )

    #===================================================================================================================
    # The following are only usable if spent_output is set on tx.inputs
    #===================================================================================================================

    def get_total_input_value(self):
        return sum( i.value for i in self.inputs )
    
    def get_fee_paid(self):
        return self.get_total_input_value() - self.get_total_output_value()

    #===================================================================================================================
    # Other
    #===================================================================================================================

    @property
    def txid_hex(self):
        return bytes_to_hash_hex(self.txid)

    def __repr__(self):
        return '<Tx %s%s>' % ( self.txid_hex, ' {COINBASE}' if self.is_coinbase else '' )
    
    
class TxInBlock:
    """
    Represents a tx along with its block-context, i.e. the block
    it appears in, and the index of the tx in the block.
    
    The `tx` attribute is the actual `Tx` object.
    
    :note: This class is designed to be `Tx`-like.  It can generally be used
        anywhere a `Tx` is needed.
    :note: This class keeps a reference to a `Block` object, so can potentially
        prevent it from being deallocated, which can cause memory consumption
        to blow up.
    """
    
    __slots__ = [ 'tx', 'block', 'index' ]
    
    
    def __init__(self, tx, block, index):
        """
        :param tx: a `Tx`.
        :param block: a `Block`.
        :param index: the index of the tx in the block.
        """
        self.tx = tx
        self.block = block
        self.index = index

    def __repr__(self):
        x = repr(self.tx)
        inblock = ' (tx #%d in block #%d)' % (self.index, self.block.height)
        return x[:-1] + inblock + x[-1:]
    
    # make this class Tx-like, by forwarding attribute access to self.tx
    
    def __getattr__(self, attr, *args):
        return getattr(self.tx, attr, *args)
    
    def __dir__(self):
        return super().__dir__() + dir(self.tx)


################################################################################
# Block Txs

class BlockTxsIterator:
    """
    An iterator over the transactions contained in a block.
    
    It parses block's tx-blob on the fly.
    
    :note: This iterator is resumable.
    """
    
    Tx = Tx
    
    
    def __init__(self, blob, num_txs, include_tx_blob = False):
        self._blob = blob
        self._num_txs = num_txs
        self.include_tx_blob = include_tx_blob
        # state
        self._offset = 0
        self._tx_idx = 0
        
    def __next__(self):
        tx_idx = self._tx_idx
        blob = self._blob[self._offset : ]
        if tx_idx >= self._num_txs:
            assert self._offset == len(self._blob), (self._offset, len(self._blob))
            raise StopIteration
        tx = self._make_tx(blob, tx_idx)
        self._tx_idx += 1
        self._offset += tx.rawsize
        return tx
        
    def _make_tx(self, blob, idx_in_block):
        return self.Tx.from_blob(blob, include_blob = self.include_tx_blob)
    
    def __iter__(self):
        return self
    
class BlockTxsInBlockIterator(BlockTxsIterator):
    """
    A `BlockTxsIterator` which generates txs along with their block-context,
    i.e. `TxInBlock` objects instead of `Tx` objects.
    """
    
    TxInBlock = TxInBlock
    
    def __init__(self, blob, num_txs, block, **kwargs):
        super().__init__(blob, num_txs, **kwargs)
        self._block = block
        
    def _make_tx(self, blob, idx_in_block):
        tx = super()._make_tx(blob, idx_in_block)
        return self.TxInBlock(tx, self._block, index = idx_in_block)

class BlockTxs:
    """
    Represents the set of transactions in a block.
    """
    
    BlockTxsIterator = BlockTxsIterator
    BlockTxsInBlockIterator = BlockTxsInBlockIterator
    
    def __init__(self, blob, num_txs, block = None):
        self._blob = blob
        self.num_txs = num_txs
        self.block = block

    def __len__(self):
        return self.num_txs

    def __iter__(self):
        return self.iter_txs()
    
    def iter_txs(self, **kwargs):
        return self.BlockTxsIterator(self._blob, self.num_txs, **kwargs)

    def iter_txs_in_block(self, **kwargs):
        """
        Same as `iter_txs`, but generates `TxInBlock` objects instead of `Tx` objects.
        """
        return self.BlockTxsInBlockIterator(self._blob, self.num_txs, self.block, **kwargs)

    def __repr__(self):
        return '<%s (%d txs)>' % (type(self).__name__, len(self))

################################################################################
# Block

class Block:
    """
    A bitcoin block.
    """
    
    __slots__ = [ 'blob', 'height', 'block_hash' ]
    
    BlockTxs = BlockTxs
    
    
    def __init__(self, blob, height):
        self.blob = blob
        self.height = height
        self.block_hash = block_hash_from_blob(self.header)

    @classmethod
    def from_blob(cls, blob, height = -1, **kwargs):
        """
        Create a `Block` from serialized raw data.
        """
        return parse_block(cls, blob, height, **kwargs)

    #===================================================================================================================
    # Block properties
    #===================================================================================================================

    @property
    def rawsize(self):
        """
        Size of the serialized block in bytes.
        """
        return len(self.blob)

    @property
    def block_hash_hex(self):
        return bytes_to_hash_hex(self.block_hash)

    @property
    def version_bytes(self):
        return self.blob[0 : 0+4]

    @property
    def version(self):
        return bytes2uint32(self.version_bytes)

    @property
    def prev_block_hash(self):
        return self.blob[4 : 4+32].tobytes()
        
    @property
    def prev_block_hash_hex(self):
        return bytes_to_hash_hex(self.prev_block_hash)
        
    @property
    def merkle_root(self):
        return self.blob[36 : 36+32]

    @property
    def timestamp_epoch(self):
        return bytes2uint32(self.blob[68 : 68+4])
    
    @property
    def timestamp(self):
        return datetime_from_timestamp(self.timestamp_epoch)
    
    @property
    def difficulty(self):
        return self.blob[72 : 72+4]
    
    @property
    def nonce(self):
        return self.blob[76 : 76+4]

    @property
    def header(self):
        return self.blob[0 : 0+80]

    #===================================================================================================================
    # Tx related
    #===================================================================================================================

    @property
    def _txs_blob(self):
        return self.blob[80 : ]

    @property
    def num_txs(self):
        return parse_varlen_integer(self._txs_blob)[0]

    @property
    def txs(self):
        return parse_block_txs(self.BlockTxs, self._txs_blob, block = self)
        
    #===================================================================================================================
    # Misc
    #===================================================================================================================
    
    def __repr__(self):
        return '<%s #%d %s>' % ( type(self).__name__, self.height, self.block_hash_hex )

class StoredBlock:
    """
    Represents a block along with info about where it stored.
    
    The `block` attribute is the actual `Block` object.
    
    :note: This class is designed to be `Block`-like.  It can generally be used
        anywhere a `Block` is needed.
    """
    
    def __init__(self, block, filepos):
        """
        :param block: a Block
        :param filepos: a FilePos
        """
        self.block = block
        self.filepos = filepos

    def __repr__(self):
        x = repr(self.block)
        stored = ' (%s)' % (self.filepos,)
        return x[:-1] + stored + x[-1:]
    
    # make this class Block-like, by forwarding attribute access to self.block
    
    def __getattr__(self, attr, *args):
        return getattr(self.block, attr, *args)
    
    def __dir__(self):
        return super().__dir__() + dir(self.block)
    

################################################################################
