from distutils.core import setup
from Cython.Build import cythonize
import numpy

setup(
      name = 'sprite',
      ext_modules = cythonize(
          ['sprite.pyx', 'cpp_sprite_assignment.cpp']
      ),
      include_dirs=[numpy.get_include()],
)
