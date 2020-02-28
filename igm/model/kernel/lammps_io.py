from __future__ import division, absolute_import, print_function
import numpy as np

from .util import reverse_readline

def get_info_from_log(output):
    ''' gets final energy, excluded volume energy and bond energy.
    TODO: get more info? '''
    info = {}
    generator = reverse_readline(output)

    for l in generator:
        if l[:9] == '  Force t':
            ll = next(generator)
            info['final-energy'] = float(ll.split()[2])
            break

    for l in generator:
        if l[:4] == 'Loop':
            ll = next(generator)
            vals = [float(s) for s in ll.split()]
            info['pair-energy'] = vals[2]
            info['bond-energy'] = vals[3]
            while not ll.startswith('Step'):
                ll = next(generator)
            keys = ll.split()
            info['thermo'] = {k: v for k, v in zip(keys[1:], vals[1:])}
            break

    for l in generator:
        if l[:4] == 'Loop':
            # MD minimization
            info['md-time'] = float(l.split()[3])

    # EN=`grep -A 1 "Energy initial, next-to-last, final =" $LAMMPSLOGTMP \
    # | tail -1 | awk '{print $3}'`
    return info

def get_last_frame(fh):

    """ Quite self-explanatory: extract coordinates from last frame produced by simulation """
    atomlines = []
    for l in reverse_readline(fh):
        if 'ITEM: ATOMS' in l:
            v = l.split()
            ii = v.index('id') - 2
            ix = v.index('x') - 2
            iy = v.index('y') - 2
            iz = v.index('z') - 2
            break
        atomlines.append(l)

    crds = np.empty((len(atomlines), 3))
    for l in atomlines:
        v = l.split()
        i = int(v[ii]) - 1  # ids are in range 1-N
        x = float(v[ix])
        y = float(v[iy])
        z = float(v[iz])
        crds[i][0] = x
        crds[i][1] = y
        crds[i][2] = z

    return crds
