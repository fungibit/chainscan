"""
The basic iterator-classes for iterating over the blocks and transactions of
the blockchain.
"""

from collections import deque
from sortedcontainers import SortedList

from .defs import GENESIS_PREV_BLOCK_HASH, HEIGHT_SAFETY_MARGIN
from .misc import hash_hex_to_bytes, FilePos, Bunch
from .rawfiles import RawDataIterator
from .block import StoredBlock, deserialize_block

from .loggers import logger


################################################################################
# filtering

class BlockFilter:
    """
    Represents start/stop criteria for blocks to include, based on height,
    timestamp, and specific block identified by its hash.
    "Start" is inclusive, "stop" is exclusive.
    
    :note: Block timestamp is approximate. Blocks are not strictly ordered by timestamp.
    """
    
    def __init__(self,
            start_block_height = None, stop_block_height = None,
            start_block_time = None, stop_block_time = None,
            start_block_hash = None, stop_block_hash = None,
            ):
        if start_block_height is not None or stop_block_height is not None:
            self.block_height = ( start_block_height, stop_block_height )
        else:
            self.block_height = None
        if start_block_time is not None or stop_block_time is not None:
            self.block_time = ( start_block_time, stop_block_time )
        else:
            self.block_time = None
        if start_block_hash is not None or stop_block_hash is not None:
            # str to bytes
            start_block_hash = hash_hex_to_bytes(start_block_hash) if isinstance(start_block_hash, str) else start_block_hash
            stop_block_hash = hash_hex_to_bytes(stop_block_hash) if isinstance(stop_block_hash, str) else stop_block_hash
            self.block_hash = ( start_block_hash, stop_block_hash )
        else:
            self.block_hash = None

    def check_block(self, block, is_started):
        """
        :return: True if need to include, False if need to exclude (i.e. before "start")
        :raise: StopIteration if need to break (i.e. after "stop")
        """
        if self.block_height is not None:
            if not self._check(block.height, self.block_height, is_started):
                return False
        if self.block_time is not None:
            if not self._check(block.timestamp, self.block_time, is_started):
                return False
        if self.block_hash is not None:
            if not self._check(block.block_hash, self.block_hash, is_started, is_ordered = False):
                return False
        return True
    
    def _check(self, value, boundaries, is_started, is_ordered = True):
        # True, False, or raise StopIteration
        start, stop = boundaries
        if start is not None and not is_started:
            # check if should start
            if is_ordered:
                if value < start:
                    # before the start
                    return False
            else:
                if value != start:
                    # before the start (haven't seen "start" yet)
                    return False
        if stop is not None and is_started:
            # check if should stop (note: stop is exclusive)
            if is_ordered:
                if value >= stop:
                    # at or after the end
                    raise StopIteration
            else:
                if value == stop:
                    # at the end
                    raise StopIteration
        return True

    def __repr__(self):
        boundaries_str = ', '.join(
            '%s.%s=%s' % (attr, side, v)
            for attr, values in sorted(self.__dict__.items())
            if values is not None
            for side, v in zip(['start', 'stop'], values)
            if v is not None
        )
        if not boundaries_str:
            boundaries_str = '[include all]'
        return '<%s %s>' % ( type(self).__name__, boundaries_str)


class _WorkingBlockFilter:
    """
    A BlockFilter along with the state needed to apply it.
    """
    
    def __init__(self, block_filter):
        self.filter = block_filter
        self.is_started = False
        self.is_ended = False
        
    def check_block(self, block):
        """
        :return: True if need to include, False if need to exclude (i.e. before "start")
        :raise: StopIteration if need to break (i.e. after "stop")
        """
        if self.is_ended:
            raise StopIteration
        try:
            should_include = self.filter.check_block(block, is_started = self.is_started)
            if should_include:
                self.is_started = True
            return should_include
        except StopIteration:
            self.is_ended = True
            raise

    def __repr__(self):
        return repr(self.filter).replace('BlockFilter', type(self).__name__)

################################################################################
# Blocks

class RawFileBlockIterator:
    """
    Iterates over ALL blocks from `blk*.dat` files -- not only blocks included in
    the longest-chain.
    Blocks appear in "storage order", which is not necessarily chronological/topological
    order.
    No processing, validation, etc., is done on the blocks.

    Element type is `StoredBlock`.
    
    :note: Height is set to -1 for all blocks.

    :note: This iterator is resumable and refreshable.
    """

    def __init__(self, raw_data_iter = None, **kwargs):
        """
        :param raw_data_iter: a RawDataIterator
        :param kwargs: extra kwargs for RawDataIterator (ignored unless raw_data_iter is None)
        """
        if raw_data_iter is None:
            raw_data_iter = RawDataIterator(**kwargs)
        self.raw_data_iter = raw_data_iter
        
        # state
        self._cur_blob = b''
        self._cur_offset = 0
        self._cur_filename = None

    def __next__(self):
        
        if self._cur_offset >= len(self._cur_blob):
            # we're done with this blob. read the next one. 
            #if self._cur_blob is not None:
            #    assert self._cur_offset == len(self._cur_blob), (self._cur_offset, len(self._cur_blob))
            self._read_next_blob()  # raises StopIteration if no more files
    
        block_offset = self._cur_offset
        block = deserialize_block(self._cur_blob[block_offset : ], -1)
        if block is None:
            # past last block (in the last blk.dat file)
            
            # refresh: check if new data was added to this blob since we read it
            if self.refresh:
                self._reread_blob()
                block = deserialize_block(self._cur_blob[block_offset : ], -1)
            
            if block is None:
                # no new data, even after refreshing
                raise StopIteration
            
        self._cur_offset += 8 + block.rawsize
        return StoredBlock(
            block = block,
            filepos = FilePos(self._cur_filename, block_offset),
        )

    def _read_next_blob(self):
        data = self.raw_data_iter.__next__()  # raises StopIteration if no more files . # easier to profile with x.__next__() instead of next(x)...
        self._cur_blob = data.blob
        self._cur_filename = data.filename
        self._cur_offset = 0

    def _reread_blob(self):
        if self._cur_filename is not None:
            # note: not updating self._cur_filename and self._cur_offset, because
            # we need to keep reading from the same offset in the same file.
            self._cur_blob = self.raw_data_iter.get_data(self._cur_filename).blob

    def __iter__(self):
        return self

    @property
    def refresh(self):
        return self.raw_data_iter.refresh

class TopologicalBlockIterator:
    """
    Iterates over *all* blocks from `blk*.dat` files (not only from longest chain).
    
    Blocks are generated according to a topological order. This means
    it is guaranteed a block will not appear before its "prev block" (indicated
    by its "prev_block_hash").
    Other than that, blocks from different forks can be generated in any order.

    Element type is `Block`.

    :note: This iterator is resumable and refreshable.
    """

    def __init__(self, rawfile_block_iter = None, **kwargs):
        """
        :param rawfile_block_iter: a RawFileBlockIterator
        :param kwargs: extra kwargs for RawFileBlockIterator (ignored unless rawfile_block_iter is None)
        """
        if rawfile_block_iter is None:
            rawfile_block_iter = RawFileBlockIterator(**kwargs)
        self.rawfile_block_iter = rawfile_block_iter

        # state
        self._height_by_hash = { GENESIS_PREV_BLOCK_HASH: -1 }  # genesis is 0, so its prev is -1
        self._orphans = {}  # block_hash -> a list of orphan blocks waiting for it to appear
        self._ready_blocks = deque()  # blocks which can be released on next call to __next__()

    def __next__(self):
        # read more data if necessary
        while not self._ready_blocks:
            self._read_another_block()
        # release a block
        return self._get_next_block_to_release()

    def _read_another_block(self):
        # note: block.height is not set by RawFileBlockIterator
        block = self.rawfile_block_iter.__next__().block  # easier to profile with x.__next__() instead of next(x)...
        #logger.debug('prev-block-reference: %s -> %s', block.block_hash_hex, block.prev_block_hash_hex) # commented out because hex() takes time...
        # handle new block either as "ready" or "orphan":
        height_by_hash = self._height_by_hash
        prev_block_hash = block.prev_block_hash
        prev_height = height_by_hash.get(prev_block_hash)
        if prev_height is None:
            # prev not found. orphan.
            self._orphans.setdefault(prev_block_hash, []).append(block)
            return False
        else:
            # prev found. block is "ready".
            self._disorphanate_block(block, prev_height + 1)
            return True

    def _get_next_block_to_release(self):
        # release a block from _ready_blocks, and disorphanate its children
        block = self._ready_blocks.popleft()
        self._disorphanate_children_of(block)
        return block
        
    def _disorphanate_children_of(self, block):
        children = self._orphans.pop(block.block_hash, ())
        child_height = block.height + 1
        for child_block in children:
            self._disorphanate_block(child_block, child_height)
            
    def _disorphanate_block(self, child_block, height):
        # block's height is known now. set it:
        child_block.height = height
        self._height_by_hash[child_block.block_hash] = height
        # no longer orphan. it is ready for releasing:
        self._ready_blocks.append(child_block)  # appendright

    def __iter__(self):
        return self


################################################################################
# Longest chain

class LongestChainBlockIterator:
    """
    Linearly iterates over blocks in the longest chain.
    
    Denoting `B(i)` and `B(i+1)` as the i-th and i+1-th blocks in the sequence, this
    iterator guarantees::
    
     - `B(i+1).prev_block_hash == B(i).block_hash`
     - `B(i+1).height == B(i).height + 1`
     
    The height of the first block (genesis) is 0, and its `prev_block_hash` is all zeros.

    Element type is `Block`.
    
    :note: This iterator is resumable and refreshable.
    """

    # TBD: an option to generate_unsafe_tail
    
    
    DEFAULT_HEIGHT_SAFETY_MARGIN = HEIGHT_SAFETY_MARGIN
    _DUMMY_PRE_GENESIS_BLOCK = Bunch(height = -1, block_hash = GENESIS_PREV_BLOCK_HASH)


    def __init__(self, block_iter = None, height_safety_margin = None, block_filter = None, **kwargs):
        """
        :param block_iter: a TopologicalBlockIterator
        :param height_safety_margin:
            how much longer should a fork be than a competing fork before we
            can safely conclude it is the eventual "winner" fork.
        :param block_filter: a BlockFilter, indicating blocks to start/stop at.
        :param kwargs: extra kwargs for TopologicalBlockIterator (ignored unless block_iter is None)
        """
        if block_iter is None:
            block_iter = TopologicalBlockIterator(**kwargs)
        self.block_iter = block_iter
        if height_safety_margin is None:
            height_safety_margin = self.DEFAULT_HEIGHT_SAFETY_MARGIN
        self.height_safety_margin = height_safety_margin
        if block_filter is not None:
            block_filter = _WorkingBlockFilter(block_filter)
        self.block_filter = block_filter
        
        # state
        root_block = self._DUMMY_PRE_GENESIS_BLOCK
        self._root_block = root_block  # the previous block released
        self._last_block = root_block  # the most recent block seen (not released yet)
        self._blocks_by_hash = { root_block.block_hash: root_block }  # block_hash -> block
        self._block_children = { root_block.block_hash: []}  # block_hash -> list of child blocks
        self._leaf_heights = SortedList([ root_block.height ])  # block heights, of the leaf blocks only

    def __next__(self):
        while True:
            block = self._get_next_block_to_release()
            if block is not None:
                self._root_block = block
                if self._check_block(block):
                    return block
            # no next block in pending blocks. need to read more data
            self._read_another_block()

    def _get_next_block_to_release(self):

        if not self._check_heights_gap():
            # longest chain not determined yet
            return None
        
        last_block = self._last_block
        root_block = self._root_block
        leaf_heights = self._leaf_heights
        
        # since there's now another block to generate, it must be _last_block which tipped it over
        assert last_block.height == leaf_heights[-1], (last_block.height, leaf_heights[-1])
        
        # find next block to generate -- search backwards from leaf to root
        next_block = self._find_child_from(last_block, root_block)
        
        # trim the neglected chains
        logger.debug('generating next root block %s', next_block)
        self._discard_tree(root_block, survivor_child = next_block)
        
        return next_block

    def _discard_block(self, block):
        """
        Remove a block from the data-structures representing the iterator state.
        :return: the children of the block discarded
        """
        block_hash = block.block_hash
        logger.debug('discarding block %s', block_hash)
        # remove from _blocks_by_hash:
        self._blocks_by_hash.pop(block_hash)
        # remove from _block_children:
        children = self._block_children.pop(block_hash)
        # remove from _leaf_heights (if there):
        if not children:
            # block is a leaf. need to remove it from _leaf_heights
            self._leaf_heights.remove(block.height)
        return children

    def _discard_tree(self, block, survivor_child = None):
        """
        recursively (DFS) discard a block and its children, except for its
        "survivor" child, the one included in the longest chain.
        """
        children = self._discard_block(block)
        for child in children:
            if child is not survivor_child:
                self._discard_tree(child)
            #else: don't discard the survivor

    def _check_heights_gap(self):
        """
        Is the longest fork leading by enough over the 2nd longest?
        """
        leaf_heights = self._leaf_heights
        height1 = leaf_heights[-1]
        height2 = leaf_heights[-2] if len(leaf_heights) >= 2 else self._root_block.height
        assert height1 >= height2, (height1, height2)
        if height1 - height2 >= self.height_safety_margin:
            # fork is leading by a large gap. can safely release next block 
            logger.debug('found next block to generate (cur leaf height = %s)', height1)
            return True
        else:
            # don't generate next block yet
            logger.debug('no next block to generate (cur leaf height = %s)', height1)
            return False
    
    def _find_child_from(self, block, root_block):
        """
        :return: the direct child of `root_block`, in the route from `root_block` to `block`.
        """
        blocks_by_hash = self._blocks_by_hash
        root_block_hash = root_block.block_hash
        while True:
            prev_block_hash = block.prev_block_hash
            if prev_block_hash == root_block_hash:
                return block
            block = blocks_by_hash[prev_block_hash]

    def _read_another_block(self):
        blocks_by_hash = self._blocks_by_hash
        block_children = self._block_children
        leaf_heights = self._leaf_heights
        
        # fetch another block
        block = self.block_iter.__next__()  # easier to profile with x.__next__() instead of next(x)...
        block_height = block.height
        block_hash = block.block_hash
        prev_block_hash = block.prev_block_hash
        
        # find new block's prev block
        try:
            prev_block = blocks_by_hash[prev_block_hash]
            if prev_block is not None:
                assert prev_block.height + 1 == block_height, (prev_block.height, block_height)
        except KeyError:
            # already neglected
            logger.info('block ignored (must be from a fork already deemed inferior): %s', block.block_hash_hex)
            return
        
        # update data structures with new block
        logger.debug('adding block: %s', block)
        self._last_block = block
        blocks_by_hash[block_hash] = block
        block_children[block_hash] = []  # no children seen yet, because each block appears before its children
        prev_block_children = block_children[prev_block_hash]
        is_prev_leaf = not prev_block_children
        prev_block_children.append(block)
        if is_prev_leaf:
            # prev is not longer a leaf. need to remove it from leaf_heights
            leaf_heights.remove(block_height - 1)
        leaf_heights.add(block_height)

    def _check_block(self, block):
        """
        apply `block_filter` to `block`
        """
        if self.block_filter is None:
            return True
        return self.block_filter.check_block(block)

    def __iter__(self):
        return self

    def __repr__(self):
        return '<%s at block #%r>' % ( type(self).__name__, self._root_block.height )


################################################################################
# Transactions

class TxIterator:
    """
    Iterates over all transactions in longest chain.
    
    Roughly equivalent to::
    
        for block in LongestChainBlockIterator():
            yield from block.iter_txs()
            
    Element type is `Tx` (or `TxInBlock`, if `include_block_context=True`.
    
    :note: This iterator is resumable and refreshable.
    """
    
    def __init__(self, include_block_context = False, include_tx_blob = False, block_iter = None, **kwargs):
        """
        :param block_iter: a LongestChainBlockIterator
        :param kwargs: extra kwargs for LongestChainBlockIterator (ignored unless block_iter is None)
        """
        if block_iter is None:
            block_iter = LongestChainBlockIterator(**kwargs)
        self.block_iter = block_iter
        self.include_block_context = include_block_context
        self.include_tx_blob = include_tx_blob
        
        # state
        self._block_txs = iter(())  # iterator over an empty sequence

    def __next__(self):
        while True:
            try:
                # return the next tx in this block:
                tx = self._block_txs.__next__()  # easier to profile with x.__next__() instead of next(x)...
                return tx
            except StopIteration:
                # done with this block
                pass
            # proceed to next block:
            self._block_txs = self._get_iter_of_next_block()

    def _get_iter_of_next_block(self):
        txs = self.block_iter.__next__().txs  # easier to profile with x.__next__() instead of next(x)...
        if self.include_block_context:
            return txs.iter_txs_in_block(include_tx_blob = self.include_tx_blob)
        else:
            return txs.iter_txs(include_tx_blob = self.include_tx_blob)

    def __iter__(self):
        return self

    def __repr__(self):
        return '<%s at %r>' % ( type(self).__name__, self.block_iter )

################################################################################
