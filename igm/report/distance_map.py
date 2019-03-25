import numpy as np
from alabtools import HssFile


def create_average_distance_map(hssfname):
    with HssFile(hssfname, 'r') as h:
        crd = h.coordinates
        index = h.index
    n = len(index.copy_index)
    fmap = np.empty((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            aves = []
            if index.chrom[i] == index.chrom[j]:
                for k, m in zip(index.copy_index[i], index.copy_index[j]):
                    aves.append(np.linalg.norm(crd[k] - crd[m], axis=1).mean())
            else:
                for k in index.copy_index[i]:
                    for m in index.copy_index[j]:
                        aves.append(np.linalg.norm(crd[k] - crd[m], axis=1).mean())
            fmap[i, j] = np.mean(aves)
    return fmap
