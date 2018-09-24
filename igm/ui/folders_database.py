#!/usr/bin/env python
import os
from os.path import normpath, abspath, isfile, isdir
import sqlite3
import time

def create_db(db_file):
    with sqlite3.connect(db_file) as db:
        q = 'CREATE TABLE paths (folder TEXT, name TEXT, cell_line TEXT, resolution TEXT, notes TEXT, tags TEXT, created INT, last_modified INT)'
        db.execute(q)

def register_folder(folder, name="", cell_line="", resolution="", notes="", tags=""):

    folder = normpath( abspath(folder) )

    if not isdir(folder):
        raise RuntimeError('Error: the directory `%s` does not exist or it is not readable\n' % folder)

    db_file = os.environ['HOME'] + '/.igm/paths.db'

    if not isfile(db_file):
        create_db(db_file)

    with sqlite3.connect(db_file) as db:

        c = db.execute('SELECT count(folder) FROM paths WHERE folder=?', (folder, )).fetchall()[0][0]
        if c > 0:
            db.execute('UPDATE paths SET name=?, cell_line=?, resolution=?, notes=?, tags=?, last_modified=? WHERE folder=?', (name, cell_line, resolution, notes, tags, int(time.time()), folder) )

        else:
            db.execute('INSERT into paths (folder, name, cell_line, resolution, notes, tags, created, last_modified) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                       (folder, name, cell_line, resolution, notes, tags, int(time.time()), int(time.time())) )

    return True

def unregister_folder(folder):
    folder = os.path.normpath( os.path.abspath(folder) )

    db_file = os.environ['HOME'] + '/.igm/paths.db'

    if not os.path.isfile(db_file):
        create_db(db_file)

    with sqlite3.connect(db_file) as db:
        x = db.execute('DELETE FROM paths WHERE folder=?', (folder,) )
        if x.rowcount == 0:
            raise RuntimeError('The folder %s is not in the database\n' % folder)

    return True

def folder_info(folder=None):
    if folder is not None:
        folder = os.path.normpath( os.path.abspath(folder) )

    db_file = os.environ['HOME'] + '/.igm/paths.db'

    if not os.path.isfile(db_file):
        create_db(db_file)

    with sqlite3.connect(db_file) as db:
        if folder is not None:
            # return only specified folder
            c = db.execute('SELECT folder, name, cell_line, resolution, notes, tags, created, last_modified FROM paths WHERE folder=?', (folder, )).fetchall()
            if len(c) == 0:
                raise RuntimeError('Error: folder `%s` not in the database\n' % folder)
            else:
                folder, name, cell_line, resolution, notes, tags, ct, mt = c[0]
                return {
                    'folder' : folder,
                    'name': name,
                    'cell_line' : cell_line,
                    'resolution' : resolution,
                    'notes' : notes,
                    'tags' : tags,
                    'created' : ct,
                    'last_modified' : mt
                }
        else:
            # return all the folders
            c = db.execute('SELECT folder, name, cell_line, resolution, notes, tags, created, last_modified FROM paths').fetchall()
            res = []
            for folder, name, cell_line, resolution, notes, tags, ct, mt in c:
                res.append({
                    'folder' : folder,
                    'name': name,
                    'cell_line' : cell_line,
                    'resolution' : resolution,
                    'notes' : notes,
                    'tags' : tags,
                    'created' : ct,
                    'last_modified' : mt
                })
            return res
