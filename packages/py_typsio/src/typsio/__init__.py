# packages/py_typsio/src/typsio/__init__.py
"""
Typsio: Type-Safe RPC for Socket.IO.
"""
from .rpc import RPCRegistry, setup_rpc

__all__ = ["RPCRegistry", "setup_rpc"]
__version__ = "0.1.0"
