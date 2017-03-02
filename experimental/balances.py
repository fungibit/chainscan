"""
Simple code for tracking balances, in an address-to-balance mapping.
"""

from chainscan import iter_txs
from bitcoinscript.script import output_script_from_raw

# TBD: for memory efficiency, avoid the python-dict, use unordered_map
# with this dict, it takes ~2.5GB -- way too much
class Balances(dict):

    def add(self, addr, value):
        if value == 0:
            return
        v = self.get(addr) + value
        if v:
            self[addr] = v
        else:
            del self[addr]

    def subtract(self, addr, value):
        return self.add(addr, -value)

    def get(self, addr, default = 0):
        return super().get(addr, default)

def main():

    balances = Balances()
    for tx in iter_txs(track_scripts = True, show_progressbar = True):
        
        # outputs: add funds to receiver addresses
        for txoutput in tx.outputs:
            oscript = output_script_from_raw(txoutput.script)
            addr = oscript.get_address()
            if addr is not None:
                balances.add(addr.hash160, txoutput.value)
                
        # inputs: subtract funds from addresses being spent
        if not tx.is_coinbase:
            for txin in tx.inputs:
                txoutput = txin.spent_output
                oscript = output_script_from_raw(txoutput.script)
                addr = oscript.get_address()
                if addr is not None:
                    balances.subtract(addr.hash160, txoutput.value)

if __name__ == '__main__':
    main()
