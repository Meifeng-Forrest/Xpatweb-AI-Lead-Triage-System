import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const root = '/Users/wangmeifeng/Projects/Developer/Limen/Xpatweb-AI-Lead-Triage-System';
const outDir = path.join(root, 'test-results/lead-detail-drawer');
const API = 'http://localhost:8000/api/v1';
const APP = 'http://localhost:3001/';
const password = 'ChangeMe123!';
const accounts = {
  superadmin: 'admin@example.com',
  agent: 'melissa@example.com',
  approver: 'jerry@example.com',
  quality_lead: 'marisa@example.com',
  reviewer: 'willem@example.com',
};

await fs.mkdir(outDir, { recursive: true });

async function api(pathname, options = {}) {
  const response = await fetch(`${API}${pathname}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  });
  const text = await response.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!response.ok) {
    throw new Error(`${options.method || 'GET'} ${pathname} failed ${response.status}: ${text.slice(0, 500)}`);
  }
  return body;
}

async function login(email) {
  const body = await api('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  if (!body?.access_token) {
    throw new Error(`No token returned for ${email}`);
  }
  return body.access_token;
}

async function getLeads(token) {
  return api('/leads?limit=50', { headers: { Authorization: `Bearer ${token}` } });
}

async function createLead(token, suffix) {
  return api('/leads/manual', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      subject: `Drawer QA Lead ${suffix}`,
      body: `Name: Drawer QA ${suffix}\nEmail: drawer.qa.${suffix}@example.com\nPhone: +2711000${suffix}\nVisa: visitor visa\nSource: website form`,
      sender_email: `drawer.qa.${suffix}@example.com`,
      source: 'website',
    }),
  });
}

const tokens = {};
for (const [role, email] of Object.entries(accounts)) {
  tokens[role] = await login(email);
}

let leads = await getLeads(tokens.superadmin);
if (!Array.isArray(leads) || leads.length < 2) {
  await createLead(tokens.superadmin, Date.now());
  await createLead(tokens.superadmin, Date.now() + 1);
  leads = await getLeads(tokens.superadmin);
}
if (!Array.isArray(leads) || leads.length < 2) {
  throw new Error(`Need at least two leads, got ${Array.isArray(leads) ? leads.length : 'non-array'}`);
}

const browser = await chromium.launch({ headless: true });
const report = {
  generatedAt: new Date().toISOString(),
  app: APP,
  api: API,
  checks: [],
  screenshots: {},
  failures: [],
};

async function runAs(role, token, fn) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 980 } });
  await context.addInitScript((authToken) => {
    window.localStorage.setItem('xpatweb.auth.token', authToken);
  }, token);
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  const consoleErrors = [];
  const pageErrors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text().slice(0, 500));
    }
  });
  page.on('pageerror', (error) => pageErrors.push(String(error).slice(0, 500)));

  try {
    await page.goto(APP, { waitUntil: 'networkidle' });
    await fn(page);
  } finally {
    report.checks.push({ role, consoleErrors, pageErrors });
    await context.close();
  }
}

async function openFirstLead(page) {
  const rows = page.locator('tbody tr');
  await rows.first().waitFor({ state: 'visible' });
  const rowCount = await rows.count();
  if (rowCount < 2) {
    throw new Error(`Expected at least two lead rows, got ${rowCount}`);
  }
  await rows.first().locator('td').first().click();
  await page.getByRole('heading', { name: /Lead Detail/i }).waitFor({ state: 'visible' });
  return rows;
}

await runAs('superadmin', tokens.superadmin, async (page) => {
  const rows = await openFirstLead(page);
  const approve = page.getByRole('button', { name: /Approve & Send/i });
  await approve.waitFor({ state: 'visible' });
  const actionButtons = await page.locator('aside button').evaluateAll((buttons) =>
    buttons
      .map((button) => (button.textContent || button.getAttribute('aria-label') || button.getAttribute('title') || '').trim())
      .filter((text) => /Approve & Send|Return|Archive/.test(text)),
  );
  report.checks.push({ role: 'superadmin-ui', drawerVisible: true, actionButtons });
  const p1 = path.join(outDir, 'superadmin-drawer-open.png');
  await page.screenshot({ path: p1, fullPage: true });
  report.screenshots.superadminOpen = p1;
  await rows.nth(1).locator('td').first().click();
  await page.waitForTimeout(500);
  await page.getByRole('heading', { name: /Lead Detail/i }).waitFor({ state: 'visible' });
  const p2 = path.join(outDir, 'superadmin-drawer-switched.png');
  await page.screenshot({ path: p2, fullPage: true });
  report.screenshots.superadminSwitched = p2;
});

await runAs('agent', tokens.agent, async (page) => {
  await openFirstLead(page);
  const approveDisabled = await page.getByRole('button', { name: /Approve & Send/i }).isDisabled();
  let fieldSaveVisible = false;
  const editFullName = page.getByRole('button', { name: /Edit Full Name/i }).first();
  if ((await editFullName.count()) > 0) {
    await editFullName.click();
    fieldSaveVisible = await page.getByRole('button', { name: /Save field/i }).first().isVisible().catch(() => false);
  }
  const editButtonCount = await page.getByRole('button', { name: /^Edit/i }).count();
  report.checks.push({ role: 'agent-ui', approveDisabled, editButtonCount, fieldSaveVisible });
  const p = path.join(outDir, 'agent-editable.png');
  await page.screenshot({ path: p, fullPage: true });
  report.screenshots.agentEditable = p;
});

for (const role of ['reviewer', 'approver', 'quality_lead']) {
  await runAs(role, tokens[role], async (page) => {
    await openFirstLead(page);
    const approve = page.getByRole('button', { name: /Approve & Send/i });
    const approveVisible = await approve.isVisible().catch(() => false);
    const approveDisabled = approveVisible ? await approve.isDisabled() : null;
    const editButtonCount = await page.getByRole('button', { name: /^Edit/i }).count();
    report.checks.push({ role: `${role}-ui`, approveVisible, approveDisabled, editButtonCount });
    const p = path.join(outDir, `${role}-readonly.png`);
    await page.screenshot({ path: p, fullPage: true });
    report.screenshots[role] = p;
  });
}

await browser.close();

const adminUi = report.checks.find((check) => check.role === 'superadmin-ui');
if (!adminUi?.actionButtons?.includes('Approve & Send') || !adminUi?.actionButtons?.includes('Return') || !adminUi?.actionButtons?.includes('Archive')) {
  report.failures.push('superadmin drawer action buttons missing');
}
const agentUi = report.checks.find((check) => check.role === 'agent-ui');
if (!agentUi?.approveDisabled) {
  report.failures.push('agent Approve & Send should be disabled');
}
if (!agentUi?.fieldSaveVisible) {
  report.failures.push('agent basic field editor did not expose Save field');
}
for (const role of ['reviewer-ui', 'approver-ui', 'quality_lead-ui']) {
  const row = report.checks.find((check) => check.role === role);
  if ((row?.editButtonCount || 0) !== 0) {
    report.failures.push(`${role} should not expose edit buttons`);
  }
}
const reviewerUi = report.checks.find((check) => check.role === 'reviewer-ui');
const qlUi = report.checks.find((check) => check.role === 'quality_lead-ui');
if (!reviewerUi?.approveDisabled) {
  report.failures.push('reviewer Approve & Send should be disabled');
}
if (!qlUi?.approveDisabled) {
  report.failures.push('quality_lead Approve & Send should be disabled');
}

const reportPath = path.join(outDir, 'report.json');
await fs.writeFile(reportPath, JSON.stringify(report, null, 2));
console.log(JSON.stringify({ reportPath, failures: report.failures, screenshots: report.screenshots, checks: report.checks }, null, 2));

if (report.failures.length > 0) {
  process.exitCode = 1;
}
