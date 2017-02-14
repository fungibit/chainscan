"""
Definition of some constants used in this package.
"""

#===================================================================================================================
# Parsing constants
#===================================================================================================================

MAGIC = 0xD9B4BEF9.to_bytes(4, byteorder='little')
ZERO_HASH = 0x0.to_bytes(32, byteorder='little')
GENESIS_PREV_BLOCK_HASH = ZERO_HASH
COINBASE_SPENT_TXID = ZERO_HASH
COINBASE_SPENT_OUTPUT_INDEX = 0xFFFFFFFF

#===================================================================================================================
# Script
#===================================================================================================================

# OPS
OP_PUSHDATA1     = 0x4C
OP_PUSHDATA2     = 0x4D
OP_PUSHDATA4     = 0x4E
OP_NOP           = 0x61
OP_RETURN        = 0x6A
OP_DUP           = 0x76
OP_EQUALVERIFY   = 0x88
OP_CHECKSIG      = 0xAC
OP_HASH160       = 0xA9


#===================================================================================================================
# Other
#===================================================================================================================

DEFAULT_DATA_DIR = '~/.bitcoin/blocks/'  # TBD support other platforms
RAW_FILES_GLOB_PATTERN = 'blk*.dat'

SATOSHIS_IN_ONE = 10**8

HEIGHT_SAFETY_MARGIN = 6
"""
A chain ahead by this many blocks can safely be considered the eventual longer
chain (making the other a "neglected fork").
This value of 6 is selected in accordance with the best practice of waiting for
6 confirmations to consider a transaction "safe".
"""

TXID_PREFIX_SIZE = 8
"""
Txid-prefixes of size TXID_PREFIX_SIZE are still unique. Can use them instead
of the full txid, to save memory (e.g. as dict keys, DB index, etc.).
As of Dec 2016, prefix=7 is also fine. Still, we use 8 to be safe.
"""

