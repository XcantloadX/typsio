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
from typing import Callable, Dict, Any, Type, Set, Union, Optional

# --- 类型映射与生成逻辑 ---
TYPE_MAP = {
    int: "number",
    float: "number",
    str: "string",
    bool: "boolean",
    type(None): "null",
    Any: "any",
}

# 全局变量跟踪警告
warnings_occurred = False
strict_mode = False


def get_ts_type(py_type: Any) -> str:
    """
    获取 Python 类型对应的 TypeScript 类型
    """
    # 基础类型
    if py_type in TYPE_MAP:
        return TYPE_MAP[py_type]
    # Pydantic Model
    if isinstance(py_type, type) and issubclass(py_type, BaseModel):
        return py_type.__name__
    # 集合和联合类型
    if hasattr(py_type, "__origin__"):
        origin = py_type.__origin__
        args = getattr(py_type, '__args__', None)
        if not args:
            # 处理没有参数的情况
            pass
        elif origin is list:
            return f"{get_ts_type(args[0])}[]"
        elif origin is dict:
            return f"{{ [key: {get_ts_type(args[0])}]: {get_ts_type(args[1])} }}"
        elif origin is set:
            return f"Set<{get_ts_type(args[0])}>"
        # 处理 Union 类型 (包括 Optional)
        elif origin is Union and args:
            ts_types = [get_ts_type(t) for t in args]
            unique_ts_types = []
            for t in ts_types:
                if t not in unique_ts_types:
                    unique_ts_types.append(t)
            return " | ".join(unique_ts_types)
    # 处理 Python 3.10+ 的新联合类型语法 (X | Y)
    elif hasattr(py_type, '__args__') and '|' in str(py_type):
        args = py_type.__args__
        ts_types = [get_ts_type(t) for t in args]
        # 过滤掉重复的类型
        unique_ts_types = []
        for t in ts_types:
            if t not in unique_ts_types:
                unique_ts_types.append(t)
        return " | ".join(unique_ts_types)
    
    # 处理未知类型
    global warnings_occurred
    type_name = getattr(py_type, '__name__', str(py_type))
    # 特殊处理联合类型显示
    if '|' in str(py_type):
        type_name = str(py_type).replace(' ', '')
    
    warning_msg = f"⚠️  Warning: Unknown type '{type_name}' mapped to 'any'"
    
    if strict_mode:
        print(f"❌ Error: {warning_msg}", file=sys.stderr)
        raise TypeError(warning_msg)
    else:
        print(warning_msg, file=sys.stderr)
        warnings_occurred = True
        return "any"


def generate_ts_interface(name: str, items: dict, formatter: Callable) -> str:
    lines = [f"export interface {name} {{"]
    for key, value in items.items():
        lines.append(f"  {formatter(key, value)}")
    lines.append("}")
    return "\n".join(lines)


def format_rpc_method(name, func) -> str:
    sig = signature(func)
    params = ", ".join(
        [f"{p.name}: {get_ts_type(p.annotation)}" for p in sig.parameters.values()]
    )
    ret_type = get_ts_type(sig.return_annotation)
    return f"{name}({params}): Promise<{ret_type}>;"


def format_event(name, model) -> str:
    return f"'{name}': (payload: {get_ts_type(model)}) => void;"


def flatten_schema_definitions(schemas: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten nested schema definitions to work with json-schema-to-typescript.
    This function extracts all nested definitions and places them at the top level,
    adjusting $ref paths accordingly and removing nested $defs.
    """
    # Collect all unique model definitions at the top level
    flattened_defs = {}
    
    # First, collect all definitions (with processed refs)
    for model_name, schema in schemas.items():
        # Process the schema for refs and remove nested $defs
        processed_schema = process_schema_refs_and_remove_nested_defs(schema)
        
        # Add the processed schema to our definitions
        if model_name not in flattened_defs:
            flattened_defs[model_name] = processed_schema
            
        # Extract any nested definitions and add them to our top-level definitions (also processed)
        if '$defs' in schema:
            for def_name, def_schema in schema['$defs'].items():
                if def_name not in flattened_defs:
                    flattened_defs[def_name] = process_schema_refs_and_remove_nested_defs(def_schema)
    
    # Process each schema again for the properties section
    processed_schemas = {}
    for model_name, schema in schemas.items():
        # Process the schema for refs and remove nested $defs
        processed_schemas[model_name] = process_schema_refs_and_remove_nested_defs(schema)
    
    return {
        "title": "TypsioModels",
        "type": "object",
        "properties": processed_schemas,
        "definitions": flattened_defs
    }

def process_schema_refs_and_remove_nested_defs(schema: Any) -> Any:
    """
    Recursively process schema to:
    1. Adjust $ref paths to point to top-level definitions.
    2. Remove any nested $defs sections.
    """
    if isinstance(schema, dict):
        processed = {}
        for key, value in schema.items():
            # Skip nested $defs
            if key == '$defs':
                continue
            elif key == '$ref' and isinstance(value, str) and value.startswith('#/$defs/'):
                # Convert #/$defs/Name to #/definitions/Name
                def_name = value.split('/')[-1]
                processed[key] = f"#/definitions/{def_name}"
            else:
                processed[key] = process_schema_refs_and_remove_nested_defs(value)
        return processed
    elif isinstance(schema, list):
        return [process_schema_refs_and_remove_nested_defs(item) for item in schema]
    else:
        return schema


def remove_unwanted_titles(schema: Any) -> Any:
    """
    Recursively removes 'title' keys from a schema, except for titles
    on objects that directly contain a 'properties' key (i.e., model definitions).
    This prevents json-schema-to-typescript from creating aliases for simple types.
    """
    if not isinstance(schema, dict):
        return schema

    # Recurse first on all values
    new_schema = {k: remove_unwanted_titles(v) for k, v in schema.items()}

    # Now, check if the current object's title should be kept
    if 'title' in new_schema:
        # Keep title only if 'properties' is also a key at this level
        if 'properties' not in new_schema:
            del new_schema['title']
            
    return new_schema


def generate_types(
    source_file: Union[str, Path],
    registry_name: str,
    output: Union[str, Path],
    s2c_events_name: Optional[str] = None,
    *,
    verbose: bool = False,
    strict: bool = False,
) -> None:
    """
    Programmatic API to generate TypeScript types.

    Raises exceptions on errors; prints progress when verbose is True.
    """
    global strict_mode, warnings_occurred

    strict_mode = strict
    warnings_occurred = False

    source_path = Path(source_file).resolve()
    output_path = Path(output).resolve()
    output_path.parent.mkdir(exist_ok=True)

    if verbose:
        print(f"🔄 Processing source file: {source_path}")
        print(f"📦 Using registry: {registry_name}")
        if s2c_events_name:
            print(f"🔔 Using S2C events: {s2c_events_name}")
        if strict:
            print("🔒 Strict mode enabled")

    spec = importlib.util.spec_from_file_location(source_path.stem, source_path)
    if not spec or not spec.loader:
        raise ImportError(f"Could not import source file '{source_path}'")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(source_path.parent))
    try:
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
    finally:
        sys.path.pop(0)

    registry = getattr(module, registry_name)
    s2c_events = getattr(module, s2c_events_name, {}) if s2c_events_name else {}
    
    all_models = registry.models.copy()
    for model in s2c_events.values():
        if isinstance(model, type) and issubclass(model, BaseModel):
            all_models.add(model)

    if verbose:
        print(f"📝 Found {len(all_models)} models to process")

    schemas = {m.__name__: m.model_json_schema() for m in all_models}
    combined_schema = flatten_schema_definitions(schemas)
    combined_schema = remove_unwanted_titles(combined_schema)
    
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".json") as tmp_file:
        json.dump(combined_schema, tmp_file, indent=2)
        tmp_schema_path = tmp_file.name
    
    if verbose:
        print(f"💾 Temporary schema file created: {tmp_schema_path}")
        print("📄 Schema content:")
        print(json.dumps(combined_schema, indent=2))
    
    banner_comment = """/* eslint-disable */
/**
* This file was automatically generated by typsio-gen.
* DO NOT MODIFY IT BY HAND.
*/"""
    try:
        cmd = [
            "json2ts",
            "--input",
            tmp_schema_path,
            "--output",
            str(output_path),
            "--bannerComment",
            banner_comment,
            "--style.singleQuote",
            "--no-additionalProperties",
        ]
        if verbose:
            print(f"🚀 Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if verbose and result.stdout:
            print(f" STDOUT: {result.stdout}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        if isinstance(e, FileNotFoundError):
            raise RuntimeError(
                "json-schema-to-typescript not found. Install it: `npm i -g json-schema-to-typescript`"
            ) from e
        raise
    finally:
        Path(tmp_schema_path).unlink(missing_ok=True)
        if verbose:
            print(f"🧹 Cleaned up temporary files")

    with open(output_path, "a") as f:
        f.write("\n\n" + generate_ts_interface("RPCMethods", registry.functions, format_rpc_method))
        if s2c_events:
            f.write("\n\n" + generate_ts_interface("ServerToClientEvents", s2c_events, format_event))
    
    if verbose:
        print(f"📄 Appended RPC methods and events interfaces")
    
    if warnings_occurred:
        if strict:
            raise RuntimeError("Generation failed due to warnings (strict mode enabled)")
        else:
            print("⚠️  Generation completed with warnings", file=sys.stderr)
    else:
        if verbose or True:
            print(f"✅ TypeScript types successfully generated at: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate TypeScript types from a Typsio Python API definition file.")
    parser.add_argument("source_file", help="Path to the Python source file containing API definitions.")
    parser.add_argument("registry_name", help="Name of the RPCRegistry instance in the source file.")
    parser.add_argument("--output", "-o", required=True, help="Output path for the generated TypeScript file.")
    parser.add_argument("--s2c-events-name", help="Name of the Server-to-Client events dictionary (optional).")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output.")
    parser.add_argument("--strict", "-s", action="store_true", help="Treat warnings as errors.")
    args = parser.parse_args()

    try:
        generate_types(
            source_file=args.source_file,
            registry_name=args.registry_name,
            output=args.output,
            s2c_events_name=args.s2c_events_name,
            verbose=args.verbose,
            strict=args.strict,
        )
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main() 