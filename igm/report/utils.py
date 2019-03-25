import numpy as np
import os.path


def aggregate_copies(v, index, fun=np.nanmean, *args, **kwargs):
    '''
    Aggregate genomic regions if more copies are present
    :param v: np.ndarray
        the values for all the regions/beads
    :param index: alabtools.Index
        the index
    :param fun: callable
        the function to apply (default: np.nanmean). It should take one vector
        and return a scalar
    :return: np.ndarray
    '''
    v = np.array(v)
    assert len(v) == len(index)
    ci = index.copy_index
    x = np.zeros(len(ci))
    for i in range(len(ci)):
        x[i] = fun(v[ci[i]], *args, **kwargs)
    return x


def average_copies(v, index):
    return aggregate_copies(v, index)


def sum_copies(v, index):
    return aggregate_copies(v, index, np.sum)


def create_folder(folder):
    if not os.path.isdir(folder):
        os.makedirs(folder)


def snormsq_ellipse(x, semiaxes, r=0):
    '''
    Returns the level of a point inside an ellipsoid
    (0 -> center, ]0, 1[ -> inside, 1 -> surface, >1 outside).
    :param x: np.ndarray
        the coordinates of the point
    :param semiaxes: np.ndarray
        the 3 semiaxes of the ellipsoid
    :param r: float
        if specified, the point is considered a sphere and level=1 means
        the surface is touching the ellipsoid.
    :return:
    '''
    a, b, c = np.array(semiaxes) - r
    sq = np.square(x)
    return sq[:, 0] / (a**2) + sq[:, 1] / (b**2) + sq[:, 2] / (c**2)
