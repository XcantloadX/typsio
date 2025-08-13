# tests/gen/inputs/pydantic_models_api.py
from pydantic import BaseModel
from typsio.rpc import RPCRegistry

class NestedModel(BaseModel):
    id: int
    name: str
    detail: str

class TopLevelModel(BaseModel):
    id: int
    nested: NestedModel

registry = RPCRegistry()

@registry.register
def get_model() -> TopLevelModel:
    ...
