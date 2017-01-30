
from os import path
from glob import glob
from codecs import open
import numpy
from setuptools import setup, Extension, find_packages

try:
    from Cython.Build import cythonize
except ImportError:
    USE_CYTHON = False
else:
    USE_CYTHON = True

here = path.abspath(path.dirname(__file__))

# Read version info from version.py
version_vars = {}
with open(path.join(here, 'chainscan', 'version.py')) as fp:
    exec(fp.read(), version_vars)
version_string = version_vars['__version_string__']

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

# cython stuff
pyx_files = glob(path.join(here, 'chainscan', '*.pyx'))
USE_CYTHON = USE_CYTHON and len(pyx_files) > 0
ext = '.pyx' if USE_CYTHON else '.c'
extensions = [
    Extension(
        'chainscan.cyt',
        [ path.join('chainscan', 'cyt' + ext) ],
        include_dirs = [ numpy.get_include(), '.' ],
        extra_compile_args = ['-O3'],
        #extra_link_args = ['-g'],
    )
]
if USE_CYTHON:
    extensions = cythonize(extensions)

# setup
setup(
    name='chainscan',
    ext_modules = extensions,

    description='Feel the blockchain, one transaction at a time.',
    long_description=long_description,
    version=version_string,

    author='fungibit',
    author_email='fungibit@yandex.com',
    url='https://github.com/fungibit/chainscan',
    license='MIT',

    packages=find_packages(exclude=['tests*',]),
    platforms = ["POSIX", "Windows"],
    keywords='bitcoin, blockchain, iterator, analysis',

)

