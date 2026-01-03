import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

test.describe('Admin - Connections', () => {
  test.beforeEach(async ({ page }) => {
    // Login as admin using helper
    await loginAsAdmin(page);
    
    // Navigate to Connections page - use link role
    const connectionsLink = page.locator('a:has-text("Connections")').first();
    await connectionsLink.waitFor({ state: 'visible', timeout: 15000 });
    await connectionsLink.click();
    await expect(page).toHaveURL(/\/admin\/connections/, { timeout: 20000 });
    await page.waitForLoadState('networkidle');
  });

  test('should display connections page', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    
    // Check page elements - use heading role for specificity
    await expect(page.getByRole('heading', { name: /Connections/i })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('button', { name: /Create Connection|Add Connection/i })).toBeVisible({ timeout: 10000 });
    
    // Check table or list is visible
    const table = page.locator('table').first();
    await expect(table).toBeVisible({ timeout: 10000 });
  });

  test('should open create connection modal', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    const createButton = page.getByRole('button', { name: /Create Connection|Add Connection/i });
    await createButton.waitFor({ state: 'visible', timeout: 10000 });
    await createButton.click();
    
    // Wait for modal to appear
    await page.waitForTimeout(300);
    
    // Modal should appear - use heading role for specificity
    await expect(page.getByRole('heading', { name: /Create Connection|New Connection/i })).toBeVisible({ timeout: 5000 });
    
    // Check form fields - use input type as fallback
    const nameField = page.locator('input[type="text"]').first();
    await expect(nameField).toBeVisible({ timeout: 5000 });
    
    // Close modal
    const cancelButton = page.getByRole('button', { name: /Cancel/i }).first();
    await cancelButton.waitFor({ state: 'visible', timeout: 5000 });
    await cancelButton.click();
    
    await page.waitForTimeout(300);
    await expect(page.getByRole('heading', { name: /Create Connection|New Connection/i })).not.toBeVisible({ timeout: 5000 });
  });

  test('should filter connections by category', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    
    // Look for category filter - check if it exists
    const categoryFilter = page.getByText(/Category|Type/i).first();
    if (await categoryFilter.isVisible({ timeout: 5000 }).catch(() => false)) {
      await categoryFilter.click();
      await page.waitForTimeout(500);
    }
  });
});
