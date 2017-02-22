"""
The BlockChain data structure and tools for populating it.
"""

from collections import OrderedDict

from .misc import bytes_to_hash_hex
from .scan import LongestChainBlockIterator


################################################################################
# The BlockChain data structure


class BlockInfo:
    """
    Block metadata.
    """
    
    __slots__ = [ 'block_hash', 'height', 'timestamp', 'num_txs', 'rawsize' ]
    
    def __init__(self, block_hash, height, timestamp, num_txs, rawsize):
        self.block_hash = block_hash
        self.height = height
        self.timestamp = timestamp
        self.num_txs = num_txs
        self.rawsize = rawsize
        
    @classmethod
    def from_block(cls, block):
        """
        Create a BlockInfo from a Block.
        """
        kw = {
            attr: getattr(block, attr)
            for attr in cls.__slots__
        }
        return cls(**kw)
        
    @property
    def block_hash_hex(self):
        return bytes_to_hash_hex(self.block_hash)

    def __repr__(self):
        return '<%s #%d %s>' % ( type(self).__name__, self.height, self.block_hash_hex )
    
class BlockChain:
    """
    Represents the blockchain -- basically a list of BlockInfos, which supports
    efficient lookup by block hash and height.
    
    This data structure includes the longest chain only, no forks.
    """
    
    def __init__(self, blocks = None):
        
        # An OrderedDict from block_hash to BlockInfo.
        # The height is reflected in the ordering of the items.
        self._blocks = OrderedDict()
        
        # Used for lookup by height (OrderedDict does not support random-access)
        self._height_to_hash = dict()

        if blocks:
            self.extend(blocks)

    # Add, remove, etc.
    
    def append(self, block):
        """
        :param block: a BlockInfo
        """
        next_height = block.height
        next_hash = block.block_hash
        last_height = self.height
        # verify height
        if next_height != last_height + 1:
            raise ValueError('Expected block with height %s, got %s' % (last_height + 1, next_height))
        # verify hash
        if next_hash in self._blocks:
            raise ValueError('Block hash already in BlockChain: %s' % block.block_hash_hex)
        # add to data structure
        self._blocks[next_hash] = block
        self._height_to_hash[next_height] = block.block_hash

    def extend(self, blocks):
        """
        :param blocks: a sequence of BlockInfos
        """
        for block in blocks:
            self.append(block)

    def clear(self):
        self._blocks.clear()
        self._height_to_hash.clear()
        
    def pop(self):
        """
        Remove the most recent block from the chain.
        """
        block = self._blocks.pop()
        del self._height_to_hash[block.height]
        return block

    # Iterating and other list operations
    
    def __len__(self):
        return len(self._blocks)

    def __iter__(self):
        return iter(self._blocks.values())

    def __reversed__(self):
        return reversed(self._blocks.values())
    
    def __contains__(self, block):
        self.contains_block(block)
    
    def contains_block(self, block):
        return self.contains_hash(block.block_hash)
    
    def contains_hash(self, block_hash):
        return block_hash in self._blocks
    
    def __getitem__(self, i):
        if isinstance(i, bytes):
            return self.get_by_hash(i)
        elif isinstance(i, int):
            return self.get_by_height(i)
        else:
            raise TypeError(i)
    
    # Other

    @property
    def genesis(self):
        return self.get_by_height(0)

    @property
    def height(self):
        # if empty, the next block is genesis with height 0, so -1 is reasonable
        return len(self) - 1
    
    @property
    def last_block(self):
        height = self.height
        if height >= 0:
            return self.get_by_height(height)
        else:
            return None

    def get_by_height(self, height):
        return self.get_by_hash(self._height_to_hash[height])
    
    def get_by_hash(self, block_hash):
        return self._blocks[block_hash]

    def __repr__(self):
        return '<%s %d blocks, last from %s>' % ( type(self).__name__, len(self), self.last_block.timestamp )


################################################################################
# Iterators

class BlockChainIterator:
    """
    Same as LongestChainBlockIterator, but also builds the BlockChain as it goes.

    E.g., if the current height is N, print the block with height=N/2::
    
        bciter = BlockChainIterator()
        for block in bciter: pass
        bc = bciter.blockchain
        print(bc[bc.height // 2])

    :note: This iterator is resumable.
    """

    BlockInfo = BlockInfo
    BlockIterator = LongestChainBlockIterator
    

    def __init__(self, blockchain = None, block_iter = None, **kwargs):
        """
        :param blockchain: a BlockChain
        :param block_iter: a LongestChainBlockIterator
        :param kwargs: extra kwargs for LongestChainBlockIterator (ignored unless block_iter is None)
        """
        if block_iter is None:
            block_iter = self.BlockIterator(**kwargs)
        self.block_iter = block_iter
        if blockchain is None:
            blockchain = BlockChain()
        self.blockchain = blockchain

    def __next__(self):
        block = next(self.block_iter)
        block_info = BlockInfo.from_block(block)
        self.blockchain.append(block_info)
        return block
        
    def __iter__(self):
        return self

################################################################################
