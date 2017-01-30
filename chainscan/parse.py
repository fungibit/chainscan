"""
Functions for parsing / deserializing blocks and transactions
from raw serialized blockchain data.

:note: Parts of the implementations are written in cython for speed.
    They can be found in `cyt.pyx`.
"""

import datetime

from .defs import COINBASE_SPENT_OUTPUT_INDEX
from .misc import doublehash

from . import cyt as _parse  # use the cythonized parsing functions (fast)
#from . import slowparse as _slowparse as _parse  # use the pure-python parsing functions (for debugging)


# make these importable from here
bytes2uint32 = _parse.bytes2uint32
parse_varlen_integer = _parse.parse_varlen_integer


################################################################################
# parsing functions

datetime_from_timestamp = datetime.datetime.fromtimestamp
block_hash_from_blob = doublehash
txid_from_blob = doublehash

def parse_block(block_type, blob, height, **kwargs):
    magic, block_size, consumed = _parse.split_block(blob)
    if magic is None:
        # past last block
        blob = blob[:0]
        return None
    block_blob = blob[8 : 8 + block_size]
    return block_type(block_blob, height = height, **kwargs)

def parse_block_txs(block_txs_type, blob, **kwargs):
    num_txs, consumed = _parse.parse_varlen_integer(blob)
    return block_txs_type(blob[consumed : ], num_txs, **kwargs)
    
def parse_tx(tx_type, blob, include_blob = False, **kwargs):
    tx_output_type = tx_type.TxOutput
    tx_input_type = tx_type.TxInput
    version, inputs_split, outputs_split, locktime, consumed = _parse.split_tx(blob)
    inputs = [ tx_input_type(*args) for args in inputs_split ]
    outputs = [ tx_output_type(*args) for args in outputs_split ]
    if inputs[0].spent_output_idx == COINBASE_SPENT_OUTPUT_INDEX:
        # coinbase tx -- replace TxInput with CoinbaseTxInput
        cb_tx_input_type = tx_type.CoinbaseTxInput
        input0 = inputs[0]
        inputs[0] = cb_tx_input_type(
            script = input0.script,
            sequence = input0.sequence,
        )
    if include_blob:
        kwargs['blob'] = blob
    return tx_type(
        version = version,
        inputs = inputs,
        outputs = outputs,
        locktime = locktime,
        txid = txid_from_blob(blob[:consumed]),
        rawsize = consumed,
        **kwargs
    )

################################################################################
