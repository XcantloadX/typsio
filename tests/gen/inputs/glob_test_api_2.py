from pydantic import BaseModel
from typsio.rpc import RPCRegistry

registry = RPCRegistry()

class GlobModel2(BaseModel):
    prop2: bool

@registry.register
def func_from_glob_2(param2: GlobModel2) -> str:
    return "hello"
