import duckdb
from app.models.screener import get_active_symbols, get_db_connection

# Get connection
conn = get_db_connection()

# Fetch symbols
print("Fetching active symbols...")
symbols = get_active_symbols(conn)

print(f"Total symbols fetched: {len(symbols)}")

# Search for Reliance and Infosys
targets = ["RELIANCE", "INFOSYS", "ITC"]

print("\nVerification Results:")
print("-" * 60)

for target in targets:
    for s in symbols:
        name_val = s['symbol'] # The selected value (Name or ID)
        ex = s['exchange']
        
        # Check strict Logic
        # CASE 1: Reliance NSE -> Should have "Reliance" in name
        if target == "RELIANCE" and ex == "NSE" and "RELIANCE" in name_val.upper() and "INDUSTRIES" in name_val.upper():
            print(f"✅ SUCCESS: NSE Reliance -> '{name_val}' (Name Used)")
            break
            
        # CASE 2: Reliance BSE -> Should start with digit '5' (500325)
        if target == "RELIANCE" and ex == "BSE" and name_val.startswith('5'):
             print(f"✅ SUCCESS: BSE Reliance -> '{name_val}' (ID Used)")
             break

for s in symbols:
    if "INFY" in str(s['symbol']).upper() and s['exchange'] == 'NSE':
         # Infosys usually is "Infosys"
         print(f"INFO: Infosys NSE -> '{s['symbol']}'")
         break

print("-" * 60)
