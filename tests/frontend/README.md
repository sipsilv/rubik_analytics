# Rubik Analytics E2E Tests

End-to-end UI tests for Rubik Analytics using Playwright.

## Prerequisites

1. Node.js (v18 or higher)
2. Backend server running on `http://localhost:8000`
3. Frontend server running on `http://localhost:3000`

## Setup

1. Install dependencies:
```bash
cd tests/frontend
npm install
```

2. Install Playwright browsers:
```bash
npm run install:browsers
```

## Running Tests

### Run all tests
```bash
npm test
```

### Run tests in headed mode (see browser)
```bash
npm run test:headed
```

### Run tests in debug mode
```bash
npm run test:debug
```

### Run tests with UI mode
```bash
npm run test:ui
```

### View test report
```bash
npm run test:report
```

## Test Structure

- `tests/auth.spec.ts` - Authentication tests (login, logout)
- `tests/dashboard.spec.ts` - Dashboard navigation and basic functionality
- `tests/admin-accounts.spec.ts` - Admin account management
- `tests/admin-requests.spec.ts` - Request & Feedback management
- `tests/admin-connections.spec.ts` - Connection management
- `tests/settings.spec.ts` - Settings page tests
- `tests/access-request.spec.ts` - Public access request form
- `tests/helpers/auth.ts` - Authentication helper functions

## Default Test Credentials

- **Username**: `admin`
- **Password**: `admin123`
- **Email**: `admin@rubikview.com`

## Configuration

Tests are configured in `playwright.config.ts`. You can modify:
- Base URLs (frontend and API)
- Browser projects (Chromium, Firefox, WebKit)
- Retry settings
- Timeout values

## Environment Variables

- `FRONTEND_URL` - Frontend server URL (default: `http://localhost:3000`)
- `API_URL` - Backend API URL (default: `http://localhost:8000`)
- `CI` - Set to `true` in CI environments

## Notes

- Tests automatically start the frontend and backend servers if they're not running
- Tests use the default admin user credentials
- Screenshots and videos are captured on test failures
- HTML reports are generated after test runs
