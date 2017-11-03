import igm

mm = igm.model.Model()

mm.addParticle(1,2,3,4,0)
mm.addParticle(2,3,4,5,0)

ee = igm.restraints.Envelope(5000,1)
mm.addRestraint(ee)

class Index:
    def __init__(self, **kwargs):
        self.chrom = [0,0]
    def __len__(self):
        return len(self.chrom)
        
index = Index()

pp = igm.restraints.Polymer(index)
mm.addRestraint(pp)
