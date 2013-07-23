Internal test code for nova db joinload/json.

Prerequess
------------

To run this test, you must have a nova source code(from github master branch) installed on the machine, as well as the mysql.
You then have to modify the novadbtest.conf file to set correct sql_connection option for this test.

Usage
------------

    python ./novadbtest.py [--num_comp  <value>] [--num_stat <value>]

Options:

  --num_comp: number of compute node, default is 10000
  
  --num_stat: number of stat record of each compute node, default is 20.


Test Types
----------

There are 2 types of tests here:

JOINLOAD:

The JOINLOAD test first create an empty database in mysql based on the configuration in novadbtest.conf, then use nova.db.migration
to create nova DB tables. It then creates <num_comp> records in the compute_nodes table in the database, and for each cmopute node,
it creates <num_stat> records in the compute_node_stats table. Then it measures the time to execute nova.db.compute_node_get_all() to
get all the compute nodes.

JSON:

The JSON test first create an empty database in mysql based on the configuration in novadbtest.conf, then use nova.db.migration
to create nova DB tables. It then creates <num_comp> records in the compute_nodes table in the database. Instead of creating records
in compute_node_stats table, it stores a json encoded python dictionary with <num_stat> entries in the 'cpu_info' field in the 
compute_nodes table. Then it measures the time to execute nova.db.compute_node_get_all() to get all the compute nodes, as well as the
time to json decode the 'cpu_info' field into a python dictionary.

