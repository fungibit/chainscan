"""
Block-related extension classes, and deserialization functionality, implemented
using Cython for speed.
"""

from chainscan._common_c cimport uint8_t, uint32_t, int32_t, bytesview

cdef class Block:

    cdef:
        readonly bytesview version_bytes
        readonly bytesview _prev_block_hash
        readonly bytesview merkle_root
        readonly uint32_t timestamp_epoch
        readonly bytesview difficulty_bytes
        readonly bytesview nonce_bytes
        
        readonly bytesview blob
        public int32_t height
        readonly bytearray _block_hash

cpdef Block deserialize_block(bytesview buf, int32_t height, bint prefix_included = *)
