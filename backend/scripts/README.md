# Backend Scripts

This directory contains all backend utility scripts organized by purpose.

## Structure

```
scripts/
├── init/                    # Initialization scripts
│   └── init_auth_database.py      # Initialize auth database and tables
│
├── migrations/              # Schema migration scripts
│   ├── migrate_core_schema.py     # Core user schema migration
│   └── migrate_accounts_schema.py # Accounts schema migration
│
└── maintenance/             # Maintenance scripts
    └── run_system_maintenance.py  # System maintenance utilities
```

## Initialization Scripts

### `init/init_auth_database.py`
Initializes the authentication database:
- Creates all database tables
- Ensures default admin user exists
- Activates and normalizes super_admin users

**Usage:**
```bash
python scripts/init/init_auth_database.py
```

## Migration Scripts

All migration scripts are idempotent and safe to run multiple times.

### `migrations/migrate_core_schema.py`
Migrates core user table schema:
- Adds `user_id`, `name`, `theme_preference`, `last_active_at` columns
- Backfills UUIDs for `user_id`

### `migrations/migrate_accounts_schema.py`
Migrates accounts system:
- Creates `audit_logs` table
- Adds `account_status` column to users

## Maintenance Scripts

### `maintenance/run_system_maintenance.py`
System maintenance and diagnostic utilities.

**Usage:**
```bash
# Diagnose all users
python scripts/maintenance/run_system_maintenance.py users

# Diagnose super admin users
python scripts/maintenance/run_system_maintenance.py super-users

# Check database status
python scripts/maintenance/run_system_maintenance.py db

# Fix stuck uploads
python scripts/maintenance/run_system_maintenance.py fix-uploads
```

## Notes

- All scripts are designed to be safe and idempotent
- No one-time fix/repair scripts remain in the codebase
- All scripts use proper path resolution for imports
- Scripts are organized by responsibility (init, migrations, maintenance)

