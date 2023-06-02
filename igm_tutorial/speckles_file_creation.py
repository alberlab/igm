import numpy as np
import pickle as pkl

# Create three speckles, i.e. sphere with a set of 3D coordinates and a radius
spe_1 = (np.array([0, 0, 0]), 300)  # center and radius
spe_2 = (np.array([1500, 0, 0]), 200)
spe_3 = (np.array([0, 1500, 0]), 500)

spe_lst = [spe_1, spe_2, spe_3]  # list of speckles

# in general, we would have a different list for each structure
# for this tutorial, we will use the same list for all structures

n_structures = 5  # number of structures

# create a list of lists of speckles
speckles = [spe_lst for i in range(n_structures)]

# save the list of lists of speckles as a pickle file
pkl.dump(speckles, open('speckles.pkl', 'wb'))
