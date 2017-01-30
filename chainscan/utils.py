"""
Miscellaneous convenience functions for iterating over blocks, txs, etc.
"""

from .scan import LongestChainBlockIterator, TxIterator
from .track import TrackedSpendingTxIterator
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
        tracker = None,
        utxoset = None,
        block_iter = None,
        blockchain = None,
        block_kwargs = {},
        tx_kwargs = {},
        show_progressbar = False,
        ):
    """
    Iterates over the transactions of the blockchain.
    
    :param track_spending: resolve spent_output for each TxInput (will use TrackedSpendingTxIterator
        instead of the basic TxIterator)
    :param tracker, utxoset: ignored unless track_spending=True
    :param block_iter: a LongestChainBlockIterator
    :param blockchain: a BlockChain object to populate on the fly
    :param block_kwargs: extra kwargs for the block_iter (LongestChainBlockIterator or BlockChainIterator)
    :param tx_kwargs: extra kwargs for the tx_iter (TxIterator or TrackedSpendingTxIterator) 
    """
    
    block_kwargs = dict(block_kwargs)
    tx_kwargs = dict(tx_kwargs)
    
    block_kwargs.update(
        show_progressbar = show_progressbar,
    )
    
    # blockchain building
    if blockchain is not None:
        # We need to build the blockchain. We wrap the original block_iter with a
        # BlockChainIterator, which builds the blockchain as we go. `blockchain` is the initial
        # BlockChain object to use, and will be updated in place.
        block_iter = BlockChainIterator(blockchain = blockchain, block_iter = block_iter, **block_kwargs)
    if block_iter is None:
        block_iter = LongestChainBlockIterator(**block_kwargs)
    
    # tracked spending
    if track_spending:
        tx_iter_cls = TrackedSpendingTxIterator
        tx_kwargs.update(tracker = tracker, utxoset = utxoset)
    else:
        tx_iter_cls = TxIterator

    # create the tx-iterator
    tx_kwargs.update(
        block_iter = block_iter,
    )
    return tx_iter_cls(**tx_kwargs)
    

################################################################################
