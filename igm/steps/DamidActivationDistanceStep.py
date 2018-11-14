from __future__ import division, print_function
import numpy as np
import h5py
import os
import os.path

from alabtools.analysis import HssFile

from ..core import Step

try:
    # python 2 izip
    from itertools import izip as zip
except ImportError:
    pass


damid_actdist_shape = [
    ('loc', 'int32'),
    ('dist', 'float32'),
    ('prob', 'float32')
]
damid_actdist_fmt_str = "%6d %10.2f %.5f"


def snormsq_sphere(x, r):
    return np.sum(np.square(x), axis=1) / r**2

def snormsq_ellipse(x, semiaxes):
    a, b, c = semiaxes
    sq = np.square(x)
    return sq[:, 0]/(a**2) + sq[:, 1]/(b**2) + sq[:, 2]/(c**2)

snormsq = {
    'sphere': snormsq_sphere,
    'ellipsoid': snormsq_ellipse
}


class DamidActivationDistanceStep(Step):
    def __init__(self, cfg):

        # prepare the list of sigmas in the runtime status
        if 'sigma_list' not in cfg.get("runtime/DamID"):
            cfg["runtime"]["DamID"]["sigma_list"] = cfg.get("restraints/DamID/sigma_list")[:]
        if "sigma" not in cfg.get("runtime/DamID"):
            cfg["runtime"]["DamID"]["sigma"] = cfg.get("runtime/DamID/sigma_list").pop(0)
        super(DamidActivationDistanceStep, self).__init__(cfg)

    def name(self):
        s = 'DamidActivationDistanceStep (cut={:.2f}%, iter={:s})'
        return s.format(
            self.cfg.get('runtime/DamID/sigma', -1) * 100.0,
            str( self.cfg.get('runtime/opt_iter', 'N/A') )
        )


    def setup(self):
        sigma = self.cfg.get("runtime/DamID/sigma")
        input_profile = self.cfg.get("restraints/DamID/input_profile")

        self.tmp_extensions = [".npy", ".tmp"]

        self.set_tmp_path()

        self.keep_temporary_files = self.cfg.get("restraints/DamID/keep_temporary_files", False)

        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)
        #---

        profile = np.loadtxt(input_profile, dtype='float32')

        mask    = profile >= sigma
        ii      = np.where(mask)[0]
        pwish   = profile[mask]

        # rescale pwish considering the number of beads for multiploid cells
        with HssFile(self.cfg.get("optimization/structure_output"), 'r') as hss:
            num_beads = hss.nbead
        pwish *= num_beads / len(profile)

        try:
            with h5py.File(self.cfg.get("runtime/DamID/damid_actdist_file")) as h5f:
                last_prob = {i : p for i, p in zip(h5f["loc"], h5f["prob"])}
        except KeyError:
            last_prob = {}

        batch_size = self.cfg.get('restraints/DamID/batch_size', 100)
        n_args_batches = len(ii) // batch_size
        if len(ii) % batch_size != 0:
            n_args_batches += 1

        for b in range(n_args_batches):
            start = b * batch_size
            end = min((b+1) * batch_size, len(ii))
            params = np.array(
                [
                    ( ii[k], pwish[k], last_prob.get(ii[k], 0.) )
                    for k in range(start, end)
                ],
                dtype=np.float32
            )
            fname = os.path.join(self.tmp_dir, '%d.damid.in.npy' % b)
            np.save(fname, params)

        self.argument_list = range(n_args_batches)

    @staticmethod
    def task(batch_id, cfg, tmp_dir):
        nucleus_parameters = None
        shape = cfg.get('model/restraints/envelope/nucleus_shape')
        if shape == 'sphere':
            nucleus_parameters = cfg.get('model/restraints/envelope/nucleus_radius')
        elif shape == 'ellipsoid':
            nucleus_parameters = cfg.get('model/restraints/envelope/nucleus_semiaxes')
        else:
            raise NotImplementedError('shape %s has not been implemented yet.' % shape)

        with HssFile(cfg.get("optimization/structure_output"), 'r') as hss:

            # read params
            fname = os.path.join(tmp_dir, '%d.damid.in.npy' % batch_id)
            params = np.load(fname)

            results = []
            for i, pwish, plast in params:
                res = get_damid_actdist(
                    int(i), pwish, plast, hss,
                    contact_range=cfg.get('restraints/DamID/contact_range', 0.05),
                    shape=shape,
                    nucleus_param=nucleus_parameters
                )
                results += res #(i, damid_actdist, p)
                #-
            #--
        fname = os.path.join(tmp_dir, '%d.out.tmp' % batch_id)
        with open(fname, 'w') as f:
            f.write('\n'.join([damid_actdist_fmt_str % x for x in results]))


    def reduce(self):
        damid_actdist_file = os.path.join(self.tmp_dir, "damid_actdist.hdf5")

        # we start with one empty element to avoid errors in np.concatenate
        # if argument_list is empty
        loc = [[]]
        dist = [[]]
        prob = [[]]

        for i in self.argument_list:
            fname = os.path.join(self.tmp_dir, '%d.out.tmp' % i)
            partial_damid_actdist = np.genfromtxt( fname, dtype=damid_actdist_shape )
            if partial_damid_actdist.ndim == 0:
                partial_damid_actdist = np.array([partial_damid_actdist], dtype=damid_actdist_shape)
            loc.append(partial_damid_actdist['loc'])
            dist.append(partial_damid_actdist['dist'])
            prob.append(partial_damid_actdist['prob'])

        with h5py.File(damid_actdist_file + '.tmp', "w") as h5f:
            h5f.create_dataset("loc", data=np.concatenate(loc))
            h5f.create_dataset("dist", data=np.concatenate(dist))
            h5f.create_dataset("prob", data=np.concatenate(prob))

        os.rename(damid_actdist_file + '.tmp', damid_actdist_file)

        self.cfg['runtime']['DamID']["damid_actdist_file"] = damid_actdist_file

    def skip(self):
        """
        Fix the dictionary values when already completed
        """
        self.set_tmp_path()
        damid_actdist_file = os.path.join(self.tmp_dir, "damid_actdist.hdf5")
        self.cfg['runtime']['DamID']["damid_actdist_file"] = damid_actdist_file
#=
    def set_tmp_path(self):
        curr_cfg = self.cfg['restraints']['DamID']
        damid_tmp_dir = curr_cfg.get('damid_actdist_dir', 'damid_actdist')

        if os.path.isabs(damid_tmp_dir):
            self.tmp_dir = damid_tmp_dir
        else:
            self.tmp_dir = os.path.join( self.cfg['parameters']['tmp_dir'], damid_tmp_dir )
            self.tmp_dir = os.path.abspath(self.tmp_dir)


def cleanProbability(pij, pexist):
    if pexist < 1:
        pclean = (pij - pexist) / (1.0 - pexist)
    else:
        pclean = pij
    return max(0, pclean)

def get_damid_actdist(locid, pwish, plast, hss, contact_range=2, shape="sphere", nucleus_param=5000.0):
    """
    Serial function to compute the damid activation distance for a locus.

    Parameters
    ----------
        locid : int
            index of the first locus
        pwish : float
            target contact probability
        plast : float
            the last refined probability
        hss : alabtools.analysis.HssFile
            file containing coordinates
        contact_range : int
            contact range of sum of radius of beads
        shape : str
            shape of the envelope
        nucleus_param : variable
            parameters for the envelope (probably this will need restructuring in the future)

    Returns
    -------
        locid (int): the locus index
        ad (float): the activation distance
        p (float): the corrected probability
    """

    # import here in case is executed on a remote machine
    import numpy as np

    n_struct = hss.get_nstruct()
    copy_index = hss.get_index().copy_index

    ii = copy_index[locid]
    n_copies = len(ii)

    r = hss.get_radii()[ ii[0] ]

    # rescale pwish considering the number of copies
    pwish = np.clip(pwish/n_copies, 0, 1)

    d_sq = np.empty(n_copies*n_struct)

    for i in range(n_copies):
        x = hss.get_bead_crd( ii[ i ] )
        d_sq[ i*n_struct:(i+1)*n_struct ] = snormsq[shape](x, nucleus_param)
    #=

    rcutsq = (1.0 - contact_range) ** 2
    d_sq[::-1].sort()

    contact_count = np.count_nonzero(d_sq >= rcutsq)
    # pnow        = float(contact_count) / (n_copies * n_struct)
    # approx 1 when at least one contact is there in each cell
    pnow = float(contact_count) / n_struct / n_copies

    t = cleanProbability(pnow, plast)
    p = cleanProbability(pwish, t)

    # set a super large actdist for the case p = 0
    activation_distance = 2
    if p>0:
        o = min(n_copies * n_struct - 1,
                int( round(n_copies * n_struct * p ) ) )
        activation_distance = np.sqrt(d_sq[o])

    return [ (i, activation_distance, p) for i in ii ]


