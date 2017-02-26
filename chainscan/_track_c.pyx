
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
from chainscan._common_c cimport bytes2uint64, bytes_to_hash_hex, copy_bytes_to_carray
from chainscan._block_c cimport Block
from chainscan._tx_c cimport TxOutput

from chainscan.misc import Bunch


################################################################################

cdef:
    ctypedef uint32_t osize_t
    ctypedef void *voidp
    
# we can represent txid_key_t as uint64_t only if TXID_PREFIX_SIZE<=8
assert TXID_PREFIX_SIZE <= 8, TXID_PREFIX_SIZE
ctypedef uint64_t txid_key_t

DEF OUTPUT_SPENT_MARKER = 0xffffffff  # max uint32


################################################################################
# UTX OUTPUT

cdef struct _UtxOutput:
    # The per-output data stored in a _UtxEntry
    btc_value value
    uint32_t script_len
    uint8_t *script


@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cdef void _UtxOutput_init(_UtxOutput &self, txoutput, uint8_t include_script):
    cdef uint32_t n
    cdef bytes script = txoutput.script

    self.value = txoutput.value
    if include_script and script is not None:
        n = len(script)
        self.script_len = n
        self.script = copy_bytes_to_carray(script, n)
        if not self.script:
            raise MemoryError()
    else:
        self.script_len = 0
        self.script = NULL

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cdef void _UtxOutput_dealloc(_UtxOutput &self) nogil:
    self.value = OUTPUT_SPENT_MARKER
    if self.script != NULL:
        free(self.script)
        self.script = NULL

cdef _UtxOutput_getstate(_UtxOutput &self):
    if self.script != NULL:
        script_bytes = bytes(self.script[:self.script_len])
    else:
        script_bytes = None
    return ( self.value, script_bytes )

cdef _UtxOutput _UtxOutput_fromstate(state):
    cdef _UtxOutput self
    value, script_bytes = state  # note: script_bytes may be None
    _UtxOutput_init(self, TxOutput(value, script_bytes), True)
    return self


################################################################################
# UTX ENTRY
    
cdef struct _UtxEntry:
    # An entry in the UtxoSet data structure (including all outputs
    # of the unspent tx).
    _UtxOutput *outputs
    osize_t num_outputs
    osize_t num_unspent
    int block_height

cdef struct _UtxoSpendingInfo:
    # per-output data about spending (including data from _UtxEntry and
    # the relevant _UtxOutput)
    _UtxOutput *output
    int block_height
    uint8_t is_last


@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cdef void _UtxEntry_init_from_tx(_UtxEntry &self, tx, uint8_t include_scripts):

    cdef list outputs = tx.outputs
    cdef osize_t n = len(outputs)
    cdef Block block
    cdef int block_height
    
    # use block.height if tx includes block-context (i.e. tx is a TxInBlock).
    # else, use block_height=-1
    block = getattr(tx, 'block', None)
    block_height = block.height if block is not None else -1

    _UtxEntry_init_basic(self, n, block_height)

    # outputs
    self.outputs = <_UtxOutput*>malloc(n * sizeof(_UtxOutput))
    if not self.outputs:
        raise MemoryError()
    for i in range(n):
        o = outputs[i]
        _UtxOutput_init(self.outputs[i], o, include_scripts)

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
cdef void _UtxEntry_dealloc(_UtxEntry &self, uint8_t deep) nogil:
    if self.outputs!= NULL:
        # Note: it is safe to call _UtxOutput_dealloc() multiple times.
        if deep:
            for i in range(self.num_outputs):
                _UtxOutput_dealloc(self.outputs[i])
        free(self.outputs)
        self.outputs = NULL

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cdef void _UtxEntry_spend(_UtxEntry &self, _UtxoSpendingInfo &spending_info, osize_t idx) nogil:
    # NOTE: we "remove" the output from self by decrementing self.num_unspent.
    # we don't deallocate the _UtxOutput data. we pass ownership of it to the caller,
    # which later calls _UtxOutput_dealloc() on it.
    spending_info.output = &(self.outputs[idx])
    spending_info.block_height = self.block_height
    # remove this output from self:
    if spending_info.output.script_len != <uint32_t>OUTPUT_SPENT_MARKER:
        self.num_unspent -= 1
    spending_info.is_last = (self.num_unspent == 0)

cdef _UtxEntry_getstate(_UtxEntry &self):
    cdef osize_t i
    outputs = [ _UtxOutput_getstate(self.outputs[i]) for i in range(self.num_outputs) ]
    return ( outputs, self.block_height, self.num_unspent )

cdef _UtxEntry _UtxEntry_fromstate(state):
    cdef _UtxEntry self
    cdef osize_t n, i
    ( outputs, self.block_height, self.num_unspent ) = state
    n = len(outputs)
    _UtxEntry_init_basic(self, n, self.block_height)
    # outputs
    self.outputs = <_UtxOutput*>malloc(n * sizeof(_UtxOutput))
    if not self.outputs:
        raise MemoryError()
    for i in range(n):
        self.outputs[i] = _UtxOutput_fromstate(outputs[i])
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
    cdef readonly uint8_t include_scripts
    
    def __init__(self, include_scripts = False):
        self._data = unordered_map[txid_key_t, _UtxEntry]()
        self.include_scripts = include_scripts
    
    def __dealloc__(self):
        cdef _UtxEntry txdata
        cdef utxo_map_iter map_iter = self._data.begin()
        cdef utxo_map_iter end_iter = self._data.end()
        while map_iter != end_iter:
            txdata = dereference(map_iter).second
            _UtxEntry_dealloc(txdata, True)
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
        cdef _UtxEntry txdata
        # create a _UtxEntry to insert:
        _UtxEntry_init_from_tx(txdata, tx, self.include_scripts)
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
        :return: a Bunch object representing spending_info
        :raise: KeyError if not found or already spent
        """
        cdef _UtxoSpendingInfo spending_info
        cdef _UtxEntry *txdata_p
        cdef utxo_map_iter map_iter, end_iter
        cdef txid_key_t key = self._get_tx_key_from_txid(spent_txid)
        
        with nogil:
            map_iter = self._data.find(key)
            end_iter = self._data.end()
            if map_iter == end_iter:
                with gil:
                    raise KeyError('Tx not found in UtxoSet: %s' % bytes_to_hash_hex(spent_txid))
            self._pop_utxo(map_iter, spending_info, spent_output_idx)  # modifies spending_info inplace
            
        txoutput = self._to_txoutput(spending_info)
        
        # need to deallocate the output, whose ownership was passed to us
        _UtxOutput_dealloc(dereference(spending_info.output))
        if spending_info.is_last:
            # last output has now been spent. discard entry
            txdata_p = &(dereference(map_iter).second)
            _UtxEntry_dealloc(dereference(txdata_p), False)
            self._data.erase(map_iter)
        
        return txoutput

    @boundscheck(False)
    @wraparound(False)
    @nonecheck(False)
    cdef txid_key_t _get_tx_key_from_txid(self, bytesview txid):
        # this implementation assumes TXID_PREFIX_SIZE=8 !
        return bytes2uint64(txid, <uint8_t>TXID_PREFIX_SIZE)
    
    @boundscheck(False)
    @wraparound(False)
    @nonecheck(False)
    cdef void _pop_utxo(self, utxo_map_iter map_iter, _UtxoSpendingInfo &spending_info, osize_t idx) nogil:
        # NOTE: self._data.find(key) returns an iterator which references a _UtxEntry.
        # However, creating a reference variable doesn't work... (https://github.com/cython/cython/issues/1108)
        # To bypass, we use a pointer (txdata_p), and then dereference() it.
        #  [1]  dereference(map_iter) --> a reference to [T,U]
        #  [2]  [1].second --> a reference to U (the value)
        #  [3]  &([2]) --> a pointer to the value
        #  [4]  dereference([3]) --> a reference to the value
        cdef _UtxEntry *txdata_p = &(dereference(map_iter).second)
        _UtxEntry_spend(dereference(txdata_p), spending_info, idx)

    @boundscheck(False)
    @wraparound(False)
    @nonecheck(False)
    cdef _to_txoutput(self, _UtxoSpendingInfo &spending_info):
        cdef _UtxOutput *output = spending_info.output
        cdef uint8_t *oscript = output.script
        cdef bytesview scriptview
        if oscript != NULL:
            if output.script_len > 0:
                scriptview = <uint8_t[ : output.script_len : 1 ]>oscript  # this doesn't work if script_len=0...
            else:
                scriptview = bytearray(b'')
        else:
            scriptview = None
        txoutput = TxOutput(output.value, scriptview)
        return Bunch(
            spent_output = txoutput,
            block_height = spending_info.block_height,
        )
    
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
