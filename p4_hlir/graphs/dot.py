# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Extract control flow and parse graphs to DOT graph descriptions and generate
PNGs of them
"""
import p4_hlir.hlir.p4 as p4
import os
import subprocess
import argparse
import dependency_graph

def get_call_name (node, exit_node=None):
    if node:
        return node.name
    else:
        return exit_node

def dump_table(node, exit_node, visited=None):
    # TODO: careful about tables with names with reserved DOT keywords

    p = ""
    if visited==None:
        visited = set([node])
    else:
        visited.add(node)

    if type(node) is p4.p4_table:
        p += "   %s [shape=ellipse];\n" % node.name
    elif type(node) is p4.p4_conditional_node:
        p += "   %s [shape=box label=\"%s\"];\n" % (get_call_name(node), str(node.condition))

    for label, next_node in node.next_.items():
        if type(node) is p4.p4_table:
            arrowhead = "normal"
            if type(label) is str:
                label_str = " label=\"%s\"" % label
            else:
                label_str = " label=\"%s\"" % label.name
        elif type(node) is p4.p4_conditional_node:
            label_str = ""
            if label:
                arrowhead = "dot"
            else:
                arrowhead = "odot"
        p += "   %s -> %s [arrowhead=%s%s];\n" % (get_call_name(node),
                                                get_call_name(next_node, exit_node),
                                                arrowhead, label_str)
        if next_node and next_node not in visited:
            p += dump_table(next_node, exit_node, visited)

    if len(node.next_) == 0:
        p += "   %s -> %s;\n" % (node.name, exit_node)

    return p

def dump_parser(node, visited=None):
    if not visited:
        visited = set()
    visited.add(node.name)

    p = ""
    p += "   %s [shape=record label=\"{" % node.name
    p += node.name
    if node.branch_on:
        p += " | {"
        for elem in node.branch_on:
            elem_name = str(elem).replace("instances.","")
            if type(elem) is tuple:
                elem_name = "current"+elem_name
            p += elem_name + " | "
        p = p[0:-3]
        p+="}"
    p += "}\"];\n"

    for case, target in node.branch_to.items():
        label = ""
        if type(case) is not list:
            case = [case]
        for caseval in case:
            if type(caseval) is int or type(caseval) is long:
                label += hex(caseval) + ", "
            elif caseval == p4.P4_DEFAULT:
                label += "default, "
            elif type(caseval) == p4.p4_parse_value_set:
                label += "set("+caseval.name+"), "
        label = label[0:-2]

        dst_name = target.name
        if type(target) is p4.p4_table:
            dst_name = "__table_"+dst_name

        p += "   %s -> %s [label=\"%s\"];\n" % (node.name, dst_name, label)

        for _, target in node.branch_to.items():
            if type(target) is p4.p4_parse_state and target.name not in visited:
                p += dump_parser(target, visited)

    return p

def generate_graph_png(dot, out):
    with open(out, 'w') as pngf:
        subprocess.check_call(["dot", "-Tpng", dot], stdout = pngf)

def generate_graph_eps(dot, out):
    with open(out, 'w') as epsf:
        subprocess.check_call(["dot", "-Teps", dot], stdout = epsf)

def generate_graph_try_format(dot_fname, out_fname, dot_format):
    with open(out_fname, 'w') as outf:
        subprocess.check_call(["dot", "-T" + dot_format, dot_fname],
                              stdout = outf)

def generate_graph(dot_fname, base_fname, dot_formats):
    for dot_format in dot_formats:
        if dot_format == 'none':
            break
        out_fname = base_fname + "." + dot_format
        success = False
        try:
            generate_graph_try_format(dot_fname, out_fname, dot_format)
            success = True
        except:
            print('Generating dot format %s for dot file %s returned error.'
                  '  Trying another.'
                  '' % (dot_format, dot_fname))
        if success:
            break


def export_parse_graph(hlir, filebase, gen_dir,
                       dot_formats = ['png', 'eps']):
    program_str = "digraph g {\n"
    program_str += "   wire [shape=doublecircle];\n"
    for entry_point in hlir.p4_ingress_ptr:
        program_str += "   %s [label=%s shape=doublecircle];\n" % ("__table_"+entry_point.name, entry_point.name)

    sub_str = dump_parser(hlir.p4_parse_states["start"])
    program_str += "   wire -> start\n"
    program_str += sub_str
    program_str += "}\n"

    filename_dot = os.path.join(gen_dir, filebase + ".parser.dot")
    with open(filename_dot, "w") as dotf:
        dotf.write(program_str)

    generate_graph(filename_dot,
                   os.path.join(gen_dir, filebase + ".parser"),
                   dot_formats)


def export_table_graph(hlir, filebase, gen_dir, predecessors=False,
                       dot_formats = ['png', 'eps']):
    program_str = "digraph g {\n"
    program_str += "   buffer [shape=doublecircle];\n"
    program_str += "   egress [shape=doublecircle];\n"

    for entry_point, invokers in hlir.p4_ingress_ptr.items():
        if predecessors:
            for invoker in invokers:
                program_str += "   %s [label=%s shape=doublecircle];\n" % ("__parser_"+invoker.name, invoker.name)
                program_str += "   %s -> %s\n" % ("__parser_"+invoker.name, get_call_name(entry_point))
        program_str += dump_table(entry_point, "buffer")

    if hlir.p4_egress_ptr:
        program_str += "   buffer -> %s\n" % get_call_name(hlir.p4_egress_ptr)
        program_str += dump_table(hlir.p4_egress_ptr, "egress")
    else:
        program_str += "   buffer -> egress [arrowhead=normal]\n"
    program_str += "}\n"

    filename_dot = os.path.join(gen_dir, filebase + ".tables.dot")
    with open(filename_dot, "w") as dotf:
        dotf.write(program_str)

    generate_graph(filename_dot,
                   os.path.join(gen_dir, filebase + ".tables"),
                   dot_formats)

def export_table_dependency_graph(hlir, filebase, gen_dir, show_conds = False,
                                  show_control_flow = True,
                                  show_condition_str = True,
                                  show_fields = True,
                                  debug_count_min_stages = False,
                                  debug_key_result_widths = False,
                                  dot_formats = ['png', 'eps'],
                                  split_match_action_events = False,
                                  show_only_critical_dependencies = False):
    # TBD: Make these command line options
    min_match_latency = 9
    min_action_latency = 1

    print
    print "TABLE DEPENDENCIES..."

    for pipeline in ['ingress', 'egress']:
        print
        print "%s PIPELINE" % (pipeline.upper())

        if pipeline == 'egress' and not hlir.p4_egress_ptr:
            print "Egress pipeline is empty"
            continue

        filename_dot = os.path.join(gen_dir, (filebase + "." + pipeline +
                                              ".tables_dep.dot"))
        if pipeline == 'ingress':
            graph = dependency_graph.build_table_graph_ingress(
                hlir,
                split_match_action_events=split_match_action_events,
                min_match_latency=min_match_latency,
                min_action_latency=min_action_latency)
        else:
            graph = dependency_graph.build_table_graph_egress(
                hlir,
                split_match_action_events=split_match_action_events,
                min_match_latency=min_match_latency,
                min_action_latency=min_action_latency)
        if split_match_action_events:
            forward_crit_path_len, earliest_time = graph.critical_path(
                'forward',
                show_conds = show_conds,
                debug = debug_count_min_stages,
                debug_key_result_widths = debug_key_result_widths,
                crit_path_edge_attr_name = 'on_forward_crit_path')
            backward_crit_path_len, latest_time = graph.critical_path(
                'backward',
                show_conds = show_conds,
                debug = debug_count_min_stages,
                debug_key_result_widths = debug_key_result_widths,
                crit_path_edge_attr_name = 'on_backward_crit_path')
            if forward_crit_path_len != backward_crit_path_len:
                print("forward and backward critical path length calculations"
                      " give different answers -- possible bug: %d vs. %d"
                      "" % (forward_crit_path_len, backward_crit_path_len))
            min_stages = forward_crit_path_len
        else:
            min_stages = graph.count_min_stages(
                show_conds = show_conds,
                debug = debug_count_min_stages,
                debug_key_result_widths = debug_key_result_widths)
            earliest_time = None
            latest_time = None
        print "pipeline", pipeline, "requires at least", min_stages, "stages"
        show_min_max_scheduled_times = split_match_action_events
        with open(filename_dot, 'w') as dotf:
            graph.generate_dot(
                out = dotf,
                show_control_flow = show_control_flow,
                show_condition_str = show_condition_str,
                show_fields = show_fields,
                earliest_time = earliest_time,
                latest_time = latest_time,
                show_min_max_scheduled_times = show_min_max_scheduled_times,
                show_only_critical_dependencies = show_only_critical_dependencies,
                forward_crit_path_edge_attr_name = 'on_forward_crit_path',
                backward_crit_path_edge_attr_name = 'on_backward_crit_path')

        generate_graph(filename_dot,
                       os.path.join(gen_dir, (filebase + "." + pipeline +
                                              ".tables_dep")),
                       dot_formats)

    print
