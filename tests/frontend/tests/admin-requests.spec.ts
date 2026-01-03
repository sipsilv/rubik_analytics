import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

test.describe('Admin - Request & Feedback', () => {
  test.beforeEach(async ({ page }) => {
    // Login as admin using helper
    await loginAsAdmin(page);
    
    // Navigate to Request & Feedback page - use link role
    const requestsLink = page.locator('a:has-text("Request & Feedback")').first();
    await requestsLink.waitFor({ state: 'visible', timeout: 15000 });
    await requestsLink.click();
    await expect(page).toHaveURL(/\/admin\/requests/, { timeout: 20000 });
    await page.waitForLoadState('networkidle');
  });

  test('should display requests page', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    // Check page elements - use heading role for specificity
    await expect(page.getByRole('heading', { name: /Access Requests/i })).toBeVisible({ timeout: 10000 });
    
    // Check for filter/status options - use button role
    const pendingButton = page.getByRole('button', { name: /Pending/i });
    await expect(pendingButton).toBeVisible({ timeout: 10000 });
  });

  test('should filter requests by status', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    
    // Find and click status filter buttons
    const approvedButton = page.getByRole('button', { name: /Approved/i });
    await approvedButton.waitFor({ state: 'visible', timeout: 10000 });
    await approvedButton.click();
    await page.waitForTimeout(500);
    
    const rejectedButton = page.getByRole('button', { name: /Rejected/i });
    await rejectedButton.waitFor({ state: 'visible', timeout: 10000 });
    await rejectedButton.click();
    await page.waitForTimeout(500);
    
    // Click All to reset
    const allButton = page.getByRole('button', { name: /^All$/i });
    await allButton.waitFor({ state: 'visible', timeout: 10000 });
    await allButton.click();
    await page.waitForTimeout(500);
  });

  test('should view request details', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000); // Wait for data to load
    
    // Find approve/reject buttons (these are the action buttons for pending requests)
    const approveButtons = page.getByRole('button', { name: /Approve/i });
    const count = await approveButtons.count();
    
    if (count > 0) {
      // If there are pending requests, we can test the approve/reject flow
      // But for viewing details, we'll just verify the table is visible
      const table = page.locator('table').first();
      await expect(table).toBeVisible({ timeout: 10000 });
      
      // Verify table has data
      const tableRows = page.locator('tbody tr');
      const rowCount = await tableRows.count();
      expect(rowCount).toBeGreaterThan(0);
    } else {
      // If no pending requests, just verify the page structure
      await expect(page.getByRole('heading', { name: /Access Requests/i })).toBeVisible();
    }
  });
});
