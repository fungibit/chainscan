"""
Tools which might be useful for processing blockchain data in parallel
(e.g. using `multiprocessing` workers).
"""


################################################################################

class IndependentTxSetGenerator:
    """
    Generates sets of txs, such that for all txs in a given set, all txs they
    depend on (i.e. all the txs they spend outputs of) have already been included
    in a set prior to that set.
    
    This means all txs in a given set are independent, and the order in which
    they are processed should not matter.
    """
    
    # TBD: try different combinations of these values, see what works
    DEFAULT_MAX_SET_SIZE = 10000
    DEFAULT_MAX_PENDING_SIZE = 500000
    
    def __init__(self, max_set_size = None, max_pending_size = None):
        if max_set_size is None:
            max_set_size = self.DEFAULT_MAX_SET_SIZE
        self.max_set_size = max_set_size
        if max_pending_size is None:
            max_pending_size = self.DEFAULT_MAX_PENDING_SIZE
        self.max_pending_size = max_pending_size
    
    def gen_sets(self, tx_iter):
        
        next_set = {}  # txid -> tx
        pending = {}  # txid -> tx
        
        for tx in tx_iter:
            txid = tx.txid
            if self._is_tx_ready(tx, next_set, pending):
                # can include in next set
                next_set[txid] = tx
            else:
                # cannot include in next set
                pending[txid] = tx
            # release next set if ready
            yield from self._release_sets(next_set, pending)

    def _release_sets(self, next_set, pending):
        while len(next_set) >= self.max_set_size or len(pending) >= self.max_pending_size:
            # convert next_set to a list of txs to release
            txs = list(next_set.values())
            next_set.clear()
            yield txs
            
            # transfer txs from pending to next_set
            for txid, tx in dict(pending).items():
                if len(next_set) >= self.max_set_size:
                    break
                if self._is_tx_ready(tx, next_set, pending):
                    next_set[txid] = tx
                    del pending[txid]

    def _is_tx_ready(self, tx, next_set, pending):
        for txinput in tx.inputs:
            spent_txid = txinput.spent_txid
            if spent_txid in pending or spent_txid in next_set:
                # spent_tx not processed yet
                return False
            # else: spent_txid must already been processed in a past set
        return True


################################################################################
