import logging
from typing import Type, Any

from google.genai import types as genai_types
from mcp import types as mcp_types
from pydantic import ValidationError, BaseModel

logger = logging.getLogger(__name__)


ALLOWED_GEMINI_SCHEMA_KEYS = {"type", "properties", "required"}

def parse_pydantic_model_schema(data: dict, model_cls: Type[BaseModel]) -> BaseModel | None:
    """
    Attempts to parse a dictionary `data` into a Pydantic model of type `model_cls`.

    - Filters out any keys not defined in the model.
    - Skips keys with `None` values.
    - Returns the constructed model or `None` if validation fails.

    Args:
        data (dict): Input dictionary to be parsed.
        model_cls (Type[BaseModel]): Target Pydantic model class.

    Returns:
        BaseModel | None: The instantiated model, or None if validation failed.
    """
    allowed_keys = model_cls.model_fields.keys()
    filtered_properties = {
        k: v for k, v in data.items()
        if k in allowed_keys and v is not None
    }

    try:
        return model_cls(**filtered_properties)
    except ValidationError as e:
        print(f"Invalid input skipped: {e}")
        return None

def _norm_type(tp: Any) -> str | None:
    """
    Normalizes a JSON Schema 'type' field into a lowercase string.

    Handles:
      - Single type strings (e.g., "Object", "ARRAY").
      - Type arrays with nullable options (e.g., ["object", "null"]).

    Args:
        tp (Any): The type value from schema (string, list, or None).

    Returns:
        str | None: Normalized type name (e.g., "object", "array") or None if not recognized.
    """
    if tp is None:
        return None
    if isinstance(tp, str):
        return tp.lower()
    if isinstance(tp, list):
        # Prioritize the first non-null type
        for t in tp:
            if isinstance(t, str) and t.lower() != "null":
                return t.lower()
    return None


def remove_additional_properties(schema: dict | list | Any) -> dict | list | Any:
    """
    Recursively removes 'additional_properties' from OpenAPI/JSON Schema definitions.

    Handles nested schemas in:
      - objects (via 'properties')
      - arrays (via 'items')
      - compositional keywords ('oneOf', 'anyOf', 'allOf')

    Args:
        schema (dict | list | Any): A schema or schema component.

    Returns:
        dict | list | Any: The cleaned schema with all 'additional_properties' fields removed.
    """
    # Return primitives as-is
    if not isinstance(schema, (dict, list)):
        return schema

    # If the schema is a list (e.g., oneOf/anyOf/allOf), recurse each item
    if isinstance(schema, list):
        return [remove_additional_properties(item) for item in schema]

    # From this point, we assume schema is a dict
    schema.pop("additional_properties", None)

    tp = _norm_type(schema.get("type"))

    # If it's an object, recurse into 'properties'
    if tp == "object":
        props = schema.get("properties")
        if isinstance(props, dict):
            for key, value in props.items():
                props[key] = remove_additional_properties(value)

    # If it's an array, recurse into 'items'
    if tp == "array":
        items = schema.get("items")
        if items is not None:
            schema["items"] = remove_additional_properties(items)

    # Recurse into common composition constructs
    for kw in ("oneOf", "anyOf", "allOf"):
        if kw in schema and isinstance(schema[kw], list):
            schema[kw] = [remove_additional_properties(sub) for sub in schema[kw]]

    return schema

def mcp_tools_to_gemini(mcp_tools: list[mcp_types.Tool]) -> list:
    """
    Converts a list of tool definitions to a format compatible with Gemini function calling.

    Args:
        mcp_tools (mcp_types.ListToolsResult): The MCP tools to convert.

    Returns:
        list[dict]: List of tools formatted for Gemini.
    """
    gemini_tools =  []
    for tool in mcp_tools:
        raw_schema = tool.inputSchema or {}
        # Extract only allowed schema keys
        valid_schema_properties = {k: v for k, v in raw_schema.items() if k in ALLOWED_GEMINI_SCHEMA_KEYS}

        # Skip tools without a valid object-type schema
        if _norm_type(valid_schema_properties.get("type")) != "object":
            logger.warning(f"Tool '{tool.name}' skipped: schema type is not 'object'.")
            continue

        props = valid_schema_properties.get("properties")
        if not isinstance(props, dict):
            logger.warning(f"Tool '{tool.name}' skipped: 'properties' is not a valid dict.")
            continue

        # Parse and filter properties using Pydantic model validation
        parsed_properties = {}
        for prop_name, prop_schema in props.items():
            if not isinstance(prop_schema, dict):
                logger.warning(f"Tool '{tool.name}' property '{prop_name}' skipped: invalid format.")
                continue

            prop_schema_parsed = parse_pydantic_model_schema(prop_schema, genai_types.Schema)
            if prop_schema_parsed:
                parsed_properties[prop_name] = prop_schema_parsed.model_dump()
            else:
                logger.warning(f"Tool '{tool.name}' property '{prop_name}' skipped: schema failed validation.")

        # Replace properties with validated and cleaned ones
        valid_schema_properties["properties"] = parsed_properties

        # Remove invalid properties across the schema
        valid_schema_properties = remove_additional_properties(valid_schema_properties)
        tool_behavior = genai_types.Behavior.BLOCKING  # Default behavior
        if tool.meta:
            tool_behavior = tool.meta.get("behavior", "BLOCKING").upper()
            tool_behavior = genai_types.Behavior.__members__.get(tool_behavior, "BLOCKING")
            #logger.info(f"Tool '{tool.name}' behavior: {tool_behavior}")

        try:
            gemini_tools.append(
                genai_types.Tool(function_declarations=[
                    genai_types.FunctionDeclaration(
                        name=tool.name,
                        description=tool.description or "No description provided.",
                        parameters=valid_schema_properties,
                        behavior=tool_behavior
                    )
                ])
            )
        except Exception as e:
            logger.error(f"Tool '{tool.name}' skipped due to schema error: {e}")
            raise

    return gemini_tools
