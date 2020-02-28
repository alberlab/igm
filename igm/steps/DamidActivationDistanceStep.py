from __future__ import division, print_function
import numpy as np
import h5py
import os
import os.path

from alabtools.analysis import HssFile

from ..core import Step
from ..utils.log import logger

try:
    # python 2 izip
    from itertools import izip as zip
except ImportError:
    pass

# dictionaries for the activation distance files
damid_actdist_shape = [
    ('loc', 'int32'),
    ('dist', 'float32'),
    ('prob', 'float32')
]
damid_actdist_fmt_str = "%6d %10.2f %.5f"

# --- AUXILIARY FUNCTIONS FOR COMPUTING DAMID RELATED BEAD-ENVELOPE CALCULATIONS ---#

def snormsq_sphere(x, R, r):

    """
    Compute radial distance of a bead to spherical nuclear envelope

    INPUT
	x (float), bead/locus coordinates
        R (float), radius of nuclear envelope, when spherical
	r (float), radius of bead

    OUTPUT (normalized) distance between bead surface and nuclear envelope
    			d = 1 if bead surface touches the envelope
			d < 1 otherwise
    """

    # return np.square(
    #     (np.linalg.norm(x, axis=1) + r) / R**2
    # )

    return np.sum(np.square(x), axis=1) / (R-r)**2



def snormsq_ellipse(x, semiaxes, r):

    """
    Compute radial distance of a bead to ellipsoidal nuclear envelope

    INPUT
        x (float), bead/locus coordinates
        r (float), radius of bead
        semiaxes (float, float, float), semiaxes of nuclear envelope, if ellipsoidal

    OUTPUT (normalized) distance between bead surface and nuclear envelope: x**2/(a-r)**2 + y**2/(b-r)**2 + z**2/(c-r)**2
			d = 1 if bead surface touches the envelope (this means the bead center is laying on a concentric ellipsoid
								    of semiaxes (a - r, b - r, c - r))
			d < 1 otherwise (the bead center is laying on a concentric ellipsoid with even shorter semiaxes) 
    """

    a, b, c = np.array(semiaxes) - r
    sq = np.square(x)
    return sq[:, 0]/(a**2) + sq[:, 1]/(b**2) + sq[:, 2]/(c**2)



# previous functions (sphere or ellipsoid) are put together into "snormsq" which takes the shape as an input
snormsq = {
    'sphere': snormsq_sphere,
    'ellipsoid': snormsq_ellipse
}


class DamidActivationDistanceStep(Step):
    def __init__(self, cfg):

        """ The value of DAMID sigma to be used this time around is computed and stored """

        # prepare the list of DAMID sigmas in the "runtime" status, unless already there
        if 'sigma_list' not in cfg.get("runtime/DamID"):
            cfg["runtime"]["DamID"]["sigma_list"] = cfg.get("restraints/DamID/sigma_list")[:]

        # compute current Damid sigma and save that to "runtime" status
        if "sigma" not in cfg.get("runtime/DamID"):
            cfg["runtime"]["DamID"]["sigma"] = cfg.get("runtime/DamID/sigma_list").pop(0)
        super(DamidActivationDistanceStep, self).__init__(cfg)

    def name(self):

        """ This is printed to logger, and indicates that the DAmid activation step has started """

        s = 'DamidActivationDistanceStep (cut={:.2f}%, iter={:s})'
        return s.format(
            self.cfg.get('runtime/DamID/sigma', -1) * 100.0,
            str( self.cfg.get('runtime/opt_iter', 'N/A') )
        )


    def setup(self):

        """ Prepare parameters, read in DAMID input file and preprocess by spitting that into batches, produce tmp files """

        # read in damid sigma activation, and the filename containing raw damid data
        sigma         = self.cfg.get("runtime/DamID/sigma")
        input_profile = self.cfg.get("restraints/DamID/input_profile")

        self.tmp_extensions = [".npy", ".tmp"]
        self.set_tmp_path()
        self.keep_temporary_files = self.cfg.get("restraints/DamID/keep_temporary_files", False)

        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        # load txt file containing DAMID data, as per configuration json file
        profile = np.loadtxt(input_profile, dtype='float32')

        # some preprocessing, by masking matrix entries
        mask    = profile >= sigma
        ii      = np.where(mask)[0]
        pwish   = profile[mask]

        # rescale pwish considering the number of beads for multiploid cells
        # with HssFile(self.cfg.get("optimization/structure_output"), 'r') as hss:
        #     num_beads = hss.nbead
        # pwish *= num_beads / len(profile)

        # if no damid_actdist_file is available (from previous iterations/sigma values), create a new one
        try:
            with h5py.File(self.cfg.get("runtime/DamID/damid_actdist_file")) as h5f:
                last_prob = {int(i) : p for i, p in zip(h5f["loc"], h5f["prob"])}
                logger.info('Read {:d} probabilities from last step'.format(len(last_prob)))
        except KeyError:
            last_prob = {}
            logger.info('Creating new damid actdist file...')

        # split the full matrix into batches of size batch_size...each chunk is then saved to a temporary damid.in.npy file
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
            # saving step
            fname = os.path.join(self.tmp_dir, '%d.damid.in.npy' % b)
            np.save(fname, params)

        self.argument_list = range(n_args_batches)

    @staticmethod
    def task(batch_id, cfg, tmp_dir):

        """ Read in temporary in.tmp files, generated list of Damid activation distances, produce out.tmp files """

        nucleus_parameters = None
        shape = cfg.get('model/restraints/envelope/nucleus_shape')
        if shape == 'sphere':
            nucleus_parameters = cfg.get('model/restraints/envelope/nucleus_radius')
        elif shape == 'ellipsoid':
            nucleus_parameters = cfg.get('model/restraints/envelope/nucleus_semiaxes')
        else:
            raise NotImplementedError('shape %s has not been implemented yet.' % shape)

        with HssFile(cfg.get("optimization/structure_output"), 'r') as hss:

            # read params from temporary damid.in.npy files
            fname = os.path.join(tmp_dir, '%d.damid.in.npy' % batch_id)
            params = np.load(fname)

            # compute the corresponding output to save to out.tmp file
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

        # save output for this chunk to file, using the format specified by string 'damid_actdist_fmt_str'
        fname = os.path.join(tmp_dir, '%d.out.tmp' % batch_id)
        with open(fname, 'w') as f:
            f.write('\n'.join([damid_actdist_fmt_str % x for x in results]))


    def reduce(self):

        """ Concatenate data from all batches into a single hdf5 damid_actdist file """

        # create filename
        damid_actdist_file = os.path.join(self.tmp_dir, "damid_actdist.hdf5")

        # we start with one empty element to avoid errors in np.concatenate
        # if argument_list is empty
        loc = [[]]
        dist = [[]]
        prob = [[]]

        # (also see 'reduce' step in ActivationDistanceStep.py) Read in all .out.tmp files and concatenate all data into a single
        # 'damid_actdist_file' file, of type h5df (see 'create-dataset attributes)
        
        # concatenate...
        for i in self.argument_list:
            
            fname = os.path.join(self.tmp_dir, '%d.out.tmp' % i)
            partial_damid_actdist = np.genfromtxt( fname, dtype=damid_actdist_shape )
            
            if partial_damid_actdist.ndim == 0:
                partial_damid_actdist = np.array([partial_damid_actdist], dtype=damid_actdist_shape)

            loc.append( partial_damid_actdist['loc'])
            dist.append(partial_damid_actdist['dist'])
            prob.append(partial_damid_actdist['prob'])

        #... write to tmp damid actdist file
        with h5py.File(damid_actdist_file + '.tmp', "w") as h5f:
            h5f.create_dataset("loc", data=np.concatenate(loc))
            h5f.create_dataset("dist", data=np.concatenate(dist))
            h5f.create_dataset("prob", data=np.concatenate(prob))

        os.rename(damid_actdist_file + '.tmp', damid_actdist_file)

        # ... update runtime parameter for next iteration/sigma value
        self.cfg['runtime']['DamID']["damid_actdist_file"] = damid_actdist_file



    def skip(self):
        """
        Fix the dictionary values when already completed
        """
        self.set_tmp_path()
        damid_actdist_file = os.path.join(self.tmp_dir, "damid_actdist.hdf5")
        self.cfg['runtime']['DamID']["damid_actdist_file"] = damid_actdist_file



    def set_tmp_path(self):
        """ Auxiliary function to play around with paths and directories """
        curr_cfg = self.cfg['restraints']['DamID']
        damid_tmp_dir = curr_cfg.get('damid_actdist_dir', 'damid_actdist')

        if os.path.isabs(damid_tmp_dir):
            self.tmp_dir = damid_tmp_dir
        else:
            self.tmp_dir = os.path.join( self.cfg['parameters']['tmp_dir'], damid_tmp_dir )
            self.tmp_dir = os.path.abspath(self.tmp_dir)


def cleanProbability(pij, pexist):

    """ Clean probability values based on the number of restraints already applied to structures """

    if pexist < 1:
        pclean = (pij - pexist) / (1.0 - pexist)
    else:
        pclean = pij
    return max(0, pclean)



def get_damid_actdist(locid, pwish, plast, hss, contact_range=0.05, shape="sphere", nucleus_param=5000.0):
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
        list of (i, activation_distance, p) entries

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
    # pwish = np.clip(pwish/n_copies, 0, 1)

    d_sq = np.empty(n_copies*n_struct)

    for i in range(n_copies):
        x = hss.get_bead_crd( ii[ i ] )
        R = np.array(nucleus_param)*(1 - contact_range)
        d_sq[ i*n_struct:(i+1)*n_struct ] = snormsq[shape](x, R, r)
    #=

    rcutsq = 1.0
    d_sq[::-1].sort()

    contact_count = np.count_nonzero(d_sq >= rcutsq)
    # pnow        = float(contact_count) / (n_copies * n_struct)
    # approx 1 when at least one contact is there in each cell
    pnow = float(contact_count) / n_struct / n_copies

    # iterative correction
    # adjust probabilites using information from current population, previous step and input data
    t = cleanProbability(pnow, plast)
    p = cleanProbability(pwish, t)

    # set a super large actdist for the case p = 0
    activation_distance = 2
    if p>0:
        # determine index pointing to p-th quantile
        o = min(n_copies * n_struct - 1,
                int( round(n_copies * n_struct * p ) ) )

        # compute activation distance
        activation_distance = np.sqrt(d_sq[o])

    return [ (i, activation_distance, p) for i in ii ]

