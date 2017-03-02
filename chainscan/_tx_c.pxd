"""
Transaction-related extension classes, and deserialization functionality, implemented
using Cython for speed.
"""

from chainscan._common_c cimport uint8_t, uint32_t, bytesview, btc_value


cdef class TxOutput:

    cdef:
        readonly btc_value value
        readonly bytes script


cdef class TxInput:

    cdef:
        readonly bytesview _spent_txid
        readonly uint32_t spent_output_idx
        readonly bytesview script
        readonly uint32_t sequence
        public object spending_info


cdef class CoinbaseTxInput:

    cdef:
        readonly bytesview script
        readonly uint32_t sequence


cdef class Tx:

    cdef:
        readonly bytesview version_bytes
        readonly list inputs
        readonly list outputs
        readonly uint32_t locktime
        readonly bytearray _txid
        readonly uint32_t rawsize
        readonly bytesview blob


# deserialization functions
cpdef Tx deserialize_tx(bytesview blob, bint include_blob=*)
cpdef tuple deserialize_tx_input(bytesview buf)
cpdef tuple deserialize_tx_output(bytesview buf)


