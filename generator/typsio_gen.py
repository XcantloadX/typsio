# generator/typsio_gen.py
import json
import subprocess
import argparse
import importlib.util
import sys
import tempfile
from pathlib import Path
from inspect import signature
from pydantic import BaseModel
from typing import Dict, Any, Type, Set

# --- 类型映射与生成逻辑 ---
TYPE_MAP = { int: "number", float: "number", str: "string", bool: "boolean", type(None): "null", Any: "any" }

def get_ts_type(py_type: Any) -> str:
    if py_type in TYPE_MAP: return TYPE_MAP[py_type]
    if hasattr(py_type, '__origin__'):
        origin = py_type.__origin__
        args = py_type.__args__
        if origin is list and args: return f"{get_ts_type(args[0])}[]"
        if origin is dict and args: return f"{{ [key: {get_ts_type(args[0])}]: {get_ts_type(args[1])} }}"
        if origin is set and args: return f"Set<{get_ts_type(args[0])}>"
    if isinstance(py_type, type) and issubclass(py_type, BaseModel): return py_type.__name__
    return "any"

def generate_ts_interface(name: str, items: dict, formatter: callable) -> str:
    lines = [f"export interface {name} {{"]
    for key, value in items.items():
        lines.append(f"  {formatter(key, value)}")
    lines.append("}")
    return "\n".join(lines)

def format_rpc_method(name, func) -> str:
    sig = signature(func)
    params = ", ".join([f"{p.name}: {get_ts_type(p.annotation)}" for p in sig.parameters.values()])
    ret_type = get_ts_type(sig.return_annotation)
    return f"{name}({params}): Promise<{ret_type}>;"

def format_event(name, model) -> str:
    return f