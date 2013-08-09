#!/usr/bin/env python
import os
import tempfile
import sqlalchemy.engine
import sys

from oslo.config import cfg

from nova.openstack.common import gettextutils
gettextutils.install('novadbtest')

from nova import context
from nova import config
from nova import db
from nova.db import migration
from nova.openstack.common import log as logging
from nova.openstack.common import jsonutils
from nova import utils


CONF = cfg.CONF
CONF.import_opt('connection',
                'nova.openstack.common.db.sqlalchemy.session', group='database')

cli_opts = [
    cfg.IntOpt('num_comp',
               default=10000,
               help='number of compute nodes'),
    cfg.IntOpt('num_stat',
               default=20,
               help='number of stats record for each compute node.'
                    'If join_stats is False, these stats will be stored as json'
                    'encoded TEXT in the cpu_info column'),
    cfg.BoolOpt('join_stats',
                default=False,
                help='generate stats data for each compute node for DB join')
]
CONF.register_cli_opts(cli_opts)

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


def generate_data():
    def _generate_stats(id_num):
        stats = {}
        i = 0
        while i < CONF.num_stat:
            key = 'key%d' % i
            stats[key] = id_num + i
            i = i + 1
        return stats

    print "Starting prepare data in DB"
    ctx = context.get_admin_context()
    for i in range(CONF.num_comp):
        if  i *100.0 % CONF.num_comp == 0:
            sys.stdout.write("prepared %d%% data\r" % (i * 100.0 / CONF.num_comp))
            sys.stdout.flush()
        svc_values = {
            'host': 'host-%d' % i,
            'binary': 'novadbtest',
            'topic': 'novadbtest',
            'report_count': 0,
        }
        #created service record
        service_ref = jsonutils.to_primitive(
                           db.service_get_by_host_and_topic(ctx, 
                                                            svc_values['host'],
                                                            svc_values['topic']))
        if not service_ref:
            service_ref = jsonutils.to_primitive(
                               db.service_create(ctx, svc_values))
        LOG.info('Service record created for id %d', service_ref['id'])
        #create/update compute node record
        comp_values = {
            'service_id': service_ref['id'],
            'vcpus': i,
            'memory_mb': i,
            'local_gb': i,
            'vcpus_used': i,
            'memory_mb_used': i,
            'local_gb_used': i,
            'hypervisor_type': 'qemu',
            'hypervisor_version': 1,
            'hypervisor_hostname': 'test',
            'free_ram_mb': i,
            'free_disk_gb': i,
            'current_workload': i,
            'running_vms': i,
            'disk_available_least': i,
            }
        if not CONF.join_stats:
            comp_values['cpu_info'] = jsonutils.dumps(_generate_stats(i))
        else:
            comp_values['cpu_info'] = jsonutils.dumps(_generate_stats(i))
            comp_values['stats'] = _generate_stats(i)
        compute_ref = jsonutils.to_primitive(
                        db.compute_node_create(ctx, comp_values))
        LOG.info('Compute node record created for id %d', compute_ref['id'])
    print "Finish preparing data in DB"

def main():
    config.parse_args(sys.argv,['novadbtest.conf'])
    logging.setup("novadbtest")
    init_db()
    generate_data()
    print "DB data succsessful generated!"
    print "==============================="
    print "# of compute nodes:          %d" % CONF.num_comp
    print "# of stat for each node:     %d" % CONF.num_stat
    print "Using JOIN:                  %s" % str(CONF.join_stats)


if __name__ == '__main__':
    main()