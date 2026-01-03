import { Page, expect } from '@playwright/test';

export const ADMIN_CREDENTIALS = {
  identifier: 'admin',
  password: 'admin123',
};

/**
 * Login as admin user with proper waits and fallback selectors
 */
export async function loginAsAdmin(page: Page) {
  await page.goto('/login', { waitUntil: 'networkidle' });
  
  // Wait for page to be fully loaded - check for main heading
  await page.waitForSelector('h1:has-text("RUBIK ANALYTICS")', { timeout: 15000 });
  await page.waitForLoadState('domcontentloaded');
  
  // Use placeholder or input type as fallback since label might not be associated
  // Try multiple strategies to find the identifier input
  const identifierInput = page.locator('input[type="text"]').first();
  await identifierInput.waitFor({ state: 'visible', timeout: 15000 });
  
  // Fill identifier - try by placeholder first, then direct input
  const placeholderInput = page.getByPlaceholder(/Enter email, mobile number, or user ID/i);
  try {
    if (await placeholderInput.isVisible({ timeout: 2000 })) {
      await placeholderInput.fill(ADMIN_CREDENTIALS.identifier);
    } else {
      await identifierInput.fill(ADMIN_CREDENTIALS.identifier);
    }
  } catch {
    await identifierInput.fill(ADMIN_CREDENTIALS.identifier);
  }
  
  // Find password input
  const passwordInput = page.locator('input[type="password"]').first();
  await passwordInput.waitFor({ state: 'visible', timeout: 15000 });
  
  // Fill password - try by placeholder first
  const passwordPlaceholder = page.getByPlaceholder(/Enter password/i);
  try {
    if (await passwordPlaceholder.isVisible({ timeout: 2000 })) {
      await passwordPlaceholder.fill(ADMIN_CREDENTIALS.password);
    } else {
      await passwordInput.fill(ADMIN_CREDENTIALS.password);
    }
  } catch {
    await passwordInput.fill(ADMIN_CREDENTIALS.password);
  }
  
  // Find and click sign in button
  const signInButton = page.locator('button:has-text("Sign In")');
  await signInButton.waitFor({ state: 'visible', timeout: 15000 });
  await signInButton.click();
  
  // Wait for dashboard to load
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 20000 });
  
  // Wait for sidebar to be visible
  await page.waitForSelector('aside', { timeout: 15000 });
  await page.waitForSelector('text=RUBIK', { timeout: 10000 });
}

/**
 * Logout from the application
 */
export async function logout(page: Page) {
  const logoutButton = page.getByText(/Logout/i);
  await logoutButton.waitFor({ state: 'visible', timeout: 10000 });
  await logoutButton.click();
  await page.waitForURL(/\/login/, { timeout: 10000 });
}

/**
 * Navigate to a specific admin page
 */
export async function navigateToAdminPage(page: Page, pageName: string) {
  const pageLink = page.getByText(pageName);
  await pageLink.waitFor({ state: 'visible', timeout: 10000 });
  await pageLink.click();
  await page.waitForTimeout(500);
  await expect(page).toHaveURL(new RegExp(`/${pageName.toLowerCase().replace(/\s+/g, '-')}`, 'i'), { timeout: 15000 });
}
