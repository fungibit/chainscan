
cimport numpy as cnp
import numpy as np
ctypedef cnp.ndarray ndarray
array = np.array

from .defs import SATOSHIS_IN_ONE


#===================================================================================================================
# General purpose definitions
#===================================================================================================================

cdef:
    ctypedef bint bool_t
    ctypedef unsigned char byte
    ctypedef bytes bytes_t
    ctypedef byte[:] bytesview


cdef inline bytes_t to_bytes(bytesview x):
    return bytes(x)

#===================================================================================================================
# Bitcoin-related definitions
#===================================================================================================================

#cdef unsigned int MAGIC = 0xD9B4BEF9
#cdef unsigned int MAGIC_ABORT = 0x00
DEF MAGIC = 0xD9B4BEF9
DEF MAGIC_ABORT = 0x00

cdef:
    ctypedef unsigned long btc_value

from .defs import COINBASE_SPENT_TXID, COINBASE_SPENT_OUTPUT_INDEX, TXID_PREFIX_SIZE

#===================================================================================================================
# Misc utility functions
#===================================================================================================================

cpdef unsigned int bytes2uint32(bytesview buf):
    return _bytes2uint32(buf, len(buf))

cdef unsigned int _bytes2uint32(bytesview buf, unsigned char len):
    cdef unsigned char i, c
    cdef unsigned int x = 0
    cdef unsigned int exp = 1
    for i in range(len):
        c = buf[i]
        x += c * exp
        exp <<= 8
    return x

cpdef unsigned long long bytes2uint64(bytesview buf):
    return _bytes2uint64(buf, len(buf))

cdef unsigned long long _bytes2uint64(bytesview buf, unsigned char len):
    cdef unsigned char i, c
    cdef unsigned long long x = 0
    cdef unsigned long long exp = 1
    for i in range(len):
        c = buf[i]
        x += c * exp
        exp <<= 8
    return x

cpdef tuple parse_varlen_integer(bytesview buf):
    """
    See: https://wiki.bitcoin.com/w/Protocol_specification#Variable_length_integer
    :return: 2-tuple of (value, num_bytes_consumed)
    """
    return _parse_varlen_integer(buf)


cdef tuple _parse_varlen_integer(bytesview buf):
    """
    See: https://wiki.bitcoin.com/w/Protocol_specification#Variable_length_integer
    :return: 2-tuple of (value, num_bytes_consumed)
    """
    cdef unsigned char v1
    cdef unsigned char consume_end
    v1 = buf[0]
    if v1 < 0xFD:
        return v1, 1
    if v1 == 0xFD:
        consume_end = 3
    elif v1 == 0xFE:
        consume_end = 5
    elif v1 == 0xFF:
        consume_end = 9
    #consume_end = 1 + 2**(v1 - 0xFC)
    return (
        _bytes2uint32(buf[1 : consume_end], consume_end-1),
        consume_end,
    )


#===================================================================================================================
# Basic bitcoin-entities parsing functions
#===================================================================================================================


cpdef split_block(bytesview buf):

    cdef unsigned int magic
    cdef size_t block_size
    magic = _bytes2uint32(buf, 4)
    if magic == MAGIC:
        pass # ok, beginning of a block
    elif magic == MAGIC_ABORT:
        return None, None, None  # past last block
    else:
        assert 0, magic
    block_size = _bytes2uint32(buf[4:], 4)
    return magic, block_size, 8

cpdef tuple split_tx(bytesview buf):
    cdef size_t idx, num_inputs, consumed, offset = 0

    version = _bytes2uint32(buf, 4)
    offset += 4
    
    # inputs
    num_inputs, consumed = _parse_varlen_integer(buf[offset:])
    offset += consumed
    inputs_split = []
    for idx in range(num_inputs):
        x, consumed = _split_tx_input(buf[offset:])
        inputs_split.append(x)
        offset += consumed
    
    # outputs
    num_outputs, consumed = _parse_varlen_integer(buf[offset:])
    offset += consumed
    outputs_split = []
    for idx in range(num_outputs):
        x, consumed = _split_tx_output(buf[offset:])
        outputs_split.append(x)
        offset += consumed
    
    locktime = _bytes2uint32(buf, 4)
    offset += 4
    
    return version, inputs_split, outputs_split, locktime, offset

cpdef tuple _split_tx_input(bytesview buf):
    #cdef bytesview initial_buf = buf
    cdef size_t script_len, consumed
    spent_txid = to_bytes(buf[:32])
    buf = buf[32:]
    spent_output_idx = _bytes2uint32(buf, 4)
    buf = buf[4:]
    script_len, script_len_consumed = _parse_varlen_integer(buf)
    buf = buf[script_len_consumed:]
    script = to_bytes(buf[:script_len])
    buf = buf[script_len:]
    sequence = _bytes2uint32(buf, 4)
    #buf = buf[4:]
    consumed = 32 + 4 + 4 + script_len_consumed + script_len
    return ( ( spent_txid, spent_output_idx, script, sequence ), consumed )

cpdef tuple _split_tx_output(bytesview buf):
    #cdef bytesview initial_buf = buf
    cdef size_t script_len, consumed
    value = _bytes2uint64(buf, 8)
    buf = buf[8:]
    script_len, script_len_consumed = _parse_varlen_integer(buf)
    buf = buf[script_len_consumed:]
    script = to_bytes(buf[:script_len])
    buf = buf[script_len:]
    consumed = 8 + script_len_consumed + script_len
    return ( ( value, script ), consumed )


#===================================================================================================================
# Bitcoin entity classes (the rest are defined in entities.py)
#===================================================================================================================

cdef class TxOutput:
    """
    A bitcoin transaction output.
    """

    cdef public btc_value value
    cdef public bytes_t script
    
    def __init__(self, btc_value value, bytes_t script):
        self.value = value
        self.script = script
        
    def __repr__(self):
        return '<TxOutput (BTC%.6f)>' % ( self.value / SATOSHIS_IN_ONE, )


cdef class TxInput:
    """
    A bitcoin transaction input.
    """

    # class-member definitions
    is_coinbase = False

    # instance-member definitions
    cdef public bytes_t spent_txid
    cdef public unsigned long spent_output_idx
    cdef public bytes_t script
    cdef public unsigned long sequence
    cdef public object spent_output
    

    def __init__(self,
            bytes_t spent_txid,
            unsigned long spent_output_idx,
            bytes_t script,
            unsigned long sequence,
            object spent_output = None,
            ):
        self.spent_txid = spent_txid
        self.spent_output_idx = spent_output_idx
        self.script = script
        self.sequence = sequence
        self.spent_output = spent_output

    @property
    def spent_txid_hex(self):
        return bytes_to_hash_hex(self.spent_txid)
    
    def __repr__(self):
        return '<TxInput spending %s:%s>' % ( self.spent_txid.hex(), self.spent_output_idx )
        
    # The following are only usable if spent_output is set
    
    @property
    def value(self):
        return self.spent_output.value


cdef class CoinbaseTxInput:
    """
    A bitcoin coinbase-transaction input.
    """

    # class-member definitions
    is_coinbase = True
    spent_txid = COINBASE_SPENT_TXID
    spent_output_idx = COINBASE_SPENT_OUTPUT_INDEX
    spent_output = None
    value = 0

    # instance-member definitions
    cdef public bytes_t script
    cdef unsigned long sequence

    
    def __init__(self, bytes_t script, unsigned long sequence):
        self.script = script
        self.sequence = sequence
        
    def __repr__(self):
        return '<TxInput {COINBASE}>'

#===================================================================================================================
# Tracked spending related classes and functions
#===================================================================================================================


cdef:
    unsigned char txid_prefix_size = TXID_PREFIX_SIZE
    ctypedef unsigned int osize_t
    
# we can represent txid_key_t as unsigned long long only if txid_prefix_size<=8
assert txid_prefix_size <= 8, txid_prefix_size
ctypedef unsigned long long txid_key_t


cdef class _UtxEntry:
    """
    An entry in the UtxoSet data structure.
    """

    cdef public ndarray outputs
    cdef public osize_t num_unspent

    
    def __init__(self, list outputs):
        cdef osize_t n = len(outputs)
        self.outputs = array([ o.value for o in outputs ], dtype = 'uint64')
        self.num_unspent = n

    def __dealloc__(self):
        self.outputs = None

    def __repr__(self):
        return '<_UtxEntry %d/%d unspent>' % ( self.num_unspent, len(self.outputs) )
        
    # pickle support
    
    def __getstate__(self):
        return ( self.outputs, self.num_unspent )
    
    def __setstate__(self, state):
        self.outputs, self.num_unspent = state


cdef class UtxoSet:
    """
    A data structure holding all the unspent tx outputs (UTXOs)
    """
    
    # TBD: the dict here consumes too much memory. better to use cython's unordered_map
    cdef readonly dict _data
    
    
    def __init__(self, data = None):
        if data is None:
            data = {}
        self._data = data
    
    cpdef add_from_tx(self, tx):
        """
        Given a Tx, add its outputs as UTXOs.
        """
        cdef txid_key_t key = self._get_tx_key(tx)
        cdef _UtxEntry txdata = self._create_tx_data(tx)
        if txdata is not None:
            self._data[key] = txdata
    
    cpdef TxOutput spend(self, bytes_t spent_txid, osize_t spent_output_idx):
        """
        Find and remove a specific UTXO.
        :return: the newly-spent TxOutput
        :raise: KeyError if not found or already spent
        """
        cdef bool_t is_last
        cdef txid_key_t key = self._get_tx_key_from_txid(spent_txid)
        cdef _UtxEntry txdata = self._data[key]
        cdef tuple pair = self._pop_output(txdata, spent_output_idx)
        output, is_last = pair
        if is_last:
            # last output has now been spent. discard entry
            self._data.pop(key, None)
        return self._to_txoutput(output)

    cdef txid_key_t _get_tx_key_from_txid(self, bytes_t txid):
    
        # HACK: due to that cython bug, we need to convert the bytes to a writable buffer:
        cdef byte[:] txid_buf = np.frombuffer(txid, dtype=np.uint8).copy()        
    
        # this implementation assumes txid_prefix_size=8 !
        return _bytes2uint64(txid_buf, txid_prefix_size)
    
    cdef _create_tx_data(self, tx):
        cdef _UtxEntry entry = _UtxEntry(tx.outputs)
        return entry if entry.num_unspent else None
    
    cdef tuple _pop_output(self, _UtxEntry txdata, osize_t idx):
        cdef osize_t num_unspent = txdata.num_unspent
        outputs = txdata.outputs
        o = outputs[idx]
        #if o is not None:
        if o:
            #outputs[idx] = None
            outputs[idx] = 0
            txdata.num_unspent -= 1
            return o, txdata.num_unspent == 0
        else:
            return o, False

    cdef TxOutput _to_txoutput(self, btc_value output):
        # arg is just the value
        return TxOutput(output, None)
    
    cdef txid_key_t _get_tx_key(self, tx):
        return self._get_tx_key_from_txid(tx.txid)
    
    def __repr__(self):
        return '<%s (%s txs)>' % (type(self).__name__, len(self._data))

    # pickle support
    
    def __getstate__(self):
        return ( self._data, )
    
    def __setstate__(self, state):
        self._data, = state


#===================================================================================================================

cdef str bytes_to_hash_hex(bytes_t b):
    return b[::-1].hex()

#===================================================================================================================

