"""
Transaction-related classes and functions.

Many of the classes and functions importable from this module are defined
and implemented using Cython, for speed.  See `_tx_c.pyx`.
"""

# Make some names importable from this module:
from ._tx_c import Tx, TxOutput, TxInput, CoinbaseTxInput
from ._tx_c import deserialize_tx, deserialize_tx_input, deserialize_tx_output
# avoid pyflakes "imported but unused" warnings:
Tx, TxOutput, TxInput, CoinbaseTxInput, deserialize_tx, deserialize_tx_input, deserialize_tx_output


################################################################################

class TxInBlock:
    """
    Represents a tx along with its block-context: the block
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
