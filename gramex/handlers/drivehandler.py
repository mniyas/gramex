import re
import os
import time
import tornado.gen
import gramex.data
import sqlalchemy as sa
from string import ascii_lowercase, digits
from random import choice
from mimetypes import guess_type
from tornado.web import HTTPError
from gramex.http import NOT_FOUND, REQUEST_ENTITY_TOO_LARGE, UNSUPPORTED_MEDIA_TYPE
from .formhandler import FormHandler

MAX_SIZE = 2**31


class DriveHandler(FormHandler):
    '''
    Lets users manage files. Here's a typical configuration::

        path: $GRAMEXDATA/apps/appname/     # Save files here
        customfields:
            user: [id, role, hd]            # user attributes to store
            tags: [tag]                     # <input name=""> to store
        filelimits:
            allow: [.doc, .docx]
            exclude: [.pdf]
            max_size: 100000
        redirect:                           # After uploading the file,
            query: next                     #   ... redirect to ?next=
            url: /$YAMLURL/                 #   ... else to this directory

    File metadata is stored in <path>/.meta.db as SQLite
    '''
    @classmethod
    def setup(cls, path, customfields=None, filelimits=None, **kwargs):
        cls.path = path
        cls.customfields = customfields or {}
        cls.filelimits = filelimits or {}
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)

        # Set up the parent FormHandler with a single SQLite URL and table
        url, table = 'sqlite:///' + os.path.join(path, '.meta.db'), 'drive'
        kwargs.update(url=url, table=table, id='id')
        cls.special_keys += ['path', 'customfields', 'filelimits']
        super().setup(**kwargs)

        # Ensure all customfields are present in "drive" table
        engine = sa.create_engine(url)
        meta = sa.MetaData(bind=engine)
        meta.reflect()
        cls._db_cols = {
            'id': sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            'file': sa.Column('file', sa.Text),             # Original file name
            'ext': sa.Column('ext', sa.Text),               # Original file extension
            'path': sa.Column('path', sa.Text),             # Saved file relative path
            'size': sa.Column('size', sa.Integer),          # File size
            'mime': sa.Column('mime', sa.Text),             # MIME type
            'date': sa.Column('date', sa.Integer),          # Uploaded date
        }
        for s in customfields.get('user', []):
            cls._db_cols['user_%s' % s] = sa.Column('user_%s' % s, sa.String)
        for s in customfields.get('tags', []):
            cls._db_cols.setdefault(s, sa.Column(s, sa.String))
        if table in meta.tables:
            with engine.connect() as conn:
                with conn.begin():
                    for col, coltype in cls._db_cols.items():
                        if col not in meta.tables[table].columns:
                            conn.execute('ALTER TABLE %s ADD COLUMN %s TEXT' % (table, col))
        else:
            sa.Table(table, meta, *cls._db_cols.values()).create(engine)

        # If ?_download=...&id=..., then download the file via modify:
        def download_plugin(data, key, handler):
            data = original_modify(data, key, handler)
            ids = handler.args.get('id', [])
            if len(ids) != 1 or '_download' not in handler.args:
                return data
            if len(data) == 0:
                raise HTTPError(NOT_FOUND, 'No file record with id=%s' % ids[0])
            path = os.path.join(handler.path, data['path'][0])
            if not os.path.exists(path):
                raise HTTPError(NOT_FOUND, 'Missing file for id=%s' % ids[0])
            handler.set_header('Content-Type', data['mime'][0])
            handler.set_header('Content-Length', os.stat(path).st_size)
            handler.set_header(
                'Content-Disposition', 'attachment; filename="%s"' % data['file'][0])
            with open(path, 'rb') as handle:
                return handle.read()

        original_modify = cls.datasets['data'].get('modify', lambda v, *args: v)
        cls.datasets['data']['modify'] = download_plugin

    def check_filelimits(self):
        max_size = self.filelimits.get('max_size') or MAX_SIZE
        allow = set(ext.lower() for ext in self.filelimits.get('allow', []))
        exclude = set(ext.lower() for ext in self.filelimits.get('exclude', []))
        for name, ext, size in zip(self.args['file'], self.args['ext'], self.args['size']):
            if size > max_size:
                raise HTTPError(REQUEST_ENTITY_TOO_LARGE, '%s: %d > %d' % (
                    name, size, max_size))
            if ext in exclude or (allow and ext not in allow):
                raise HTTPError(UNSUPPORTED_MEDIA_TYPE, name)

    @tornado.gen.coroutine
    def post(self, *path_args, **path_kwargs):
        '''Saves uploaded files, then updates metadata DB'''
        uploads = self.request.files.get('file', [])
        n = len(uploads)
        # Initialize all DB columns (except ID) to have the same number of rows as uploads
        for key, col in list(self._db_cols.items())[1:]:
            self.args[key] = self.args.get(key, []) + [col.type.python_type()] * n
        for key in self.args:
            self.args[key] = self.args[key][:n]
        for i, upload in enumerate(uploads):
            file = os.path.basename(upload.get('filename', ''))
            ext = os.path.splitext(file)[1]
            path = re.sub(r'[^!#$%&()+,.0-9;<=>@A-Z\[\]^`a-z{}~]', '-', file)
            while os.path.exists(os.path.join(self.path, path)):
                path = os.path.splitext(path)[0] + choice(digits + ascii_lowercase) + ext
            self.args['file'][i] = file
            self.args['ext'][i] = ext.lower()
            self.args['path'][i] = path
            self.args['size'][i] = len(upload['body'])
            self.args['date'][i] = int(time.time())
            # Guess MIME type from filename if it's unknown
            self.args['mime'][i] = upload['content_type']
            if self.args['mime'][i] == 'application/unknown':
                self.args['mime'][i] = guess_type(file, strict=False)[0]
            # Append user attributes
            for s in self.customfields.get('user', []):
                self.args['user_%s' % s][i] = (self.current_user or {}).get(s, None)
        self.check_filelimits()
        yield super().post(*path_args, **path_kwargs)
        for upload, path in zip(uploads, self.args['path']):
            with open(os.path.join(self.path, path), 'wb') as handle:
                handle.write(upload['body'])

    @tornado.gen.coroutine
    def delete(self, *path_args, **path_kwargs):
        '''Deletes files from metadata DB and from file system'''
        conf = self.datasets.data
        files = gramex.data.filter(conf.url, table=conf.table, args=self.args)
        result = yield super().delete(*path_args, **path_kwargs)
        for index, row in files.iterrows():
            path = os.path.join(self.path, row['path'])
            if os.path.exists(path):
                os.remove(path)
        return result
