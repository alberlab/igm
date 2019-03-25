import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from scipy.ndimage import gaussian_filter


def logloghist2d(d1, d2, bins=(100, 100), ranges=((1e-3, 1), (1e-3, 1)), outfile=None, vmin=1e2, vmax=1e5, nlevels=5,
                 sigma=None, xlabel='in', ylabel='out', smooth=None, **kwargs):

    if ranges[0] is None:
        x0, x1 = np.min(d1), np.max(d1)
    else:
        x0, x1 = ranges[0]

    if ranges[1] is None:
        y0, y1 = np.min(d2), np.max(d2)
    else:
        y0, y1 = ranges[1]

    xx = np.logspace(np.log10(x0), np.log10(x1), bins[0] + 1, base=10)
    yy = np.logspace(np.log10(y0), np.log10(y1), bins[1] + 1, base=10)
    bottom_left = max(xx[0], yy[0])
    top_right = min(xx[-1], yy[-1])

    # Note: we invert axes, because in a plot, the x axis actually correspond to
    # columns, while the y to rows. np.histogram2d puts the value from the first dataset on
    # rows, and the ones from the second in columns.
    h, e1, e2 = np.histogram2d(d2, d1, bins=(yy, xx))

    # Smooth histogram with a gaussian kernel for visualization purposes
    if smooth:
        h = gaussian_filter(h, **smooth)

    # pad the histogram, so that we can extend the image to fit the whole space, and set the x and
    # y axes point to the midpoints in the plot (in this case we need to take into account the log
    # scaling of the axis)
    lex = np.log(e1)
    ley = np.log(e2)
    dx = lex[1] - lex[0]
    dy = ley[1] - ley[0]
    midx = np.exp(np.arange(lex[0] - dx / 2, lex[-1] + dx, dx))
    midy = np.exp(np.arange(ley[0] - dy / 2, ley[-1] + dy, dy))

    h = np.pad(h, 1, 'edge')

    f = plt.figure(figsize=(5, 5))
    # p = plt.pcolormesh(xx, yy, h, **kwargs)
    grid_x, grid_y = np.meshgrid(midx, midy)
    q = h.copy()

    # set the maximum histogram value to the cutoff, or we will have blank areas in the contour plots
    h[h > vmax] = vmax

    levels = np.logspace(np.log10(vmin), np.log10(vmax), nlevels, base=10)
    p = plt.contourf(grid_x, grid_y, h, norm=LogNorm(vmin, vmax), cmap='Reds', levels=levels, **kwargs)
    if sigma is not None:
        plt.axvline(x=sigma, ls='--', c='#dddddd')

    plt.plot([bottom_left, top_right], [bottom_left, top_right], 'k--')
    plt.xscale('log')
    plt.yscale('log')
    plt.xlim(xx[0], xx[-1])
    plt.ylim(yy[0], yy[-1])
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    if outfile is not None:
        plt.savefig(outfile)
    return f, p, q, e1, e2


def density_histogram_2d(d1, d2, bins=(100, 100), ranges=((1e-3, 1), (1e-3, 1)),
                         outfile=None, vmin=1e1, vmax=1e5, nlevels=5,
                         xlabel='in', ylabel='out', smooth=None, **kwargs):

    if ranges is None:
        ranges = (None, None)

    if ranges[0] is None:
        x0, x1 = np.min(d1), np.max(d1)
    else:
        x0, x1 = ranges[0]

    if ranges[1] is None:
        y0, y1 = np.min(d2), np.max(d2)
    else:
        y0, y1 = ranges[1]

    xx = np.linspace(x0, x1, bins[0])
    yy = np.linspace(y0, y1, bins[1])

    bottom_left = max(xx[0], yy[0])
    top_right = min(xx[-1], yy[-1])

    # Note: we invert axes, because in a plot, the x axis actually correspond to
    # columns, while the y to rows. np.histogram2d puts the value from the first dataset on
    # rows, and the ones from the second in columns.
    h, e1, e2 = np.histogram2d(d2, d1, bins=(yy, xx))

    # Smooth histogram with a gaussian kernel for visualization purposes
    if smooth:
        h = gaussian_filter(h, **smooth)

    # pad the histogram, so that we can extend the image to fit the whole space, and set the x and
    # y axes point to the midpoints in the plot
    lex = e1
    ley = e2
    dx = lex[1] - lex[0]
    dy = ley[1] - ley[0]
    midx = np.arange(lex[0] - dx / 2, lex[-1] + dx, dx)
    midy = np.arange(ley[0] - dy / 2, ley[-1] + dy, dy)

    h = np.pad(h, 1, 'edge')

    f = plt.figure(figsize=(5, 5))
    # p = plt.pcolormesh(xx, yy, h, **kwargs)
    grid_x, grid_y = np.meshgrid(midx, midy)
    q = h.copy()

    h[h > vmax] = vmax
    levels = np.logspace(np.log10(vmin), np.log10(vmax), nlevels, base=10)
    p = plt.contourf(grid_x, grid_y, h, norm=LogNorm(vmin, vmax),
                     cmap='Blues', levels=levels, **kwargs)
    plt.plot([bottom_left, top_right], [bottom_left, top_right], 'k--')
    plt.xlim(xx[0], xx[-1])
    plt.ylim(yy[0], yy[-1])
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    if outfile is not None:
        plt.savefig(outfile)
    return f, p, q, e1, e2
