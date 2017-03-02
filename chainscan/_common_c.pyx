"""
Basic functions used throughout this package, implemented using Cython for speed.
"""

from cython cimport boundscheck, wraparound, nonecheck
from libc.stdlib cimport malloc, free
from libc.string cimport memcpy
cimport numpy as np


cpdef str bytes_to_hash_hex(bytesview b):
    return bytes(b[::-1]).hex()

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cpdef uint32_t bytes2uint32(bytesview buf, uint8_t len) nogil:
    cdef:
        uint8_t i
        uint32_t x = 0
        uint32_t exp = 1
    for i in range(len):
        x += buf[i] * exp
        exp <<= 8
    return x

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cpdef uint64_t bytes2uint64(bytesview buf, uint8_t len) nogil:
    cdef:
        uint8_t i
        uint64_t x = 0
        uint64_t exp = 1
    for i in range(len):
        x += buf[i] * exp
        exp <<= 8
    return x

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cpdef varlenint_pair deserialize_varlen_integer(bytesview buf) nogil:
    cdef uint8_t v1
    cdef uint8_t consume_end
    cdef varlenint_pair res
    v1 = buf[0]
    if v1 < 0xFD:
        res.first = v1
        res.second = 1
        return res
    if v1 == 0xFD:
        consume_end = 3
    elif v1 == 0xFE:
        consume_end = 5
    elif v1 == 0xFF:
        consume_end = 9
    
    res.first = bytes2uint32(buf[1 : consume_end], consume_end-1)
    res.second = consume_end
    return res

# This functions allocates a new C-array using malloc() and returns
# a pointer to it.  It is caller's responsibility to free() it.
@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cdef uint8_t* copy_bytes_to_carray(bytes data, uint32_t size):
    # this is the best way I found to do this... couldn't make it work using memoryviews...
    cdef uint8_t *dstptr = <uint8_t*>malloc(size * sizeof(uint8_t))
    cdef np.ndarray[uint8_t, ndim=1, mode="c"] npview = <np.ndarray[uint8_t, ndim=1, mode="c"]>data
    if dstptr != NULL:
        memcpy(dstptr, &(npview[0]), size)
    return dstptr
    

################################################################################
# SHA256
################################################################################

cdef extern from "<openssl/sha.h>" nogil:
    ctypedef struct SHA256_CTX:
        uint32_t h[8]
        uint32_t Nl, Nh
        uint32_t data[16]
        unsigned int num, md_len
    int SHA256_Init(SHA256_CTX *c)
    int SHA256_Update(SHA256_CTX *c, const void *data, size_t len)
    int SHA256_Final(unsigned char *md, SHA256_CTX *c)

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cpdef bytearray doublehash(bytesview buf):
    """
    Compute the double SHA256 of `buf`.
    :return: a bytearray of size 32
    """
    cdef void *buf_p = &(buf[0])
    cdef uint32_t size = buf.size
    cdef uint8_t[32] res
    cdef uint8_t[::1] resview = res
    cdef SHA256_CTX ctx
    
    with nogil:
        SHA256_Init(&ctx)
        SHA256_Update(&ctx, buf_p, size)
        SHA256_Final(res, &ctx)
        SHA256_Init(&ctx)
        SHA256_Update(&ctx, res, sizeof(res))
        SHA256_Final(res, &ctx)
    
    return bytearray(resview)

# for debugging
#from hashlib import sha256
#cpdef bytearray doublehash_slow(bytesview x):
#    return bytearray(sha256(sha256(x).digest()).digest())

