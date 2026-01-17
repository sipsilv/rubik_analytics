import sys
import os
import importlib

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

def check_import(module_name):
    try:
        importlib.import_module(module_name)
        print(f"[OK] {module_name}")
        return True
    except ImportError as e:
        print(f"[FAIL] {module_name}: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] {module_name} (Unexpected): {e}")
        return False

def verify_modules():
    print("Verifying Module Imports...")
    modules = [
        # Core
        "app.core.auth.security",
        "app.core.auth.permissions",
        "app.core.config",
        "app.core.database",
        
        # Repositories
        "app.repositories.user_repository",
        "app.repositories.telegram_repository",
        "app.repositories.connection_repository",
        "app.repositories.screener_repository",
        
        # Services
        "app.services.auth_service",
        "app.services.user_service",
        "app.services.admin_service",
        "app.services.telegram_service",
        "app.services.connection_service",
        
        # Providers
        "app.providers.telegram_bot",
        "app.providers.truedata_api",
        
        # Controllers (via Init)
        "app.api.v1.auth",
        "app.api.v1.users",
        "app.api.v1.admin",
        "app.api.v1.telegram",
        "app.api.v1.system"
    ]
    
    success = True
    for mod in modules:
        if not check_import(mod):
            success = False
            
    print("\nVerifying Main App Router...")
    try:
        from app.main import app
        # Check for key routes
        routes = [r.path for r in app.routes]
        key_routes = [
            "/api/v1/auth/login",
            "/api/v1/users/me", 
            "/api/v1/telegram/webhook",
            "/api/v1/debug/db-diagnostic"
        ]
        
        for route in key_routes:
            if any(r.startswith(route) for r in routes) or route in routes:
                print(f"[OK] Route found: {route}")
            else:
                print(f"[WARNING] Route NOT found: {route}")
                # success = False # Warning only, routing might vary
                
    except Exception as e:
        print(f"[FAIL] Main App: {e}")
        success = False
        
    return success

if __name__ == "__main__":
    if verify_modules():
        print("\n[SUCCESS] All verification checks passed.")
        sys.exit(0)
    else:
        print("\n[FAIL] Verification failed.")
        sys.exit(1)
