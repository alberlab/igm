import os
import sqlite3
import time
import json

from ..utils.log import logger
from .config import Config

class StepDB(object):

    SCHEMA = [
        ('uid', 'TEXT'),
        ('name', 'TEXT'),
        ('cfg', 'TEXT'),
        ('time', 'INT'),
        ('status', 'TEXT'),
        ('data', 'TEXT')
    ]

    JSONCOLS = ['cfg', 'data']

    COLUMNS = [x[0] for x in SCHEMA]

    def __init__(self, cfg, mode='a'):
        self.db = None
        if isinstance(cfg, str):
            try:
                cfg = Config(cfg)
            except:
                pass
        elif isinstance(cfg, Config):
            pass
        elif isinstance(cfg, dict):
            cfg = Config(cfg)
        else:
            raise ValueError('Invalid argument (needs to be Config, dict or string, got %s)' % type(cfg) )
        self.prepare_db(cfg, mode=mode)

    def prepare_db(self, cfg, mode='a'):
        if isinstance(cfg, str):
            self.db = cfg
        else:
            self.db = cfg.get('parameters/step_db', None)
        if self.db:
            if os.path.isfile(self.db):
                logger.debug('db file found')
                # check db follows the schema
                try:
                    with sqlite3.connect(self.db) as conn:
                        s = conn.execute('PRAGMA table_info(steps)').fetchall()
                    assert s is not None
                    for i, (n, t) in enumerate(StepDB.SCHEMA):
                        if n != s[i][1] or t != s[i][2]:
                            msg = 'invalid column %s %s ' % (s[i][1], s[i][2])
                            msg += '(expected: %s %s)' % (n, t)
                            raise AssertionError(msg)

                except AssertionError as e:
                    msg = 'Invalid database file %s.' % self.db
                    raise type(e)(e.message + '\n' + msg)

            else:
                if mode == 'r':
                    raise OSError('File not found')
                with sqlite3.connect(self.db) as conn:
                    conn.execute(
                        'CREATE TABLE steps (' +
                        ','.join([
                            ' '.join(x) for x in StepDB.SCHEMA
                        ]) +
                        ')'
                    )

    def record(self, **kwargs):

        if self.db is None:
            return

        data = {}

        # prepare columns
        for c, t in StepDB.SCHEMA:
            if c == 'time':
                data['time'] = kwargs.get('time', time.time())
            elif c in StepDB.JSONCOLS:
                data[c] = json.dumps( kwargs.get(c, None) )
            else:
                data[c] = kwargs.get(c, '')

        with sqlite3.connect(self.db) as conn:
            conn.execute(
                'INSERT INTO steps (' +
                ','.join(StepDB.COLUMNS) +
                ') VALUES (' +
                ','.join( ['?'] * len(StepDB.COLUMNS) ) +
                ')',
                tuple(data[c] for c in StepDB.COLUMNS)
            )

    def unpack(self, result):
        out = {}
        for i, c in enumerate(StepDB.COLUMNS):
            if c in StepDB.JSONCOLS:
                out[c] = json.loads(result[i])
            else:
                out[c] = result[i]
        return out

    def get_history(self, uid=None):

        with sqlite3.connect(self.db) as conn:
            if uid is None:
                query = 'SELECT * FROM steps ORDER BY time'
                r = conn.execute(
                    query
                ).fetchall()
            else:
                query = 'SELECT * FROM steps WHERE uid=? ORDER BY time'
                r = conn.execute(
                    query,
                    (uid,)
                ).fetchall()
        return [ self.unpack(x) for x in r ]
