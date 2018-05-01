import numpy as np
import h5py 

SPRITE_H5_CHUNKSIZE = 1000000

def sprite_clusters_txt_to_h5(textfile, outfile):
    with h5py.File(outfile, 'w') as h5f:
        indptr = [ 0 ]
        lastwrite = 0
        h5f.create_dataset('data', shape=(0,), maxshape=(None,), chunks=(SPRITE_H5_CHUNKSIZE,) , dtype=np.int32)
        data = np.empty(shape=(0,), dtype=np.int32) 
        for line in open(textfile, 'r'):
            cluster = np.array([ int(x) for x in line.split()[1:] ], dtype=np.int32)
            indptr.append(indptr[-1] + len(cluster))
            data = np.concatenate([data, cluster])
            if indptr[-1] - lastwrite > SPRITE_H5_CHUNKSIZE:
                h5f['data'].resize( (indptr[-1], ) )
                h5f['data'][lastwrite:] = data
                lastwrite = indptr[-1]
                data = np.empty(shape=(0,), dtype=np.int32) 

        h5f['data'].resize( (indptr[-1], ) )
        h5f['data'][lastwrite:] = data
        h5f.create_dataset('indptr', data=indptr, dtype=np.int32) 
        
