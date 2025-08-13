# tests/gen/inputs/basic_types_api.py
from pydantic import BaseModel
from typing import Any, Optional
from typsio.rpc import RPCRegistry

class BasicTypesModel(BaseModel):
    an_int: int
    a_float: float
    a_str: str
    a_bool: bool
    a_none: Optional[str]
    any_type: Any

registry = RPCRegistry()

@registry.register
def get_basic_types() -> BasicTypesModel:
    ...
