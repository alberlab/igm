import glob
from os.path import basename, normpath, abspath, isdir, isfile

def list_directory(path, root='/', ext=None):

    root = normpath(root)
    dname = normpath( abspath(root + '/' + path) )

    if not dname.startswith(root) or not isdir(dname):
        return {}

    content = glob.glob(dname + '/*')
    dirs = []

    if abspath(dname) != abspath(root):
        dirs += [ '..' ]

    rootlen = len(root)+1
    dirs += [basename( normpath(c) ) for c in content if isdir(c)]
    files = [basename( normpath(c) ) for c in content if isfile(c)]

    if ext is not None:
        if not isinstance(ext, list):
            ext = [ext]
        nfiles = []
        for e in ext:
            nfiles += [c for c in files if c.endswith(e)]
        files = nfiles

    return {
        'path': dname[rootlen:],
        'dirs': dirs,
        'files': files,
    }
