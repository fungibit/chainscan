"""
Code for generating artificial block data in the format of a blk.dat file,
which includes forks. Used for testing.
"""

import datetime

from chainscan.defs import MAGIC
from chainscan.entities import Block

FORKED_NONCE = 0xffffffff

block_counter = 0

def make_block(height, prev_block_hash, nonce = None):
    global block_counter
    block_counter += 1
    #blob = b''
    version = to_bytes(1, 4)
    merkle_root = to_bytes(0, 32)
    t = datetime.datetime(2009, 1, 9) + block_counter * datetime.timedelta(minutes = 10)
    timestamp = to_bytes(int(t.timestamp()), 4)
    difficulty = b'\xff\xff\x00\x1d'
    if nonce is None:
        nonce = height
    nonce = to_bytes(nonce, 4)
    num_txs = to_bytes(0, 1)  # if num_txs>0xfc, need to properly format a varlen int

    blob = \
        version + \
        prev_block_hash + \
        merkle_root + \
        timestamp + \
        difficulty + \
        nonce + \
        num_txs
    
    size = len(blob)
    blob = MAGIC + to_bytes(size, 4) + blob
    return Block(memoryview(blob), height)

def gen_blocks(next_height, prev_block_hash, num_blocks, **kwargs):
    blocks = []
    while len(blocks) < num_blocks:
        block = make_block(next_height, prev_block_hash, **kwargs)
        blocks.append(block)
        next_height += 1
        prev_block_hash = blocks[-1].block_hash
    return blocks

def to_bytes(x, n):
    return x.to_bytes(n, byteorder='little')

def swap(lst, i, j):
    try:
        lst[i], lst[j] = lst[j], lst[i]
    except IndexError:
        pass

def gen_artificial_block_rawdata_with_forks(num_blocks = 200):
    # generate blocks with forks
    blocks = []
    next_height = 0
    prev_block_hash = 0x00.to_bytes(32, byteorder = 'little')
    while len(blocks) < num_blocks:
        cur_blocks = gen_blocks(next_height, prev_block_hash, 50)
        blocks.extend(cur_blocks)
        next_height = blocks[-1].height + 1
        prev_block_hash = blocks[-1].block_hash

        # make a fork
        forked_block1 = blocks[-15]
        fork_blocks1 = gen_blocks(forked_block1.height+1, forked_block1.block_hash, 5, nonce = FORKED_NONCE)
        # fork the fork
        forked_block2 = fork_blocks1[-3]
        fork_blocks2 = gen_blocks(forked_block2.height+1, forked_block2.block_hash, 2, nonce = FORKED_NONCE)
        # insert the fork, in a "competitive" location:
        fork_blocks = fork_blocks1 + fork_blocks2
        blocks = blocks[:-9] + fork_blocks + blocks[-9:]
    
    # swap some, to mess up order...
    swap(blocks, 2, 3)
    swap(blocks, 12, 13)
    swap(blocks, 14, 16)
    for i in range(4):
        swap(blocks, 20+i, 30+i)
    for i in range(4):
        swap(blocks, 88+i, 98+i)
    for i in range(4):
        swap(blocks, 106+i, 114-i)
    
    # return a single blob
    blob = bytes()
    for block in blocks:
        blob += block.blob
    return blob
   
###############################################################################
