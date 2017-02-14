"""
Miscellaneous functions used throughout this package.
"""

from hashlib import sha256
from decimal import Decimal

from .defs import SATOSHIS_IN_ONE

# make these importable from here:
from .cyt import bytes2uint32, bytes2uint64

#===================================================================================================================
# unit conversion
#===================================================================================================================

def satoshi2float(x):
    return x / SATOSHIS_IN_ONE

def satoshi2decimal(x):
    return Decimal(x) / SATOSHIS_IN_ONE

# aliases
s2f = satoshi2float
s2d = satoshi2decimal

#===================================================================================================================
# hash related
#===================================================================================================================

def doublehash(x):
    return sha256(sha256(x).digest()).digest()

def bytes_to_hash_hex(b):
    return b[::-1].hex()

def hash_hex_to_bytes(hash_hex):
    return bytes.fromhex(hash_hex)[::-1]

#===================================================================================================================
# other
#===================================================================================================================

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


# taken from here: https://code.activestate.com/recipes/52308-the-simple-but-handy-collector-of-a-bunch-of-named/
class Bunch:
    def __init__(self, **kwds):
        self.__dict__.update(kwds)

#===================================================================================================================
