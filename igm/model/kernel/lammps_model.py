import numpy as np
from ..particle import Particle

class BondType(object):
    '''
    Bond Type. Abstract base class
    '''
    HARMONIC_UPPER_BOUND = 0
    HARMONIC_LOWER_BOUND = 1

    def __init__(self):
        pass

    def __str__(self):
        raise NotImplementedError('This is an abstract base class')

    def __hash__(self):
        raise NotImplementedError('This is an abstract base class')

    def __eq__(self, other):
        return hash(self) == hash(other)

    def get_violation(self):
        raise NotImplementedError('This is an abstract base class')

    def get_relative_violation(self):
        raise NotImplementedError('This is an abstract base class')

    def get_energy(self):
        raise NotImplementedError('This is an abstract base class')


class HarmonicUpperBound(BondType):
    '''
    Harmonic upper bound restraint. Force is computed as
    F = -k * (r-r0)     if r > r0
    F = 0               otherwise
    '''
    style_str = 'harmonic_upper_bound'
    style_id = BondType.HARMONIC_UPPER_BOUND

    def __init__(self, b_id=-1, k=1.0, r0=0.0):
        self.id = b_id
        self.k = k
        self.r0 = r0

    def __str__(self):
        return '{} {} {} {}'.format(self.id + 1,
                                    self.__class__.style_str,
                                    self.k,
                                    self.r0)

    def __hash__(self):
        return hash((self.__class__.style_id, self.k, self.r0))

    def get_violation(self, bond_length):
        if bond_length > self.r0:
            return self.k*(bond_length - self.r0)
        return 0.0

    def get_relative_violation(self, bond_length):
        return self.get_violation(bond_length) / self.r0

    def get_energy(self, bond_length):
        return self.get_violation(bond_length) * self.k


class HarmonicLowerBound(BondType):
    '''
    Harmonic lower bound restraint. Force is computed as
    F = -k * (r0 - r)     if r < r0
    F = 0               otherwise
    '''
    style_str = 'harmonic_lower_bound'
    style_id = BondType.HARMONIC_LOWER_BOUND

    def __init__(self, b_id=-1, k=1.0, r0=0.0):
        self.id = b_id
        self.k = k
        self.r0 = r0

    def __str__(self):
        return '{} {} {} {}'.format(self.id + 1,
                                    self.__class__.style_str,
                                    self.k,
                                    self.r0)

    def __hash__(self):
        return hash((self.__class__.style_id, self.k, self.r0))

    def get_violation(self, bond_length):
        if bond_length < self.r0:
            return (self.r0 - bond_length)
        return 0.0

    def get_relative_violation(self, bond_length):
        return self.get_violation(bond_length) / self.r0

    def get_energy(self, bond_length):
        return self.get_violation(bond_length) * self.k


class Bond(object):
    '''
    A bond between two atoms. The indexes are saved in
    the *0, ... , N-1* index, while its string
    representation is in the *1, ..., N* LAMMPS
    format.
    '''
    OTHER=-1
    CONSECUTIVE = 0
    HIC = 1
    DAMID = 2
    FISH_RADIAL = 3
    FISH_PAIR = 4
    BARCODED_CLUSTER = 5
    ENVELOPE = 6

    def __init__(self, b_id, bond_type, i, j, restraint_type=OTHER):
        self.id = b_id
        self.bond_type = bond_type
        self.i = i
        self.j = j
        self.restraint_type=restraint_type

    def __str__(self):
        return '{} {} {} {}'.format(self.id + 1,
                                    self.bond_type.id + 1,
                                    self.i.id + 1,
                                    self.j.id + 1)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def length(self, crds):
        return np.linalg.norm(crds[self.i.id] - crds[self.j.id])

    def get_violation(self, crds):
        return self.bond_type.get_violation(self.length(crds))

    def get_relative_violation(self, crds):
        return self.bond_type.get_relative_violation(self.length(crds))

    def get_energy(self, crds):
        return self.bond_type.get_energy(self.length(crds))

class AtomType(object):
    '''
    Atom type. Abstract class.
    '''
    BEAD = 0
    CLUSTER_CENTROID = 1
    FIXED_DUMMY = 2

    def __init__(self):
        pass

    def __str__(self):
        raise NotImplementedError('This is an abstract base class')

    def __hash__(self):
        raise NotImplementedError('This is an abstract base class')

    def __eq__(self, other):
        return hash(self) == hash(other)


class DNABead(AtomType):
    '''
    DNA beads are defined by their radius
    '''
    atom_category = AtomType.BEAD

    def __init__(self, radius, type_id=-1):
        self.id = type_id
        self.radius = radius

    def __str__(self):
        return str(self.id + 1)

    def __hash__(self):
        return hash((self.__class__.atom_category, self.radius))


class FrozenPhantomBead(AtomType):
    MAX_BONDS = 20
    atom_category = AtomType.FIXED_DUMMY
    def __init__(self, type_id=-1):
        self.id = type_id

    def __str__(self):
        return str(self.id + 1)

    def __hash__(self):
        return hash(self.__class__.atom_category)


class ClusterCentroid(AtomType):
    atom_category = AtomType.CLUSTER_CENTROID
    def __init__(self, type_id=-1):
        self.id = type_id

    def __str__(self):
        return str(self.id + 1)

    def __hash__(self):
        return hash(self.__class__.atom_category)


class Atom(object):
    BEAD = 0
    CLUSTER_CENTROID = 1
    FIXED_DUMMY = 2

    def __init__(self, a_id, atom_type, mol_id, xyz):
        self.id = a_id
        self.atom_type = atom_type
        self.mol_id = mol_id
        self.xyz = xyz
        self.nbonds = 0

    def __str__(self):
        return '{} {} {} {} {} {}'.format(self.id + 1,
                                          self.mol_id + 1,
                                          self.atom_type.id + 1,
                                          self.xyz[0],
                                          self.xyz[1],
                                          self.xyz[2])


class LammpsModel(object):
    '''
    An intermediate (possibly non-necessary)  class to organize data to generate lammps input files.

    Parameters
    ----------
    model : igm.model.Model, optional
        tranfer data from a igm.Model to a LammpsModel, which is then used to generate the input files for a production run
    '''

    def __init__(self, model=None, uid=0):
        self.atoms = []
        self.atom_types = {}
        self.bonds = []
        self.bond_types = {}
        self.nmol = 1
        self.id = uid
        self.envelopes = []
        if model is not None:
            self.imap = []
            self.from_model(model)

    def from_model(self, model):
        self.id = model.id

        # loop over particles, add appropriate beads for NORMAL, DUMMY_STATIC, DUMMY_DYNAMIC
        centroid_type = ClusterCentroid()
        for p in model.particles:
  
            # if NORMAL, add a regular DNA bead
            if p.ptype == Particle.NORMAL:
                att = DNABead(p.r)
                if hasattr(p, 'chainID'):
                    mol_id = p.chainID + 1
                else:
                    mol_id = 0
                atom = self.add_atom(att, p.pos, mol_id=mol_id)

            # if DUMMY particles, define properties and add them
            elif p.ptype == Particle.DUMMY_STATIC:
                atom = self.get_next_dummy(p.pos)
            elif p.ptype == Particle.DUMMY_DYNAMIC:
                atom = self.add_atom(centroid_type, p.pos)
            else:
                raise ValueError('Unknown particle type')
            self.imap.append(atom.id)

        # loop over the different physical forces involved in the model
        for f in model.forces:
            if (f.ftype == f.ENVELOPE) or (f.ftype == f.GENERAL_ENVELOPE):
                self.envelopes.append(f)     # see Guido's email: la classe del model viene aggiunta alle envelopes del Lammpsmodel
            elif f.ftype == f.EXCLUDED_VOLUME:
                self.evfactor = f.k

            else:
                pi, pj = self.atoms[self.imap[f.i]], self.atoms[self.imap[f.j]]

                # dummies creation depend on the number of bonds, so we may need to
                # create new atoms if we add bonds
                if pi.atom_type == Atom.FIXED_DUMMY:
                    pi = self.get_next_dummy()
                if pj.atom_type == Atom.FIXED_DUMMY:
                    pj = self.get_next_dummy()


                if f.ftype == f.HARMONIC_UPPER_BOUND:
                    bond_type = HarmonicUpperBound(r0=f.d, k=f.k)
                    self.add_bond(pi.id, pj.id, bond_type)
                elif f.ftype == f.HARMONIC_LOWER_BOUND:
                    bond_type = HarmonicLowerBound(r0=f.d, k=f.k)
                    self.add_bond(pi.id, pj.id, bond_type)

    def get_next_dummy(self, pos=np.array([0., 0., 0.])):
        if (self.atoms[-1].atom_type == Atom.FIXED_DUMMY and
            self.atoms[-1].nbonds < FrozenPhantomBead.MAX_BONDS and
            np.all(self.atoms[-1].xyz == pos)):
                dummy = self.atoms[-1]
        else:
            atype = FrozenPhantomBead()
            dummy = self.add_atom(atype, xyz=pos)

        return dummy

    def add_bond(self, i, j, bond_type, restraint_type=Bond.OTHER):
        if not isinstance(i, Atom):
            i = self.atoms[i]
        if not isinstance(j, Atom):
            j = self.atoms[j]
        btype = self.bond_types.get(bond_type, None)
        if btype is None:
            bond_type.id = len(self.bond_types)
            btype = self.bond_types[bond_type] = bond_type

        bond_id = len(self.bonds)
        bond = Bond(bond_id, btype, i, j, restraint_type)
        self.bonds.append(bond)
        i.nbonds += 1
        j.nbonds += 1
        return bond

    def add_atom(self, atom_type,
                 xyz=np.array([0., 0., 0.]),
                 mol_id=0 # molecules are not used anyway
                 ):

        atom_id = len(self.atoms)
        atype = self.atom_types.get(atom_type, None)
        if atype is None:
            atom_type.id = len(self.atom_types)
            atype = self.atom_types[atom_type] = atom_type
        atom = Atom(atom_id, atype, mol_id, xyz)
        self.atoms.append(atom)
        self.nmol = max(mol_id, self.nmol)
        return atom

