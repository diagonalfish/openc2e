import re
import sys
import json

TDISP = {
    "any": "CI_ANYVALUE",
    "float": "CI_NUMERIC",
    "integer": "CI_NUMERIC",
    "string": "CI_STRING",
    "agent": "CI_AGENT",
    "bytestring": "CI_BYTESTR",
    "variable": "CI_VARIABLE",
    "any": "CI_OTHER",
    "anything": "CI_OTHER",
    "condition": None,
    "comparison": None,
    "decimal": "CI_NUMERIC",
    "decimal variable": "CI_OTHER",
    "byte-string": "CI_BYTESTR",
    "label": None,
    "vector": "CI_VECTOR",
    "bareword": "CI_BAREWORD",
    "token": "CI_BAREWORD",
    "subcommand": "CI_SUBCOMMAND",
    "command": "CI_COMMAND",
}


def miscprep(variant, cmds):
    for cmd in cmds:
        cmd["evalcost"][variant] = cmd["evalcost"].get(
            variant, cmd["evalcost"]["default"]
        )
        if cmd["type"] != "command" and cmd["evalcost"][variant] != 0:
            raise Exception(
                (
                    "{} has non-zero evalcost in an expression cost.\n"
                    + "This causes a race condition which can potentially lead to crashes.\n"
                    + "If you really need this, please contact bd_. Aborting for now."
                ).format(cmd["lookup_key"])
            )


def printinit(variant, cmdarr):
    print("static Dialect dialect_{}({}, std::string(\"{}\"));".format(variant, cmdarr, variant))


def printdispatch():
    print("#ifdef VCPP_BROKENNESS")
    print("void dispatchCAOS(class caosVM *vm, int idx) {")
    print("\tswitch (idx) {")
    for impl in sorted(DISP_TBL):
        print("\t\tcase {}: vm->{}(); break;".format(DISP_TBL[impl], impl))
    print("\t\tdefault:\n\t\t{")
    print("\t\t\tchar buf[256];")
    print('\t\t\tsprintf(buf, "%d", idx);')
    print(
        '\t\t\tthrow caosException(std::string("Unknown dispatchCAOS index: ") + buf);'
    )
    print("\t\t}")
    print("\t}")
    print("}")
    print("#endif")


def writelookup(cmds):
    for cmd in cmds:
        if cmd["type"] == "command":
            prefix = "cmd "
        else:
            prefix = "expr "
        cmd["lookup_key"] = prefix + cmd["name"].lower()


def printarr(cmds, variant, arrname):
    buf = ""
    buf += "static const struct cmdinfo {}[] = {{\n".format(arrname)
    idx = 0
    for cmd in cmds:
        argp = "NULL"
        if cmd.get("arguments") is not None:
            args = ""
            for arg in cmd["arguments"]:
                type = TDISP[arg["type"]]
                if not type:
                    args = None
                    break
                args += "{}, ".format(type)
            if args is not None:
                argp = "{}_t_{}_{}".format(arrname, cmd["type"], cmd["key"])
                print(
                    "static const enum ci_type {}[] = {{ {}CI_END }};".format(
                        argp, args
                    )
                )

        buf += "\t{{ // {} {}\n".format(idx, cmd["key"])
        idx += 1

        buf += "#ifndef VCPP_BROKENNESS\n"
        if not cmd.get("implementation"):
            cmd["implementation"] = "caosVM::dummy_cmd"
        if not cmd.get("saveimpl"):
            cmd["saveimpl"] = "caosVM::dummy_cmd"

        buf += "\t\t&{}, // handler\n".format(cmd["implementation"])
        buf += "\t\t&{}, // savehandler\n".format(cmd["saveimpl"])
        buf += "#else\n"
        buf += "\t\t{}, // handler_idx\n".format(handler_idx(cmd["implementation"]))
        buf += "\t\t{}, // savehandler_idx\n".format(handler_idx(cmd["saveimpl"]))
        buf += "#endif\n"

        buf += '\t\t"{}", // lookup_key\n'.format(cmd["lookup_key"])
        buf += '\t\t"{}", // key\n'.format(cmd["key"])
        buf += '\t\t"{}", // name\n'.format(cmd["match"].lower())
        buf += '\t\t"{}", // fullname\n'.format(cmd["name"])
        buf += '\t\t"{}", // docs\n'.format(cescape(cmd.get("description")))
        buf += "\t\t{}, // argc\n".format(len(cmd["arguments"]))
        buf += "\t\t{}, // stackdelta\n".format(cmd["stackdelta"])
        buf += "\t\t{}, // argtypes\n".format(argp)

        rettype = TDISP[cmd["type"]]
        if not rettype:
            raise Exception(
                "Unknown return type {} in {}: {}".format(cmd["type"], cmd["name"], cmd)
            )

        buf += "\t\t{}, // rettype\n".format(rettype)
        cost = cmd["evalcost"][variant]
        buf += "\t\t{} // evalcost\n".format(cost)
        buf += "\t},\n"

    buf += "\t{ NULL, NULL, NULL, NULL, NULL, NULL, NULL, 0, 0, NULL, CI_END, 0 }\n"
    buf += "};"
    print(buf)


def sortname(cmds):
    cmds.sort(key=lambda c: c["lookup_key"])


def inject_ns(cmds):
    namespaces = {}
    names = {}
    for cmd in cmds:
        type = "command" if cmd["type"] == "command" else "any"
        if cmd.get("namespace"):
            namespaces[cmd["namespace"]] = namespaces.get(cmd["namespace"], {})
            namespaces[cmd["namespace"]][type] = (
                namespaces[cmd["namespace"]].get(type, 0) + 1
            )
        names["{} {}".format(type, cmd["name"]).lower()] = (
            names.get("{} {}".format(type, cmd["name"]).lower(), 0) + 1
        )

    for ns in namespaces:
        for type in namespaces[ns]:
            if ns == "face":  # hack
                continue
            if names.get("{} {}".format(type, ns).lower()):
                continue
            key = "k_" + ns.upper()
            key = re.sub(r"[^a-zA-Z0-9_]", "", key)
            cmds.append(
                dict(
                    arguments=[dict(name="cmd", type="subcommand")],
                    category="internal",
                    description="",
                    evalcost=dict(default=0),
                    filename="",
                    implementation=None,
                    match=ns.upper(),
                    name=ns.lower(),
                    pragma=dict(),
                    status="internal",
                    key=key,
                    type=type,
                    syntaxstring="{} (command/expr) subcommand (subcommand)\n".format(
                        ns.upper()
                    ),
                    stackdelta="INT_MAX",
                )
            )
            # print(cmds[-1])


def checkdup(cmds, desc):
    mark = {}
    for cmd in cmds:
        if not cmd["lookup_key"]:
            raise Exception("No name for {}".format(cmd["key"]))
        mark[cmd["lookup_key"]] = mark.get(cmd["lookup_key"], [])
        mark[cmd["lookup_key"]].append(cmd)
        if len(mark[cmd["lookup_key"]]) > 1:
            # Please do not disable this assert
            # bsearch()'s behavior is unpredictable with duplicate keys
            raise Exception(
                "Duplicate command in {}: {}\n{}".format(
                    desc, cmd["lookup_key"], mark[cmd["lookup_key"]]
                )
            )


def cescape(s):
    if not s:
        return ""

    new_s = ""
    for c in s:
        if c in ("\n", "\r", "\t", "\\", '"'):
            new_s += {"\n": "\\n", "\r": "\\r", "\t": "\\t", "\\": "\\\\", '"': '\\"',}[
                c
            ]
        else:
            new_s += c

    return new_s


DISP_TBL = {}
DISP_ID = 1


def handler_idx(impl):
    if not impl in DISP_TBL:
        global DISP_ID
        DISP_TBL[impl] = DISP_ID
        DISP_ID += 1
    return DISP_TBL[impl]


with open(sys.argv[1]) as f:
    data = json.load(f)

print(
    """// THIS IS AN AUTOMATICALLY GENERATED FILE
// DO NOT EDIT


#include <string>
#include <cstdio>
#include <climits>
#include "cmddata.h"
#include "caosVM.h"
#include "dialect.h"
#include "openc2e.h"

"""
)

for variant_name in sorted(data["variants"]):
    variant = data["variants"][variant_name]
    for key in variant:
        variant[key]["key"] = key

    cmds = list(variant.values())

    inject_ns(cmds)
    writelookup(cmds)
    checkdup(cmds, "{} commands".format(variant_name))
    sortname(cmds)
    miscprep(variant_name, cmds)

    printarr(cmds, variant_name, "{}_cmds".format(variant_name))
    printinit(variant_name, "{}_cmds".format(variant_name))

printdispatch()

print("Dialect* getDialectByName(const std::string& name) {")
for variant_name in sorted(data["variants"]):
    print("\tif (name == \"{}\") {{ return &dialect_{}; }}".format(variant_name, variant_name))
print("\treturn nullptr;")
print("}")

print("std::vector<std::string> getDialectNames() {")
print("\treturn { " + ", ".join('"{}"'.format(name) for name in sorted(data["variants"])) + "};")
print("}")
