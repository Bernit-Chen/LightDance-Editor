from typing import Callable

import bpy


def execute_operator(idname: str):
    attrs = idname.split(".")
    if len(attrs) != 2:
        print("Invalid idname:", idname)
        return

    module_name, ops_name = attrs

    try:
        module = getattr(bpy.ops, module_name)
        ops: Callable[[str], None] = getattr(module, ops_name)
        ops("INVOKE_DEFAULT")
    except:
        print("Failed to execute operator:", idname)
