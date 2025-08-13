## **最终方案：`typsio` - 类型安全的 Socket.IO RPC 框架**

### 1. 项目愿景与核心特性

**`typsio`** 是一个轻量级、非侵入式的库，旨在为 `python-socketio` 和 `socket.io-client` 带来端到端的类型安全。

*   **项目名称**: `typsio` (Typed Socket.IO)
*   **核心特性**:
    1.  **端到端类型安全**: 从 Python 后端到 TypeScript 前端的函数签名和数据模型完全同步。
    2.  **声明式 API**: 使用简单的装饰器定义 RPC 接口。
    3.  **双向通信**: 无缝支持客户端发起的 RPC 和服务器主动推送的事件。
    4.  **现代 Python 工作流**: 使用 `pyproject.toml` 和 `uv` 进行包管理和任务运行。
    5.  **灵活集成**: 支持作为 `pip`/`npm` 包安装，或直接以源码形式集成。
    6.  **健壮设计**: 通过注册表模式从根本上避免循环引用问题。

### 2. 最终项目结构

```
typsio/
├── packages/
│   ├── py_typsio/                # Python 包
│   │   ├── src/
│   │   │   └── typsio/
│   │   │       ├── __init__.py
│   │   │       └── rpc.py
│   │   └── pyproject.toml
│   │
│   └── ts_typsio/                # TypeScript 包
│       ├── src/
│       │   └── index.ts
│       ├── package.json
│       └── tsconfig.json
│
├── generator/
│   └── typsio_gen.py             # 代码生成器脚本
│
├── examples/                     # 一个完整的、可运行的示例项目
│   ├── backend/
│   │   ├── src/
│   │   │   └── my_app/
│   │   │       ├── __init__.py
│   │   │       ├── api_defs.py   # 业务 API 定义
│   │   │       └── server.py     # 服务器主应用
│   │   └── pyproject.toml        # 示例项目的依赖和任务
│   │
│   └── frontend/
│       ├── src/
│       │   ├── api.ts
│       │   ├── main.ts
│       │   └── generated/
│       │       └── api-types.ts
│       ├── index.html
│       ├── package.json
│       └── tsconfig.json
│
└── README.md
```
**说明**: 我们采用 monorepo 风格，将 Python 包、TypeScript 包、生成器和示例项目都放在一个仓库中，便于统一管理。

### 3. Python 包 (`py_typsio`)

#### 3.1. `packages/py_typsio/pyproject.toml`

```toml
[project]
name = "typsio"
version = "0.1.0"
authors = [
    { name = "Your Name", email = "your.email@example.com" },
]
description = "A type-safe RPC and event library for python-socketio."
readme = "../../../README.md"  # Assuming README is at the monorepo root
requires-python = ">=3.8"
classifiers = [
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Framework :: AsyncIO",
    "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
]
dependencies = [
    "python-socketio>=5.0.0",
    "pydantic>=2.0.0",
]

[project.urls]
"Homepage" = "https://github.com/your-repo/typsio"
"Bug Tracker" = "https://github.com/your-repo/typsio/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

#### 3.2. `packages/py_typsio/src/typsio/rpc.py`

这是 Python 库的核心，提供 `RPCRegistry` 和 `setup_rpc`。

```python
# packages/py_typsio/src/typsio/rpc.py
import asyncio
from inspect import iscoroutinefunction, signature, Parameter
from typing import Dict, Any, Callable, Type, Set
import socketio
from pydantic import BaseModel, ValidationError

class RPCRegistry:
    """
    一个无状态的注册表，用于收集 RPC 函数及其关联的 Pydantic 模型。
    这种设计避免了在定义 API 时产生循环导入。
    """
    def __init__(self):
        self.functions: Dict[str, Callable] = {}
        self.models: Set[Type[BaseModel]] = set()

    def _add_model_from_type(self, py_type: Any):
        """递归地从类型提示中提取并注册 Pydantic 模型。"""
        # 处理泛型，例如 list[MyModel] 或 dict[str, MyModel]
        if hasattr(py_type, '__args__'):
            for arg in py_type.__args__:
                self._add_model_from_type(arg)
        
        if isinstance(py_type, type) and issubclass(py_type, BaseModel):
            self.models.add(py_type)

    def register(self, func: Callable) -> Callable:
        """
        一个装饰器，用于将函数注册到本注册表中。
        它会自动从函数签名中提取 Pydantic 模型用于代码生成。
        """
        if not callable(func):
            raise TypeError("A callable function must be provided.")
        
        self.functions[func.__name__] = func
        
        sig = signature(func)
        self._add_model_from_type(sig.return_annotation)
        for param in sig.parameters.values():
            self._add_model_from_type(param.annotation)
            
        return func

class _RPCHandler:
    """内部 RPC 处理器，将注册表中的函数应用到 Socket.IO 服务器。"""
    def __init__(self, sio: socketio.AsyncServer, registry: RPCRegistry, rpc_event_name: str, response_event_name: str):
        self._sio = sio
        self._functions = registry.functions
        self._rpc_event_name = rpc_event_name
        self._response_event_name = response_event_name

    async def _handle_rpc_call(self, sid: str, data: Dict[str, Any]):
        call_id = data.get("call_id")
        function_name = data.get("function_name")
        args = data.get("args", [])

        if not all([call_id, function_name]):
            return

        if function_name not in self._functions:
            await self._sio.emit(self._response_event_name, {"call_id": call_id, "error": f"RPC Error: Function '{function_name}' not found."}, to=sid)
            return

        func = self._functions[function_name]
        try:
            sig = signature(func)
            bound_args = {}
            func_params = list(sig.parameters.values())

            # 自动 Pydantic 模型验证
            for i, arg_val in enumerate(args):
                if i < len(func_params):
                    param = func_params[i]
                    if isinstance(param.annotation, type) and issubclass(param.annotation, BaseModel):
                        bound_args[param.name] = param.annotation.model_validate(arg_val)
                    else:
                        bound_args[param.name] = arg_val
                else:
                    # 处理 *args 的情况，虽然在此 RPC 设计中不常见
                    pass

            result = await func(**bound_args) if iscoroutinefunction(func) else func(**bound_args)
            
            if isinstance(result, BaseModel):
                result = result.model_dump(mode='json')

            await self._sio.emit(self._response_event_name, {"call_id": call_id, "result": result, "error": None}, to=sid)
        except (ValidationError, TypeError) as e:
            await self._sio.emit(self._response_event_name, {"call_id": call_id, "error": f"Argument validation failed: {e}"}, to=sid)
        except Exception as e:
            await self._sio.emit(self._response_event_name, {"call_id": call_id, "error": f"RPC Execution Error: {e}"}, to=sid)

    def attach_to_server(self):
        self._sio.on(self._rpc_event_name, self._handle_rpc_call)

def setup_rpc(sio: socketio.AsyncServer, registry: RPCRegistry, rpc_event_name: str = 'rpc_call') -> None:
    """
    将 RPCRegistry 中定义的所有函数附加到 Socket.IO 服务器。

    :param sio: `python-socketio` 的 AsyncServer 实例。
    :param registry: 包含已注册 RPC 函数的 `RPCRegistry` 实例。
    :param rpc_event_name: 用于 RPC 调用的事件名称，必须与客户端匹配。
    """
    response_event_name = f"{rpc_event_name}_response"
    handler = _RPCHandler(sio, registry, rpc_event_name, response_event_name)
    handler.attach_to_server()

```

#### 3.3. `packages/py_typsio/src/typsio/__init__.py`
```python
# packages/py_typsio/src/typsio/__init__.py
"""
Typsio: Type-Safe RPC for Socket.IO.
"""
from .rpc import RPCRegistry, setup_rpc

__all__ = ["RPCRegistry", "setup_rpc"]
__version__ = "0.1.0"
```

### 4. TypeScript 包 (`ts_typsio`)

#### 4.1. `packages/ts_typsio/package.json`
```json
{
  "name": "typsio-client",
  "version": "0.1.0",
  "description": "Type-safe client for Typsio.",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "prepublishOnly": "npm run build"
  },
  "keywords": ["socket.io", "rpc", "typescript", "type-safe"],
  "author": "Your Name <your.email@example.com>",
  "license": "MIT",
  "peerDependencies": {
    "socket.io-client": "^4.0.0"
  },
  "devDependencies": {
    "socket.io-client": "^4.7.2",
    "typescript": "^5.2.2"
  },
  "files": [
    "dist"
  ]
}
```

#### 4.2. `packages/ts_typsio/tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2018",
    "module": "commonjs",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "declaration": true,
    "sourceMap": true
  },
  "include": ["src"]
}
```

#### 4.3. `packages/ts_typsio/src/index.ts`
```typescript
// packages/ts_typsio/src/index.ts
import { io, Socket } from 'socket.io-client';

// 默认类型，将被用户生成的类型覆盖
export interface DefaultRPCMethods { [key: string]: (...args: any[]) => Promise<any>; }
export interface DefaultServerEvents { [key: string]: (...args: any[]) => void; }

export interface TypsioClientOptions {
  timeout?: number;
  rpcEventName?: string;
}

interface PendingCall {
  resolve: (value: any) => void;
  reject: (reason?: any) => void;
  timeoutTimer: NodeJS.Timeout;
}

/**
 * 创建一个类型安全的 Typsio 客户端。
 * @param socket 一个已存在的 socket.io-client 实例。
 * @param options Typsio 客户端的配置选项。
 * @returns 一个包含 remote (用于 RPC 调用) 和事件监听器 (on, off) 的客户端实例。
 */
export function createTypsioClient<
  ServerEvents extends DefaultServerEvents = DefaultServerEvents,
  ClientRPC extends DefaultRPCMethods = DefaultRPCMethods
>(socket: Socket, options: TypsioClientOptions = {}) {
  const {
    timeout = 10000,
    rpcEventName = 'rpc_call',
  } = options;
  const responseEventName = `${rpcEventName}_response`;

  let callCounter = 0;
  const pendingCalls = new Map<string, PendingCall>();

  socket.on(responseEventName, (data: { call_id: string; result?: any; error?: string }) => {
    const pending = pendingCalls.get(data.call_id);
    if (!pending) return;

    clearTimeout(pending.timeoutTimer);
    if (data.error) {
      pending.reject(new Error(data.error));
    } else {
      pending.resolve(data.result);
    }
    pendingCalls.delete(data.call_id);
  });
  
  socket.on('disconnect', () => {
    pendingCalls.forEach((call, id) => {
      clearTimeout(call.timeoutTimer);
      call.reject(new Error('Socket disconnected. RPC call aborted.'));
      pendingCalls.delete(id);
    });
  });

  const remote = new Proxy({}, {
    get: (target, prop) => {
      if (typeof prop !== 'string') return undefined;
      return (...args: any[]) => {
        return new Promise((resolve, reject) => {
          if (!socket.connected) {
            return reject(new Error("Socket is not connected."));
          }
          const callId = `${socket.id}-${callCounter++}`;

          const timeoutTimer = setTimeout(() => {
            pendingCalls.delete(callId);
            reject(new Error(`RPC call '${prop}' timed out after ${timeout}ms`));
          }, timeout);

          pendingCalls.set(callId, { resolve, reject, timeoutTimer });

          socket.emit(rpcEventName as any, {
            call_id: callId,
            function_name: prop,
            args,
          });
        });
      };
    },
  }) as ClientRPC;

  return {
    remote,
    on<E extends keyof ServerEvents>(event: E, listener: ServerEvents[E]): void {
      socket.on(event as string, listener);
    },
    off<E extends keyof ServerEvents>(event: E, listener?: ServerEvents[E]): void {
      socket.off(event as string, listener);
    },
    socket,
  };
}
```

### 5. 代码生成器 (`typsio_gen`)

#### 5.1. `generator/typsio_gen.py`

```python
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
    return f"'{name}': (payload: {get_ts_type(model)}) => void;"

def main():
    parser = argparse.ArgumentParser(description="Generate TypeScript types from a Typsio Python API definition file.")
    parser.add_argument("source_file", help="Path to the Python source file containing API definitions.")
    parser.add_argument("registry_name", help="Name of the RPCRegistry instance in the source file.")
    parser.add_argument("--output", "-o", required=True, help="Output path for the generated TypeScript file.")
    parser.add_argument("--s2c-events-name", help="Name of the Server-to-Client events dictionary (optional).")
    args = parser.parse_args()

    source_path = Path(args.source_file).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(exist_ok=True)

    spec = importlib.util.spec_from_file_location(source_path.stem, source_path)
    if not spec or not spec.loader:
        print(f"Error: Could not import source file '{source_path}'", file=sys.stderr)
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(source_path.parent))
    spec.loader.exec_module(module)
    sys.path.pop(0)

    registry = getattr(module, args.registry_name)
    s2c_events = getattr(module, args.s2c_events_name, {}) if args.s2c_events_name else {}
    
    all_models = registry.models.copy()
    for model in s2c_events.values():
        if isinstance(model, type) and issubclass(model, BaseModel):
            all_models.add(model)

    schemas = {m.__name__: m.model_json_schema() for m in all_models}
    combined_schema = {"title": "TypsioModels", "type": "object", "properties": schemas, "definitions": schemas}
    
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".json") as tmp_file:
        json.dump(combined_schema, tmp_file, indent=2)
        tmp_schema_path = tmp_file.name
    
    banner_comment = "/* eslint-disable */\n/**\n* This file was automatically generated by typsio-gen.\n* DO NOT MODIFY IT BY HAND.\n*/"
    try:
        subprocess.run(
            ["json-schema-to-typescript", "--input", tmp_schema_path, "--output", str(output_path), "--banner-comment", banner_comment, "--style.singleQuote", "true"],
            check=True, capture_output=True, text=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"❌ Error during TypeScript generation. Is 'json-schema-to-typescript' installed globally (`npm i -g json-schema-to-typescript`)?", file=sys.stderr)
        if isinstance(e, subprocess.CalledProcessError):
            print(e.stderr, file=sys.stderr)
        sys.exit(1)
    finally:
        Path(tmp_schema_path).unlink()

    with open(output_path, "a") as f:
        f.write("\n\n" + generate_ts_interface("RPCMethods", registry.functions, format_rpc_method))
        if s2c_events:
            f.write("\n\n" + generate_ts_interface("ServerToClientEvents", s2c_events, format_event))
    
    print(f"✅ TypeScript types successfully generated at: {output_path}")

if __name__ == "__main__":
    main()
```

### 6. 示例项目 (`examples/`)

这是一个完整的、可运行的演示，展示了 `typsio` 的最佳实践。

#### 6.1. 后端 (`examples/backend/`)

**`pyproject.toml`**
```toml
[project]
name = "typsio-example-backend"
version = "0.1.0"
dependencies = [
    "uvicorn",
    "typsio @ {root:uri}/../../packages/py_typsio" # 本地路径依赖
]

[tool.uv.scripts]
dev = "uvicorn my_app.server:app --reload --reload-dir src"
gen-types = "python ../../../generator/typsio_gen.py src/my_app/api_defs.py rpc_registry --s2c-events-name SERVER_EVENTS -o ../frontend/src/generated/api-types.ts"
```

**`src/my_app/api_defs.py`**
```python
from pydantic import BaseModel, Field
from typsio import RPCRegistry
import datetime

# 1. 定义数据模型
class User(BaseModel):
    id: int
    name: str

class Message(BaseModel):
    text: str = Field(..., max_length=256)
    user: User

# 2. 创建 RPC 注册表
rpc_registry = RPCRegistry()

# 3. 注册 RPC 函数
@rpc_registry.register
async def get_user(user_id: int) -> User | None:
    if user_id == 1:
        return User(id=1, name="Alice")
    return None

@rpc_registry.register
def send_message(message: Message) -> bool:
    print(f"Received message from {message.user.name}: {message.text}")
    # 在真实应用中，这里会触发一个事件
    return True

# 4. 定义服务器到客户端的事件
class Notification(BaseModel):
    message: str
    timestamp: datetime.datetime

SERVER_EVENTS = {
    "newNotification": Notification
}
```

**`src/my_app/server.py`**
```python
import socketio
import uvicorn
from typsio import setup_rpc
from .api_defs import rpc_registry

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio)

# 将 API 定义附加到服务器
setup_rpc(sio, rpc_registry)

@sio.event
async def connect(sid, environ):
    print(f'Client connected: {sid}')

if __name__ == "__main__":
    uvicorn.run("my_app.server:app", host="0.0.0.0", port=8000, reload=True)
```

#### 6.2. 前端 (`examples/frontend/`)

**`package.json`**
```json
{
  "name": "typsio-example-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "gen-types": "uv run gen-types"
  },
  "dependencies": {
    "socket.io-client": "^4.7.4",
    "typsio-client": "file:../../packages/ts_typsio"
  },
  "devDependencies": {
    "typescript": "^5.2.2",
    "vite": "^5.0.8"
  }
}
```
**`src/api.ts`**
```typescript
import { io } from 'socket.io-client';
import { createTypsioClient } from 'typsio-client';
import type { RPCMethods, ServerToClientEvents } from './generated/api-types';

const socket = io('http://localhost:8000');
const client = createTypsioClient<ServerToClientEvents, RPCMethods>(socket);

export const api = client.remote;
export const on = client.on;
export const socketInstance = client.socket;
```
**`src/main.ts`**
```typescript
import { api, on, socketInstance } from './api';
import './style.css'

document.querySelector<HTMLDivElement>('#app')!.innerHTML = `
  <div>
    <h1>Typsio Demo</h1>
    <div id="logs"></div>
  </div>
`
const logs = document.querySelector<HTMLDivElement>('#logs')!;
const log = (msg: string) => {
  logs.innerHTML += `<p>${new Date().toLocaleTimeString()}: ${msg}</p>`;
};

socketInstance.on('connect', async () => {
  log('✅ Connected to server!');
  
  // Test RPC call 1
  try {
    const user = await api.get_user(1);
    log(`RPC get_user(1) success: ${JSON.stringify(user)}`);

    // Test RPC call 2
    if(user) {
      const success = await api.send_message({ text: 'Hello Typsio!', user });
      log(`RPC send_message success: ${success}`);
    }
  } catch (e) {
    log(`RPC Error: ${(e as Error).message}`);
  }
});

// Test event listener
on('newNotification', (payload) => {
  log(`EVENT newNotification received: ${payload.message} at ${payload.timestamp}`);
});
```

### 7. 最终工作流

1.  **启动后端**: `cd examples/backend` 然后 `uv run dev`。
2.  **启动前端**: `cd examples/frontend` 然后 `npm install` (或 `yarn`, `pnpm i`)，接着 `npm run dev`。
3.  **修改API**: 编辑 `examples/backend/src/my_app/api_defs.py`。
4.  **重新生成类型**: 在 `examples/frontend/` 目录下运行 `npm run gen-types`（它会通过 `uv` 调用 Python 脚本）。
5.  **查看结果**: 前端 TypeScript 代码会立即获得新的类型提示和错误检查。浏览器会自动刷新，展示新的交互结果。

这份方案涵盖了项目结构、库代码、打包配置、生成器和完整的示例，构成了一个可立即实施的、高质量的开源项目基础。