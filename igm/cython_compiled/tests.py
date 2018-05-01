from sprite import *

import numpy as np

crd = np.array([ [ [1,0,0] ] , [ [-1, 0, 0] ], [ [0,-1,0] ], [ [0,1,0] ]], dtype=np.float32)
copies_num = np.array([1,1,1,1], dtype=np.int32)

get_rgs2(crd, copies_num)
# (array([1.], dtype=float32), 0, array([[0, 0, 0, 0]], dtype=int32))


crd = np.array([ [ [1,0,0] ] , [ [0.5, 0, 0] ], [ [0,-0.5,0] ], [ [0,0.5,0] ]], dtype=np.float32)
copies_num = np.array([2,2], dtype=np.int32)
get_rgs2(crd, copies_num)

# (array([1.], dtype=float32), 0, array([[0, 0, 0, 0]], dtype=int32))

crd = np.array([ [ [1,0,0], [0.1,0,0] ] , [ [0.5, 0, 0], [1,0,0] ], [ [0,-0.5,0], [-1,0,0] ], [ [0,0.5,0], [-0.1,0,0] ] ], dtype=np.float32)
copies_num = np.array([2,2], dtype=np.int32)
get_rgs2(crd, copies_num)
# (array([0.125, 0.01 ], dtype=float32), 1, array([[1, 0], [0, 1]], dtype=int32))