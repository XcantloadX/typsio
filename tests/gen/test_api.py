import sys
import unittest
from pathlib import Path

from .helper import run_generator, ts_typecheck


class TestTypsioAPI(unittest.TestCase):
    def test_glob(self):
        """Test generate_types with glob pattern input."""
        input_glob = str(Path(__file__).parent / "inputs" / "glob_test_api_*.py")
        output_path = run_generator([input_glob], "api_test_glob.ts")
        self.assertTrue(output_path.exists())
        ts_typecheck("glob_test.validate.ts")


if __name__ == "__main__":
    (Path(__file__).parent / "generated").mkdir(exist_ok=True)
    unittest.main()