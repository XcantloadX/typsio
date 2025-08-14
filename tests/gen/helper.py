import subprocess
from pathlib import Path

import typsio

def run_generator(input_files, output_file):
    if isinstance(input_files, str):
        # Keep original behavior for single file string
        source_file = str(Path(__file__).parent / "inputs" / input_files)
    else:
        # Assume it's a list of paths/globs
        source_file = input_files

    output_path = Path(__file__).parent / "generated" / output_file

    output_path.parent.mkdir(exist_ok=True)

    typsio.generate_types(
        source_file=source_file,
        registry_name="registry",
        output=str(output_path),
    )
    return output_path


def ts_typecheck(validation_file: str):
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