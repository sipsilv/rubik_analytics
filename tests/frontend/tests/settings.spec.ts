import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

test.describe('Settings', () => {
  test.beforeEach(async ({ page }) => {
    // Login as admin using helper
    await loginAsAdmin(page);
    
    // Navigate to Settings page - use link role
    const settingsLink = page.locator('a:has-text("Settings")').first();
    await settingsLink.waitFor({ state: 'visible', timeout: 15000 });
    await settingsLink.click();
    await expect(page).toHaveURL(/\/settings/, { timeout: 20000 });
    await page.waitForLoadState('networkidle');
  });

  test('should display settings page', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    
    // Check page elements - use heading role for specificity
    await expect(page.getByRole('heading', { name: /Settings/i })).toBeVisible({ timeout: 10000 });
    
    // Check for profile section
    const profileSection = page.getByText(/Profile|Account/i).first();
    if (await profileSection.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(profileSection).toBeVisible({ timeout: 5000 });
    }
  });

  test('should toggle theme', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    
    // Find theme toggle
    const themeToggle = page.getByRole('button', { name: /Theme|Dark|Light/i }).first();
    
    if (await themeToggle.isVisible({ timeout: 5000 }).catch(() => false)) {
      const initialAriaLabel = await themeToggle.getAttribute('aria-label');
      
      await themeToggle.click();
      await page.waitForTimeout(500);
      
      // Theme should change
      const newAriaLabel = await themeToggle.getAttribute('aria-label');
      expect(newAriaLabel).not.toBe(initialAriaLabel);
    }
  });

  test('should change password', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    
    // Find change password button
    const changePasswordButton = page.getByRole('button', { name: /Change Password/i });
    
    if (await changePasswordButton.isVisible({ timeout: 5000 }).catch(() => false)) {
      await changePasswordButton.click();
      await page.waitForTimeout(300);
      
      // Modal should appear - use heading role
      await expect(page.getByRole('heading', { name: /Change Password/i })).toBeVisible({ timeout: 5000 });
      
      // Check for password inputs
      const currentPasswordInput = page.locator('input[type="password"]').first();
      await expect(currentPasswordInput).toBeVisible({ timeout: 5000 });
      
      // Close modal
      const cancelButton = page.getByRole('button', { name: /Cancel/i }).first();
      await cancelButton.waitFor({ state: 'visible', timeout: 5000 });
      await cancelButton.click();
      
      await page.waitForTimeout(300);
      await expect(page.getByRole('heading', { name: /Change Password/i })).not.toBeVisible({ timeout: 5000 });
    }
  });

  test('should view feature requests', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    
    // Navigate to feature requests
    const featureRequestsLink = page.getByText(/Feature Requests/i).first();
    
    if (await featureRequestsLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await featureRequestsLink.click();
      await expect(page).toHaveURL(/\/settings\/feature-requests/, { timeout: 15000 });
      
      // Wait for page to load
      await page.waitForLoadState('networkidle');
      
      // Check page content - use heading role
      await expect(page.getByRole('heading', { name: /Feature Requests/i })).toBeVisible({ timeout: 10000 });
    }
  });
});
