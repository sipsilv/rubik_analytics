import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Login first using helper
    await loginAsAdmin(page);
  });

  test('should display dashboard after login', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    // Check sidebar is visible
    await expect(page.getByText('RUBIK')).toBeVisible({ timeout: 10000 });
    
    // Check navigation items - use link role for specificity
    await expect(page.getByRole('link', { name: /Dashboard/i })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('link', { name: /Analytics/i })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('link', { name: /Reports/i })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('link', { name: /Settings/i })).toBeVisible({ timeout: 10000 });
  });

  test('should navigate to different pages', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    // Navigate to Analytics - use link role
    const analyticsLink = page.getByRole('link', { name: /Analytics/i });
    await analyticsLink.waitFor({ state: 'visible', timeout: 10000 });
    await analyticsLink.click();
    await expect(page).toHaveURL(/\/analytics/, { timeout: 15000 });
    
    // Navigate to Reports
    const reportsLink = page.getByRole('link', { name: /Reports/i });
    await reportsLink.waitFor({ state: 'visible', timeout: 10000 });
    await reportsLink.click();
    await expect(page).toHaveURL(/\/reports/, { timeout: 15000 });
    
    // Navigate to Settings
    const settingsLink = page.getByRole('link', { name: /Settings/i });
    await settingsLink.waitFor({ state: 'visible', timeout: 10000 });
    await settingsLink.click();
    await expect(page).toHaveURL(/\/settings/, { timeout: 15000 });
    
    // Navigate back to Dashboard
    const dashboardLink = page.getByRole('link', { name: /Dashboard/i });
    await dashboardLink.waitFor({ state: 'visible', timeout: 10000 });
    await dashboardLink.click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  });

  test('should toggle sidebar', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    // Sidebar should be expanded by default
    const sidebar = page.locator('aside');
    await expect(sidebar).toHaveClass(/w-64/, { timeout: 10000 });
    
    // Find and click toggle button - use fixed position button
    const toggleButton = page.locator('button[aria-label*="Collapse sidebar"], button[aria-label*="Expand sidebar"]').first();
    await toggleButton.waitFor({ state: 'visible', timeout: 10000 });
    await toggleButton.click();
    
    // Wait for transition
    await page.waitForTimeout(400);
    
    // Sidebar should be collapsed
    await expect(sidebar).toHaveClass(/w-16/, { timeout: 5000 });
    
    // Click again to expand
    await toggleButton.click();
    await page.waitForTimeout(400);
    await expect(sidebar).toHaveClass(/w-64/, { timeout: 5000 });
  });

  test('should logout successfully', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    // Click logout button
    const logoutButton = page.locator('button:has-text("Logout")');
    await logoutButton.waitFor({ state: 'visible', timeout: 10000 });
    await logoutButton.click();
    
    // Should redirect to login page
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
    
    // Should not be able to access dashboard without login
    await page.goto('/dashboard', { waitUntil: 'networkidle' });
    await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
  });
});
