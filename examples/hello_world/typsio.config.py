from typsio.gen import TypsioGenConfig

export = TypsioGenConfig(
    source_file="my_app/api_defs.py",
    registry_name="rpc_registry",
    output="./web/generated/api-types.ts",
)