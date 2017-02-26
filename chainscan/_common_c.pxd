
# distutils: language = c++

"""
Basic functions and definitions used throughout this package.
"""

################################################################################
# TYPES AND TYPEDEFS
################################################################################

from libc.stdint cimport int8_t, uint8_t, int32_t, uint32_t, int64_t, uint64_t
from libcpp.pair cimport pair

cdef:

    ctypedef uint8_t[::1] bytesview
    ctypedef uint64_t btc_value
    ctypedef pair[uint32_t, uint8_t] varlenint_pair  # [value, consumed]

################################################################################
# FUNCTIONS
################################################################################

cpdef str bytes_to_hash_hex(bytesview b)
cpdef uint32_t bytes2uint32(bytesview buf, uint8_t len) nogil
cpdef uint64_t bytes2uint64(bytesview buf, uint8_t len) nogil
cpdef varlenint_pair deserialize_varlen_integer(bytesview buf) nogil
cpdef bytearray doublehash(bytesview buf)
#cpdef bytearray doublehash_slow(bytesview x)  # for debugging

cdef uint8_t* copy_bytes_to_carray(bytes data, uint32_t size)
# This functions allocates a new C-array using malloc() and returns
# a pointer to it.  It is caller's responsibility to free() it.
