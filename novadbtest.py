# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2011 X.commerce, a business unit of eBay Inc.
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

# Interactive shell based on Django:
#
# Copyright (c) 2005, the Lawrence Journal-World
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     1. Redistributions of source code must retain the above copyright notice,
#        this list of conditions and the following disclaimer.
#
#     2. Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#
#     3. Neither the name of Django nor the names of its contributors may be
#        used to endorse or promote products derived from this software without
#        specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


"""
  CLI interface for nova management.
"""

import argparse
import os
import sys
import tempfile
import time

from oslo.config import cfg

from nova.openstack.common import gettextutils
gettextutils.install('novadbtest')

from nova import context
from nova import db
from nova.db import migration
from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging
from nova import utils
from nova import version

import sqlalchemy.engine


CONF = cfg.CONF
CONF.import_opt('sql_connection',
                'nova.openstack.common.db.sqlalchemy.session')
LOG = logging.getLogger(__name__)

cli_opts = [
    cfg.IntOpt('num_comp',
               default=10000,
               help='number of compute nodes'),
    cfg.IntOpt('num_stat',
               default=20,
               help='number of stats record for each compute node')
]
CONF.register_cli_opts(cli_opts)


def timing(f):
    def wrap(*args):
        time1 = time.time()
        ret = f(*args)
        time2 = time.time()
        return (ret, time2-time1)
    return wrap

def init_conf():
    #parse configuration file to get sql_connection
    path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                        'novadbtest.conf')
    assert os.path.exists(path)
    try:
        CONF(sys.argv[1:],
              project='novadbtest',
              version=version.version_string(),
              default_config_files=[path])
        logging.setup("novadbtest")
    except cfg.ConfigFilesNotFoundError:
        cfgfile = CONF.config_file[-1] if CONF.config_file else None
        if cfgfile and not os.access(cfgfile, os.R_OK):
            st = os.stat(cfgfile)
            print "Could not read %s. Re-running with sudo" % cfgfile
            try:
                os.execvp('sudo', ['sudo', '-u', '#%s' % st.st_uid] + sys.argv)
            except Exception:
                print 'sudo failed, continuing as if nothing happened'

        print 'Please re-run nova-manage as root.'
        exit(2)


def _init_db():
    # create DB
    print "Starting creating DB tables"
    url=sqlalchemy.engine.url.make_url(CONF.sql_connection)
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


def _generate_stats(id_num):
    stats = {}
    i = 0
    while i < CONF.num_stat:
        key = 'key%d' % i
        stats[key] = id_num + i
        i = i + 1
    return stats


def parepare_data(use_json=False):
    _init_db()
    print "Starting prepare data in DB"
    ctx = context.get_admin_context()
    i = 0
    while i < CONF.num_comp:
        if CONF.num_comp >= 100 and i % (CONF.num_comp/100) == 0:
            sys.stdout.write("prepared %d%% data\r" % (i * 100 / CONF.num_comp))
            sys.stdout.flush()
        svc_values = {
            'host': 'host-%d' % i,
            'binary': 'novadbtest',
            'topic': 'novadbtest',
            'report_count': 0,
        }
        #created service record
        service_ref = jsonutils.to_primitive(
                           db.service_create(ctx, svc_values))
        LOG.info(_('Service record created for %s')
                    % service_ref['host'])
        #create compute node record
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
        if use_json:
            comp_values['cpu_info'] = jsonutils.dumps(_generate_stats(i))
        else:
            comp_values['cpu_info'] = jsonutils.dumps('')
            comp_values['stats'] = _generate_stats(i)
        compute_ref = jsonutils.to_primitive(
                        db.compute_node_create(ctx, comp_values))
        LOG.info(_('Compute node record created for %s')
                    % service_ref['host'])
        i = i + 1
    print "Finish preparing data in DB"


@timing
def do_get_compute_node(use_json=False):
    ctx = context.get_admin_context()
    compute_nodes = db.compute_node_get_all(ctx)
    if use_json:
        for node in compute_nodes:
            stats = node.get('stats',{})
            assert(not stats)
            node['cpu_info'] = jsonutils.loads(node['cpu_info'])


def test_main(use_json, desc, results):
    print "\nStart test %s" % desc
    parepare_data(use_json)
    (ret, elapse_time) = do_get_compute_node(use_json)
    print "Finish test %s in %f seconds\n" % (desc, elapse_time)
    results[desc] = elapse_time

def main():
    init_conf()
    results = {}
    test_main(False, 'JOINLOAD', results)
    test_main(True, 'JSON', results)
    print '============Summary============'
    print '# of compute nodes: %d' % CONF.num_comp
    print '# of stat records per compute node: %d' % CONF.num_stat
    print '==============================='
    for (key,value) in results.iteritems():
        print 'TestName:%s \t Time:%f sec' % (key, value)


if __name__ == '__main__':
    main()
