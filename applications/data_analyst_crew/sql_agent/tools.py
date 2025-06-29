import os
import sqlite3
import logging
from typing import Any, Dict

from google.adk.tools import ToolContext
import google.genai.types as types
from tabulate import tabulate
import pandas as pd

logger = logging.getLogger(__name__)



def get_db_schema() -> Dict[str, Any]:
    """Fetch the SQL schema of the database as Markdown text."""
    try:
        db_path = os.getenv("DB_PATH")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, sql FROM sqlite_master 
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name;
            """)
            schema_entries = cursor.fetchall()

        schema_md = "** SQLite Schema\n"
        for table_name, create_sql in schema_entries:
            schema_md += f"\n** Table: {table_name}\n{create_sql};\n"

        return {"status": "success", "schema": schema_md}
    except sqlite3.Error as e:
        logger.exception("Failed to fetch DB schema.")
        return {"status": "error", "error_message": str(e)}


async def execute_sql_query(query: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Execute a SQL query and return results as a Markdown table."""
    logger.info("Executing SQL query:\n%s", query)
    try:
        db_path = os.getenv("DB_PATH")
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            headers = [desc[0] for desc in cursor.description]

        if not rows:
            return {"status": "success", "results": "No results returned."}

        markdown_table = tabulate(rows, headers=headers, tablefmt="github")
        logger.info("Query executed successfully. Results:\n%s", markdown_table)
        # Convert to DataFrame for better formatting
        df = pd.DataFrame(rows, columns=headers)
        artifact_part = types.Part(
            inline_data=types.Blob(
                mime_type="text/csv",
                data=df.to_csv(index=False).encode("utf-8")
            )
        )
        await tool_context.save_artifact("sql_results.csv", artifact_part)
        return {"status": "success", "results": markdown_table}
    except sqlite3.Error as e:
        logger.exception("Query execution failed.")
        return {"status": "error", "error_message": str(e)}
