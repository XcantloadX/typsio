# packages/py_typsio/src/typsio/__init__.py
"""
Typsio: Type-Safe RPC for Socket.IO.
"""
from .rpc import RPCRegistry, setup_rpc
from .gen import generate_types

__all__ = ["RPCRegistry", "setup_rpc", "generate_types"]
__version__ = "0.1.0"
