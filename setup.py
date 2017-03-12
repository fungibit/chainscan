
from os import path
from glob import glob
from codecs import open
from setuptools import setup, Extension, find_packages
from Cython.Build import cythonize
import numpy

################################################################################

EXTENSION_KWARGS = dict(
    include_dirs = [ numpy.get_include(), '.' ],
    libraries = [ 'crypto' ],
    extra_compile_args = ['-O3'],
)

CYTHONIZE_KWARGS = dict(
    #annotate = True,
)

# The directory containing this file (setup.py):
here = path.abspath(path.dirname(__file__))

################################################################################
# cython stuff

pyx_files = [ path.basename(f) for f in glob(path.join(here, 'chainscan', '*.pyx')) ]
extensions = [
    Extension(
        'chainscan.%s' % pyx_file.split('.')[0],
        [ path.join('chainscan', pyx_file) ],
        **EXTENSION_KWARGS
    )
    for pyx_file in pyx_files
]
extensions = cythonize(extensions, **CYTHONIZE_KWARGS)

################################################################################

# Read version info from version.py
version_vars = {}
with open(path.join(here, 'chainscan', 'version.py')) as fp:
    exec(fp.read(), version_vars)
version_string = version_vars['__version_string__']

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

################################################################################
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
    include_package_data = True,
    package_data={ 'chainscan': [ 'chainscan/*pyx', 'chainscan/*pxd', 'chainscan/*pxi' ] },

    platforms = ["POSIX", "Windows"],
    keywords='bitcoin, blockchain, iterator, analysis',

)

################################################################################
