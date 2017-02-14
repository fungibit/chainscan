#! /usr/bin/env python3
"""
An alternative implementation for Rusty Russell's *bitcoin-iterate* tool
(https://github.com/rustyrussell/bitcoin-iterate), based on the chainscan library.

This script is included here mainly for being useful for testing the chainscan
library.

* If you use this script and find it useful, all credit goes to Rusty Russell! *


From the original documentation (with minor changes):

*--block*='FORMAT'::
  Print out the format string for each block.  Escape codes are prefixed
  with '%':

  %bl: block length
  %bv: block version
  %bp: block prev hash as a 64-character little-endian hex string
  %bm: block merkle hash as a 64-character little-endian hex string
  %bs: block timestamp
  %bt: block target
  %bn: block nonce
  %bc: block transaction count
  %bh: block hash as a 64-character little-endian hex string
  %bN: block height (0 == genesis)
  %bH: block header as a hex string

*--tx,--transaction*='FORMAT'::
  Print out the format string for each transaction (in the order they
  are in the block).  All the block escape codes are valid, and the
  following additional ones:

  %th: transaction hash as a 64-character little-endian hex string
  %tv: transaction version
  %ti: transaction input count
  %to: transaction output count
  %tt: transaction locktime
  %tl: transaction length
  %tF: transaction fee paid by block (negative for coinbase reward)
  %tN: transaction number within block
  %tD: transaction bitcoin days destroyed (by block times)
  %tX: transaction as a hex string (including inputs and outputs)

*--input*='FORMAT'::
  Print out the format string for each transaction input (in the order
  they are in the transaction).  All the block and transaction escape
  codes are valid, and the following additional ones:

  %ih: input hash as a 64-character-little-endian hex string
  %it: spent transaction hash (this format is missing from original bitcoin-iterate tool)
  %ii: input index
  %il: input script length
  %is: input script as a hex string
  %iN: input number within transaction
  %iB: input UTXO block number (0 for coinbase)
  %iX: input as a hex string
  %ia: input amount (value)
  %ip: spent output type
  
*--output*='FORMAT'::
  Print out the format string for each transaction output (in the order
  they are in the transaction).  All the block and transaction escape
  codes are valid, and the following additional ones:

  %oa: output amount
  %ol: output script length
  %os: output script as a hex string.
  %oN: output number within transaction
  %oU: output is unspendable (0==spendable)
  %oX: output as a hex string
  
"""

import datetime
from argparse import ArgumentParser

from chainscan import iter_blocks, BlockFilter
from chainscan.track import TxSpendingTracker
from chainscan.utils import tailable
from chainscan.misc import bytes2uint32, hash_hex_to_bytes, s2f
from chainscan.defs import OP_RETURN


###############################################################################

BLOCK_EVAL = {
    'l': lambda b: str(b.rawsize),
    'v': lambda b: str(b.version),
    'p': lambda b: tohex(b.prev_block_hash),
    'm': lambda b: tohex(b.merkle_root),
    's': lambda b: str(b.timestamp_epoch),
    't': lambda b: str(bytes2uint32(b.difficulty)),
    'n': lambda b: str(bytes2uint32(b.nonce)),
    'c': lambda b: str(b.num_txs),
    'h': lambda b: tohex(b.block_hash),
    'N': lambda b: str(b.height),
    'H': lambda b: tohex(b.header),
}

TX_EVAL = {
    'h': lambda tx, idx: tohex(tx.txid),
    'v': lambda tx, idx: str(tx.version),
    'i': lambda tx, idx: str(len(tx.inputs)),
    'o': lambda tx, idx: str(len(tx.outputs)),
    't': lambda tx, idx: str(tx.locktime),
    'l': lambda tx, idx: str(tx.rawsize),
    'N': lambda tx, idx: str(idx),

    # The following require track_spending=True:
    'F': lambda tx, idx: str(s2f(tx.get_fee_paid())),
    
    # The following are not supported by us:
    #'D': lambda tx, idx: tx.bitcoin days destroyed (by block times),  # TBD?
    #'X': lambda tx, idx: tx.as a hex string (including inputs and outputs),
}

INPUT_EVAL = {
    't': lambda i, idx: tohex(i.spent_txid),  # is this missing from the original?
    'i': lambda i, idx: str(i.spent_output_idx),
    'l': lambda i, idx: str(len(i.script)),
    's': lambda i, idx: tohex(i.script),
    'N': lambda i, idx: str(idx),
    
    # The following require track_spending=True:
    'a': lambda i, idx: str(i.value),

    # The following are not supported by us:
    #'B': lambda i, idx: i.UTXO block number (0 for coinbase),
    #'h': lambda i, idx: tohex(i.hash),
    #'X': lambda i, idx: i as a hex string,
    #'p': lambda i, idx: i.output_type
}

OUTPUT_EVAL = {
    'a': lambda o, idx: str(o.value),
    'l': lambda o, idx: str(len(o.script)),
    's': lambda o, idx: tohex(o.script),
    'N': lambda o, idx: str(idx),
    'U': lambda o, idx: str(int(is_unspendable(o))),
    
    # The following are not supported by us:
    #'X': lambda o, idx: tohex(o.raw),
}

TRACK_SPENDING_ON_FORMATS = [ '%tF', '%tD', '%iB', '%ia', '%ip' ]


###############################################################################

def format_block_value(fmt, block):
    return BLOCK_EVAL[fmt](block)

def format_tx_value(fmt, tx, idx):
    return TX_EVAL[fmt](tx, idx)

def format_input_value(fmt, input, idx):
    return INPUT_EVAL[fmt](input, idx)

def format_output_value(fmt, output, idx):
    return OUTPUT_EVAL[fmt](output, idx)

def format_line(fmt, block, tx, tx_idx, input, input_idx, output, output_idx):
    parts = []
    offset = 0
    n = len(fmt)
    while offset < n:
        if block is not None and fmt[offset : offset+2] == '%b':
            value = format_block_value(fmt[offset+2], block)
            offset += 3
        elif tx is not None and fmt[offset : offset+2] == '%t':
            value = format_tx_value(fmt[offset+2], tx, tx_idx)
            offset += 3
        elif input is not None and fmt[offset : offset+2] == '%i':
            value = format_input_value(fmt[offset+2], input, input_idx)
            offset += 3
        elif output is not None and fmt[offset : offset+2] == '%o':
            value = format_output_value(fmt[offset+2], output, output_idx)
            offset += 3
        else:
            value = fmt[offset]
            offset += 1
        parts.append(value)
    return ''.join(parts)

def tohex(x):
    return x.hex()

def is_unspendable(txout):
    return txout.script and txout.script[0] == OP_RETURN

def parse_time(x):
    return datetime.datetime.strptime(x, '%Y-%m-%d')

def broken_pipe_resistant(func):
    def f(*a,**kw):
        try:
            return func(*a,**kw)
        except BrokenPipeError:
            pass  # stdin or stdout disconnected
    return f

###############################################################################
# MAIN

@broken_pipe_resistant
def main():
    
    options = getopt()
    
    block_filter = BlockFilter(
        start_block_height = options.start_block_height, stop_block_height = options.stop_block_height,
        start_block_time = options.start_block_time, stop_block_time = options.stop_block_time,
        start_block_hash = options.start_block_hash, stop_block_hash = options.stop_block_hash,
    )
    
    blk_format = options.block
    tx_format = options.tx
    input_format = options.input
    output_format = options.output
    all_formats = [ blk_format, tx_format, input_format, output_format ]
    
    any_not_none = lambda fmts: any(fmt is not None for fmt in fmts)
    should_iter_blocks = any_not_none([ blk_format, tx_format, input_format, output_format ])
    should_iter_txs = any_not_none([ tx_format, input_format, output_format ])
    should_iter_inputs = any_not_none([ input_format, ])
    should_iter_outputs = any_not_none([ output_format, ])
    
    if not should_iter_blocks:
        return
        
    track_spending = any(
        subfmt in fmt
        for subfmt in TRACK_SPENDING_ON_FORMATS
        for fmt in all_formats if fmt is not None
    )
    
    if track_spending:
        track = TxSpendingTracker()
    else:
        track = lambda txs: txs  # noop
    
    block_iter = iter_blocks(block_filter = block_filter)
    if options.tailable:
        block_iter = tailable(block_iter)
    
    for block in block_iter:
        
        if blk_format is not None:
            print(format_line(blk_format, block, None, None, None, None, None, None))
        
        txs = block.txs if should_iter_txs else []
        for tx_idx, tx in enumerate(track(txs)):
            
            if tx_format is not None:
                print(format_line(tx_format, block, tx, tx_idx, None, None, None, None))
                
            if should_iter_inputs:
                for input_idx, input in enumerate(tx.inputs):
                    print(format_line(input_format, block, tx, tx_idx, input, input_idx, None, None))

            if should_iter_outputs:
                for output_idx, output in enumerate(tx.outputs):
                    print(format_line(output_format, block, tx, tx_idx, None, None, output, output_idx))


###############################################################################

def getopt():
    parser = ArgumentParser()
    
    # formats
    parser.add_argument('--block',  help = 'Format to print for each block')
    parser.add_argument('--tx', '--transaction', help = 'Format to print for each transaction')
    parser.add_argument('--input', help = 'Format to print for each transaction input')
    parser.add_argument('--output', help = 'Format to print for each transaction output')
    #parser.add_argument('--utxo', help = 'Format to print for each UTXO')  # not supported by us
    
    # start / stop filters
    parser.add_argument('--start-block-height', type = int)
    parser.add_argument('--stop-block-height', type = int)
    parser.add_argument('--start-block-time', type = parse_time)
    parser.add_argument('--stop-block-time', type = parse_time)
    parser.add_argument('--start-block-hash', type = hash_hex_to_bytes)
    parser.add_argument('--stop-block-hash', type = hash_hex_to_bytes)
    
    # other
    parser.add_argument('--tailable', '-f', '--follow', action = 'store_true',
                        help = 'wait for more data, process it as it arrives')
    
    return parser.parse_args()

###############################################################################

if __name__ == '__main__':
    main()
