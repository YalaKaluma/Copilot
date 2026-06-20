from typing import Any

import pandas as pd

from models.copilot.base import ToolProperty, ToolPropertyItem
from services.python_repl import get_session_data_dir


def write_local_code_execution_dataset(
    session_id: str,
    file_name: str,
    df: pd.DataFrame,
) -> str:
    data_dir = get_session_data_dir(session_id)
    normalized_file_name = (
        file_name if file_name.endswith(".csv") else f"{file_name}.csv"
    )
    file_path = data_dir / normalized_file_name
    df.to_csv(file_path, index=False)
    return file_path.as_posix()


def date_property(description: str, nullable: bool = False) -> ToolProperty:
    """Create a date property (ISO format string)."""
    return ToolProperty(
        type="string",
        description=f"{description} (ISO format: YYYY-MM-DD)",
        nullable=nullable,
    )


def string_property(
    description: str,
    enum_vals: list[str] | None = None,
    nullable: bool = False,
) -> ToolProperty:
    """Create a string property."""
    return ToolProperty(
        type="string",
        description=description,
        enum=enum_vals,
        nullable=nullable,
    )


def number_property(description: str, nullable: bool = False) -> ToolProperty:
    """Create a number property."""
    return ToolProperty(type="number", description=description, nullable=nullable)


def integer_property(description: str, nullable: bool = False) -> ToolProperty:
    """Create an integer property."""
    return ToolProperty(type="integer", description=description, nullable=nullable)


def boolean_property(description: str, nullable: bool = False) -> ToolProperty:
    """Create a boolean property."""
    return ToolProperty(type="boolean", description=description, nullable=nullable)


def array_property(
    description: str,
    item_type: str = "string",
    enum_vals: list[str] | None = None,
    nullable: bool = False,
) -> ToolProperty:
    """Create an array/list property."""
    return ToolProperty(
        type="array",
        description=description,
        items=ToolPropertyItem(
            type=item_type, enum=enum_vals if item_type == "string" else None
        ),
        nullable=nullable,
    )


def parse_list_param(value: Any) -> list[str] | None:
    """Parse a list parameter from string or list."""
    if value is None:
        return None
    if isinstance(value, list):
        return list(map(str, value))
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return None
