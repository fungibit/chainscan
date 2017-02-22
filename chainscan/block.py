"""
Block-related classes and functions.

Many of the classes and functions importable from this module are defined
and implemented using Cython, for speed.  See `_block_c.pyx`.
"""

# Make some names importable from this module:
from ._block_c import Block, deserialize_block
from ._block import BlockTxs, BlockTxsIterator
# avoid pyflakes "imported but unused" warnings:
Block, deserialize_block, BlockTxs, BlockTxsIterator


################################################################################

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
