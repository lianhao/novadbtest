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

import os
import sys
import time

os.environ['EVENTLET_NO_GREENDNS'] = 'yes'
import eventlet
eventlet.monkey_patch(os=False)

from oslo.config import cfg

from nova.openstack.common import gettextutils
gettextutils.install('novadbtest')

from nova import context
from nova import config
from nova import db
from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging


CONF = cfg.CONF
CONF.import_opt('connection',
                'nova.openstack.common.db.sqlalchemy.session', group='database')
LOG = logging.getLogger(__name__)

cli_opts = [
    cfg.IntOpt('total',
               default=100,
               help='number of runs'),
]
CONF.register_cli_opts(cli_opts)


def timing(f):
    def wrap(*args):
        time1 = time.time()
        ret = f(*args)
        time2 = time.time()
        return (ret, time2-time1)
    return wrap


@timing
def do_get_compute_node():
    ctx = context.get_admin_context()
    compute_nodes = db.compute_node_get_all(ctx)
    for node in compute_nodes:
        node['cpu_info'] = jsonutils.loads(node['cpu_info'])
        if hasattr(node, 'metrics'):
            node['metrics'] = jsonutils.loads(node['metrics'] or jsonutils.dumps(''))

    return {'num_comp': len(compute_nodes),
            'num_stat': len(compute_nodes[0]['cpu_info']),
            'join_stats': len(compute_nodes[0].get('stats', [])) > 0
           }


def test_main(results,total):
    i = 0
    total_elapse = 0
    info = {}
    while i<total:       
        (info, elapse_time) = do_get_compute_node()
        i += 1
        print "Finish round %d in  %f seconds (num of nodes: %d, num of stats: %d, join_stats: %s)" % (i, elapse_time,
               info['num_comp'], info['num_stat'], info['join_stats'])
        total_elapse += elapse_time
        #time.sleep(0.5)
        eventlet.sleep(0.5)

    return (info, total_elapse)

def main():
    config.parse_args(sys.argv,['novadbtest.conf'])
    logging.setup("novadbtest")
    results = {'total_time': 0.0,
               'rounds': 0
               }
    #test_main(False, 'JOINLOAD', results)
    (info, total_time) = test_main(results, CONF.total)
    print '============Summary============'
    print 'total run:  %d' % CONF.total
    print '# num_comp: %d' % info.get('num_comp', 0)
    print '# num_stat: %d' % info.get('num_stat', 0)
    print '# join_stats: %s' % info.get('join_stats', False)
    print '==============================='
    print 'Average time of compute_node_get_all(): %f seconds' % (total_time / CONF.total)


if __name__ == '__main__':
    main()
