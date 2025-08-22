# Typsio
> [!WARNING]
> This project is still under development and not ready for production use.

Typsio is a RPC library designed to provide type safety and ease of use for your Python server(with Pydantic) and TypeScript client, especially for desktop applications based on Web technologies.

## Installation
Python side:
```bash
# Python 3.8+
pip install typsio
```

TypeScript side:
```bash
npm install typsio-client socket.io-client
# And install json-schema-to-typescript for type generation
npm install -g json-schema-to-typescript
```

## Quickstart
1. Define your business functions
```python
from pydantic import BaseModel
class User(BaseModel):
    id: int
    name: str

def get_user(user_id: int) -> User | None:
    # Complex database query
    ...
```

2. Register your RPC methods
```python
from typsio import RPCRegistry
from .models import User
rpc_registry = RPCRegistry()

@rpc_registry.register
def get_user(user_id: int) -> User | None:
    return get_user(user_id)
```

3. Create config file `typsio.config.py` in your project root directory
```python
# Importing is optional. It's just to make your type checker happy.
# If you like, you can use `if typing.TYPE_CHECKING: ...` pattern,
# or just omit this import.
from typsio.gen import TypsioGenConfig

# Variable name must be `export`
export = TypsioGenConfig(
    source_file='./backend/rpc_methods.py', # Glob pattern also works
    registry_name='rpc_registry', # Variable name of RPCRegistry instance
    output='./frontend/api-types.ts',
)
```

## Documentation
WIP.

## Contributing
### Setup
1. Fork & Clone

2. Setup Python envioronment:
```bash
# cd typsio
# with venv
uv venv
uv pip install -e packages/py_typsio
# without venv
python -m venv .venv
pip install -e packages/py_typsio
```

3. Setup Typescript environment:
```bash
cd packages/ts_typsio
npm install
```

### Packaging
```bash
# For Linux/macOS
./scripts/publish.sh

# For Windows
./scripts/publish.ps1
```
This will publish the package to PyPI and npm.