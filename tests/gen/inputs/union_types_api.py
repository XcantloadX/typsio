# tests/gen/inputs/union_types_api.py
from pydantic import BaseModel
from typing import Union, Optional
from typsio.rpc import RPCRegistry

class UnionTypesModel(BaseModel):
    classic_union: Union[str, int]
    optional_type: Optional[bool]
    new_union_syntax: str | float | None

registry = RPCRegistry()

@registry.register
def get_unions() -> UnionTypesModel:
    ...
