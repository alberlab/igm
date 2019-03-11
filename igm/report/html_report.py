import os
import os.path as op
import base64
from alabtools.utils import natural_sort


css = '''
table {
    border: 1px solid grey;
}

td, th {
    text-align: center;
    padding: .3em 1em .3em 1em;
}

.folder {
    padding-left:1em;
    border-left:1px solid grey;
}

.lvl-1 {
    padding-left:0;
    border-left:0;
}

pre {
    border: 1px dashed grey;
    background-color: #eeeeee;
}

th {
    font-weight:bold;
}

.pfile {
    padding: 1em;
    border: 1px dotted #dddddd;
}

img {
    max-width: 70vw;
    max-height: 80vh;
    width: auto;
    height: auto;
}
'''


def looks_like_a_table(filename):
    lines = open(filename).readlines()
    if len(lines) < 2:
        return False
    if not lines[0].startswith('#'):
        return False
    n = len(lines[1].split())
    for l in lines[2:]:
        if l.strip() == '':
            continue
        if len(l.split()) != n:
            return False
    return True


def to_html_table(textfile, attrs=''):
    lines = open(textfile).readlines()
    headers = lines[0].replace('#', '').strip().split()
    thead = '<thead><th>' + '</th><th>'.join(headers) + '</th></thead>'
    tbody = '<tbody>'
    for l in lines[1:]:
        values = l.strip().split()
        tbody += '<tr><td>' + '</td><td>'.join(values) + '</td></tr>'
    tbody += '</tbody>'
    return '<table ' + attrs + '>' + thead + tbody + '</table>'


def handle_file(filename, lines):
    lines.append(f'<a href="file:///{op.abspath(filename)}">'
                 f'{op.basename(filename)}</a></p>')
    _, ext = op.splitext(filename)
    if ext in ['.png', '.jpg', '.bmp', '.gif']:
        data_uri = base64.b64encode(
            open(filename, 'rb').read()).decode('utf-8').replace('\n', '')
        lines.append(f'<img width="100%" src="data:image/{ext[1:]};base64,{data_uri}"/>')
    elif ext == '.txt':
        # check if it is a table
        if looks_like_a_table(filename):
            lines.append(to_html_table(filename, 'border="1"'))
        else:
            content = open(filename).read()
            clines = content.split('\n')
            nlines = len(clines)
            if nlines > 40:
                preview_text = '\n'.join(clines[:8]) + f'\n... (+ {nlines - 8} other lines)'
                lines.append(f'<pre>{preview_text}</pre>')
            else:
                lines.append(f'<pre>{content}</pre>')

    else:
        lines.append('<p>Preview not available.</p>')


def sort_items(base, items):
    files = []
    folders = []
    for it in items:
        if op.isfile(op.join(base, it)):
            files.append(it)
        elif op.isdir(op.join(base, it)):
            folders.append(it)
    folders.sort()
    files = natural_sort(files)
    return folders + files


def process_dir(folder, lvl, lines):
    items = sort_items(folder, os.listdir(folder))
    lines.append(f'<div class="folder lvl-{lvl}">')
    lines.append(f'<h{lvl}>{op.basename(folder)}</h{lvl}>')

    for it in items:
        if op.isfile(op.join(folder, it)):
            lines.append('<div class="pfile">')
            handle_file(op.join(folder, it), lines)
            lines.append(f'</div>')
        elif op.isdir(op.join(folder, it)):
            process_dir(op.join(folder, it), lvl+1, lines)

    lines.append(f'</div>')


def generate_html_report(folder):
    """
    Scrapes the output folder and generates a single, navigable file.
    Parameters
    ----------
    folder : str
    """

    while folder.endswith('/'):
        folder = folder[:-1]

    # get the label
    try:
        with open('label.txt', 'r') as f:
            run_label = f.read()
    except IOError:
        run_label = ''

    if run_label == '':
        run_label = op.basename(folder)

    lines = []
    process_dir(folder, 1, lines)
    head = f'<head><title>IGM Report: {op.basename(folder)}</title><style>{css}</style></head>'

    header = f'<h1>{run_label}</h1><h2>{op.abspath(folder)}</h2><hr>'

    body = '<body>' + header + '\n'.join(lines) + '</body>'
    return head + body
