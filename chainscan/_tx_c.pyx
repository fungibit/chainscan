"""
Transaction-related extension classes, and deserialization functionality, implemented
using Cython for speed.
"""

from cython cimport boundscheck, wraparound, nonecheck

include "consts.pxi"

from chainscan._common_c cimport uint32_t, uint64_t, bytesview, btc_value, varlenint_pair
from chainscan._common_c cimport bytes2uint32, bytes2uint64, bytes_to_hash_hex, deserialize_varlen_integer, doublehash

from chainscan.misc import Bunch


################################################################################
# TX-RELATED EXTENSION CLASSES
################################################################################

cdef class TxOutput:
    """
    A bitcoin transaction output.
    """
    
    def __init__(self, btc_value value, bytesview script):
        self.value = value
        self.script = bytes(script) if script is not None else None
        
    def __repr__(self):
        return '<TxOutput (BTC%.6f)>' % ( float(self.value) / SATOSHIS_IN_ONE, )

    # pickle support -- not using memoryviews, so can use simple __[gs]etstate__

    def __getstate__(self):
        return ( self.value, self.script )
    def __setstate__(self, state):
        self.value, self.script = state


cdef class TxInput:
    """
    A bitcoin transaction input.
    """

    def __init__(self,
            bytesview spent_txid,
            uint32_t spent_output_idx,
            bytesview script,
            uint32_t sequence,
            object spending_info = None,
            ):
        self._spent_txid = spent_txid
        self.spent_output_idx = spent_output_idx
        self.script = script
        self.sequence = sequence
        self.spending_info = spending_info

    property is_coinbase:
        def __get__(self):
            return False
        
    # _spent_txid is a memoryview. Useful to access this field as bytes
    property spent_txid:
        def __get__(self):
            return bytes(self._spent_txid)
    
    property spent_txid_hex:
        def __get__(self):
            return bytes_to_hash_hex(self._spent_txid)
    
    def __repr__(self):
        return '<TxInput spending %s:%s>' % ( self.spent_txid_hex, self.spent_output_idx )
        
    # The following are only usable if spending_info is set
    
    property spent_output:
        def __get__(self):
            return self.spending_info.spent_output
        
    property value:
        def __get__(self):
            return self.spending_info.spent_output.value

    property output_script:
        def __get__(self):
            return self.spending_info.spent_output.script

    # pickle support
    # Note we convert bytesview to bytearray, making copies. This means the restored objects
    # can use more memory than the original objects.
    
    def __getstate__(self):
        return (
            bytearray(self._spent_txid),
            self.spent_output_idx,
            bytearray(self.script),
            self.sequence,
            self.spending_info,
        )
    
    def __setstate__(self, state):
        (
            self._spent_txid,
            self.spent_output_idx,
            self.script,
            self.sequence,
            self.spending_info,
        ) = state


cdef class CoinbaseTxInput:
    """
    A bitcoin coinbase-transaction input.
    """

    SPENDING_INFO = Bunch(
        spent_output = None,
        block_height = -1,
    )

    def __init__(self, bytesview script, uint32_t sequence):
        self.script = script
        self.sequence = sequence
        
    property is_coinbase:
        def __get__(self):
            return True

    property spent_txid:
        def __get__(self):
            return COINBASE_SPENT_TXID

    property spent_output_idx:
        def __get__(self):
            return COINBASE_SPENT_OUTPUT_INDEX

    property spent_output:
        def __get__(self):
            return None

    property value:
        def __get__(self):
            return 0

    property spending_info:
        def __get__(self):
            return self.SPENDING_INFO

    def __repr__(self):
        return '<TxInput {COINBASE}>'

    # pickle support
    # Note we convert bytesview to bytearray, making copies. This means the restored objects
    # can use more memory than the original objects.
    
    def __getstate__(self):
        return (
            bytearray(self.script),
            self.sequence,
        )
    
    def __setstate__(self, state):
        (
            self.script,
            self.sequence,
        ) = state

cdef class Tx:
    """
    A bitcoin transaction.
    """
    
    def __init__(self,
                bytesview version_bytes,
                list inputs,
                list outputs,
                uint32_t locktime,
                bytearray txid,
                uint32_t rawsize,
                bytesview blob = None,
            ):
        self.version_bytes = version_bytes
        self.inputs = inputs
        self.outputs = outputs
        self.locktime = locktime
        self._txid = txid
        self.rawsize = rawsize
        self.blob = blob


    property version:
        def __get__(self):
            return bytes2uint32(self.version_bytes, 4)

    # _txid is a bytearray. Useful to access this field as bytes
    property txid:
        def __get__(self):
            return bytes(self._txid)

    property txid_hex:
        def __get__(self):
            return bytes_to_hash_hex(self._txid)

    property is_coinbase:
        def __get__(self):
            return self.inputs[0].is_coinbase

    def get_total_output_value(self):
        cdef TxOutput o
        return sum( o.value for o in self.outputs )

    # The following are only usable if spending_info is set on tx.inputs

    def get_total_input_value(self):
        return sum( i.value for i in self.inputs )
    
    def get_fee_paid(self):
        return self.get_total_input_value() - self.get_total_output_value()

    # Misc

    def __repr__(self):
        return '<Tx %s%s>' % ( self.txid_hex, ' {COINBASE}' if self.is_coinbase else '' )

    # pickle support
    # Note we convert bytesview to bytearray, making copies. This means the restored objects
    # can use more memory than the original objects.
    
    def __getstate__(self):
        return (
            bytearray(self.version_bytes),
            self.inputs,
            self.outputs,
            self.locktime,
            self._txid,
            self.rawsize,
            bytearray(self.blob) if self.blob is not None else self.blob,
        )
    
    def __setstate__(self, state):
        (
            self.version_bytes,
            self.inputs,
            self.outputs,
            self.locktime,
            self._txid,
            self.rawsize,
            self.blob,
        ) = state


################################################################################
# DESERIALIZATION
################################################################################

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cpdef Tx deserialize_tx(bytesview blob, bint include_blob = False):

    cdef:
        bytesview version_bytes
        size_t num_elements
        size_t consumed
        size_t offset
        varlenint_pair pair
        tuple pairtxio
        bytearray txid
    
    with nogil:
        
        version_bytes = blob[ : 4]
        offset = 4
        
        # inputs
        pair = deserialize_varlen_integer(blob[offset:])
        num_elements = pair.first
        offset += pair.second
        with gil:
            inputs = []
            while num_elements > 0:
                num_elements -= 1
                pairtxio = deserialize_tx_input(blob[offset:])
                inputs.append(pairtxio[0])
                offset += pairtxio[1]
        
        # outputs
        pair = deserialize_varlen_integer(blob[offset:])
        num_elements = pair.first
        offset += pair.second
        with gil:
            outputs = []
            while num_elements > 0:
                num_elements -= 1
                pairtxio = deserialize_tx_output(blob[offset:])
                outputs.append(pairtxio[0])
                offset += pairtxio[1]
        
        locktime = bytes2uint32(blob, 4)
        offset += 4

        blob = blob[:offset]
    
    txid = doublehash(blob)

    if inputs[0].spent_output_idx == COINBASE_SPENT_OUTPUT_INDEX:
        # coinbase tx -- replace TxInput with CoinbaseTxInput
        input0 = inputs[0]
        inputs[0] = CoinbaseTxInput(
            script = input0.script,
            sequence = input0.sequence,
        )
        
    if not include_blob:
        blob = None
        
    return Tx(
        version_bytes = version_bytes,
        inputs = inputs,
        outputs = outputs,
        locktime = locktime,
        txid = txid,
        rawsize = offset,
        blob = blob,
    )

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cpdef tuple deserialize_tx_input(bytesview buf):
    cdef:
        bytesview spent_txid
        bytesview script
        size_t script_len
        size_t consumed
        varlenint_pair pair
    
    with nogil:
        spent_txid = buf[:32]
        spent_output_idx = bytes2uint32(buf[32:], 4)
        consumed = 36
        pair = deserialize_varlen_integer(buf[consumed:])
        script_len = pair.first
        consumed += pair.second
        script = buf[consumed : consumed+script_len]
        consumed += script_len
        sequence = bytes2uint32(buf[consumed:], 4)
        consumed += 4

    return ( TxInput(spent_txid, spent_output_idx, script, sequence), consumed )

@boundscheck(False)
@wraparound(False)
@nonecheck(False)
cpdef tuple deserialize_tx_output(bytesview buf):
    
    cdef:
        uint64_t value
        bytesview script
        size_t script_len
        size_t consumed
        varlenint_pair pair
        
    with nogil:
    
        value = bytes2uint64(buf, 8)
        pair = deserialize_varlen_integer(buf[8:])
        consumed = 8
        script_len = pair.first
        consumed += pair.second
        script = buf[consumed : consumed+script_len]
        consumed += script_len
    
    return ( TxOutput(value, script), consumed )

