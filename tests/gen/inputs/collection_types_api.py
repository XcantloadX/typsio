# tests/gen/inputs/collection_types_api.py
from pydantic import BaseModel
from typing import List, Dict, Set
from typsio.rpc import RPCRegistry

class CollectionTypesModel(BaseModel):
    str_list: List[str]
    num_dict: Dict[str, int]
    int_set: Set[int]

registry = RPCRegistry()

@registry.register
def get_collections() -> CollectionTypesModel:
    ...
