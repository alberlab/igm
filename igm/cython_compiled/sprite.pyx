# distutils: language = c++

import cython

# import both numpy and the Cython declarations for numpy
import numpy as np
cimport numpy as np


def read_from_h5_dataset(crd, beads):
    beads = np.array(beads)
    # hdf5 files require to ask indexes in order
    sequential_order = np.argsort(beads)
    original_order = np.empty(len(beads), dtype=np.int32)
    original_order[sequential_order] = np.arange(len(beads))
    tmp_crd = crd[ list(beads[sequential_order]) ].astype('f4')
    return np.asarray(tmp_crd[original_order], order='C')


# declare the interface to the C code
cdef extern from "cpp_sprite_assignment.h":
    void get_rg2s_cpp(
        float* crds,
        int n_struct,
        int n_bead,
        int n_segments,
        int* copies_num,
        float* rg2s,
        int* copy_idxs,
        int* min_struct
    )


@cython.boundscheck(False)
@cython.wraparound(False)
def get_rgs2(np.ndarray[float, ndim=3, mode="c"] crds not None,
             np.ndarray[int, ndim=1, mode="c"] copies_num not None,
             ):
    """
    Compute radiuses of gyrations (Rg) of N structures, each consisting
    of M beads. Each bead i=0..M-1 can have K(i) alternative locations
    x_i(0), x_i(1), .., x_i(K(i) - 1).
    The combination of alternative locations which minimizes the Rg is
    selected and returned for each structure.
    Note that this choice is performed by mere enumeration, so this
    scales exponentially with the number of alternative locations. The
    complexity is O(K(0) x K(1) x ... x K(M-1)).

    Parameters
    ----------
    crds (np.ndarray) : vector of the coordinates, with shape (N x B x 3),
        where N is the number of structures, and B is the total number of
        alternative coordinates, i.e. B = sum({K(i) : i = 0..M-1}). The
        alternative coordinates should be placed consecutively.
        Call x(s, i, k) the 3D coordinates of the k-th alternative
        for the i-th bead in the s-th structure.
        For example, if we have 2 beads:
         - i=0 with K(0)=2 alternative locations
         - i=1 with K(1)=3 alternative locations
        crd should have the following structure:
        [
          [ x(0, 0, 0), x(0, 0, 1), x(0, 1, 0), x(0, 1, 1), x(0, 1, 2) ],
          [ x(1, 0, 0), x(1, 0, 1), x(1, 1, 0), x(1, 1, 1), x(1, 1, 2) ],
          ...
          [ x(N-1, 0, 0), x(N-1, 0, 1), x(N-1, 1, 0), x(N-1, 1, 1), x(N-1, 1, 2) ]
        ]

    copies_num (np.array) : M integers representing the number of copies
        for each bead [K(0), K(1), .., K(M-1)]. In the case above [2, 3]

    Returns
    -------
    rg2s (np.array) : the squared radius of gyration for each structure
    best_structure (int) : the index of the structure which minimize
        the Rg, i.e. rg2s[best_structure] = min(rg2s)
    copy_idxs (np.ndarray) : a N x M matrix containing the selection
        of alternative locations for each structure which minimize Rg:
        [
            W(0),
            W(1),
            ...
            W(N-1),
        ]
        where the vector W(s) = [w(0), w(1), .., w(N-1)] is the best
        combination of alternative positions, and rg2s[s] corresponds
        to the squared Rg computed on the set of coordinates
        { x(s, i, W(s)[i]) : i=0..M-1 }

    """
    cdef int n_struct = crds.shape[1]
    cdef int n_bead = crds.shape[0]
    cdef int best_structure
    cdef int n_segments = copies_num.shape[0]

    cdef np.ndarray[float, ndim=1] rg2s = np.zeros(n_struct, dtype=np.float32)
    cdef np.ndarray[int, ndim=2, mode="c"] copy_idxs = np.zeros((n_struct, n_segments), dtype = np.int32)

    get_rg2s_cpp(&crds[0,0,0], n_struct, n_bead, n_segments,
                 &copies_num[0], &rg2s[0], &copy_idxs[0,0], &best_structure)

    return rg2s, best_structure, copy_idxs


def compute_gyration_radius(crd, cluster, index, copy_index):
    '''
    Computes the radius of gyration (Rg) for a set of genomic segments across
    a whole population of structures.

    Note that in case of multiple copies of a chromosome, a selection
    of the beads corresponding to the segments is performed (see `Notes`
    below.

    For performance reasons, the selection is made by randomly selecting only
    one bead per chromosome involved (a `representative`).

    Parameters
    ----------
    crd (np.array) : input coordinates (n_structures x n_beads x 3)
    cluster (list of ints) : the ids of segments in the set
    index (alabtools.Index) : the index for the system
    copy_index (list of list) : the bead indexes corresponding to
        each segment in the system. In a diploid genome, each segment
        maps to 2 beads, in a quadruploid genome to 4 beads, etc.
    full_check (bool) : whether the final Rg's are computed on the
        selected representatives only (False, default), or on all the
        cluster beads (True).

    Returns
    -------
    rg2s (np.array) : the squared radius of gyration for each structure
    best_structure (int) : the index of the structure which minimize
        the Rg, i.e. rg2s[best_structure] = min(rg2s)
    selected_beads (np.ndarray) : the bead indexes selected as the cluster
        after considering the possible combinations of chromosome copies.

    Notes
    -----

    SEGMENT refers to a genome segment, and has a single copy
    multiple BEADS can map to the same SEGMENT.

    Since the cell could have multiple copies of the same
    chromosome, we want to select the combination of copies
    which, being more compact, yields the minimum Rg.
    The combinatorial space, however, grows exponentially with the number
    of segments.
    As a reasonable approximation, we group the segments by chromosome and
    assume that all the regions mapping to the same chromosome come from the
    same copy.
    Under this approximation, the number of possible combinations scales
    with the number of chromosomes involved rather than the number of
    regions. Segments can be hundreds, chromosomes are usually a small
    number.
    A second approximation is to select a single representative segment from
    each chromosome, and find an optimal chromosome-copy selection:
    for each structure, a single copy of each involved chromosome
    is selected, such that the radius of gyration between the representative
    segments is minimized. The function returns the Rg value of the cluster
    using this selection, one for each structure.

    Example:
    The cluster counts 3 regions labeled 0, 1 and 20. Regions 0 and 1
    belong to chr1, region 2 belongs to chr2. There are two chromosomes
    involved, and assume both of them have two copies. Therefore in each
    structure there are two beads corresponding to each region, e.g.

    #region #chrom  #bead1 #bead2
    0       1       0      100
    1       1       1      101
    20      2       20     120

    Representative regions are selected: 1 for chr1, 20 for chr2.
    Assume the computation of Rg in the first structure is as follows:

    #bead1 #bead2 #Rg
      1     20    102.6
    101     20     23.1
      1    120    300.2
    101    120    155.3

    The minimum value is 23.1, using beads 101 and 20.
    The selected copies are thus the second (1) for chr1, and the first (0)
    for chr2. Based on this, the selected beads are 100, 101 and 20.
    The first element in the rg2s vector is thus the radius of gyration of
    beads 100, 101, 20.
    '''

    cdef int n_segments = len(cluster)
    cdef int n_struct = crd.shape[1]
    cdef int i
    cdef int k
    cdef int c


    # Group segments by chromosome
    cluster = np.sort(cluster)
    cchroms = index.chrom[cluster]

    # handles single chromosome clusters differently, does not select
    # a representative, just try with all the copies.
    if len(np.unique(cchroms)) == 1:
        nc = len(copy_index[cluster[0]])
        selected_beads = []
        rgs = [None] * nc
        bead_group = [None] * nc
        for k in range(nc):
            bead_group[k] = [ copy_index[i][k] for i in cluster ]
            allcrd = read_from_h5_dataset(crd, bead_group[k])
            rep_copies_num = np.array([1] * len(cluster), dtype=np.int32)
            rgs[k], _, _ = get_rgs2(allcrd, rep_copies_num)
        cidx = np.argsort(rgs, axis=0)[0,:]
        rgs = np.array([rgs[k][i] for i, k in enumerate(cidx)])
        selected_beads = np.array([bead_group[k] for k in cidx])
        return rgs, np.argmin(rgs), selected_beads


    segments_by_chrom = []
    for c in np.unique(cchroms):
        segments_by_chrom.append( cluster[np.where(cchroms==c)] )

    # Select one representative segment for each chromosome
    cdef np.ndarray[int, ndim=1] representative_segments = np.array(
        [np.random.choice(x) for x in segments_by_chrom if len(x)], dtype='i4')

    # select all the bead copies for each representative segment
    cdef np.ndarray[int, ndim=1] representative_beads = np.array(
        np.concatenate(
            [ copy_index[i] for i in representative_segments ]
        ),
        dtype='i4'
    )

    # count the number of copies for each representative segment
    rep_copies_num = np.array(
        [len(copy_index[i]) for i in representative_segments], dtype='i4')


    # representative_crd are the coordinates of all the copies of each representative
    # segment, ordered by chromosomes
    representative_crd = read_from_h5_dataset(crd, representative_beads)

    cdef np.ndarray[int, ndim=2] selected_copies_vector
    rrg, rmin, selected_copies_vector = get_rgs2(representative_crd, rep_copies_num)

    # reclaim memory
    del representative_crd

    # compute rg for the full segments by using the copy selection at the
    # previous step


    # all the segments involved in the clusters, ordered by chromosome
    all_segments = np.concatenate(segments_by_chrom)

    # obtain only the subset of coordinates needed for this computation
    all_crd = [read_from_h5_dataset(crd, copy_index[i]) for i in all_segments]

    selected_by_chromosome =  {
        index.chrom[b] : selected_copies_vector[:, i]
        for i, b in enumerate(representative_segments)
    }

    # full_crd are the final set of coordinates after copy selection
    full_crd = np.empty((n_segments, n_struct, 3), dtype='f4')
    selected_beads = np.empty((n_segments, n_struct), dtype='i4')

    # this is to slice
    struct_range = np.arange(n_struct, dtype='i4')

    cdef int isegment
    for isegment in range(n_segments):
        curr_beads = np.array( copy_index[ all_segments[ isegment ] ] )
        sel = selected_by_chromosome[ index.chrom[ all_segments[ isegment ] ] ]
        selected_beads[isegment] = curr_beads[sel]
        full_crd[isegment] = all_crd[isegment][sel, struct_range]

    # we alread chose the copy, so we set the number of copies
    # for each segment to 1
    full_copy_num = np.array([1] * n_segments, dtype='i4')

    # get the squared Rg's, ignore the trivial copy vector
    rg2s, best_structure, _ = get_rgs2(full_crd, full_copy_num)
    return rg2s, best_structure, selected_beads.swapaxes(0, 1)







