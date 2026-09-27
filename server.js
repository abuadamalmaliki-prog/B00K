const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const stripe = require('./stripe-setup');
const PORT = process.env.PORT || 3000;
const DATA_DIR = path.join(__dirname, 'data');
const INVOICES_FILE = path.join(DATA_DIR, 'invoices.json');
const CLIENTS_FILE = path.join(DATA_DIR, 'clients.json');
const SETTINGS_FILE = path.join(DATA_DIR, 'settings.json');

if (!fs.existsSync(INVOICES_FILE)) fs.writeFileSync(INVOICES_FILE, '[]');
if (!fs.existsSync(CLIENTS_FILE)) fs.writeFileSync(CLIENTS_FILE, '[]');
if (!fs.existsSync(SETTINGS_FILE)) fs.writeFileSync(SETTINGS_FILE, JSON.stringify({
  companyName: 'Your Company',
  companyEmail: '',
  companyAddress: '',
  companyPhone: '',
  currency: 'USD',
  taxRate: 0,
  invoicePrefix: 'INV',
  nextNumber: 1001
}));

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

function readJSON(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function writeJSON(file, data) {
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
}

function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => {
      body += chunk;
      if (body.length > 1e6) { req.destroy(); reject(new Error('Too large')); }
    });
    req.on('end', () => {
      try { resolve(JSON.parse(body)); } catch { reject(new Error('Invalid JSON')); }
    });
  });
}

function sendJSON(res, code, data) {
  res.writeHead(code, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

async function handleAPI(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const segments = url.pathname.split('/').filter(Boolean);
  const method = req.method;

  // GET /api/invoices
  if (method === 'GET' && segments[1] === 'invoices' && !segments[2]) {
    return sendJSON(res, 200, readJSON(INVOICES_FILE));
  }

  // GET /api/invoices/:id
  if (method === 'GET' && segments[1] === 'invoices' && segments[2]) {
    const invoices = readJSON(INVOICES_FILE);
    const inv = invoices.find(i => i.id === segments[2]);
    return inv ? sendJSON(res, 200, inv) : sendJSON(res, 404, { error: 'Not found' });
  }

  // POST /api/invoices
  if (method === 'POST' && segments[1] === 'invoices' && !segments[2]) {
    const body = await parseBody(req);
    const settings = readJSON(SETTINGS_FILE);
    const invoices = readJSON(INVOICES_FILE);
    const invoice = {
      id: crypto.randomUUID(),
      number: `${settings.invoicePrefix}-${settings.nextNumber}`,
      ...body,
      status: body.status || 'draft',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    invoices.push(invoice);
    writeJSON(INVOICES_FILE, invoices);
    settings.nextNumber++;
    writeJSON(SETTINGS_FILE, settings);
    return sendJSON(res, 201, invoice);
  }

  // PUT /api/invoices/:id
  if (method === 'PUT' && segments[1] === 'invoices' && segments[2]) {
    const body = await parseBody(req);
    const invoices = readJSON(INVOICES_FILE);
    const idx = invoices.findIndex(i => i.id === segments[2]);
    if (idx === -1) return sendJSON(res, 404, { error: 'Not found' });
    invoices[idx] = { ...invoices[idx], ...body, updatedAt: new Date().toISOString() };
    writeJSON(INVOICES_FILE, invoices);
    return sendJSON(res, 200, invoices[idx]);
  }

  // DELETE /api/invoices/:id
  if (method === 'DELETE' && segments[1] === 'invoices' && segments[2]) {
    let invoices = readJSON(INVOICES_FILE);
    invoices = invoices.filter(i => i.id !== segments[2]);
    writeJSON(INVOICES_FILE, invoices);
    return sendJSON(res, 200, { ok: true });
  }

  // GET /api/clients
  if (method === 'GET' && segments[1] === 'clients' && !segments[2]) {
    return sendJSON(res, 200, readJSON(CLIENTS_FILE));
  }

  // POST /api/clients
  if (method === 'POST' && segments[1] === 'clients') {
    const body = await parseBody(req);
    const clients = readJSON(CLIENTS_FILE);
    const client = { id: crypto.randomUUID(), ...body, createdAt: new Date().toISOString() };
    clients.push(client);
    writeJSON(CLIENTS_FILE, clients);
    return sendJSON(res, 201, client);
  }

  // DELETE /api/clients/:id
  if (method === 'DELETE' && segments[1] === 'clients' && segments[2]) {
    let clients = readJSON(CLIENTS_FILE);
    clients = clients.filter(c => c.id !== segments[2]);
    writeJSON(CLIENTS_FILE, clients);
    return sendJSON(res, 200, { ok: true });
  }

  // GET /api/settings
  if (method === 'GET' && segments[1] === 'settings') {
    return sendJSON(res, 200, readJSON(SETTINGS_FILE));
  }

  // PUT /api/settings
  if (method === 'PUT' && segments[1] === 'settings') {
    const body = await parseBody(req);
    const settings = readJSON(SETTINGS_FILE);
    Object.assign(settings, body);
    writeJSON(SETTINGS_FILE, settings);
    return sendJSON(res, 200, settings);
  }

  // GET /api/dashboard
  if (method === 'GET' && segments[1] === 'dashboard') {
    const invoices = readJSON(INVOICES_FILE);
    const total = invoices.reduce((s, i) => s + (i.total || 0), 0);
    const paid = invoices.filter(i => i.status === 'paid').reduce((s, i) => s + (i.total || 0), 0);
    const pending = invoices.filter(i => i.status === 'sent').reduce((s, i) => s + (i.total || 0), 0);
    const overdue = invoices.filter(i => i.status === 'overdue').reduce((s, i) => s + (i.total || 0), 0);
    return sendJSON(res, 200, {
      totalInvoices: invoices.length,
      totalRevenue: total,
      paidAmount: paid,
      pendingAmount: pending,
      overdueAmount: overdue,
      recentInvoices: invoices.slice(-5).reverse(),
    });
  }

  // POST /api/checkout — create Stripe checkout for an invoice
  if (method === 'POST' && segments[1] === 'checkout') {
    const body = await parseBody(req);
    const invoices = readJSON(INVOICES_FILE);
    const inv = invoices.find(i => i.id === body.invoiceId);
    if (!inv) return sendJSON(res, 404, { error: 'Invoice not found' });
    const session = await stripe.createCheckoutSession(body.invoiceId, inv);
    return sendJSON(res, 200, session);
  }

  // POST /api/subscribe — create Stripe subscription checkout
  if (method === 'POST' && segments[1] === 'subscribe') {
    const body = await parseBody(req);
    const session = await stripe.createSubscriptionCheckout(body.plan);
    return sendJSON(res, 200, session);
  }

  sendJSON(res, 404, { error: 'Not found' });
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.url.startsWith('/api/')) {
      return await handleAPI(req, res);
    }

    let filePath = req.url === '/' ? '/index.html' : req.url;
    filePath = path.join(__dirname, 'public', filePath);
    const ext = path.extname(filePath);

    fs.readFile(filePath, (err, content) => {
      if (err) {
        fs.readFile(path.join(__dirname, 'public', 'index.html'), (_, c) => {
          res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
          res.end(c);
        });
      } else {
        res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
        res.end(content);
      }
    });
  } catch (e) {
    sendJSON(res, 500, { error: 'Internal error' });
  }
});

server.listen(PORT, () => console.log(`InvoiceBot running → http://localhost:${PORT}`));
