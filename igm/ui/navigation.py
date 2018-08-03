import os, os.path, glob

def list_directory(path, root):

    dname = root + '/' + path

    if not os.path.abspath(dname).startswith(root) or not os.path.isdir(dname):
        return {}

    dname = os.path.abspath(dname)

    content = glob.glob(dname + '/*')
    if os.path.abspath(dname) != os.path.abspath(root):
        dirs = [ path + '/..']
    else:
        dirs = []
    n = len(root)
    dirs += [c[n:] for c in content if os.path.isdir(c)]
    files = [c[n:] for c in content if os.path.isfile(c)]
    return {
        'path': dname,
        'dirs': dirs,
        'files': files,
    }
