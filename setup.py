#!/usr/bin/env python
from distutils.core import setup, Extension

install_requires = [
    'numpy>=1.9', 
    'scipy>=0.16', 
    'h5py>=2.5', 
]

tests_require = [
    'mock'
]


extras_require = {
    'docs': [
        'Sphinx>=1.1', 
    ]
}
    
setup(
        name = 'igm', 
        version = '0.0.1', 
        author = 'Guido Polles, Nan Hua', 
        author_email = 'polles@usc.edu nhua@usc.edu', 
        url = 'https://github.com/alberlab/gim', 
        description = 'Integrated Genome Modeling',
        packages=['igm'],
        package_data={'igm' : ['core/defaults/*']},
        install_requires=install_requires,
        tests_require=tests_require,
        extras_require=extras_require,
)
