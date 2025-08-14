import unittest
from pathlib import Path

from .helper import run_generator, ts_typecheck


class TestTypsioTypes(unittest.TestCase):
    def test_basic_types(self):
        run_generator("basic_types_api.py", "basic_types.ts")
        ts_typecheck("basic_types.validate.ts")

    def test_pydantic_models(self):
        run_generator(
            "pydantic_models_api.py", "pydantic_models.ts"
        )
        ts_typecheck("pydantic_models.validate.ts")

    def test_collection_types(self):
        run_generator(
            "collection_types_api.py", "collection_types.ts"
        )
        ts_typecheck("collection_types.validate.ts")

    def test_union_types(self):
        run_generator("union_types_api.py", "union_types.ts")
        ts_typecheck("union_types.validate.ts")


if __name__ == "__main__":
    (Path(__file__).parent / "generated").mkdir(exist_ok=True)
    unittest.main()