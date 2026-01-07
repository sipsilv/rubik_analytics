# Rubik Analytics - Documentation

## Overview

**Rubik Analytics** is an enterprise analytics platform with comprehensive user management, role-based access control, and flexible multi-database architecture.

## Quick Start

1. **Start all services:**
   ```batch
   server\windows\start-all.bat
   ```

2. **Default login:**
   - Username: ``
   - Password: ``

3. **Access:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

For detailed setup instructions, see [QUICK-START.md](./QUICK-START.md).

## Documentation

### Core Documentation

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System architecture, authentication, database design, and technology choices
- **[PROJECT-STRUCTURE.md](./PROJECT-STRUCTURE.md)** - Directory structure, organization rules, and conventions
- **[QUICK-START.md](./QUICK-START.md)** - Setup, deployment, and batch scripts guide
- **[TROUBLESHOOTING.md](./TROUBLESHOOTING.md)** - Common issues and solutions

## Tech Stack

### Backend
- FastAPI 0.109.0
- SQLAlchemy 2.0
- SQLite / DuckDB / PostgreSQL
- JWT Authentication

### Frontend
- Next.js 14.2.5
- React 18.3.1
- TypeScript 5.5.3
- Tailwind CSS 3.4.4

## Project Status

**Version:** 1.0.0  
**Status:** Production Ready

---

For detailed information, see the documentation files listed above.
