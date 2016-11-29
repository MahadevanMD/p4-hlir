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

import math
import pprint
import p4_hlir.hlir.p4_tables as p4_tables
import p4_hlir.hlir.p4_headers as p4_headers
import p4_hlir.hlir.p4_imperatives as p4_imperatives


def match_field_info(table):
    """Given a p4_table, return a dict with the following keys:

        'table_name' (str) - name of the table

        'num_fields' (int) - number of fields in the table search key

        'total_field_width' (int) - total number of bits in all search
        key fields

        'field_name_widths' (list of (str, int)) - a list of tuples,
        where each tuple is a string describing the search key field,
        and an int with the width of that field in bits.  The string
        is often just hte name of the field, but also mentions the
        mask if one is specified, or 'valid(field)' if the match type
        is 'valid'."""
    if type(table) is p4_tables.p4_conditional_node:
        # TBD: It might be nice to return info about the fields used
        # in the evaluation of the condition node here.  For now
        # simply return 0.
        return {'table_name': table.name,
                'num_fields': 0,
                'total_field_width': 0,
                'field_names_widths': []}
    try:
        mfs = table.match_fields
    except AttributeError:
        print('type(table)=%s' % (type(table)))
        pprint.pprint(table)
        raise
    fnames = []
    total_width = 0
    for mf in mfs:
        if isinstance(mf[0], p4_headers.p4_header_instance):
            # Then the match type had better be P4_MATCH_VALID, or else
            # it seems to violate the P4 spec from my reading.
            assert(mf[1] == p4_tables.p4_match_type.P4_MATCH_VALID)
            assert(mf[2] is None)
            # Whether a field is valid only needs 1 bit in the search key
            width = 1
            fname = "valid(%s)" % (mf[0].name)
        elif isinstance(mf[0], p4_headers.p4_field):
            fullwidth = mf[0].width
            if mf[2] is None:
                width = fullwidth
                fname = mf[0].name
            elif isinstance(mf[2], int) or isinstance(mf[2], long):
                # Then it is a mask width
                mask = mf[2]
                fullmask = (1 << fullwidth) - 1
                # All bits in the mask should be inside the field's width
                assert((mask & fullmask) == mask)
                # Count 1s in the binary representation of the mask.
                # Any bits that are 0 in the mask need not be sent to the
                # table as part of the search key.
                width = bin(mask).count('1')
                fname = "%s mask 0x%x" % (mf[0].name, mf[2])
            else:
                msg = ("Unexpected type %s for mf[2]=%s" % (type(mf[2]), mf[2]))
                raise ValueError(msg)
        else:
            msg = ("Unexpected type %s for arg %s" % (type(mf[0]), mf[0]))
            raise ValueError(msg)
        fnames.append((fname, width))
        total_width += width
    return {'table_name': table.name,
            'num_fields': len(mfs),
            'total_field_width': total_width,
            'field_names_widths': fnames}


def num_action_type_bits(num_actions):
    assert(num_actions >= 0)
    if num_actions <= 1:
        return 0
    return int(math.ceil(math.log(num_actions, 2)))


def result_info(table):
    """Given a p4_table, return a dict with the following keys:

        'table_name' (str) - name of the table

        'result_width' (int) - total number of bits in one
        straightforward encoding of the result bits, with a single
        unique identifier with log_2(n) bits where n is the number of
        possible actions, plus the maximum size of result fields
        needed by any of those actions.

        'actions' (dict) - a sub-dict with string keys equal to the
        action names for the table, and values that are sub-sub-dicts
        with these keys:

            'signature' (list of str) - a list of argument names to
            the action block.

            'signature_widths' (list of int) - a list of argument
            widths in bits, in the same order as the names in the
            previous list.

            'total_width' (int) - sum of all widths in
            'signature_widths' list.
    """
    ret = {'table_name': table.name,
           'actions': {}}
    if type(table) is p4_tables.p4_conditional_node:
        # The 'result' of a condition node is 1 bit to represent
        # True/False.
        ret['num_actions'] = 1
        ret['result_width'] = 1
        return ret
    assert(isinstance(table.actions, list))
    max_width = 0
    for act in table.actions:
        if isinstance(act, p4_imperatives.p4_action):
            assert(isinstance(act.name, str))
            assert(isinstance(act.required_params, int))
            assert(isinstance(act.signature, list))
            assert(isinstance(act.signature_flags, dict))
            assert(isinstance(act.signature_widths, list))
            assert(len(act.signature_flags) == 0)
            assert(act.required_params == len(act.signature))
            assert(act.required_params == len(act.signature_widths))
            total_width = sum(act.signature_widths)
#            info = {'required_params': act.required_params,
            info = {'signature': act.signature,
                    'signature_widths': act.signature_widths,
                    'total_width': total_width}
            ret['actions'][act.name] = info
            if total_width > max_width:
                max_width = total_width
        else:
            msg = ("Unexpected type %s for act=%s" % (type(act), act))
            raise ValueError(msg)
    ret['num_actions'] = len(table.actions)
    # Don't worry about trying to absolutely minimize table width
    # using Huffman encoding of the action type, but a real optimized
    # implementation might want to do that.
    ret['result_width'] = (num_action_type_bits(ret['num_actions']) +
                           max_width)
    return ret
