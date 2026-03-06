/**
 * Playwright E2E tests — Full user journey through the UI.
 *
 * These tests run against the real frontend + backend servers.
 * They exercise the complete flow a user would take.
 *
 * Prerequisites:
 *   - Backend running on :5000
 *   - Frontend dev server on :3000
 *   - A temp project directory (created in beforeAll)
 */
import { expect, test } from '@playwright/test';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

let tempProjectDir: string;

test.beforeAll(() => {
  // Create a temp project directory with docs structure
  tempProjectDir = fs.mkdtempSync(path.join(os.tmpdir(), 'ralph_e2e_'));
  const docsDirs = [
    'docs/01-requirements',
    'docs/02-architecture',
    'docs/03-design',
    'docs/04-test-architecture',
    'docs/05-milestones',
    '.ralph',
  ];
  for (const dir of docsDirs) {
    fs.mkdirSync(path.join(tempProjectDir, dir), { recursive: true });
  }
  // Create handover files
  for (const dir of docsDirs.slice(0, 5)) {
    fs.writeFileSync(
      path.join(tempProjectDir, dir, 'handover.json'),
      JSON.stringify({ status: 'complete' })
    );
  }
  fs.writeFileSync(
    path.join(tempProjectDir, 'README.md'),
    '# E2E Test Project\n'
  );
});

test.afterAll(() => {
  // Cleanup temp dir
  fs.rmSync(tempProjectDir, { recursive: true, force: true });
});

test.describe('Application Shell', () => {
  test('loads the dashboard page', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/dashboard/);
  });

  test('sidebar is visible', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByText('Pipeline Executor')).toBeVisible();
  });

  test('shows empty state when no project selected', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByText('No Project Selected')).toBeVisible();
  });

  test('sidebar shows "No projects yet" initially', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByText('No projects yet')).toBeVisible();
  });
});

test.describe('Link Project Flow', () => {
  test('can open link project modal from sidebar', async ({ page }) => {
    await page.goto('/dashboard');
    await page.getByTitle('Add Project').click();
    await expect(page.getByRole('heading', { name: 'Link Project' })).toBeVisible();
  });

  test('can open link project modal from empty state', async ({ page }) => {
    await page.goto('/dashboard');
    await page.getByRole('button', { name: 'Link Project' }).click();
    await expect(page.getByRole('heading', { name: 'Link Project' })).toBeVisible();
  });

  test('link button is disabled with empty path', async ({ page }) => {
    await page.goto('/dashboard');
    await page.getByRole('button', { name: 'Link Project' }).click();

    // Get the modal's Link Project button (not the sidebar one)
    const linkBtn = page.locator('button:text("Link Project")').last();
    await expect(linkBtn).toBeDisabled();
  });

  test('can link a project', async ({ page }) => {
    await page.goto('/dashboard');
    await page.getByRole('button', { name: 'Link Project' }).click();

    // Fill in project path
    await page.getByPlaceholder('/path/to/your/project').fill(tempProjectDir);
    
    // Click the modal's Link Project button
    const linkBtn = page.locator('button:text("Link Project")').last();
    await linkBtn.click();

    // Modal should close
    await expect(
      page.getByRole('heading', { name: 'Link Project' })
    ).not.toBeVisible({ timeout: 5000 });

    // Project should appear in sidebar
    const projectName = path.basename(tempProjectDir);
    await expect(page.getByText(projectName)).toBeVisible({ timeout: 5000 });
  });

  test('shows error for invalid path', async ({ page }) => {
    await page.goto('/dashboard');
    await page.getByTitle('Add Project').click();

    await page
      .getByPlaceholder('/path/to/your/project')
      .fill('/nonexistent/path/that/does/not/exist');

    const linkBtn = page.locator('button:text("Link Project")').last();
    await linkBtn.click();

    // Error message should appear
    await expect(page.getByText(/does not exist|Failed/)).toBeVisible({
      timeout: 5000,
    });
  });
});

test.describe('Project Dashboard Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Link the project first
    await page.goto('/dashboard');
    await page.getByTitle('Add Project').click();
    await page.getByPlaceholder('/path/to/your/project').fill(tempProjectDir);
    const linkBtn = page.locator('button:text("Link Project")').last();
    await linkBtn.click();
    // Wait for modal to close
    await expect(
      page.getByRole('heading', { name: 'Link Project' })
    ).not.toBeVisible({ timeout: 5000 });
  });

  test('clicking project in sidebar shows setup flow', async ({ page }) => {
    const projectName = path.basename(tempProjectDir);
    await page.getByText(projectName).click();

    // Should show Setup Required since no pipeline-config.json
    await expect(page.getByText('Setup Required')).toBeVisible({ timeout: 5000 });
  });

  test('setup flow shows docs structure', async ({ page }) => {
    const projectName = path.basename(tempProjectDir);
    await page.getByText(projectName).click();

    await expect(page.getByText('Docs Structure')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('docs/01-requirements')).toBeVisible({
      timeout: 5000,
    });
  });

  test('setup flow shows pipeline configurator button', async ({ page }) => {
    const projectName = path.basename(tempProjectDir);
    await page.getByText(projectName).click();

    await expect(
      page.getByText('Run Pipeline Configurator')
    ).toBeVisible({ timeout: 5000 });
  });

  test('project becomes setup after config is created', async ({ page }) => {
    const projectName = path.basename(tempProjectDir);

    // Create pipeline-config.json on disk
    fs.writeFileSync(
      path.join(tempProjectDir, 'pipeline-config.json'),
      JSON.stringify({ project_name: projectName, milestones: [1] })
    );

    // Reload and click project
    await page.reload();
    await page.getByText(projectName).click();

    // Should show the full dashboard (has tabs) not setup flow
    await expect(page.getByText('Pipeline State')).toBeVisible({
      timeout: 10000,
    });

    // Cleanup
    fs.unlinkSync(path.join(tempProjectDir, 'pipeline-config.json'));
  });
});

test.describe('Navigation', () => {
  test('can navigate to requirements page', async ({ page }) => {
    await page.goto('/requirements');
    await expect(page).toHaveURL(/requirements/);
  });

  test('can navigate to editor page', async ({ page }) => {
    await page.goto('/editor');
    await expect(page).toHaveURL(/editor/);
  });

  test('root redirects to dashboard', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveURL(/dashboard/);
  });
});

test.describe('Health Check', () => {
  test('health endpoint returns ok', async ({ request }) => {
    const resp = await request.get('http://localhost:5000/api/health');
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.status).toBe('ok');
  });
});

test.describe('API Integration', () => {
  test('can list projects via API', async ({ request }) => {
    const resp = await request.get('http://localhost:5000/api/projects');
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(Array.isArray(body)).toBeTruthy();
  });

  test('can create and delete a project via API', async ({ request }) => {
    // Create
    const createResp = await request.post('http://localhost:5000/api/projects', {
      data: { project_path: tempProjectDir },
    });
    expect(createResp.ok()).toBeTruthy();
    const project = await createResp.json();
    expect(project.id).toBeDefined();

    // Delete
    const deleteResp = await request.delete(
      `http://localhost:5000/api/projects/${project.id}`
    );
    expect(deleteResp.ok()).toBeTruthy();

    // Verify deleted
    const getResp = await request.get(
      `http://localhost:5000/api/projects/${project.id}`
    );
    expect(getResp.status()).toBe(404);
  });

  test('pre-check returns valid structure', async ({ request }) => {
    const resp = await request.post(
      'http://localhost:5000/api/projects/pre-check',
      {
        data: { project_path: tempProjectDir },
      }
    );
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.valid).toBe(true);
    expect(body.docs_structure).toBeDefined();
  });

  test('duplicate project returns existing', async ({ request }) => {
    // Create once
    const resp1 = await request.post('http://localhost:5000/api/projects', {
      data: { project_path: tempProjectDir },
    });
    const p1 = await resp1.json();

    // Create again
    const resp2 = await request.post('http://localhost:5000/api/projects', {
      data: { project_path: tempProjectDir },
    });
    expect(resp2.ok()).toBeTruthy();
    const p2 = await resp2.json();
    expect(p2.id).toBe(p1.id);

    // Cleanup
    await request.delete(`http://localhost:5000/api/projects/${p1.id}`);
  });
});
