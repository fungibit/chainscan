
#include <stdint.h>
#include <malloc.h>
#include <cstddef>
#include <unordered_map>
#include <iostream>

using namespace std;


////////////////////////////////////////////////////////////////////////////////

typedef uint32_t osize_t;
typedef uint64_t txid_key_t;
typedef uint64_t btc_value;

// 0xffffffffffffffff = max(uint64_t)
#define OUTPUT_SPENT_MARKER 0xffffffffffffffff

////////////////////////////////////////////////////////////////////////////////
// UTX OUTPUT -- The per-output data stored in a CUtxEntry

class CUtxOutputBase {

public:

    btc_value value;

public:

    inline CUtxOutputBase() : value(0) {}
    inline CUtxOutputBase(btc_value value) : value(value) {}

    inline void dealloc() { this->value = OUTPUT_SPENT_MARKER; }

};

class CUtxOutputMinimal : public CUtxOutputBase {

public:

    inline CUtxOutputMinimal() {}
    inline CUtxOutputMinimal(btc_value value, uint32_t, uint8_t *) : CUtxOutputBase(value) {}
        
    inline void set(btc_value value, uint32_t, uint8_t *) {
        this->value = value;
    }
    
};

class CUtxOutputScript : public CUtxOutputBase {

public:
        
    uint32_t script_len;
    uint8_t *script;

public:

    inline CUtxOutputScript() { this->set(0, 0, NULL); }
    
    inline CUtxOutputScript(btc_value value, uint32_t script_len, uint8_t *script) {
        this->set(value, script_len, script);
    }

    inline void set(btc_value value, uint32_t script_len, uint8_t *script) {
        this->value = value;
        this->script_len = script_len;
        // Note: we use the given pointer, no copying.
        this->script = script;
    }
    
    inline void dealloc() {
        CUtxOutputBase::dealloc();
        if (this->script != NULL) {
            free(this->script);
            this->script = NULL;
        }
    }
        
};


////////////////////////////////////////////////////////////////////////////////
// SPENDING INFO: per-output data about spending (including data from CUtxEntry
// and the relevant CUtxOutput)

template <typename CUtxOutput>
class CUtxoSpendingInfo {
public:
    typedef CUtxOutput COutput;
public:
    CUtxOutput *output;
    int32_t block_height;
    bool is_last;
};


////////////////////////////////////////////////////////////////////////////////
// UTX ENTRY: an entry in the CUtxoSet data structure (including all outputs of
// the unspent tx)

template <typename CUtxOutput>
class CUtxEntry {

public:
    
    typedef CUtxOutput COutput;
    typedef CUtxoSpendingInfo<CUtxOutput> CSpendingInfo;
    
    
public:
    
    CUtxOutput *outputs;
    osize_t num_outputs;
    osize_t num_unspent;
    int32_t block_height;
    
public:

    CUtxEntry() : outputs(NULL), num_outputs(0), num_unspent(0), block_height(0) {}
    
    void _init(osize_t num_outputs, int32_t block_height) {
        this->block_height = block_height;
        this->num_outputs = num_outputs;
        this->num_unspent = num_outputs;
        this->outputs = new CUtxOutput[num_outputs];
    }
    
    void set_output(osize_t oidx, btc_value value, uint32_t script_len, uint8_t *script) {
        this->outputs[oidx].set(value, script_len, script);
    }

    void spend(CSpendingInfo &spending_info, osize_t idx) {
        // NOTE: we "remove" the output from self by decrementing num_unspent.
        // we don't deallocate the CUtxOutput data. we pass ownership of it to the caller,
        // which later calls CUtxOutput::dealloc() on it.
        spending_info.output = &(this->outputs[idx]);
        spending_info.block_height = this->block_height;
        // mark this output as spent:
        if (spending_info.output->value != OUTPUT_SPENT_MARKER) {
            this->num_unspent--;
        }
        spending_info.is_last = (this->num_unspent == 0);
    }

    void dealloc(bool deep) {
        // Note: it is safe to call dealloc() multiple times.
        if (this->outputs != NULL) {
            if (deep) {
                for (osize_t i = 0; i < this->num_outputs; ++i) {
                    this->outputs[i].dealloc();
                }
            }
            delete[] this->outputs;
            this->outputs = NULL;
        }
    }


};


////////////////////////////////////////////////////////////////////////////////
// UTXO SET

template <typename CUtxOutput>
class CUtxoSet {
    
public:
    
    typedef CUtxOutput COutput;
    typedef CUtxEntry<CUtxOutput> E;
    typedef typename E::CSpendingInfo CSpendingInfo;
    typedef unordered_map<txid_key_t, E> Map;
    typedef typename unordered_map<txid_key_t, E>::iterator MapIter;
    
public:

    Map _data;

public:

    ~CUtxoSet() {
        for (MapIter it = this->_data.begin(); it != this->_data.end(); ++it) {
            it->second.dealloc(true);
        }
        this->_data.clear();
    }

    E& add_tx(txid_key_t key, osize_t num_outputs, int32_t block_height) {
        E &new_utxentry = this->_data.operator[](key);
        new_utxentry._init(num_outputs, block_height);
        return new_utxentry;
    }
    
    bool spend_output(txid_key_t key, osize_t output_idx, CSpendingInfo& spending_info) {
        MapIter map_iter = this->_data.find(key);
        MapIter end_iter = this->_data.end();
        if (map_iter == end_iter) {
            return false;
        }
        this->_spend_utxo(map_iter, spending_info, output_idx);  // modifies spending_info inplace
        return true;
    }

    void _spend_utxo(MapIter map_iter, CSpendingInfo &spending_info, osize_t output_idx) {
        map_iter->second.spend(spending_info, output_idx);
    }

    void dealloc_output(txid_key_t key, CUtxOutput *output, bool is_last) {
        // need to deallocate the output, whose ownership was passed to us
        output->dealloc();
        if (is_last) {
            // last output has now been spent. discard entry
            // TBD: avoid the double-lookup (in spend_output(), then in dealloc_output())
            MapIter map_iter = this->_data.find(key);
            map_iter->second.dealloc(false);
            this->_data.erase(map_iter);
        }
    }
    
    uint64_t size() {
        return this->_data.size();
    }

};

////////////////////////////////////////////////////////////////////////////////

