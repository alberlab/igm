def batch(sequence, n=1):
    l = len(sequence)
    for ndx in range(0, l, n):
        yield sequence[ndx:min(ndx + n, l)]

def split_evenly(sequence, n=1):
    l = len(sequence)
    n = min(l, n)

    k = l // n
    if n % l != 0:
        k += 1

    for ndx in range(0, l, k):
        yield sequence[ndx:min(ndx + n, l)]