Internal test code for nova db joinload/json.

Prerequess
------------

First, you need to modify the /etc/security/limits.conf to enlarge the max number of open files 'nofile' for the rabbitmq user and the client, and restart the rabbitmq-server.

To run this test, you must have a working nova code(from github master branch) installed on the machine, as well as the mysql.
You then have to modify the novadbtest.conf file to set correct sql_connection option for this test.

Usage
------------
1) Create the DB tables if hasn't been done:

    ./novadbtest-initdb.py [options]

Options:

  --num_comp NUM_COMP:          Number of compute node to be created. Default is 10000.
  
  --num_stat NUM_STAT:          Number of stat record of each compute node, Default is 20.
                                If join_stats is False, these stats will be stored as json
                                encoded TEXT in the cpu_info column.
              
  --join_stats <True or False>: Whether to generate stats data for each compute node for DB join.
                                Default is False.

2) Start the nova-conductor service using the config file novadbtest.conf:

    nova-conductor --config-file ./novadbtest.conf

3) Start to mimic nova_compute service to create compute nodes in DB and mimic the periodic updates.

    ./novadbtest-compute.py [options]

Options:  

  --num NUM:	                How many compute nodes to udpate, 0 means all. Default is 0.

  --num_proc NUM_PROC:          Maximum subprocess allowed to launch to mimic the nova-compute updates.
                                Each subprocess will update the number of NUM/NUM_PROC compute nodes
                                at a periodic interval of 60/NUM_PROC seconds. Default is 100.

  --start START:                Skip the first num of START compute nodes for updating, 0 means no skip.
                                Default is 0.

  --periodic_fuzzy_delay PERIODIC_FUZZY_DELAY:
                                Range of seconds to randomly delay when starting the periodic task to
                                reduce stampeding. Default is 60. (Disable by setting to 0)


4) Test the performance of compute_node_get_all() call.

    ./novadbtest.py [options]

Options:
  
  --total TOTAL:                Number of run.


NOTE
------------

We can have several nova-conductor and novadbtest-compute.py on different machines for scale out test, 
as long as we have the correct settings in the novadbtest.conf configuration file.
