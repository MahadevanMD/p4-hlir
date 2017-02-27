p4-hlir
==========

Dependencies:  
The following are required to run `p4-validate` and `p4-graphs`:
- the Python `yaml` package
- the Python `ply` package
- the `dot` tool

`ply` will be installed automatically by `setup.py` when installing `p4-hlir`.

On Ubuntu, the following packages can be installed with `apt-get` to satisfy the
remaining dependencies:
- `python-yaml`
- `graphviz`


To install system wide:

    sudo python setup.py install

To install in your personal user directory (see
https://docs.python.org/3/install/index.html for more documentation on
setup options):

    python setup.py install --user

    # To see the base directory where this will install things:
    python
    >>> import site
    >>> site.USER_BASE
    '/Users/jafinger/Library/Python/2.7'

    # Executables like p4-validate and p4-graphs will go in a 'bin'
    # directory inside of site.USER_BASE.

    # In a bash shell, you can do this to add this bin directory to
    # your path:
    export PATH=`python -c 'import site; print site.USER_BASE'`/bin:$PATH

To run validate tool:  
p4-validate \<path_to_p4_program\>

To open a Python shell with an HLIR instance accessible:  
p4-shell \<path_to_p4_program\>

To build the HLIR and access its objects:  
from p4_hlir.main import HLIR  
h = HLIR(\<path_to_p4_program\>)  
h.build()

You can then access the different P4 top level objects using these Python
OrderedDict's:  
h.p4_actions  
h.p4_control_flows  
h.p4_headers  
h.p4_header_instances  
h.p4_fields  
h.p4_field_lists  
h.p4_field_list_calculations  
h.p4_parser_exceptions  
h.p4_parse_value_sets  
h.p4_parse_states  
h.p4_counters  
h.p4_meters  
h.p4_registers  
h.p4_nodes  
h.p4_tables  
h.p4_action_profiles  
h.p4_action_selectors  
h.p4_conditional_nodes  

The ingress entry points are stored in a dictionary:  
h.p4_ingress_ptr

The egress entry point is:  
h.p4_egress_ptr


To access the P4 types you can use the following import:  
import p4_hlir.hlir.p4 as p4


# Getting the graphs

To get the table graph or parse graph for a P4 program, use:  
p4-graphs \<path_to_p4_program\>

# Compiling to EBPF

There are multiple back-ends that can consume the HLIR P4 program representation.
A compiler back-end which compiles programs expressed in a restricted subset of P4
into eBPF programs that can be run in the Linux kernel can be found at
https://github.com/iovisor/bcc/tree/master/src/cc/frontends/p4



# sched_data dependency graphs

When you specify the new `--split-match-action-events` command line
option to `p4-graphs`, it produces files
`<basename>.ingress.sched_data.txt` and
`<basename>.egress.sched_data.txt`.  Each of these files contains 2
Python dicts: one called `nodes` and the other called `edges`.

`nodes` defines attributes about matches, actions, and conditions that
need to be scheduled.  The keys are strings that name the nodes.  The
corresponding values are themselves sub-dicts with these keys:

    'type' - str with one of the values: 'match', 'action', 'condition'

    'num_fields' - This key is only present if 'type' is 'action' or
    'condition'.  For 'action' type nodes, the value is an int equal
    to the maximum number of primitive actions performed by any of the
    table's user-defined compound actions.  For 'condition' type
    nodes, it is currently always filled in with 0.

    'key_width' - This key is only present if 'type' is 'matcyh'.  The
    value is an int equal to the nuber of bits in the table's search
    key.  Note that this value can be 0 if the P4 table has no search
    key fields.  This can be useful in P4 for a 'global config
    register' type of table, where the control plane can specify an
    action to perform on the packet regardless of the values in the
    packet's header fields.

    'condition' - This key is only present if the node is a condition
    node.  Its value is a string representing the conditional
    expression in the P4 source code.  This expression will have any
    #define's replaced with their corresponding values, so may not
    match the source code character for character.


`edges` defines scheduling dependencies between nodes.  The keys are
tuples containing 2 strings, each a node name.  The dependency is from
the node named by the first string, to the node named by the second
string.

The value associated with each key is a sub-dict.  One of the keys is
the string 'dep_type', and its corresponding value is one of the
strings listed below.  There is also a key 'delay' that is currently
given an int value that is one of 0, min_action_latency (currently 1),
or min_match_latency (currently 9).

* 'new_match_to_action' - the dependency is from the MATCH node for a
  table, to the ACTION node for the same table.  'delay' is
  min_match_latency.

* 'rmt_match' - 'delay' is min_action_latency.  Corresponds to a match
  dependency for the RMT architecture.  The dependency is from an
  ACTION node for a table, to some other node that reads a packet
  field that might be written by the ACTION node.  The 'to' node could
  be a MATCH node for a table, or a condition node that reads a field
  modified by the action.  TBD if there are any other cases possible,
  but those 2 cases can definitely occur.

* 'rmt_action' - 'delay' is min_action_latency.  Corresponds to an
  action dependency for the RMT architecture.  The dependency is from
  an ACTION node for one table, to an ACTION node for a different
  table.  The from node action might modify a packet header field that
  is either read or written by the to node's action.

* 'rmt_successor' - 'delay' is 0.  Corresponds to a successor
  dependency for the RMT architecture.  At least the following cases
  are possible:
  * From and to nodes are both condition nodes, and the conditions are
    evaluated in the order 'from' followed by 'to' sequentially in the
    P4 source code.
  * From node is if condition, to node is table action whose side
    effects should only occur if the condition has the appropriate
    true or false value (depending on whether the table's action is in
    the 'then' or 'else' branch of the 'if' statement).
  * TBD if there are any other cases possible.

* 'new_successor_conditional_on_table_result_action_type' - 'delay' is
  min_match_latency.  At least the following cases have been observed:
  * From node is a match node for a table, where the table has
    conditional blocks of code that depend on whether the table's
    result is a hit/miss, or depending on which action the control
    plane selected to execute for the matching table entry.  The to
    node is an action node for a different table, that is applied
    conditionally based upon the result of the from table.
  * Similar to the previous case, except the to node is a condition
    node that is the condition of an 'if' statement that is itself
    executed conditionally in the P4 source code, based upon the
    hit/miss or action choice result of the from node table's result.

* 'rmt_reverse_read' - 'delay' is 0.  Corresponds to a reverse read
  dependency from the RMT architecture.  Only case observed is that
  the from node is an action node for one table, and the to node is an
  action node for a different table.  The dependency exists if none of
  the more restrictive kinds of dependencies above exist between the
  nodes, but the from action might read a field that the to action
  might write, so the to node action must be scheduled at the same
  time as, or later than, the from node action.

* 'rmt_control_flow' - the current code should never include such
  dependencies in the output.


Edges that represent conditional dependencies of either the
'rmt_successor' type or
'new_successor_conditional_on_table_result_action_type' type have a
key called 'condition'.

If the from node of the edge is a condition node, then the value of
'condition' will be either True or False, depending on whether the
conditional execution of the "to node" is based on the condition being
evaluated as True or False.  Note that there can be more than one edge
out of a condition node with 'condition' equal to True, if there are
multiple nodes depending upon the condition being evaluated as True.
There can also be no edges out of a condition node with 'condition'
equal to True, e.g. if the 'then' part of the 'if' statement has no
code to execute.

Similarly, there can be more than one edge out of a condition node
with 'condition' equal to False.  There can also be no edges out of a
condition node with 'condition' False, e.g. for an 'if' statement in
the code that has no 'else', or it has an 'else' branch with no code
to execute in that branch.


If the from node of the edge is a table '_MATCH' node, then the value
of 'condition' will be a list of strings, which are names of actions
of that table.  Every table match will result in either a hit, and
exactly one of the action types defined in the P4 source code as an
action for the table, or a miss.  For example, an edge from table
"t1_MATCH' with 'condition' equal to ['a', 'b', 'c'] would represent
that the "to node" should only be executed if the result of the search
in table 't1' was one of the actions 'a', 'b', or 'c'.

Just as there can be multiple edges out of a condition node with the
same 'condition' value, the same is true for multiple edges out of a
table '_MATCH' node -- they can have the same list of actions.  There
can be actions of the table that are not conditions on any of its
outgoing edges, e.g. if the P4 source code has no mention of that
table action name in its conditional execution clauses.
