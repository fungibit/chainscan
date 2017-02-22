
# distutils: extra_compile_args = ['-std=c++11']

"""
Definition of the UtxoSet class, used for tracking spending.
"""

include "consts.pxi"

from libc.stdlib cimport malloc, free
from libcpp.pair cimport pair
from libcpp.unordered_map cimport unordered_map

from cython cimport boundscheck, wraparound, nonecheck
from cython.operator cimport dereference, preincrement

from chainscan._common_c cimport uint8_t, uint32_t, uint64_t, bytesview, btc_value
from chainscan._common_c cimport bytes2uint64, bytes_to_hash_hex
from chainscan._tx_c cimport TxOutput


################################################################################

cdef:
    ctypedef uint32_t osize_t
    ctypedef void *voidp
    
# we can represent txid_key_t as uint64_t only if TXID_PREFIX_SIZE<=8
assert TXID_PREFIX_SIZE <= 8, TXID_PREFIX_SIZE
ctypedef uint64_t txid_key_t

################################################################################
# UTX ENTRY

ctypedef pair[uint64_t, uint8_t] value_pair  # [value, is_last]

cdef struct _UtxEntry:
    # An entry in the UtxoSet data structure.
    btc_value *output_value_arr
    osize_t num_outputs
    osize_t num_unspent
    int block_height


@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cdef void _UtxEntry_init_from_output_list(_UtxEntry &self, list outputs, int block_height):
    cdef osize_t n = len(outputs)
    cdef unsigned int i
    cdef TxOutput output

    _UtxEntry_init_basic(self, n, block_height)

    self.output_value_arr = <btc_value*>malloc(n * sizeof(btc_value))
    for i in range(n):
        output = outputs[i]
        self.output_value_arr[i] = output.value

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cdef void _UtxEntry_init_basic(_UtxEntry &self, osize_t num_outputs, int block_height):
    self.num_outputs = num_outputs
    self.num_unspent = num_outputs
    self.block_height = block_height

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cdef void _UtxEntry_dealloc(_UtxEntry &self) nogil:
    if self.output_value_arr != NULL:
        free(self.output_value_arr)

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cdef btc_value _UtxEntry_spend(_UtxEntry &self, osize_t idx) nogil:
    cdef btc_value o = self.output_value_arr[idx]
    if o > 0:
        self.output_value_arr[idx] = 0
        self.num_unspent -= 1
    return o

cdef _UtxEntry_getstate(_UtxEntry &self):
    cdef osize_t i
    output_values = [ self.output_value_arr[i] for i in range(self.num_outputs) ]
    return dict(
        output_values = output_values,
        num_unspent = self.num_unspent,
        block_height = self.block_height,
    )

cdef _UtxEntry _UtxEntry_fromstate(state):
    cdef _UtxEntry self
    cdef osize_t n, i
    cdef btc_value value
    output_values = state['output_values']
    n = len(state['output_values'])

    _UtxEntry_init_basic(self, n, state['block_height'])
    self.num_unspent = state['num_unspent']

    self.output_value_arr = <btc_value*>malloc(n * sizeof(btc_value))
    for i, value in enumerate(output_values):
        self.output_value_arr[i] = value

    return self
    

################################################################################
# UTXO SET

cdef:
    ctypedef unordered_map[txid_key_t, _UtxEntry] utxo_map
    ctypedef unordered_map[txid_key_t, _UtxEntry].iterator utxo_map_iter
    

cdef class UtxoSet:
    """
    A data structure holding all the unspent tx outputs (UTXOs)
    """
    
    cdef utxo_map _data
    
    def __init__(self):
        self._data = unordered_map[txid_key_t, _UtxEntry]()
    
    def __dealloc__(self):
        cdef _UtxEntry txdata
        cdef utxo_map_iter map_iter = self._data.begin()
        cdef utxo_map_iter end_iter = self._data.end()
        while map_iter != end_iter:
            txdata = dereference(map_iter).second
            _UtxEntry_dealloc(txdata)
            preincrement(map_iter)
        self._data.clear()

    
    @boundscheck(False)
    @wraparound(False)
    @nonecheck(False)
    def add_from_tx(self, tx):
        """
        Given a Tx, add its outputs as UTXOs.
        """
        cdef txid_key_t key
        cdef list outputs = tx.outputs

        # create a _UtxEntry to insert:
        cdef _UtxEntry txdata
        _UtxEntry_init_from_output_list(txdata, outputs, -1)  # TBD: set block_height

        # insert to the map:
        if txdata.num_unspent > 0:
            key = self._get_tx_key(tx)
            self._data[key] = txdata
    
    @boundscheck(False)
    @wraparound(False)
    @nonecheck(False)
    def spend(self, bytesview spent_txid, osize_t spent_output_idx):
        """
        Find and remove a specific UTXO.
        :return: the newly-spent TxOutput
        :raise: KeyError if not found or already spent
        """
        cdef uint8_t is_last
        cdef txid_key_t key = self._get_tx_key_from_txid(spent_txid)
        
        # NOTE: self._data.find(key) returns a ref to a _UtxEntry, which is good.
        # However, creating a reference variable doesn't work... (https://github.com/cython/cython/issues/1108)
        # To bypass, we use a pointer (txdata_p), and then dereference() it.
        cdef _UtxEntry *txdata_p
        cdef value_pair spent_info

        cdef utxo_map_iter map_iter = self._data.find(key)
        cdef utxo_map_iter end_iter = self._data.end()
        if map_iter == end_iter:
            raise ValueError('Tx not found in UtxoSet: %s' % bytes_to_hash_hex(spent_txid))

        txdata_p = &(dereference(map_iter).second)
        spent_info = self._pop_output(dereference(txdata_p), spent_output_idx)
        if spent_info.second:  # second=is_last
            # last output has now been spent. discard entry
            _UtxEntry_dealloc(dereference(txdata_p))
            self._data.erase(key)
        return self._to_txoutput(spent_info.first)  # first=value

    @boundscheck(False)
    @wraparound(False)
    @nonecheck(False)
    cdef txid_key_t _get_tx_key_from_txid(self, bytesview txid):
        # this implementation assumes TXID_PREFIX_SIZE=8 !
        return bytes2uint64(txid, <uint8_t>TXID_PREFIX_SIZE)
    
    @boundscheck(False)
    @wraparound(False)
    @nonecheck(False)
    cdef value_pair _pop_output(self, _UtxEntry &txdata, osize_t idx):
        cdef btc_value o
        cdef value_pair spent_info
        with nogil:
            o = _UtxEntry_spend(txdata, idx)
            # first=value, second=is_last
            spent_info.first = o
            spent_info.second = (txdata.num_unspent == 0)
            return spent_info

    @boundscheck(False)
    @wraparound(False)
    @nonecheck(False)
    cdef TxOutput _to_txoutput(self, btc_value value):
        # arg is just the value
        return TxOutput(value, None)  # TBD: support setting script
    
    @boundscheck(False)
    @wraparound(False)
    @nonecheck(False)
    cdef txid_key_t _get_tx_key(self, tx):
        # HACK: due to that cython bug, we need to convert the bytes to a writable buffer
        cdef bytearray txid_buf = bytearray(tx.txid)  # TBD avoid the bytearray copying...
        return self._get_tx_key_from_txid(txid_buf)
    
    def __repr__(self):
        return '<%s (%s txs)>' % (type(self).__name__, self._data.size())

    # pickle support
    # TBD: when the set is big, the temporary pickleable state created by __getstate__ can
    # be too big, and make us run out of memory...
    
    def __getstate__(self):
        cdef _UtxEntry txdata
        cdef utxo_map_iter map_iter = self._data.begin()
        cdef utxo_map_iter end_iter = self._data.end()
        state = []
        while map_iter != end_iter:
            key = dereference(map_iter).first
            txdata = dereference(map_iter).second
            value = _UtxEntry_getstate(txdata)
            state.append((key, value))
            preincrement(map_iter)
        return state
    
    def __setstate__(self, state):
        cdef _UtxEntry txdata
        for key, value in state:
            txdata = _UtxEntry_fromstate(value)
            self._data[key] = txdata

################################################################################
