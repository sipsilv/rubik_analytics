"""
Script to consolidate multiple symbol databases into a single database.
Checks all symbol databases, merges data, and removes duplicates.
"""

import os
import duckdb
import sqlite3
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
import shutil

# Root data directory
ROOT_DATA = Path(r"C:/Users/jallu/OneDrive/pgp/Python/Stock predictor/rubik-analytics/data")

# Primary database (the one the code uses)
PRIMARY_DB = ROOT_DATA / "analytics" / "duckdb" / "symbols.duckdb"

# All symbol database locations to check
SYMBOL_DBS = [
    ROOT_DATA / "analytics" / "duckdb" / "symbols.duckdb",  # Primary (used by code)
    ROOT_DATA / "symbols" / "symbols.duckdb",
    ROOT_DATA / "symbols" / "symbols.db",
    ROOT_DATA / "analytics" / "symbols" / "symbols.duckdb",
    ROOT_DATA.parent / "backend" / "data" / "analytics" / "duckdb" / "symbols.duckdb",
    ROOT_DATA.parent / "backend" / "data" / "symbols" / "symbols.duckdb",
    ROOT_DATA.parent / "backend" / "data" / "symbols" / "symbols.db",
    ROOT_DATA.parent / "backend" / "data" / "analytics" / "symbols" / "symbols.duckdb",
]

def get_table_info_duckdb(db_path: Path) -> Dict:
    """Get information about tables and row counts in a DuckDB database"""
    if not db_path.exists():
        return {"exists": False, "tables": {}, "total_rows": 0, "size": 0}
    
    try:
        conn = duckdb.connect(str(db_path), config={'allow_unsigned_extensions': True})
        tables = {}
        total_rows = 0
        
        # Get all tables
        result = conn.execute("SHOW TABLES").fetchall()
        for table_row in result:
            table_name = table_row[0]
            try:
                count_result = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
                row_count = count_result[0] if count_result else 0
                tables[table_name] = row_count
                total_rows += row_count
            except Exception as e:
                tables[table_name] = f"Error: {str(e)}"
        
        conn.close()
        size = db_path.stat().st_size
        
        return {
            "exists": True,
            "tables": tables,
            "total_rows": total_rows,
            "size": size
        }
    except Exception as e:
        return {"exists": True, "error": str(e), "tables": {}, "total_rows": 0, "size": db_path.stat().st_size if db_path.exists() else 0}

def get_table_info_sqlite(db_path: Path) -> Dict:
    """Get information about tables and row counts in a SQLite database"""
    if not db_path.exists():
        return {"exists": False, "tables": {}, "total_rows": 0, "size": 0}
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        tables = {}
        total_rows = 0
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [row[0] for row in cursor.fetchall()]
        
        for table_name in table_names:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                tables[table_name] = row_count
                total_rows += row_count
            except Exception as e:
                tables[table_name] = f"Error: {str(e)}"
        
        conn.close()
        size = db_path.stat().st_size
        
        return {
            "exists": True,
            "tables": tables,
            "total_rows": total_rows,
            "size": size
        }
    except Exception as e:
        return {"exists": True, "error": str(e), "tables": {}, "total_rows": 0, "size": db_path.stat().st_size if db_path.exists() else 0}

def check_all_databases():
    """Check all symbol databases and report their status"""
    print("=" * 80)
    print("CHECKING ALL SYMBOL DATABASES")
    print("=" * 80)
    print()
    
    db_info = {}
    
    for db_path in SYMBOL_DBS:
        print(f"Checking: {db_path}")
        print(f"  Exists: {db_path.exists()}")
        
        if db_path.exists():
            if db_path.suffix == ".duckdb":
                info = get_table_info_duckdb(db_path)
            elif db_path.suffix == ".db":
                info = get_table_info_sqlite(db_path)
            else:
                info = {"exists": True, "error": "Unknown database type", "tables": {}, "total_rows": 0, "size": db_path.stat().st_size}
            
            db_info[str(db_path)] = info
            
            if "error" in info:
                print(f"  ERROR: {info['error']}")
            else:
                print(f"  Size: {info['size']:,} bytes ({info['size'] / 1024 / 1024:.2f} MB)")
                print(f"  Total Rows: {info['total_rows']:,}")
                print(f"  Tables: {len(info['tables'])}")
                for table_name, row_count in info['tables'].items():
                    print(f"    - {table_name}: {row_count:,} rows")
        else:
            print(f"  (File does not exist)")
        
        print()
    
    return db_info

def merge_duckdb_data(source_path: Path, target_path: Path):
    """Merge data from source DuckDB to target DuckDB"""
    print(f"Merging data from {source_path} to {target_path}")
    
    # Ensure target exists
    if not target_path.exists():
        # Create parent directory
        target_path.parent.mkdir(parents=True, exist_ok=True)
        # Create empty database
        conn = duckdb.connect(str(target_path))
        conn.close()
    
    source_conn = duckdb.connect(str(source_path))
    target_conn = duckdb.connect(str(target_path))
    
    try:
        # Get all tables from source
        tables = source_conn.execute("SHOW TABLES").fetchall()
        
        for table_row in tables:
            table_name = table_row[0]
            print(f"  Processing table: {table_name}")
            
            try:
                # Get table schema from source
                schema_result = source_conn.execute(f"DESCRIBE {table_name}").fetchall()
                
                # Check if table exists in target
                target_tables = [row[0] for row in target_conn.execute("SHOW TABLES").fetchall()]
                
                if table_name not in target_tables:
                    # Create table in target with same schema
                    # Get CREATE TABLE statement
                    create_sql = source_conn.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'").fetchone()
                    if not create_sql:
                        # DuckDB doesn't have sqlite_master, so we'll create based on schema
                        columns = []
                        for col in schema_result:
                            col_name = col[0]
                            col_type = col[1]
                            nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                            columns.append(f"{col_name} {col_type} {nullable}")
                        
                        create_sql = f"CREATE TABLE {table_name} ({', '.join(columns)})"
                        target_conn.execute(create_sql)
                
                # Get row count before
                before_count = target_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0] if table_name in target_tables else 0
                
                # Insert data (using INSERT OR IGNORE to avoid duplicates)
                # First, let's get the data
                data = source_conn.execute(f"SELECT * FROM {table_name}").fetchdf()
                
                if len(data) > 0:
                    # Insert with conflict handling
                    # For DuckDB, we'll use INSERT OR IGNORE equivalent
                    # Check if there's a unique constraint
                    try:
                        target_conn.execute(f"INSERT INTO {table_name} SELECT * FROM read_parquet('{source_path}') WHERE table_name = '{table_name}'")
                    except:
                        # Fallback: insert directly
                        target_conn.execute(f"INSERT INTO {table_name} SELECT * FROM (SELECT * FROM read_csv_auto('{source_path}'))")
                    
                    # Better approach: use pandas DataFrame
                    target_conn.execute(f"INSERT OR IGNORE INTO {table_name} SELECT * FROM source_conn.execute('SELECT * FROM {table_name}').fetchdf()")
                    
                    # Actually, let's use a simpler approach
                    for _, row in data.iterrows():
                        try:
                            # Convert row to INSERT statement
                            values = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) if v is not None else "NULL" for v in row.values])
                            target_conn.execute(f"INSERT OR IGNORE INTO {table_name} VALUES ({values})")
                        except:
                            pass  # Skip duplicates
                
                after_count = target_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                added = after_count - before_count
                print(f"    Added {added:,} rows (total: {after_count:,})")
                
            except Exception as e:
                print(f"    ERROR processing {table_name}: {str(e)}")
        
        target_conn.commit()
        
    finally:
        source_conn.close()
        target_conn.close()

def consolidate_databases(db_info: Dict):
    """Consolidate all symbol databases into the primary one"""
    print("=" * 80)
    print("CONSOLIDATING DATABASES")
    print("=" * 80)
    print()
    
    # Ensure primary database directory exists
    PRIMARY_DB.parent.mkdir(parents=True, exist_ok=True)
    
    # If primary doesn't exist, find the database with most data
    if not PRIMARY_DB.exists():
        print("Primary database doesn't exist. Finding database with most data...")
        max_rows = 0
        best_db = None
        
        for db_path_str, info in db_info.items():
            if info.get("exists") and not info.get("error") and info.get("total_rows", 0) > max_rows:
                max_rows = info["total_rows"]
                best_db = Path(db_path_str)
        
        if best_db:
            print(f"Using {best_db} as primary (has {max_rows:,} rows)")
            # Copy to primary location
            shutil.copy2(best_db, PRIMARY_DB)
            print(f"Copied to {PRIMARY_DB}")
        else:
            print("No existing database found. Creating new primary database...")
            # Create empty database
            conn = duckdb.connect(str(PRIMARY_DB), config={'allow_unsigned_extensions': True})
            conn.execute("""
                CREATE TABLE IF NOT EXISTS symbols (
                    id INTEGER PRIMARY KEY,
                    exchange VARCHAR NOT NULL,
                    trading_symbol VARCHAR NOT NULL,
                    exchange_token VARCHAR,
                    name VARCHAR,
                    instrument_type VARCHAR,
                    segment VARCHAR,
                    series VARCHAR,
                    isin VARCHAR,
                    expiry_date DATE,
                    strike_price DOUBLE,
                    lot_size INTEGER,
                    status VARCHAR DEFAULT 'ACTIVE',
                    source VARCHAR DEFAULT 'MANUAL',
                    created_at TIMESTAMP WITH TIME ZONE,
                    updated_at TIMESTAMP WITH TIME ZONE,
                    last_updated_at TIMESTAMP WITH TIME ZONE,
                    UNIQUE(exchange, trading_symbol)
                )
            """)
            conn.close()
    
    # Now merge data from all other databases
    print()
    print("Merging data from other databases...")
    
    for db_path in SYMBOL_DBS:
        if db_path == PRIMARY_DB:
            continue
        
        if not db_path.exists():
            continue
        
        print()
        print(f"Processing: {db_path}")
        
        try:
            if db_path.suffix == ".duckdb":
                # For DuckDB, merge using pandas DataFrames
                target_conn = duckdb.connect(str(PRIMARY_DB), config={'allow_unsigned_extensions': True})
                source_conn = duckdb.connect(str(db_path))
                
                # Get tables from source
                source_tables = [row[0] for row in source_conn.execute("SHOW TABLES").fetchall()]
                
                for table_name in source_tables:
                    try:
                        # Get data from source
                        source_data = source_conn.execute(f"SELECT * FROM {table_name}").fetchdf()
                        
                        if len(source_data) == 0:
                            print(f"    {table_name}: Empty table, skipping")
                            continue
                        
                        # Check if table exists in target
                        target_tables = [row[0] for row in target_conn.execute("SHOW TABLES").fetchall()]
                        before_count = 0
                        
                        if table_name not in target_tables:
                            # Create table from source data structure
                            print(f"    {table_name}: Creating table...")
                            # Register source data temporarily
                            target_conn.register('temp_create', source_data)
                            # Create table with schema from source
                            target_conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM temp_create LIMIT 0")
                            target_conn.unregister('temp_create')
                        else:
                            before_count = target_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                        
                        # Register source data as temporary table
                        target_conn.register('temp_source', source_data)
                        
                        # Get column names
                        cols = list(source_data.columns)
                        
                        # Try to insert with duplicate handling
                        # For tables with unique constraints, use NOT EXISTS
                        try:
                            # Check if table has unique constraint (common for symbols table)
                            if 'exchange' in cols and 'trading_symbol' in cols:
                                # Use unique key matching
                                target_conn.execute(f"""
                                    INSERT INTO {table_name} 
                                    SELECT * FROM temp_source
                                    WHERE NOT EXISTS (
                                        SELECT 1 FROM {table_name} t
                                        WHERE t.exchange = temp_source.exchange 
                                        AND t.trading_symbol = temp_source.trading_symbol
                                    )
                                """)
                            else:
                                # For other tables, try to find a unique identifier
                                # Use all columns for matching (simple approach)
                                if 'id' in cols:
                                    target_conn.execute(f"""
                                        INSERT INTO {table_name} 
                                        SELECT * FROM temp_source
                                        WHERE NOT EXISTS (
                                            SELECT 1 FROM {table_name} t
                                            WHERE t.id = temp_source.id
                                        )
                                    """)
                                else:
                                    # No unique key, try direct insert (may fail on duplicates)
                                    target_conn.execute(f"INSERT INTO {table_name} SELECT * FROM temp_source")
                            
                            after_count = target_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                            added = after_count - before_count
                            print(f"    {table_name}: Added {added:,} rows (total: {after_count:,})")
                        except Exception as e:
                            # If NOT EXISTS fails, try direct insert
                            try:
                                target_conn.execute(f"INSERT INTO {table_name} SELECT * FROM temp_source")
                                after_count = target_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                                added = after_count - before_count
                                print(f"    {table_name}: Added {added:,} rows (total: {after_count:,})")
                            except Exception as e2:
                                print(f"    {table_name}: Warning - Could not insert all rows: {str(e2)}")
                                # Try row by row as last resort
                                try:
                                    for _, row in source_data.iterrows():
                                        try:
                                            # Convert row to dict and insert
                                            row_dict = row.to_dict()
                                            cols_str = ', '.join(cols)
                                            vals = []
                                            for col in cols:
                                                val = row_dict[col]
                                                if pd.isna(val):
                                                    vals.append('NULL')
                                                elif isinstance(val, str):
                                                    vals.append(f"'{val.replace(chr(39), chr(39)+chr(39))}'")
                                                else:
                                                    vals.append(str(val))
                                            vals_str = ', '.join(vals)
                                            target_conn.execute(f"INSERT INTO {table_name} ({cols_str}) VALUES ({vals_str})")
                                        except:
                                            pass  # Skip duplicates/errors
                                    after_count = target_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                                    added = after_count - before_count
                                    print(f"    {table_name}: Added {added:,} rows using row-by-row (total: {after_count:,})")
                                except:
                                    print(f"    {table_name}: Failed to merge data")
                        
                        target_conn.unregister('temp_source')
                    
                    except Exception as e:
                        print(f"    Error processing {table_name}: {str(e)}")
                
                source_conn.close()
                target_conn.close()
                
            elif db_path.suffix == ".db":
                # SQLite database - read and insert into DuckDB
                print(f"    Converting SQLite to DuckDB format...")
                try:
                    sqlite_conn = sqlite3.connect(str(db_path))
                except sqlite3.DatabaseError as e:
                    print(f"    [SKIP] Invalid SQLite database: {str(e)}")
                    continue
                cursor = sqlite_conn.cursor()
                
                tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                
                duckdb_conn = duckdb.connect(str(PRIMARY_DB), config={'allow_unsigned_extensions': True})
                
                for table_name in tables:
                    try:
                        # Read from SQLite
                        cursor.execute(f"SELECT * FROM {table_name}")
                        columns = [desc[0] for desc in cursor.description]
                        rows = cursor.fetchall()
                        
                        if len(rows) > 0:
                            # Convert to DataFrame and insert
                            df = pd.DataFrame(rows, columns=columns)
                            
                            # Check if table exists
                            target_tables = [row[0] for row in duckdb_conn.execute("SHOW TABLES").fetchall()]
                            if table_name not in target_tables:
                                # Create table
                                duckdb_conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df LIMIT 0")
                                duckdb_conn.execute(f"DROP TABLE {table_name}")
                            
                            # Insert
                            duckdb_conn.register('temp_df', df)
                            try:
                                duckdb_conn.execute(f"INSERT INTO {table_name} SELECT * FROM temp_df")
                                count = duckdb_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
                                print(f"    {table_name}: {len(rows):,} rows inserted, total: {count:,}")
                            except Exception as e:
                                print(f"    Warning inserting into {table_name}: {str(e)}")
                            finally:
                                duckdb_conn.unregister('temp_df')
                    
                    except Exception as e:
                        print(f"    Error processing {table_name}: {str(e)}")
                
                sqlite_conn.close()
                duckdb_conn.close()
        
        except Exception as e:
            print(f"  ERROR: {str(e)}")
    
    print()
    print("Consolidation complete!")

def remove_duplicate_databases():
    """Remove duplicate databases after consolidation"""
    print("=" * 80)
    print("REMOVING DUPLICATE DATABASES")
    print("=" * 80)
    print()
    
    removed = []
    
    for db_path in SYMBOL_DBS:
        if db_path == PRIMARY_DB:
            continue
        
        if db_path.exists():
            print(f"Removing: {db_path}")
            # Check if file is locked
            import time
            max_retries = 3
            removed_file = False
            for attempt in range(max_retries):
                try:
                    db_path.unlink()
                    removed.append(str(db_path))
                    print(f"  [OK] Removed")
                    removed_file = True
                    break
                except PermissionError:
                    if attempt < max_retries - 1:
                        print(f"  [WAIT] File locked, retrying in 1 second...")
                        time.sleep(1)
                    else:
                        print(f"  [SKIP] File is locked (may be in use). Please close any applications using it and remove manually.")
                except Exception as e:
                    print(f"  [ERROR] Error removing: {str(e)}")
                    break
    
    print()
    print(f"Removed {len(removed)} duplicate database(s)")
    
    return removed

def check_other_databases():
    """Check for other duplicate databases"""
    print("=" * 80)
    print("CHECKING FOR OTHER DUPLICATE DATABASES")
    print("=" * 80)
    print()
    
    # Check analytics databases
    analytics_dbs = [
        ("ohlcv.duckdb", ROOT_DATA / "analytics" / "duckdb" / "ohlcv.duckdb"),
        ("indicators.duckdb", ROOT_DATA / "analytics" / "duckdb" / "indicators.duckdb"),
        ("signals.duckdb", ROOT_DATA / "analytics" / "duckdb" / "signals.duckdb"),
        ("jobs.duckdb", ROOT_DATA / "analytics" / "duckdb" / "jobs.duckdb"),
    ]
    
    backend_data = ROOT_DATA.parent / "backend" / "data"
    
    duplicates_found = []
    
    for db_name, primary_path in analytics_dbs:
        backend_path = backend_data / "analytics" / "duckdb" / db_name
        
        if backend_path.exists() and primary_path.exists():
            primary_size = primary_path.stat().st_size
            backend_size = backend_path.stat().st_size
            
            print(f"{db_name}:")
            print(f"  Primary: {primary_path} ({primary_size:,} bytes)")
            print(f"  Duplicate: {backend_path} ({backend_size:,} bytes)")
            
            if backend_size == primary_size:
                print(f"  -> Same size, likely duplicate")
                duplicates_found.append(backend_path)
            else:
                print(f"  -> Different sizes, may have different data")
        
        print()
    
    # Check auth database
    auth_primary = ROOT_DATA / "auth" / "sqlite" / "auth.db"
    auth_backend = backend_data / "auth" / "sqlite" / "auth.db"
    
    if auth_backend.exists() and auth_primary.exists():
        primary_size = auth_primary.stat().st_size
        backend_size = auth_backend.stat().st_size
        
        print(f"auth.db:")
        print(f"  Primary: {auth_primary} ({primary_size:,} bytes)")
        print(f"  Duplicate: {auth_backend} ({backend_size:,} bytes)")
        
        if backend_size == primary_size:
            print(f"  -> Same size, likely duplicate")
            duplicates_found.append(auth_backend)
        else:
            print(f"  -> Different sizes, may have different data")
    
    print()
    return duplicates_found

def main():
    print("=" * 80)
    print("SYMBOL DATABASE CONSOLIDATION SCRIPT")
    print("=" * 80)
    print()
    
    # Step 1: Check all databases
    db_info = check_all_databases()
    
    # Step 2: Consolidate
    print("\nProceeding with consolidation...")
    consolidate_databases(db_info)
    
    # Step 3: Verify primary database
    print()
    print("=" * 80)
    print("VERIFYING PRIMARY DATABASE")
    print("=" * 80)
    print()
    primary_info = get_table_info_duckdb(PRIMARY_DB)
    if primary_info.get("exists"):
        print(f"Primary database: {PRIMARY_DB}")
        print(f"Size: {primary_info['size']:,} bytes ({primary_info['size'] / 1024 / 1024:.2f} MB)")
        print(f"Total Rows: {primary_info['total_rows']:,}")
        print(f"Tables: {len(primary_info['tables'])}")
        for table_name, row_count in primary_info['tables'].items():
            print(f"  - {table_name}: {row_count:,} rows")
    
    # Step 4: Remove duplicates
    print()
    print("Removing duplicate databases...")
    removed = remove_duplicate_databases()
    
    # Step 5: Check other databases
    print()
    duplicates = check_other_databases()
    
    if duplicates:
        print(f"\nFound {len(duplicates)} other duplicate database(s) in backend/data/")
        print("These can be removed if the primary databases are working correctly.")
    
    print()
    print("=" * 80)
    print("CONSOLIDATION COMPLETE!")
    print("=" * 80)
    print(f"\nPrimary symbol database: {PRIMARY_DB}")
    print(f"Removed {len(removed)} duplicate symbol database(s)")

if __name__ == "__main__":
    main()

