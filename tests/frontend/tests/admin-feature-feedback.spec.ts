import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth';

test.describe('Admin - Feature Request Status Logic', () => {
    test.beforeEach(async ({ page }) => {
        await loginAsAdmin(page);
        // Navigate directly to the page since verification of navigation menu is not the primary goal here
        await page.goto('/admin/requests-feedback/details');
        await page.waitForLoadState('networkidle');
    });

    test('should match status and progress logic', async ({ page }) => {
        // Wait for table to load
        await expect(page.locator('h1')).toContainText('Feature Request & Feedback');

        // Check availability of items or wait for 'No items found'
        const table = page.locator('table');
        const noItems = page.locator('text=No items found');

        await Promise.race([
            expect(table).toBeVisible(),
            expect(noItems).toBeVisible()
        ]);

        if (await noItems.isVisible()) {
            console.log("No items to test status logic on.");
            return;
        }

        // Open first item
        await page.locator('button:has-text("View")').first().click();

        // Wait for modal
        const modal = page.locator('.fixed.inset-0.z-\\[9999\\]');
        await expect(modal).toBeVisible();

        // Get Selectors
        const statusSelect = modal.locator('select').nth(0); // Assumption: First select is Status
        const progressSelect = modal.locator('select').nth(1); // Assumption: Second select is Progress

        // 1. Verify Rejected Logic
        await statusSelect.selectOption('rejected');
        await expect(progressSelect).toHaveValue('Closed');

        // 2. Verify Approved Logic
        await statusSelect.selectOption('approved');
        // Defaults to In Progress
        await expect(progressSelect).toHaveValue('In Progress');

        // "Open" should NOT be present (we check value mainly)
        // Check options: In Progress, Implemented
        await expect(progressSelect.locator('option[value="In Progress"]')).toBeAttached();
        await expect(progressSelect.locator('option[value="Implemented"]')).toBeAttached();
        // Open should not be there for Approved
        await expect(progressSelect.locator('option[value="Open"]')).not.toBeAttached();

        // 3. Verify Pending Logic (if available)
        const pendingOption = statusSelect.locator('option[value="pending"]');
        if (await pendingOption.count() > 0) {
            await statusSelect.selectOption('pending');
            // Should default to Open
            await expect(progressSelect).toHaveValue('Open');
            // Should NOT have "Closed" anymore
            await expect(progressSelect.locator('option[value="Closed"]')).not.toBeAttached();
        }
    });
});
