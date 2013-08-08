Internal test code for nova db joinload/json.

Prerequess
------------

To run this test, you must have a working nova code(from github master branch) installed on the machine, as well as the mysql.
You then have to modify the novadbtest.conf file to set correct sql_connection option for this test.

Usage
------------
1) Create the DB tables if hasn't been done:

    ./novadbtest-initdb.py

2) Start the nova-conductor service using the config file novadbtest.conf:

    nova-conductor --config-file ./novadbtest.conf

3) Start to mimic nova_compute service to create compute nodes in DB and mimic the periodic updates:

    ./novadbtest-compute.py [options]

Options:

  --num_comp NUM_COMP:          Number of compute node to be created. Default is 10000.
  
  --num_stat NUM_STAT:          Number of stat record of each compute node, Default is 20.
                                If join_stats is False, these stats will be stored as json
                                encoded TEXT in the cpu_info column.
              
  --join_stats <True or False>: Whether to generate stats data for each compute node for DB join.
                                Default is False.

  --num_proc NUM_PROC:          How many subprocess to launch to mimic the nova-compute updates.
                                Each subprocess will update the number of num_comp/num_proc compute nodes
                                at a periodic interval of 60/num_proc seconds.

4) Test the performance of compute_node_get_all() call.

    ./novadbtest.py [options]

Options:

  --join_stats <True or False>: This should be the same as the one specified in novadbtest-compute.
  
  --total TOTAL:                Number of runs.
    
