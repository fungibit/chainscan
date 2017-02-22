"""
Definition of some constants used in this package.

:note: the constants are defined in `consts.pxi`.  We automagically "import" those
    consts to be defined here as well.
"""

import os
import ast
_consts_path = os.path.join(os.path.dirname(__file__), 'consts.pxi')
with open(_consts_path) as f:
    for line in f:
        if line.startswith('DEF '):
            k, d, v = line[4:].partition('=')
            globals()[k.strip()] = ast.literal_eval(v.strip())
        
del f, line, k, d, v
