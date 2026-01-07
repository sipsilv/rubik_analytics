import os
from sqlalchemy import create_engine

# Simulate the string that would come from the bat file
# In bat: set "DATABASE_URL=sqlite:///%PROJECT_ROOT%\data\auth\sqlite\auth.db"
# PROJECT_ROOT is usually C:\Users\jallu\OneDrive\pgp\Python\Stock predictor\rubik-analytics
# So the string is approximately:
test_url = r"sqlite:///C:\Users\jallu\OneDrive\pgp\Python\Stock predictor\rubik-analytics\data\auth\sqlite\auth.db"

print(f"Testing URL: {test_url}")

try:
    engine = create_engine(test_url)
    connection = engine.connect()
    print("Connection successful!")
    connection.close()
except Exception as e:
    print(f"Connection failed: {e}")
    # Try replacing backslashes
    try:
        fixed_url = test_url.replace("\\", "/")
        print(f"Testing Fixed URL: {fixed_url}")
        engine = create_engine(fixed_url)
        connection = engine.connect()
        print("Fixed URL Connection successful!")
        connection.close()
    except Exception as e2:
        print(f"Fixed URL failed too: {e2}")

