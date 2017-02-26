"""
Tools for scanning while tracking refs from inputs to the outputs they spend.
"""

from .scan import TxIterator
from ._track_c import UtxoSet


################################################################################
# TxIteratoryWith tracked spending

class TxSpendingTracker:
    """
    The "tracking" logic used by TrackedSpendingTxIterator.
    
    This class can also be used directly, for finer control over the tracking
    process.  For this purpose, the `__call__` operator is useful.  E.g.::
    
        track = TxSpendingTracker()
        for block in iter_blocks():
            for tx in track(block.txs):
                for txinput in txinput:
                    print(txinput.spent_output)
            if len(track.utxoset) > N:
                do_something(track.utxoset)
        
    """
    
    def __init__(self, utxoset = None):
        if utxoset is None:
            utxoset = UtxoSet()
        self.utxoset = utxoset
        
    def process_tx(self, tx):
        _track_tx_spending(tx, self.utxoset)
        
    def process_txs_gen(self, tx_iter):
        for tx in tx_iter:
            self.process_tx(tx)
            yield tx
        
    def __call__(self, tx_iter):
        """
        For convenience (see class's docstring).
        """
        return self.process_txs_gen(tx_iter)

class TrackedSpendingTxIterator(TxIterator):
    """
    A TxIterator which resolves references from a TxInput to the TxOutput it spends.
    
    For each tx returned, each tx-input has its `spending_info` attribute set (except for
    coinbase inputs).

    Element type is `Tx`.

    :note: to track, requires maintaining a very big data structure of unspent tx outputs, thus
        this iterator can consume a lot of RAM (>6GB).
    
    :note: This iterator is resumable and refreshable.
    """
    
    def __init__(self, tracker = None, utxoset = None, *args, **kwargs):
        """
        :param tracker: a TxSpendingTracker
        :param utxoset: a UtxoSet
        :param args, kwargs: extra args to pass to `TxInput.__init__`
        """
        super().__init__(*args, **kwargs)
        if tracker is None:
            tracker = TxSpendingTracker(utxoset = utxoset)
        self.tracker = tracker
        
    def __next__(self):
        tx = super().__next__()
        return self._track(tx)
    
    def _track(self, tx):
        self.tracker.process_tx(tx)
        return tx


def _track_tx_spending(tx, utxoset):
    """
    Updates both tx (specifically the spending_info attribute of the
    tx.inputs) and utxoset (removes utxos being spent by tx, and adds tx.outputs
    as utxos).
    """
    # track the outputs being spent in this tx, by removing each output being spent
    # from utxoset, and setting it on input spending it
    for txin in tx.inputs:
        if txin.is_coinbase:
            continue
        spending_info = utxoset.spend(txin._spent_txid, txin.spent_output_idx)
        txin.spending_info = spending_info
    # add outputs of new tx to utxoset
    utxoset.add_from_tx(tx)

################################################################################
