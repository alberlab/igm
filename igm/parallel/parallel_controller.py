'''
The reduce function should always accept an iterable
The map function should always return an iterable
'''
from tqdm import tqdm

class ParallelController(object):

    def __init__(self):
        """
        A parallel controller that map parallel jobs into workers
        """

    def setup(self):
        pass

    def map(self, parallel_task, args):
        raise NotImplementedError()

    def reduce(self, reduce_task, outs):
        return reduce_task(outs)

    def map_reduce(self, parallel_task, reduce_task, args):
        return self.reduce(reduce_task, self.map(parallel_task, args))

    def teardown(self):
        pass

class SerialController(ParallelController):
    def map(self, parallel_task, args):
        return [parallel_task(a) for a in tqdm(args, desc="(SERIAL)")]



def map_reduce(parallel_task, reduce_function, args, controller):
    controller.setup()
    result = controller.map_reduce(parallel_task, reduce_function, args)
    controller.teardown()
    return result
