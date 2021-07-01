import pynvim
from collections import defaultdict
from os import path
from tree_sitter import Language, Parser
import subprocess
from functools import reduce

# TODO: fix hardcoded path #
PLUGIN_PATH = "/Users/gauteab/.vim/plugged/talon-fluent-nvim"
LIB_PATH = path.join(PLUGIN_PATH, "build", "languages.so")
Language.build_library(
    LIB_PATH, (path.join(PLUGIN_PATH, p) for p in [
        "vendor/tree-sitter-python",
        "vendor/tree-sitter-javascript"
    ])
)

PYTHON = Language(LIB_PATH, "python")
JAVASCRIPT = Language(LIB_PATH, "javascript")

python_query = PYTHON.query("""(identifier) @identifier
(class_definition (identifier) @type)
(function_definition (identifier) @function)
(import_statement name: (dotted_name) @module)
(aliased_import (dotted_name) @module alias: (identifier) @module)
(import_from_statement module_name: (dotted_name) @module (dotted_name) @value)
""")


TALON_REPL = path.expanduser("~/.talon/.venv/bin/repl")


@pynvim.plugin
class Main(object):
    def __init__(self, vim):
        self.vim = vim

    @pynvim.autocmd("BufWrite", pattern="*.py,*.js")
    def on_save(self):
        self.fluent_update([])

    @pynvim.function("FluentUpdate")
    def fluent_update(self, args):
        buffer = self.vim.eval("join(getline(1, '$'), '\n')")
        source = bytes(buffer, "utf-8")
        parser = Parser()
        parser.set_language(PYTHON)
        tree = parser.parse(source)
        captures = python_query.captures(tree.root_node)
        def f(capture): return (capture[1], node_text(capture[0], source))
        result = dict(group(map(f, captures)))
        self.talon_user_action("fluent_update", [result])

    def talon_send(self, cmd):
        self.vim.out_write(cmd+"\n")
        talon = subprocess.Popen(TALON_REPL, stdin=subprocess.PIPE)
        talon.communicate(bytes(cmd+"\n", "utf8"))

    def talon_call(self, name, args):
        args = [f'"{args}"'] if type(args) == str else map(str, args)
        cmd = f"{name}({','.join(args)})"
        self.talon_send(cmd)

    def talon_user_action(self, name, args):
        self.talon_call(f"actions.user.{name}", args)


def node_text(node, source_bytes):
    return source_bytes[node.start_byte:node.end_byte].decode('utf8')


def group(seq):
    def g(grp, val): return grp[val[0]].append(val[1]) or grp
    return reduce(g, seq, defaultdict(list))
