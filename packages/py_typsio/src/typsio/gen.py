# generator/typsio_gen.py
import json
import subprocess
import argparse
import importlib.util
import sys
import tempfile
import glob
from pathlib import Path
from inspect import signature
from pydantic import BaseModel
from typing import Callable, Dict, Any, Type, Set, Union, Optional, List
from dataclasses import dataclass

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


# TODO: docstring 改用英文

@dataclass
class TypsioGenConfig:
    """
    参数配置类，用于通过 -c/--config 传入配置文件时提供参数。

    在配置文件中需要实例化此类，例如：

    from typsio.gen import TypsioGenConfig
    config = TypsioGenConfig(
        source_files=["./api.py", "./more_api.py"],
        registry_name="rpc_registry",
        output="./types.gen.ts",
        s2c_events_name="S2C_EVENTS",
        verbose=True,
        strict=False,
    )
    或者兼容单文件：
    config = TypsioGenConfig(
        source_file="./api.py",
        registry_name="rpc_registry",
        output="./types.gen.ts",
    )
    """
    source_file: Optional[Union[str, Path]] = None
    """
    输入 Python 文件路径（单文件，兼容旧版本）。
    """
    source_files: Optional[List[Union[str, Path]]] = None
    """
    输入多个 Python 文件路径。与 source_file 互斥，优先使用此字段。
    """
    registry_name: str = ""
    """
    输入文件中注册表变量（RPCRegistry 实例）的名称。
    """
    output: Union[str, Path] = ""
    """
    输出 TypeScript 定义文件路径。
    """
    s2c_events_name: Optional[str] = None
    """
    输入文件中 S2C 事件字典变量（ServerToClientEvents 实例）的名称。
    """
    verbose: bool = False
    """
    是否打印详细信息。
    """
    strict: bool = False
    """
    是否启用严格模式。
    """


def _load_config_from_py(config_path: Union[str, Path]) -> TypsioGenConfig:
    """
    导入配置文件，并返回其中的 TypsioGenConfig 实例。

    支持在配置中使用导入语句；执行前会将配置文件所在目录临时加入 sys.path。

    示例：
    ```python
    from typsio.gen import TypsioGenConfig # 可不写，只是为了让 TypingChecker 通过
    export = TypsioGenConfig(
        source_files=["my_app/api_defs.py", "my_app/more_api.py"],
        registry_name="registry",
        output="../frontend/src/generated/api-types.ts",
    )
    ```
    """
    cfg_path = Path(config_path).resolve()
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")

    source_code = cfg_path.read_text(encoding="utf-8")

    # 隔离执行环境，仅暴露必要对象
    exec_globals: Dict[str, Any] = {
        "__builtins__": __builtins__,
        "TypsioGenConfig": TypsioGenConfig,
        "Path": Path,
    }
    exec_locals: Dict[str, Any] = {}

    # 将配置文件目录加入 sys.path 以支持其内部导入
    sys.path.insert(0, str(cfg_path.parent))
    try:
        compiled = compile(source_code, str(cfg_path), "exec")
        exec(compiled, exec_globals, exec_locals)
    except Exception as e:
        raise RuntimeError(f"Failed to evaluate config file '{cfg_path}': {e}") from e
    finally:
        sys.path.pop(0)

    # 在执行命名空间中查找 TypsioGenConfig 的实例
    for ns in (exec_locals, exec_globals):
        for _name, value in ns.items():
            if isinstance(value, TypsioGenConfig):
                return value

    raise ValueError(
        f"No TypsioGenConfig instance found in '{cfg_path}'. "
        "Please instantiate TypsioGenConfig, e.g. `config = TypsioGenConfig(...)`."
    )


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
            return f"Record<{get_ts_type(args[0])}, {get_ts_type(args[1])}>"
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
    source_file: Union[str, Path, List[Union[str, Path]]],
    registry_name: str,
    output: Union[str, Path],
    s2c_events_name: Optional[str] = None,
    *,
    verbose: bool = False,
    strict: bool = False,
) -> None:
    """
    Programmatic API to generate TypeScript types.

    Supports multiple Python source files. Aggregates all models, RPC methods,
    and S2C events, then emits a single merged TypeScript file.

    Raises exceptions on errors; prints progress when verbose is True.
    """
    global strict_mode, warnings_occurred

    strict_mode = strict
    warnings_occurred = False

    # 解析输入文件路径，支持 glob
    if not isinstance(source_file, list):
        source_patterns = [source_file]
    else:
        source_patterns = source_file

    source_paths: List[Path] = []
    for pattern in source_patterns:
        # NOTE: Path patterns are relative to the current working directory.
        # `glob` will expand them. `recursive=True` allows for `**`.
        matched_files = glob.glob(str(pattern), recursive=True)
        for f_str in matched_files:
            f_path = Path(f_str)
            if f_path.is_file():
                source_paths.append(f_path.resolve())

    # Remove duplicates and sort for consistent order
    if source_paths:
        source_paths = sorted(list(set(source_paths)))

    if not source_paths:
        patterns_str = ', '.join(map(str, source_patterns))
        raise FileNotFoundError(f"No source files found for given patterns: {patterns_str}")

    output_path = Path(output).resolve()
    output_path.parent.mkdir(exist_ok=True)

    if verbose:
        if len(source_paths) == 1:
            print(f"🔄 Processing source file: {source_paths[0]}")
        else:
            print(f"🔄 Processing {len(source_paths)} source files:")
            for p in source_paths:
                print(f"   • {p}")
        print(f"📦 Using registry: {registry_name}")
        if s2c_events_name:
            print(f"🔔 Using S2C events: {s2c_events_name}")
        if strict:
            print("🔒 Strict mode enabled")

    # 聚合容器
    all_models: Set[Type[BaseModel]] = set()
    all_functions: Dict[str, Callable[..., Any]] = {}
    all_s2c_events: Dict[str, Type[BaseModel]] = {}

    # 导入各个模块，收集 registry 与事件
    for source_path in source_paths:
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

        # 模型
        for model in registry.models:
            if isinstance(model, type) and issubclass(model, BaseModel):
                all_models.add(model)

        # RPC 方法（名称冲突后者覆盖并给出警告）
        for func_name, func in getattr(registry, 'functions', {}).items():
            if func_name in all_functions and verbose:
                print(f"⚠️  Duplicate RPC method '{func_name}' found. Overriding previous definition.", file=sys.stderr)
            all_functions[func_name] = func

        # 事件（名称冲突后者覆盖并给出警告）
        for evt_name, evt_model in getattr(s2c_events, 'items', lambda: [])():
            if evt_name in all_s2c_events and verbose:
                print(f"⚠️  Duplicate S2C event '{evt_name}' found. Overriding previous definition.", file=sys.stderr)
            if isinstance(evt_model, type) and issubclass(evt_model, BaseModel):
                all_models.add(evt_model)
                all_s2c_events[evt_name] = evt_model

    if verbose:
        print(f"📝 Found {len(all_models)} models to process")
        print(f"🧩 Aggregated {len(all_functions)} RPC methods and {len(all_s2c_events)} S2C events")

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
        f.write("\n\n" + generate_ts_interface("RPCMethods", all_functions, format_rpc_method))
        if all_s2c_events:
            f.write("\n\n" + generate_ts_interface("ServerToClientEvents", all_s2c_events, format_event))
    
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
    # 允许省略位置参数以支持纯配置文件方式调用
    parser.add_argument("registry_name", nargs="?", help="Name of the RPCRegistry instance in the source files.")
    parser.add_argument("--input", "-i", nargs="+", help="Path(s) to Python source file(s) containing API definitions.")
    parser.add_argument("--output", "-o", required=False, help="Output path for the generated TypeScript file.")
    parser.add_argument("--s2c-events-name", help="Name of the Server-to-Client events dictionary (optional, same name in each file).")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output.")
    parser.add_argument("--strict", "-s", action="store_true", help="Treat warnings as errors.")
    parser.add_argument("--config", "-c", help="Path to a .py config file that instantiates TypsioGenConfig.")
    args = parser.parse_args()

    try:
        config_obj: Optional[TypsioGenConfig] = None

        if args.config:
            # 显式指定配置文件
            config_obj = _load_config_from_py(args.config)
        else:
            # 检测是否完全未指定任何参数（包含位置参数与选项）
            no_args_provided = (
                (not args.input) and
                args.registry_name is None and
                args.output is None and
                args.s2c_events_name is None and
                args.verbose is False and
                args.strict is False
            )
            if no_args_provided:
                default_cfg = Path("./typsio.config.py").resolve()
                if default_cfg.exists():
                    config_obj = _load_config_from_py(default_cfg)
                else:
                    raise ValueError(
                        "No arguments were provided and './typsio.config.py' was not found. "
                        "Provide CLI args or a config file via --config/-c."
                    )

        if config_obj is None:
            # 使用 CLI 传参路径（必须完整提供三要素）
            if not (args.input and args.registry_name and args.output):
                raise ValueError(
                    "Incomplete CLI arguments. Provide '-i/--input', 'registry_name' and '--output', "
                    "or use '--config/-c', or provide no args to use './typsio.config.py'."
                )
            # 构建配置对象
            config_obj = TypsioGenConfig(
                source_files=args.input,
                registry_name=args.registry_name,
                output=args.output,
                s2c_events_name=args.s2c_events_name,
                verbose=bool(args.verbose),
                strict=bool(args.strict),
            )

        # 选择 source_files 优先，否则回退到单文件
        cfg_sources: Union[str, Path, List[Union[str, Path]]]
        if config_obj.source_files and len(config_obj.source_files) > 0:
            cfg_sources = config_obj.source_files
        elif config_obj.source_file:
            cfg_sources = config_obj.source_file
        else:
            raise ValueError("TypsioGenConfig must include 'source_files' or 'source_file'.")

        generate_types(
            source_file=cfg_sources,
            registry_name=config_obj.registry_name,
            output=config_obj.output,
            s2c_events_name=config_obj.s2c_events_name,
            verbose=config_obj.verbose,
            strict=config_obj.strict,
        )
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main() 