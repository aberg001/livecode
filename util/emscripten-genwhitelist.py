#!/usr/bin/env python

# This script extracts symbols from an LLVM bitcode file, and uses
# them to generate a whitelist of symbols that should be compiled with
# Emterpreter.
#
# There are two sets of regular expressions loaded from JSON files:
# "include" expressions are used to find functions that should be
# Emterpreted, and "exclude" expressions are used to prune out
# functions that are too greedily included.

import sys
import os
import subprocess
import re
import json

# Get any relevant info from the environment
# ------------------------------------------

env_verbose = os.getenv('V', '0').strip()
env_nm = os.getenv('NM', 'llvm-nm')

# Separate out separate elements of command line
nm = env_nm.split()

# Verbosity
verbose = (env_verbose.strip() is not '0')

# Process command line options
# ----------------------------
#
# Each option absorbs all subsequent arguments up to the next option.
# Options are identified by the fact they start with "--".

option = None
options = {}
for arg in sys.argv[1:]:
    if arg.startswith('--'):
        option = arg[2:]
        options[option] = []
    else:
        if option is None:
            print('ERROR: unrecognized option \'{}\''.format(arg))
            sys.exit(1)
        options[option].append(arg)

# Generate include/exclude predicate
# ----------------------------------

def build_regexp_from_json_files(paths):
    expressions = []
    for p in paths:
        with file(p) as fp:
            expressions += json.load(fp)
    if len(expressions) is 0:
        return None
    return '(' + '|'.join(expressions) + ')'

exclude_re = None
if 'exclude' in options:
    exclude_re = build_regexp_from_json_files(options['exclude'])
if exclude_re is not None:
    exclude_re = re.compile(exclude_re)

include_re = None
if 'include' in options:
    include_re = build_regexp_from_json_files(options['include'])
if include_re is not None:
    include_re = re.compile(include_re)

def is_emterpreted(symbol):
    if include_re is not None:
        if include_re.search(symbol) is None:
            return False
    if exclude_re is not None:
        if exclude_re.search(symbol) is not None:
            return False
    return True

# Generate emterpreter whitelist
# ------------------------------

# Run llvm-nm and yield symbol names from its standard output
def iter_archive_symbols(archive):
    command = nm + ['-B', archive]
    if verbose:
        print(' '.join(command))
    output = subprocess.check_output(command)
    for line in output.splitlines():
        line = line.strip()

        if len(line) is 0:
            # Empty line
            continue

        if line.endswith(':'):
            # This line names a code object file (foo.o), so ignore it
            continue

        # Split the line into elements.  The layout of the line should
        # be something like: "[<address>] <type> <name>"
        line = line.split()

        # Only "text" symbols, i.e. code defined in the current
        # object, should be emterpreted.
        if len(line) < 3 or line[1].lower() != 't':
            continue

        # Put an "_" before each symbol to get the name as generated
        # by emscripten
        yield ('_' + line[2])


# Generate list of all symbols that should be whitelisted
object_path = options['input'][0]
whitelist_symbols = []
blacklist_symbols = []
for symbol in iter_archive_symbols(object_path):
    if is_emterpreted(symbol):
        whitelist_symbols.append(symbol)
    else:
        blacklist_symbols.append(symbol)

print("Compiling {} functions".format(len(blacklist_symbols)))
print("Emterpreting {} functions".format(len(whitelist_symbols)))

# Put into a JSON file
if len(options['output']) > 0:
    json_path = options['output'][0]
    with file(json_path, 'w') as fp:
        json.dump(whitelist_symbols, fp, indent=4, separators=(',', ': '))
if len(options['output']) > 1:
    json_path = options['output'][1]
    with file(json_path, 'w') as fp:
        json.dump(blacklist_symbols, fp, indent=4, separators=(',', ': '))