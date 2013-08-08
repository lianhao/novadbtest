#!/usr/bin/env python
import os
import tempfile
import sqlalchemy.engine
import sys


from oslo.config import cfg

from nova.openstack.common import gettextutils
gettextutils.install('novadbtest')

from nova import config
from nova.db import migration
from nova.openstack.common import log as logging
from nova import utils


CONF = cfg.CONF
CONF.import_opt('connection',
                'nova.openstack.common.db.sqlalchemy.session', group='database')
LOG = logging.getLogger(__name__)


def init_db():
    # create DB
    print "Starting creating DB tables"
    url=sqlalchemy.engine.url.make_url(CONF.database.connection)
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "w") as f:
        f.write('mysql -u%s -p%s -h%s -e "DROP DATABASE IF EXISTS %s;"\n' % (
                 url.username, url.password, url.host, url.database))
        f.write('mysql -u%s -p%s -h%s -e "CREATE DATABASE %s CHARACTER SET %s;"\n' % (
                 url.username, url.password, url.host, url.database, 
                 url.query.get('charset', 'utf8')))
    utils.execute('sh', '%s' % path)
    os.remove(path)
    #create tables
    migration.db_sync()
    print "Finished creating DB tables"


def main():
    config.parse_args(sys.argv,['novadbtest.conf'])
    logging.setup("novadbtest")
    init_db()


if __name__ == '__main__':
    main()