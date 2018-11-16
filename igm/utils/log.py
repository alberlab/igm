from time import time, strftime, localtime
import sys
import logging
import os.path

# clear root logger handler
FORMAT = '(%(name)s) %(asctime)-15s [%(levelname)s] %(message)s'
logging.basicConfig(format=FORMAT, level=logging.INFO)
logger = logging.getLogger('IGM')

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def SetupLogging(cfg):
    if 'log' in cfg['parameters']:
        loglevel=logging.INFO
        set_log(cfg['parameters']['log'], loglevel=loglevel)


def set_log(fname, loglevel=logging.INFO):

    fname = os.path.abspath(fname)

    # ensure the file is not double added
    hs = [h.baseFilename for h in logger.handlers if isinstance(h, logging.FileHandler)]
    if fname in hs:
        return

    fh = logging.FileHandler(fname)
    fh.setFormatter(logging.Formatter(FORMAT))
    logger.addHandler(fh)


def pretty_time(seconds):
    '''
    Prints the *seconds* in the format h mm ss
    '''
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return "%dh %02dm %02ds" % (h, m, s)

def print_progress(iterable,
                   length=None,
                   every=1,
                   timeout=None,
                   size=12,
                   fmt='(IGM) {bar} {percent:6.2f}% ({completed}/{total}) | {elapsed:12s} | ETA: {remaining:12s}',
                   timefmt='%c',
                   fd=sys.stdout ):

    if hasattr(iterable, '__len__') and length is None:
        length = len(iterable)

    last = 0
    fill = 0
    if hasattr(fd, 'isatty') and (not fd.isatty()):
        fd.write('0 |' + ' ' * size + '| 100\n  |')
        fd.flush()
        lastfill = fill
    start = time()
    for i, v in enumerate(iterable):
        if fd.isatty():
            print_flag = ( i == 0 )
            if timeout is not None and time() - last > timeout:
                last = time()
                print_flag = True
            elif every is not None and (i+1) % every == 0:
                print_flag = True
            elif length is not None and i == length - 1:
                print_flag = True

            if print_flag:
                vals = {}
                vals['completed'] = i + 1
                vals['total'] = length
                if length is not None:
                    vals['percent'] = (i + 1) * 100.0 / length
                    fill = int(size * float(i+1) / length)
                else:
                    vals['percent'] = 0.0
                    fill += 1

                now = time()
                elapsed = now - start
                vals['elapsed'] = pretty_time(elapsed)
                if i == 0 or length is None:
                    vals['remaining'] = 'N/A'
                    vals['eta'] = 'N/A'
                else:
                    remaining = elapsed / i * ( length - i )
                    vals['remaining'] = pretty_time(remaining)
                    eta = now + remaining
                    vals['eta'] = strftime(timefmt, localtime(eta))

                if length:
                    pb = '[' + '=' * fill + ' ' * (size-fill) + '] '
                else:
                    pos = fill % (2*(size-1))
                    if pos >= size:
                        pos = 2*size - pos - 2
                    pb = '[' + ' ' * (pos) + '=' + ' ' * (size-pos-1) + '] '
                vals['bar'] = pb
                fd.write( '\r' + fmt.format(**vals) )
                fd.flush()
        else:
            if length:
                fill = ( (i + 1) * size ) // length
                if fill > lastfill:
                    lastfill = fill
                    fd.write('=')

        yield v

    if not fd.isatty():
        fd.write('|')
    fd.write('\n')
    fd.flush()
