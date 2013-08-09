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
import signal
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
from nova.openstack.common import importutils
from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging
from nova.openstack.common import periodic_task
from nova.openstack.common import service

rpc = importutils.try_import('nova.openstack.common.rpc')
CONF = cfg.CONF
CONF.import_opt('connection',
                'nova.openstack.common.db.sqlalchemy.session', group='database')
LOG = logging.getLogger(__name__)

cli_opts = [
    cfg.IntOpt('periodic_fuzzy_delay',
               default=60,
               help='range of seconds to randomly delay when starting the'
                    ' periodic task to reduce stampeding.'
                    ' (Disable by setting to 0)'),
    cfg.IntOpt('num_proc',
               default=100,
               help='maximum allowed subprocess to launch to mimic the nova-compute updates.'
                    'each subprocess will update num/num_proc number of compute nodes'
                    'at a periodic interval of 60/num_proc'),
    cfg.IntOpt('start',
               default=0,
               help='how many compute nodes to skip for udpate.'),
    cfg.IntOpt('num',
               default=0,
               help='how many compute nodes to udpate, 0 means all'),
]
CONF.register_cli_opts(cli_opts)


PERIORICAL_INTERNVAL = 60


'''
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


def mimic_compute_update(compute_node, values):
    manager = MimicComputeManger(compute_node, values)
    service = MimicService(manager)
    service.start()
    service.wait()
'''

class DummyService(service.Service):
    def start(self):
        super(DummyService, self).start()
        # Add a dummy thread to have wait() working
        self.tg.add_timer(604800, lambda: None)


def mimic_update(group_datas, initial_delay):
    conductor_api = conductor.API()
    if initial_delay:
        eventlet.sleep(initial_delay)
    while True:
        length = len(group_datas)
        for i in range(length):
            (compute_node, values) = group_datas[i]
            LOG.debug("update_compute id %d",compute_node['id'])
            ctxt = context.get_admin_context()
            if "service" in compute_node:
                    del compute_node['service']
            compute_node = conductor_api.compute_node_update(
                    ctxt, compute_node, values, True)
            group_datas[i] = (compute_node, values)
        eventlet.sleep(PERIORICAL_INTERNVAL * 1.0/length)


def _get_initial_delay():
    if CONF.periodic_fuzzy_delay:
        initial_delay = random.randint(0, CONF.periodic_fuzzy_delay)
    else:
        initial_delay = 0
    return initial_delay


def parepare_process():

    def _statmap(stats):
        return dict((st['key'], st['value']) for st in stats)

    datas = []
    procs = []
    ctx = context.get_admin_context()
    all_compute_nodes = jsonutils.to_primitive(db.compute_node_get_all(ctx))
    total = len(all_compute_nodes)
    start = CONF.start
    num = CONF.num
    if num <= 0:
        num = total
    num -= start

    if total < 1:
        print "No compute nodes found"
        sys.exit(-1)

    print "# of compute nodes total:    %d" % total
    print "# of compute nodes to update:   %d" % num
    print "# of stat for each node:     %d" % len(jsonutils.loads(all_compute_nodes[0]['cpu_info']))
    print "Using JOIN:                  %s" % str(len(all_compute_nodes[0]['stats']) > 0)

    for compute_ref in sorted(all_compute_nodes, key=lambda node: node['id']):
        if start > 0:
            start -= 1
            continue
        values = copy.deepcopy(compute_ref)
        if "service" in values:
            del values['service']
        if "id" in values:
            del values['id']
        #convert stats
        stats = values.get('stats', [])
        statmap = _statmap(stats)
        values['stats'] = statmap

        datas.append((compute_ref, values))

        #prepare for the update process
        if len(datas) >= num / CONF.num_proc and len(procs) < CONF.num_proc - 1:
            p = Process(target=mimic_update, args=(copy.deepcopy(datas), _get_initial_delay()))
            procs.append(p)
            datas = []
    #remaining data
    if len(datas):
        p = Process(target=mimic_update, args=(copy.deepcopy(datas), _get_initial_delay()))
        procs.append(p)
        datas = []

    '''
    # start thread to mimic compute node update DB
    for (ref, val) in datas:
        #comp_srv=threading.Thread(target=mimic_compute_update,
        #                          args=(ref, val))
        #comp_srv.start()
        eventlet.spawn(mimic_compute_update, ref, val)
    '''
    return procs
    

class SignalExit(SystemExit):
    def __init__(self, signo, exccode=1):
        super(SignalExit, self).__init__(exccode)
        self.signo = signo

        
def _handle_signal(signo, frame):
    # Allow the process to be killed again and die from natural causes
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    raise SignalExit(signo)    

    
def main():
    config.parse_args(sys.argv,['novadbtest.conf'])
    logging.setup("novadbtest")
    procs = parepare_process()
    # start subprocess
    for p in procs:
        p.start()
    print 'All %d subprocesses have been started' % len(procs)
    dummy = DummyService()
    dummy.start()
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    try:
        status = None
        dummy.wait()
    except SignalExit as exc:
        signame = {signal.SIGTERM: 'SIGTERM',
                   signal.SIGINT: 'SIGINT'}[exc.signo]
        LOG.info('Caught %s, exiting', signame)
        status = exc.code
        for p in procs:
            p.terminate()
    except SystemExit as exc:
        status = exc.code
    finally:
        if rpc:
            rpc.cleanup()
        dummy.stop()
    return status


if __name__ == '__main__':
    main()
