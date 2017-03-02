"""
Block-related extension classes, and deserialization functionality, implemented
using Cython for speed.
"""

import datetime

include "consts.pxi"

from cython cimport boundscheck, wraparound, nonecheck

from chainscan._common_c cimport varlenint_pair
from chainscan._common_c cimport doublehash, bytes2uint32, bytes_to_hash_hex, deserialize_varlen_integer

from chainscan._block import BlockTxs


################################################################################
# BLOCK-RELATED EXTENSION CLASSES
################################################################################

cdef class Block:
    """
    A bitcoin block.
    """
    
    def __init__(self,
            bytesview version_bytes,
            bytesview prev_block_hash,
            bytesview merkle_root,
            uint32_t timestamp_epoch,
            bytesview difficulty_bytes,
            bytesview nonce_bytes,
            bytesview blob,
            int32_t height = -1,
            ):

        self.version_bytes = version_bytes
        self._prev_block_hash = prev_block_hash
        self.merkle_root = merkle_root
        self.timestamp_epoch = timestamp_epoch
        self.difficulty_bytes = difficulty_bytes
        self.nonce_bytes = nonce_bytes
        self.blob = blob
        self.height = height
        self._block_hash = doublehash(blob[:80])  # doublehash of the 80-byte header


    # Block properties

    property rawsize:
        def __get__(self):
            return len(self.blob)
        
    # _block_hash is a bytearray. Useful to access this field as bytes
    property block_hash:
        def __get__(self):
            return bytes(self._block_hash)

    property block_hash_hex:
        def __get__(self):
            return bytes_to_hash_hex(bytearray(self.block_hash)) # TBD avoid the bytearray copying...

    # _prev_block_hash is a memoryview. Useful to access this field as bytes
    property prev_block_hash:
        def __get__(self):
            return bytes(self._prev_block_hash)
        
    property prev_block_hash_hex:
        def __get__(self):
            return bytes_to_hash_hex(self._prev_block_hash)
        
    property version:
        def __get__(self):
            return bytes2uint32(self.version_bytes, 4)

    property nonce:
        def __get__(self):
            return bytes2uint32(self.nonce_bytes, 4)

    property timestamp:
        def __get__(self):
            return datetime.datetime.fromtimestamp(self.timestamp_epoch)
    
    property header:
        def __get__(self):
            return self.blob[0 : 0+80]

    # Tx related

    property _txs_blob:
        def __get__(self):
            return self.blob[80 : ]

    property num_txs:
        def __get__(self):
            cdef varlenint_pair pair = deserialize_varlen_integer(self._txs_blob)
            return pair.first

    property txs:
        def __get__(self):
            return BlockTxs(self)
        
    # Misc
    
    def __repr__(self):
        return '<%s #%d %s>' % ( type(self).__name__, self.height, self.block_hash_hex )

    def __reduce__(self):
        return (
            # The function to call to create the object:
            deserialize_block,
            # Args to pass to the function:
            ( bytearray(self.blob), self.height, False ),
        )
    

################################################################################
# DESERIALIZATION
################################################################################

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cpdef Block deserialize_block(bytesview buf, int32_t height, bint prefix_included = True):

    cdef:
        uint32_t magic
        uint32_t block_size
        bytesview block_blob

        bytesview version_bytes
        bytesview prev_block_hash
        bytesview merkle_root
        uint32_t timestamp_epoch
        bytesview difficulty_bytes
        bytesview nonce_bytes
        bytesview txs_blob


    if not prefix_included:
        magic = <uint32_t>MAGIC
        block_size = len(buf)
        
    with nogil:
        
        if prefix_included:
            magic = bytes2uint32(buf, 4)

        if magic == <uint32_t>MAGIC:
            # ok, beginning of a block
            
            if prefix_included:
                block_size = bytes2uint32(buf[4:], 4)
                block_blob = buf[8 : 8 + block_size]
            else:
                block_blob = buf

            version_bytes = block_blob[0 : 4]
            prev_block_hash = block_blob[4 : 36]
            merkle_root = block_blob[36 : 68]
            timestamp_epoch = bytes2uint32(block_blob[68 : 72], 4)
            difficulty_bytes = block_blob[72 : 76]
            nonce_bytes = block_blob[76 : 80]

    if magic == <uint32_t>MAGIC:
        return Block(
            version_bytes,
            prev_block_hash,
            merkle_root,
            timestamp_epoch,
            difficulty_bytes,
            nonce_bytes,
            block_blob,
            height,
        )
    elif magic == <uint32_t>MAGIC_ABORT:
        # past last block
        return None
    else:
        assert 0, ( 'Invalid MAGIC. Data corrupted?', magic )

