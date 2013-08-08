#!/usr/bin/env python
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


import copy
import os
import random
import sys
import tempfile
from multiprocessing import Process

os.environ['EVENTLET_NO_GREENDNS'] = 'yes'
import eventlet
eventlet.monkey_patch(os=False, thread=False)

from oslo.config import cfg

from nova.openstack.common import gettextutils
gettextutils.install('novadbtest')

from nova import conductor
from nova import context
from nova import config
from nova import db
from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging
from nova.openstack.common import periodic_task
from nova.openstack.common import service
from nova import utils

import sqlalchemy.engine


CONF = cfg.CONF
CONF.import_opt('connection',
                'nova.openstack.common.db.sqlalchemy.session', group='database')
LOG = logging.getLogger(__name__)

cli_opts = [
    cfg.IntOpt('num_comp',
               default=10000,
               help='number of compute nodes'),
    cfg.IntOpt('num_stat',
               default=20,
               help='number of stats record for each compute node'),
    cfg.IntOpt('periodic_fuzzy_delay',
               default=60,
               help='range of seconds to randomly delay when starting the'
                    ' periodic task scheduler to reduce stampeding.'
                    ' (Disable by setting to 0)'),
    cfg.BoolOpt('join_stats',
                default=False,
                help='generate stats data for each compute node for DB join')
]
CONF.register_cli_opts(cli_opts)


def _init_db():
    # cleaning tables DB
    url=sqlalchemy.engine.url.make_url(CONF.database.connection)
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "w") as f:
        f.write('mysql -u%s -p%s -h%s -e "use %s; delete from compute_nodes; delete from compute_node_stats"\n' % (
                 url.username, url.password, url.host, url.database))
    utils.execute('sh', '%s' % path)
    os.remove(path)


class MimicComputeManger(periodic_task.PeriodicTasks):
    def __init__(self, compute_node, values):
        self.compute_node = compute_node
        self.values = values
        self.conductor_api = conductor.API()
    
    def periodic_tasks(self, context, raise_on_error=False):
        """Tasks to be run at a periodic interval."""
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    @periodic_task.periodic_task    
    def update_compute(self, context):
        #import pdb
        #pdb.set_trace()
        LOG.info("update_compute id %d", self.compute_node['id'])
        if "service" in self.compute_node:
            del self.compute_node['service']
        self.compute_node = self.conductor_api.compute_node_update(
            context, self.compute_node, self.values, False)


class MimicService(service.Service):
    def __init__(self, manager):
        super(MimicService, self).__init__(threads=1)
        self.manager = manager
        self.periodic_fuzzy_delay = CONF.periodic_fuzzy_delay
    
    def periodic_tasks(self, raise_on_error=False):
        """Tasks to be run at a periodic interval."""
        ctxt = context.get_admin_context()
        return self.manager.periodic_tasks(ctxt, raise_on_error=raise_on_error)
    
    def start(self):
        if self.periodic_fuzzy_delay:
            initial_delay = random.randint(0, self.periodic_fuzzy_delay)
        else:
            initial_delay = None
        self.tg.add_dynamic_timer(self.periodic_tasks,
                                     initial_delay=initial_delay,
                                     periodic_interval_max=None)

class DummyService(service.Service):
    def start(self):
        super(DummyService, self).start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)
                


def mimic_compute_update(compute_node, values):
    manager = MimicComputeManger(compute_node, values)
    service = MimicService(manager)
    service.start()
    service.wait()


def mimic_update(compute_node, values, initial_delay):
    PERIORICAL_INTERNVAL = 60
    conductor_api = conductor.API()
    if initial_delay:
        eventlet.sleep(initial_delay)
    while True:
        print("update_compute id %d" % compute_node['id'])
        ctxt = context.get_admin_context()
        if "service" in compute_node:
            del compute_node['service']
        compute_node = conductor_api.compute_node_update(
            ctxt, compute_node, values, False)
        eventlet.sleep(PERIORICAL_INTERNVAL)


def _generate_stats(id_num):
    stats = {}
    i = 0
    while i < CONF.num_stat:
        key = 'key%d' % i
        stats[key] = id_num + i
        i = i + 1
    return stats


def parepare_data(join_stats):
    _init_db()
    print "Starting prepare data in DB"
    ctx = context.get_admin_context()
    i = 0
    
    datas = []
    while i < CONF.num_comp:
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
        if not join_stats:
            comp_values['cpu_info'] = jsonutils.dumps(_generate_stats(i))
        else:
            comp_values['cpu_info'] = jsonutils.dumps('')
            comp_values['stats'] = _generate_stats(i)
        values = copy.deepcopy(comp_values)
        compute_ref = jsonutils.to_primitive(
                        db.compute_node_create(ctx, comp_values))
        LOG.info('Compute node record created for id %d', compute_ref['id'])
        #datas.append((compute_ref, values))
        
        #prepare for the update process
        if CONF.periodic_fuzzy_delay:
            initial_delay = random.randint(0, CONF.periodic_fuzzy_delay)
        else:
            initial_delay = 0
        initial_delay = 0
        p = Process(target=mimic_update, args=(compute_ref, values, initial_delay))
        p.daemon = True
        datas.append(p)
        i = i + 1

    '''
    # start thread to mimic compute node update DB
    for (ref, val) in datas:
        #comp_srv=threading.Thread(target=mimic_compute_update,
        #                          args=(ref, val))
        #comp_srv.start()
        eventlet.spawn(mimic_compute_update, ref, val)
    '''
    for p in datas:
        p.start()
    
    print "Finish preparing data in DB"
    
    
def main():
    config.parse_args(sys.argv,['novadbtest.conf'])
    logging.setup("novadbtest")
    parepare_data(CONF.join_stats)
    dummy = DummyService()
    dummy.start()
    dummy.wait()


if __name__ == '__main__':
    main()
