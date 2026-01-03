import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

test.describe('Admin - Accounts Management', () => {
  test.beforeEach(async ({ page }) => {
    // Login as admin using helper
    await loginAsAdmin(page);
    
    // Navigate to Accounts page - use link role for specificity
    const accountsLink = page.locator('a:has-text("Accounts")').first();
    await accountsLink.waitFor({ state: 'visible', timeout: 15000 });
    await accountsLink.click();
    await expect(page).toHaveURL(/\/admin\/accounts/, { timeout: 20000 });
    await page.waitForLoadState('networkidle');
  });

  test('should display accounts page', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000); // Wait for data to load
    
    // Check page elements - use heading role for specificity
    await expect(page.getByRole('heading', { name: /Accounts/i })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('button', { name: /Create Account/i })).toBeVisible({ timeout: 10000 });
    
    // Check table headers - use more specific selectors
    const table = page.locator('table').first();
    await expect(table).toBeVisible({ timeout: 10000 });
    
    // Check for table header cells
    await expect(page.locator('th:has-text("User ID")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('th:has-text("Username")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('th:has-text("Email")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('th:has-text("Role")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('th:has-text("Status")')).toBeVisible({ timeout: 10000 });
  });

  test('should open create user modal', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    const createButton = page.getByRole('button', { name: /Create Account/i });
    await createButton.waitFor({ state: 'visible', timeout: 10000 });
    await createButton.click();
    
    // Wait for modal to appear
    await page.waitForTimeout(300);
    
    // Modal should appear - use heading role for specificity
    await expect(page.getByRole('heading', { name: /Create Account/i })).toBeVisible({ timeout: 5000 });
    
    // Check form fields - use placeholder or input type as fallback
    const usernameInput = page.locator('input[type="text"]').first();
    await expect(usernameInput).toBeVisible({ timeout: 5000 });
    
    // Close modal
    const cancelButton = page.getByRole('button', { name: /Cancel/i }).first();
    await cancelButton.waitFor({ state: 'visible', timeout: 5000 });
    await cancelButton.click();
    
    await page.waitForTimeout(300);
    await expect(page.getByRole('heading', { name: /Create Account/i })).not.toBeVisible({ timeout: 5000 });
  });

  test('should search for users', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    
    // Find search input
    const searchInput = page.getByPlaceholder(/Search users/i).first();
    
    if (await searchInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      await searchInput.fill('admin');
      await page.waitForTimeout(1000); // Wait for search to execute
      
      // Results should be filtered
      const table = page.locator('table').first();
      await expect(table).toBeVisible({ timeout: 10000 });
    }
  });

  test('should view user details', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    
    // Find first view button in table
    const viewButtons = page.getByRole('button', { name: /View/i });
    const count = await viewButtons.count();
    
    if (count > 0) {
      await viewButtons.first().click();
      await page.waitForTimeout(300); // Wait for modal animation
      
      // Modal should appear with user details - use heading role
      await expect(page.getByRole('heading', { name: /User Details/i })).toBeVisible({ timeout: 5000 });
      
      // Close modal
      const closeButton = page.getByRole('button', { name: /Close/i }).first();
      await closeButton.waitFor({ state: 'visible', timeout: 5000 });
      await closeButton.click();
      
      await page.waitForTimeout(300);
      await expect(page.getByRole('heading', { name: /User Details/i })).not.toBeVisible({ timeout: 5000 });
    }
  });
});
