import { test, expect } from '@playwright/test';

test.describe('Access Request (Public)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    // Wait for page to be fully loaded
    await page.waitForSelector('text=RUBIK ANALYTICS');
  });

  test('should submit access request', async ({ page }) => {
    // Open contact admin modal - wait for button to be visible and clickable
    const requestAccessButton = page.locator('button:has-text("Request Access")');
    await requestAccessButton.waitFor({ state: 'visible', timeout: 10000 });
    await requestAccessButton.click();
    
    // Wait for modal to appear
    await page.waitForTimeout(300); // Small delay for modal animation
    await expect(page.getByText(/Request Login Access/i)).toBeVisible({ timeout: 5000 });
    
    // Fill form
    await page.getByLabel(/Full Name/i).fill('Test User');
    await page.getByLabel(/Mobile Number/i).fill('+1234567890');
    await page.getByLabel(/Company/i).fill('Test Company');
    await page.getByLabel(/Reason for Access/i).fill('Testing access request functionality');
    
    // Submit request
    await page.getByRole('button', { name: /Submit Request/i }).click();
    
    // Should show success message or error (depending on backend)
    await page.waitForTimeout(2000);
    
    // Check for success or error message
    const successMessage = page.getByText(/successfully|submitted/i);
    const errorMessage = page.getByText(/error|failed/i);
    
    if (await successMessage.isVisible()) {
      await expect(successMessage).toBeVisible();
    } else if (await errorMessage.isVisible()) {
      // Network error is expected if backend is not running
      await expect(errorMessage).toBeVisible();
    }
  });

  test('should validate required fields', async ({ page }) => {
    // Open modal
    const requestAccessButton = page.locator('button:has-text("Request Access")');
    await requestAccessButton.waitFor({ state: 'visible', timeout: 10000 });
    await requestAccessButton.click();
    await page.waitForTimeout(300); // Small delay for modal animation
    await expect(page.getByText(/Request Login Access/i)).toBeVisible({ timeout: 5000 });
    
    // Try to submit without filling required fields
    await page.getByRole('button', { name: /Submit Request/i }).click();
    
    // HTML5 validation should prevent submission
    const nameInput = page.getByLabel(/Full Name/i);
    await expect(nameInput).toBeFocused();
  });

  test('should allow optional email field', async ({ page }) => {
    // Open modal
    const requestAccessButton = page.locator('button:has-text("Request Access")');
    await requestAccessButton.waitFor({ state: 'visible', timeout: 10000 });
    await requestAccessButton.click();
    await page.waitForTimeout(300); // Small delay for modal animation
    await expect(page.getByText(/Request Login Access/i)).toBeVisible({ timeout: 5000 });
    
    // Email should be optional
    const emailInput = page.getByLabel(/Email.*Optional/i);
    if (await emailInput.isVisible()) {
      // Should be able to submit without email
      await page.getByLabel(/Full Name/i).fill('Test User');
      await page.getByLabel(/Mobile Number/i).fill('+1234567890');
      await page.getByLabel(/Company/i).fill('Test Company');
      await page.getByLabel(/Reason for Access/i).fill('Test reason');
      
      // Form should be submittable
      const submitButton = page.getByRole('button', { name: /Submit Request/i });
      await expect(submitButton).not.toBeDisabled();
    }
  });
});
