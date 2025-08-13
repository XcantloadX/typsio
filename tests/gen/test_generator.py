import unittest
import subprocess
import sys
from pathlib import Path
import os


class TestTypsioGenerator(unittest.TestCase):
	maxDiff = None

	def _run_generator(self, input_file, output_file):
		generator_path = Path(__file__).parent.parent.parent / "generator/typsio_gen.py"
		input_path = Path(__file__).parent / "inputs" / input_file
		output_path = Path(__file__).parent / "generated" / output_file

		output_path.parent.mkdir(exist_ok=True)

		project_root = Path(__file__).parent.parent.parent

		# Create a modified environment for the subprocess
		env = os.environ.copy()
		python_path = env.get("PYTHONPATH", "")
		# Prepend the project root to PYTHONPATH
		env["PYTHONPATH"] = f"{project_root}{os.pathsep}{python_path}"
		args = [
			sys.executable,
			str(generator_path),
			str(input_path),
			"registry",
			"--output",
			str(output_path),
		]
		print('Run command:', ' '.join(args))
		try:
			result = subprocess.run(
				args,
				check=True,
				capture_output=True,
				text=True,
				env=env,  # Pass the modified environment
			)
		except subprocess.CalledProcessError as e:
			print("--- STDOUT ---")
			print(e.stdout)
			print("--- STDERR ---")
			print(e.stderr)
			raise e

		return output_path

	def _ts_typecheck(self, validation_file: str):
		"""Run TypeScript compiler in no-emit mode on a specific validation file."""
		validate_path = Path(__file__).parent / "validate" / validation_file
		# Run tsc directly on this file so it only type-checks this test case and its imports
		args = [
			"npx",
			"--yes",
			"tsc",
			"--noEmit",
			"--lib",
			"esnext",
			str(validate_path),
		]
		print('Type-check command:', ' '.join(str(a) for a in args))
		try:
			result = subprocess.run(
				args,
				check=True,
				capture_output=True,
				text=True,
				cwd=str(Path(__file__).parent),
			)
		except subprocess.CalledProcessError as e:
			print("--- TSC STDOUT ---")
			print(e.stdout)
			print("--- TSC STDERR ---")
			print(e.stderr)
			raise e

	def tearDown(self):
		# Clean up generated files after each test
		generated_dir = Path(__file__).parent / "generated"
		if generated_dir.exists():
			for f in generated_dir.glob("*.ts"):
				os.remove(f)

	def test_basic_types(self):
		self._run_generator("basic_types_api.py", "basic_types.ts")
		self._ts_typecheck("basic_types.validate.ts")

	def test_pydantic_models(self):
		self._run_generator(
			"pydantic_models_api.py", "pydantic_models.ts"
		)
		self._ts_typecheck("pydantic_models.validate.ts")

	def test_collection_types(self):
		self._run_generator(
			"collection_types_api.py", "collection_types.ts"
		)
		self._ts_typecheck("collection_types.validate.ts")

	def test_union_types(self):
		self._run_generator("union_types_api.py", "union_types.ts")
		self._ts_typecheck("union_types.validate.ts")


if __name__ == "__main__":
	(Path(__file__).parent / "generated").mkdir(exist_ok=True)
	unittest.main()
