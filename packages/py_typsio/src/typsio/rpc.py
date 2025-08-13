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
