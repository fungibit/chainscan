"""
Constants used throughout this package.

:note: the constants here get automagically added to `defs.py`, so they
    can be used from cython code (using #include "consts.pxi") and python code
    (using "from .defs import SOME_CONST).
"""

################################################################################
# Data deserialization constants
################################################################################

DEF DEFAULT_DATA_DIR = '~/.bitcoin/blocks/'  # TBD support other platforms
DEF RAW_FILES_GLOB_PATTERN = 'blk*.dat'

DEF MAGIC       = 0xD9B4BEF9
DEF MAGIC_ABORT = 0x00000000

DEF GENESIS_PREV_BLOCK_HASH = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
DEF COINBASE_SPENT_TXID     = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
DEF COINBASE_SPENT_OUTPUT_INDEX = 0xFFFFFFFF

DEF SATOSHIS_IN_ONE = 100000000


################################################################################
# Other
################################################################################

DEF HEIGHT_SAFETY_MARGIN = 6
"""
A chain ahead by this many blocks can safely be considered the eventual longer
chain (making the other a "neglected fork").
This value of 6 is selected in accordance with the best practice of waiting for
6 confirmations to consider a transaction "safe".
"""

DEF TXID_PREFIX_SIZE = 8
"""
Txid-prefixes of size TXID_PREFIX_SIZE are still unique. Can use them instead
of the full txid, to save memory (e.g. as dict keys, DB index, etc.).
As of Dec 2016, prefix=7 is also fine. Still, we use 8 to be safe.
"""


################################################################################
# Script
################################################################################

# OPS
DEF OP_PUSHDATA1     = 0x4C
DEF OP_PUSHDATA2     = 0x4D
DEF OP_PUSHDATA4     = 0x4E
DEF OP_NOP           = 0x61
DEF OP_RETURN        = 0x6A
DEF OP_DUP           = 0x76
DEF OP_EQUALVERIFY   = 0x88
DEF OP_CHECKSIG      = 0xAC
DEF OP_HASH160       = 0xA9
