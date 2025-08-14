from pydantic import BaseModel
from typsio.rpc import RPCRegistry

registry = RPCRegistry()

class GlobModel1(BaseModel):
    prop1: str

@registry.register
def func_from_glob_1(param1: GlobModel1) -> int:
    return 1
