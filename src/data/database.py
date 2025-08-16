import duckdb
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class CVRDatabase:
    """
    Manages DuckDB connection and executes SQL scripts for CVR analysis.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to DuckDB file. If None, uses in-memory database.
        """
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        self.sql_dir = Path(__file__).parent.parent.parent / "sql"
        
    def execute_script(self, script_name: str, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Execute a SQL script file with optional parameters.
        
        Args:
            script_name: Name of SQL file (without .sql extension)
            params: Parameters to substitute in SQL script
            
        Returns:
            DataFrame with query results (if any)
        """
        script_path = self.sql_dir / f"{script_name}.sql"
        
        if not script_path.exists():
            raise FileNotFoundError(f"SQL script not found: {script_path}")
            
        with open(script_path, 'r') as f:
            sql = f.read()
            
        # Simple parameter substitution for file paths
        if params:
            if isinstance(params, dict):
                for key, value in params.items():
                    # Properly quote file paths for SQL
                    quoted_value = f"'{str(value)}'" if isinstance(value, (str, Path)) else str(value)
                    sql = sql.replace("?", quoted_value, 1)
            elif isinstance(params, (list, tuple)):
                for value in params:
                    # Properly quote file paths for SQL
                    quoted_value = f"'{str(value)}'" if isinstance(value, (str, Path)) else str(value)
                    sql = sql.replace("?", quoted_value, 1)
            else:
                # Properly quote file paths for SQL
                quoted_value = f"'{str(params)}'" if isinstance(params, (str, Path)) else str(params)
                sql = sql.replace("?", quoted_value, 1)
                
        try:
            result = self.conn.execute(sql).fetchdf()
            logger.info(f"Executed script: {script_name}")
            return result
        except Exception as e:
            logger.error(f"Error executing script {script_name}: {e}")
            raise
            
    def query(self, sql: str) -> pd.DataFrame:
        """Execute a SQL query and return results as DataFrame."""
        return self.conn.execute(sql).fetchdf()
        
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        result = self.conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            [table_name]
        ).fetchone()
        return result[0] > 0
        
    def get_table_info(self, table_name: str) -> pd.DataFrame:
        """Get column information for a table."""
        return self.conn.execute(f"DESCRIBE {table_name}").fetchdf()
        
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()