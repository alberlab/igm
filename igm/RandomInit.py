from __future__ import division, print_function

from .core import Step

class RandomInit(Step):
    def task(self, struct_id):
        with open("tmp/%s.txt"%(struct_id),'w') as f:
            f.write("%s"%(self.config['genome']['genome']))
            
    
        


