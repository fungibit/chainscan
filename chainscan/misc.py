"""
Miscellaneous functions used throughout this package.
"""

from decimal import Decimal

from .defs import SATOSHIS_IN_ONE

# make these importable from here:
from ._common_c import doublehash, bytes2uint32, bytes2uint64, bytes_to_hash_hex, deserialize_varlen_integer
# avoid pyflakes "imported but unused" warnings:
doublehash, bytes2uint32, bytes2uint64, bytes_to_hash_hex, deserialize_varlen_integer


################################################################################
# unit conversion
################################################################################

def satoshi2float(x):
    return x / SATOSHIS_IN_ONE

def satoshi2decimal(x):
    return Decimal(x) / SATOSHIS_IN_ONE

# aliases
s2f = satoshi2float
s2d = satoshi2decimal

################################################################################
# other
################################################################################

def hash_hex_to_bytes(hash_hex):
    return bytes.fromhex(hash_hex)[::-1]


class FilePos:
    """
    A position within a file.
    """
    
    def __init__(self, filename, offset):
        self.filename = filename
        self.offset = offset
        
    def __repr__(self):
        return '%s(%r, %s)' % (type(self).__name__, self.filename, self.offset)

    def __str__(self):
        return '%r, offset %s' % (self.filename, self.offset)


class Bunch(dict):
    """ A dict which allows accessing its items using attribute-access. """

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)
    
    def __setattr__(self, k, v):
        self[k] = v        
    
    def __delattr__(self, k):
        del self[k]        
    
    def __dir__(self):
        return dir({}) + list(self.keys())

################################################################################
