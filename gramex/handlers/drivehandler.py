import os
import time
import tornado.gen
import gramex.data
import sqlalchemy as sa
from string import ascii_lowercase, digits
from random import choice
from mimetypes import guess_type
from .formhandler import FormHandler


class DriveHandler(FormHandler):
    '''
    Lets users manage files. Here's a typical configuration::

        path: $GRAMEXDATA/apps/appname/     # Save files here
        cols:
            user: [id, role, hd]            # user attributes to store
            keys: [purpose]                 # <input name=""> to store
        redirect:                           # After uploading the file,
            query: next                     #   ... redirect to ?next=
            url: /$YAMLURL/                 #   ... else to this directory

    Notes:
    - File metadata is stored in <path>/.drivehandler.db.
    - If the same filename is re-uploaded, it's saved as file.<random-suffix>.ext
    '''
    @classmethod
    def setup(cls, path, cols=None, **kwargs):
        cls.path, cls.cols = path, cols
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)

        # Set up the parent FormHandler with a single SQLite URL and table
        url, table = 'sqlite:///' + os.path.join(path, '.meta.db'), 'drive'
        kwargs.update(url=url, table=table, id='id')
        cls.special_keys += ['path', 'cols']
        super().setup(**kwargs)

        # Ensure all cols are present in "drive" table
        engine = sa.create_engine(url)
        meta = sa.MetaData(bind=engine)
        meta.reflect()
        db_cols = {
            'id': sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
            'file': sa.Column('file', sa.Text),             # Original file name
            'path': sa.Column('path', sa.Text),             # Saved file relative path
            'size': sa.Column('size', sa.Integer),          # File size
            'mime': sa.Column('mime', sa.Text),             # MIME type
            'date': sa.Column('date', sa.Integer),          # Uploaded date
        }
        for s in cols.get('user', []):
            db_cols['user_%s' % s] = sa.Column('user_%s' % s, sa.String)
        for s in cols.get('keys', []):
            db_cols[s] = sa.Column(s, sa.String)
        if table in meta.tables:
            with engine.connect() as conn:
                with conn.begin():
                    for col, coltype in db_cols.items():
                        if col not in meta.tables[table].columns:
                            conn.execute('ALTER TABLE %s ADD COLUMN %s TEXT' % (table, col))
        else:
            sa.Table(table, meta, *cols.values()).create(engine)

    @tornado.gen.coroutine
    def delete(self, *args, **kwargs):
        conf = self.datasets['data']
        files = gramex.data.filter(conf.url, table=conf.table, args=self.args)
        result = yield super().delete(*args, **kwargs)
        for index, row in files.iterrows():
            path = os.path.join(self.path, row['path'])
            if os.path.exists(path):
                os.remove(path)
        return result

    @tornado.gen.coroutine
    def post(self, *args, **kwargs):
        arg = self.args
        arg['file'], arg['path'], arg['size'], arg['mime'], arg['date'] = [], [], [], [], []
        arg.setdefault('overwrite', [])
        for s in self.cols.get('user', []):
            arg['user_%s' % s] = []
        for i, upload in enumerate(self.request.files.get('file', [])):
            file = path = os.path.basename(upload.get('filename', ''))
            overwrite = arg['overwrite'][i] if len(arg['overwrite']) > i else False
            while os.path.exists(os.path.join(self.path, path)) and overwrite:
                name, ext = os.path.splitext(path)
                path = name + choice(digits + ascii_lowercase) + ext
            with open(os.path.join(self.path, path), 'wb') as handle:
                handle.write(upload['body'])
            arg['file'].append(file)
            arg['path'].append(path)
            arg['size'].append(len(upload['body']))
            arg['mime'].append(upload['content_type'] or guess_type(file, strict=False)[0])
            arg['date'].append(int(time.time()))
            for s in self.cols.get('user', []):
                arg['user_%s' % s].append((self.current_user or {}).get(s, None))
        # If more fields are provided than files, truncate the rest
        for key in arg:
            arg[key] = arg[key][:len(arg['file'])]

        yield super().post(*args, **kwargs)
