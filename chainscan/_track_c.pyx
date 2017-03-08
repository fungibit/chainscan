
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

from chainscan._common_c cimport uint8_t, int32_t, uint32_t, uint64_t, bytesview, btc_value
from chainscan._common_c cimport bytes2uint64, bytes_to_hash_hex, copy_bytes_to_carray
from chainscan._block_c cimport Block
from chainscan._tx_c cimport TxOutput

from chainscan.misc import Bunch


################################################################################

cdef:
    ctypedef uint32_t osize_t
    
# we can represent txid_key_t as uint64_t only if TXID_PREFIX_SIZE<=8
assert TXID_PREFIX_SIZE <= 8, TXID_PREFIX_SIZE
ctypedef uint64_t txid_key_t


################################################################################

cdef extern from "_utxo.hpp" nogil:

    cdef cppclass CUtxOutputMinimal:
        uint64_t value
        void set(btc_value value, uint32_t script_len, uint8_t *script)

    cdef cppclass CUtxOutputScript:
        btc_value value
        uint32_t script_len
        uint8_t *script
        void set(btc_value value, uint32_t script_len, uint8_t *script)
    
    cdef cppclass CUtxoSpendingInfo[CUtxOutput]:
        CUtxOutput *output
        int32_t block_height
        bint is_last

    cdef cppclass CUtxEntry[CUtxOutput]:
        void set_output(osize_t oidx, btc_value value, uint32_t script_len, uint8_t *script)

    cdef cppclass CUtxoSet[CUtxOutput]:
        CUtxEntry[CUtxOutput]& add_tx(txid_key_t key, osize_t num_outputs, int32_t block_height) except +
        bint spend_output(txid_key_t key, osize_t output_idx, CUtxoSpendingInfo[CUtxOutput]& spending_info)
        void dealloc_output(txid_key_t key, CUtxOutput *output, bint is_last)
        uint64_t size()


################################################################################
# UTXO SET

cdef:
    ctypedef CUtxOutputMinimal _Output1
    ctypedef CUtxOutputScript  _Output2
    ctypedef CUtxoSpendingInfo[_Output1] _SInfo1
    ctypedef CUtxoSpendingInfo[_Output2] _SInfo2
    ctypedef CUtxEntry[_Output1] _Entry1
    ctypedef CUtxEntry[_Output2] _Entry2
    ctypedef CUtxoSet[_Output1] _Set1
    ctypedef CUtxoSet[_Output2] _Set2

cdef fused _OutputX:
    _Output1
    _Output2
    
cdef fused _SInfoX:
    _SInfo1
    _SInfo2
    
cdef fused _EntryX:
    _Entry1
    _Entry2
    
cdef fused CUtxoSetX:
    _Set1
    _Set2

cdef class UtxoSet:
    """
    A data structure holding all the unspent tx outputs (UTXOs)
    """
    
    cdef _Set1 _data1
    cdef _Set2 _data2
    cdef void *_dataptr
    cdef readonly bint include_scripts
    
    def __init__(self, include_scripts = False):
        self.include_scripts = include_scripts
        if include_scripts:
            self._dataptr = &(self._data2)
        else:
            self._dataptr = &(self._data1)
    
    @boundscheck(False)
    @wraparound(False)
    @nonecheck(False)
    def add_from_tx(self, tx):
        """
        Given a Tx, add its outputs as UTXOs.
        """
        
        cdef txid_key_t key = self._get_tx_key(tx)
        cdef list outputs = tx.outputs
        cdef osize_t num_outputs = len(outputs)
        cdef osize_t oidx
        cdef btc_value value
        cdef bytes script
        cdef uint32_t script_len
        cdef uint8_t *scriptptr
        cdef int block_height
        cdef _Entry1 *entry1
        cdef _Entry2 *entry2

        # use block.height if tx includes block-context (i.e. tx is a TxInBlock).
        # else, use block_height=-1
        block = getattr(tx, 'block', None)
        block_height = block.height if block is not None else -1

        if self.include_scripts:
            entry2 = &(<_Set2*>self._dataptr).add_tx(key, num_outputs, block_height)

            for oidx in range(num_outputs):
                o = outputs[oidx]
                value = o.value
                script = o.script
                script_len = len(script)
                scriptptr = copy_bytes_to_carray(script, script_len)
                if scriptptr == NULL:
                    raise MemoryError()
                entry2.set_output(oidx, value, script_len, scriptptr)

        else:
            entry1 = &(<_Set1*>self._dataptr).add_tx(key, num_outputs, block_height)

            for oidx in range(num_outputs):
                o = outputs[oidx]
                value = o.value
                entry1.set_output(oidx, value, 0, NULL)
        
    @boundscheck(False)
    @wraparound(False)
    @nonecheck(False)
    def spend(self, bytesview spent_txid, osize_t spent_output_idx):
        """
        Find and remove a specific UTXO.
        :return: a Bunch object representing spending_info
        :raise: KeyError if not found or already spent
        """
        cdef txid_key_t key = self._get_tx_key_from_txid(spent_txid)
        cdef _SInfo1 sinfo1
        cdef _SInfo2 sinfo2
        cdef bint found

        if self.include_scripts:
            found = (<_Set2*>self._dataptr).spend_output(key, spent_output_idx, sinfo2)
            if not found:
                raise KeyError('Tx not found in UtxoSet: %s' % bytes_to_hash_hex(spent_txid))
            txoutput = _spending_info2_to_txoutput(sinfo2)
            # need to deallocate the output, whose ownership was passed to us
            (<_Set2*>self._dataptr).dealloc_output(key, sinfo2.output, sinfo2.is_last)
        else:
            found = (<_Set1*>self._dataptr).spend_output(key, spent_output_idx, sinfo1)
            if not found:
                raise KeyError('Tx not found in UtxoSet: %s' % bytes_to_hash_hex(spent_txid))
            txoutput = _spending_info1_to_txoutput(sinfo1)
            # need to deallocate the output, whose ownership was passed to us
            (<_Set1*>self._dataptr).dealloc_output(key, sinfo1.output, sinfo1.is_last)
        
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
    cdef txid_key_t _get_tx_key(self, tx):
        # HACK: due to that cython bug, we need to convert the bytes to a writable buffer
        cdef bytearray txid_buf = bytearray(tx.txid)  # TBD avoid the bytearray copying...
        return self._get_tx_key_from_txid(txid_buf)
    
    def __repr__(self):
        return '<%s (%s txs)>' % (type(self).__name__, len(self))

    def __len__(self):
        if self.include_scripts:
            return (<_Set2*>self._dataptr).size()
        else:
            return (<_Set1*>self._dataptr).size()
    

    # pickle support
    # TBD: when the set is big, the temporary pickleable state created by __getstate__ can
    # be too big, and make us run out of memory...

    # TBD: not currently supported    
    def __getstate__(self):
        return ( self.include_scripts, )
    def __setstate__(self, state):
        include_scripts, = state
        self.__init__(include_scripts)

#    def __getstate__(self):
#        if self.include_scripts:
#            data = dereference(<_Set2*>self._dataptr)
#        else:
#            data = dereference(<_Set1*>self._dataptr)
#        map_iter = data.begin()
#        end_iter = data.end()
#        data = []
#        while map_iter != end_iter:
#            key = dereference(map_iter).first
#            txdata = dereference(map_iter).second
#            value = txdata.getstate()
#            data.append((key, value))
#            preincrement(map_iter)
#        return ( data, self.include_scripts )
#    
#    def __setstate__(self, state):
#        data, include_scripts = state
#        self.__init__(include_scripts)
#        if self.include_scripts:
#            data = dereference(<_Set2*>self._dataptr)
#        else:
#            data = dereference(<_Set1*>self._dataptr)
#        for key, value in data:
#            if self.include_scripts:
#                txdata = _Entry2.fromstate(value)
#            else:
#                txdata = _Entry1.fromstate(value)
#            data[key] = txdata


@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cdef _spending_info1_to_txoutput(_SInfo1 &spending_info):
    cdef _Output1 *output = spending_info.output
    txoutput = TxOutput(output.value, None)
    return Bunch(
        spent_output = txoutput,
        block_height = spending_info.block_height,
    )

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cdef _spending_info2_to_txoutput(_SInfo2& spending_info):
    cdef _Output2 *output = spending_info.output
    cdef bytesview scriptview
    cdef uint8_t *oscript = output.script
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

################################################################################
