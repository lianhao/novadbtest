#!/usr/bin/env python
import sys

from nova.openstack.common import gettextutils
gettextutils.install('t')

from nova import conductor
from nova import context
from nova import config
from nova.openstack.common import log as logging


LOG = logging.getLogger(__name__)

def test():
    LOG.warn("runnint test()")
    conductor_api = conductor.API()
    ctxt = context.get_admin_context()
    services = conductor_api.service_get_all(ctxt)
    LOG.warn("Get %d service",len(services))



def main():
    config.parse_args(sys.argv)
    logging.setup("t")
    test()


if __name__ == '__main__':
    main()

