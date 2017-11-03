'''
The reduce function should always accept an iterable
The map function should always return an iterable
'''

class MapReduceController(object):
    def __init__(self):
        pass
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

class SerialController(MapReduceController):
    def map(self, parallel_task, args):
        return [parallel_task(a) for a in args]


    
def map_reduce(parallel_task, reduce_function, args, controller):
    controller.setup()
    result = controller.map_reduce(parallel_task, reduce_function, args)
    controller.teardown()
    return result
