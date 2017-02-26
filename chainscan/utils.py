"""
Miscellaneous convenience functions for iterating over blocks, txs, etc.
"""

import time
import threading

from .scan import LongestChainBlockIterator, TxIterator
from .track import TrackedSpendingTxIterator, UtxoSet
from .blockchain import BlockChainIterator


################################################################################
# Blocks

def iter_blocks(block_iter = None, **kwargs):
    """
    Currently, this function doesn't do much.
    It is roughly equivalent to `return LongestChainBlockIterator()`.
    It is here mainly for forward-compatibility.
    For simple cases, it is encouraged to use this function instead of LongestChainBlockIterator
    directly.  In the future we might add various useful options and flags to it.
    """
    if block_iter is None:
        block_iter = LongestChainBlockIterator(**kwargs)
    return block_iter

def get_blockchain(blockchain_iter = None, **kwargs):
    """
    :param blockchain_iter: a BlockChainIterator
    :param kwargs: extra kwargs for BlockChainIterator (ignored unless blockchain_iter is None)
    :return: a BlockChain
    """
    if blockchain_iter is None:
        blockchain_iter = BlockChainIterator(**kwargs)
    # blockchain_iter builds the block chain as we iterate over it
    for _ in blockchain_iter: pass
    return blockchain_iter.blockchain


################################################################################
# Txs

def iter_txs(
        track_spending = False,
        track_scripts = False,
        tracker = None,
        utxoset = None,
        block_iter = None,
        blockchain = None,
        block_kwargs = {},
        block_filter = None,
        show_progressbar = False,
        **tx_kwargs
        ):
    """
    Iterates over the transactions of the blockchain.
    
    :param track_spending: resolve spent_output for each TxInput (will use TrackedSpendingTxIterator
        instead of the basic TxIterator)
    :param track_scripts: when resolving spent_output, also include its script. track_scripts=True
        implies track_spending=True. (ignored unless utxoset is None)
    :param tracker, utxoset: ignored unless track_spending=True
    :param block_iter: a LongestChainBlockIterator
    :param blockchain: a BlockChain object to populate on the fly
    :param block_kwargs: extra kwargs for the block_iter (LongestChainBlockIterator or BlockChainIterator)
    :param tx_kwargs: extra kwargs for the tx_iter (TxIterator or TrackedSpendingTxIterator) 
    """
    
    block_kwargs = dict(block_kwargs)
    block_kwargs.setdefault('block_filter', block_filter)
    block_kwargs.setdefault('show_progressbar', show_progressbar)
    
    # block_iter and blockchain building
    if blockchain is not None:
        # We need to build the blockchain. We wrap the original block_iter with a
        # BlockChainIterator, which builds the blockchain as we go. `blockchain` is the initial
        # BlockChain object to use, and will be updated in place.
        block_iter = BlockChainIterator(blockchain = blockchain, block_iter = block_iter, **block_kwargs)
    if block_iter is None:
        block_iter = LongestChainBlockIterator(**block_kwargs)
    
    # tracked spending
    if track_scripts:
        # track_scripts=True implies track_spending=True
        track_spending = True
    if track_spending:
        if utxoset is None:
            utxoset = UtxoSet(include_scripts = track_scripts)
        tx_iter_cls = TrackedSpendingTxIterator
        tx_kwargs.update(tracker = tracker, utxoset = utxoset)
    else:
        tx_iter_cls = TxIterator

    # create the tx-iterator
    return tx_iter_cls(block_iter = block_iter, **tx_kwargs)
    

################################################################################
# itertools

class tailable:
    """
    An iterator-wrapper which keeps waiting for new data from the underlying
    iterator.
    
    The underlying iterator needs to be "refreshable", i.e. calls to next()
    can keep returning more data as it arrives, even after raising
    StopIteration on past calls to next().
    
    :note: This iterator is resumable if the underlying is resumable.
    """
    
    def __init__(self, iterator, timeout = None, polling_interval = 5):
        self.iter = iterator
        if timeout is None:
            timeout = float('Inf')
        self.timeout = timeout
        self.polling_interval = polling_interval
        self._stop_event = threading.Event()
        
    def __next__(self):
        start_time = time.time()
        while not self._stop_event.is_set():
            try:
                return next(self.iter)
            except StopIteration:
                # no more available data. check timeout, then sleep+retry
                elapsed_time = time.time() - start_time
                remaining_time = self.timeout - elapsed_time
                if remaining_time <= 0:
                    # timed out, waited long enough
                    break
                self._stop_event.wait(timeout = min(self.polling_interval, remaining_time))
        raise StopIteration
    
    def __iter__(self):
        return self
    
    def stop(self):
        """
        Signal the iterator to stop waiting for more data
        """
        self._stop_event.set()
    

################################################################################
