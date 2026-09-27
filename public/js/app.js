const App = {
  currentPage: 'landing',
  invoices: [],
  clients: [],
  settings: {},
  dashboard: {},

  async init() {
    const isApp = localStorage.getItem('ib_entered');
    if (isApp) {
      this.currentPage = 'dashboard';
      await this.loadData();
    }
    this.render();
  },

  async loadData() {
    const [invoices, clients, settings, dashboard] = await Promise.all([
      fetch('/api/invoices').then(r => r.json()),
      fetch('/api/clients').then(r => r.json()),
      fetch('/api/settings').then(r => r.json()),
      fetch('/api/dashboard').then(r => r.json()),
    ]);
    this.invoices = invoices;
    this.clients = clients;
    this.settings = settings;
    this.dashboard = dashboard;
  },

  navigate(page) {
    if (page === 'dashboard' && !localStorage.getItem('ib_entered')) {
      localStorage.setItem('ib_entered', '1');
      this.loadData().then(() => { this.currentPage = page; this.render(); });
      return;
    }
    this.currentPage = page;
    this.render();
  },

  render() {
    const app = document.getElementById('app');
    if (this.currentPage === 'landing') {
      app.innerHTML = this.renderLanding();
    } else {
      app.innerHTML = `<div class="app">${this.renderSidebar()}<div class="main">${this.renderPage()}</div></div>`;
    }
    this.attachEvents();
  },

  renderLanding() {
    return `
    <div class="landing">
      <nav class="landing-nav">
        <div class="logo">Invoice<span>Bot</span></div>
        <div>
          <button class="btn-primary" onclick="App.navigate('dashboard')">Open App</button>
        </div>
      </nav>
      <div class="hero">
        <h1>Get paid faster.<br>Invoice in <em>30 seconds</em>.</h1>
        <p>The simplest invoicing tool for freelancers. Create professional invoices, track payments, and get paid — no sign-up required to try.</p>
        <div class="hero-cta">
          <button class="btn-primary" onclick="App.navigate('dashboard')">Start Invoicing — Free</button>
          <button class="btn-secondary" onclick="document.querySelector('.pricing').scrollIntoView({behavior:'smooth'})">See Pricing</button>
        </div>
      </div>
      <div class="features">
        <div class="feature-card">
          <div class="icon">&#9889;</div>
          <h3>30-Second Invoices</h3>
          <p>No bloat, no learning curve. Pick a client, add line items, send. Done.</p>
        </div>
        <div class="feature-card">
          <div class="icon">&#128176;</div>
          <h3>Get Paid Online</h3>
          <p>Accept credit cards and bank transfers via Stripe. Money hits your account in 2 days.</p>
        </div>
        <div class="feature-card">
          <div class="icon">&#128202;</div>
          <h3>Track Everything</h3>
          <p>See who owes you, what's overdue, and your total revenue at a glance.</p>
        </div>
        <div class="feature-card">
          <div class="icon">&#128196;</div>
          <h3>PDF Export</h3>
          <p>Download beautiful PDF invoices. Attach them to emails or print for records.</p>
        </div>
        <div class="feature-card">
          <div class="icon">&#127912;</div>
          <h3>Your Branding</h3>
          <p>Add your logo, colors, and company info. Every invoice looks like you.</p>
        </div>
        <div class="feature-card">
          <div class="icon">&#128274;</div>
          <h3>Client Portal</h3>
          <p>Clients view invoices online, pay with one click, and download receipts.</p>
        </div>
      </div>
      <div class="pricing">
        <h2>Simple, transparent pricing</h2>
        <div class="pricing-grid">
          <div class="pricing-card">
            <h3>Starter</h3>
            <div class="price">$0<small>/month</small></div>
            <div class="desc">Try it out, no card required</div>
            <ul>
              <li>3 invoices per month</li>
              <li>1 client</li>
              <li>Basic invoice template</li>
              <li>Email support</li>
            </ul>
            <button class="btn-secondary" style="width:100%" onclick="App.navigate('dashboard')">Get Started</button>
          </div>
          <div class="pricing-card featured">
            <h3>Pro</h3>
            <div class="price">$19<small>/month</small></div>
            <div class="desc">Everything a freelancer needs</div>
            <ul>
              <li>Unlimited invoices</li>
              <li>Unlimited clients</li>
              <li>PDF export & branding</li>
              <li>Online payments (Stripe)</li>
              <li>Client portal</li>
              <li>Priority support</li>
            </ul>
            <button class="btn-primary" style="width:100%" onclick="App.navigate('dashboard')">Start Free Trial</button>
          </div>
          <div class="pricing-card">
            <h3>Business</h3>
            <div class="price">$39<small>/month</small></div>
            <div class="desc">For growing businesses</div>
            <ul>
              <li>Everything in Pro</li>
              <li>Multi-currency</li>
              <li>Recurring invoices</li>
              <li>Expense tracking</li>
              <li>Revenue reports</li>
              <li>API access</li>
            </ul>
            <button class="btn-secondary" style="width:100%" onclick="App.navigate('dashboard')">Start Free Trial</button>
          </div>
        </div>
      </div>
      <footer class="landing-footer">&copy; 2026 InvoiceBot. Built for freelancers who value their time.</footer>
    </div>`;
  },

  renderSidebar() {
    const links = [
      { id: 'dashboard', icon: '&#9633;', label: 'Dashboard' },
      { id: 'invoices', icon: '&#128196;', label: 'Invoices' },
      { id: 'clients', icon: '&#128101;', label: 'Clients' },
      { id: 'settings', icon: '&#9881;', label: 'Settings' },
    ];
    return `
    <aside class="sidebar">
      <div class="sidebar-logo">Invoice<span>Bot</span></div>
      <nav>${links.map(l => `<a href="#" class="${this.currentPage === l.id ? 'active' : ''}" onclick="event.preventDefault();App.navigate('${l.id}')">${l.icon} ${l.label}</a>`).join('')}</nav>
      <a href="#" onclick="event.preventDefault();localStorage.removeItem('ib_entered');App.navigate('landing')" style="color:var(--text-2);font-size:.85rem;padding:10px 14px">Back to site</a>
    </aside>`;
  },

  renderPage() {
    switch (this.currentPage) {
      case 'dashboard': return this.renderDashboard();
      case 'invoices': return this.renderInvoices();
      case 'clients': return this.renderClients();
      case 'settings': return this.renderSettings();
      default: return '';
    }
  },

  fmt(n) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: this.settings.currency || 'USD' }).format(n || 0);
  },

  renderDashboard() {
    const d = this.dashboard;
    return `
    <div class="page-header"><h1>Dashboard</h1><button class="btn-primary" onclick="App.showInvoiceModal()">+ New Invoice</button></div>
    <div class="stats-grid">
      <div class="stat-card"><div class="label">Total Revenue</div><div class="value">${this.fmt(d.totalRevenue)}</div></div>
      <div class="stat-card"><div class="label">Paid</div><div class="value green">${this.fmt(d.paidAmount)}</div></div>
      <div class="stat-card"><div class="label">Pending</div><div class="value yellow">${this.fmt(d.pendingAmount)}</div></div>
      <div class="stat-card"><div class="label">Overdue</div><div class="value red">${this.fmt(d.overdueAmount)}</div></div>
    </div>
    <h2 style="font-size:1.1rem;margin-bottom:16px">Recent Invoices</h2>
    ${(d.recentInvoices && d.recentInvoices.length) ? `
    <div class="table-wrap"><table>
      <thead><tr><th>Invoice</th><th>Client</th><th>Amount</th><th>Status</th><th>Date</th></tr></thead>
      <tbody>${d.recentInvoices.map(i => `<tr>
        <td><strong>${i.number}</strong></td>
        <td>${i.clientName || '—'}</td>
        <td>${this.fmt(i.total)}</td>
        <td><span class="badge badge-${i.status}">${i.status}</span></td>
        <td>${new Date(i.createdAt).toLocaleDateString()}</td>
      </tr>`).join('')}</tbody>
    </table></div>` : `<div class="empty-state"><div class="icon">&#128196;</div><p>No invoices yet. Create your first one!</p><button class="btn-primary" onclick="App.showInvoiceModal()">+ New Invoice</button></div>`}`;
  },

  renderInvoices() {
    return `
    <div class="page-header"><h1>Invoices</h1><button class="btn-primary" onclick="App.showInvoiceModal()">+ New Invoice</button></div>
    ${this.invoices.length ? `
    <div class="table-wrap"><table>
      <thead><tr><th>Invoice</th><th>Client</th><th>Amount</th><th>Status</th><th>Date</th><th>Actions</th></tr></thead>
      <tbody>${this.invoices.map(i => `<tr>
        <td><strong>${i.number}</strong></td>
        <td>${i.clientName || '—'}</td>
        <td>${this.fmt(i.total)}</td>
        <td>
          <select onchange="App.updateInvoiceStatus('${i.id}', this.value)" style="background:transparent;border:none;color:inherit;font-size:.8rem;padding:2px">
            ${['draft','sent','paid','overdue'].map(s => `<option value="${s}" ${i.status===s?'selected':''}>${s}</option>`).join('')}
          </select>
        </td>
        <td>${new Date(i.createdAt).toLocaleDateString()}</td>
        <td>
          <button class="btn-sm btn-secondary" onclick="App.showInvoicePreview('${i.id}')">View</button>
          <button class="btn-sm btn-danger" onclick="App.deleteInvoice('${i.id}')">Delete</button>
        </td>
      </tr>`).join('')}</tbody>
    </table></div>` : `<div class="empty-state"><div class="icon">&#128196;</div><p>No invoices yet.</p><button class="btn-primary" onclick="App.showInvoiceModal()">+ Create Invoice</button></div>`}`;
  },

  renderClients() {
    return `
    <div class="page-header"><h1>Clients</h1><button class="btn-primary" onclick="App.showClientModal()">+ Add Client</button></div>
    ${this.clients.length ? `
    <div class="table-wrap"><table>
      <thead><tr><th>Name</th><th>Email</th><th>Company</th><th>Invoices</th><th>Actions</th></tr></thead>
      <tbody>${this.clients.map(c => `<tr>
        <td><strong>${c.name}</strong></td>
        <td>${c.email || '—'}</td>
        <td>${c.company || '—'}</td>
        <td>${this.invoices.filter(i => i.clientId === c.id).length}</td>
        <td><button class="btn-sm btn-danger" onclick="App.deleteClient('${c.id}')">Delete</button></td>
      </tr>`).join('')}</tbody>
    </table></div>` : `<div class="empty-state"><div class="icon">&#128101;</div><p>No clients yet.</p><button class="btn-primary" onclick="App.showClientModal()">+ Add Client</button></div>`}`;
  },

  renderSettings() {
    const s = this.settings;
    return `
    <div class="page-header"><h1>Settings</h1></div>
    <div style="max-width:500px">
      <div class="form-group"><label>Company Name</label><input id="s-name" value="${s.companyName || ''}"></div>
      <div class="form-group"><label>Email</label><input id="s-email" value="${s.companyEmail || ''}"></div>
      <div class="form-group"><label>Address</label><textarea id="s-address" rows="2">${s.companyAddress || ''}</textarea></div>
      <div class="form-group"><label>Phone</label><input id="s-phone" value="${s.companyPhone || ''}"></div>
      <div class="form-row">
        <div class="form-group"><label>Currency</label>
          <select id="s-currency">
            ${['USD','EUR','GBP','CAD','AUD','JPY'].map(c => `<option ${s.currency===c?'selected':''}>${c}</option>`).join('')}
          </select>
        </div>
        <div class="form-group"><label>Tax Rate (%)</label><input id="s-tax" type="number" value="${s.taxRate || 0}"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>Invoice Prefix</label><input id="s-prefix" value="${s.invoicePrefix || 'INV'}"></div>
        <div class="form-group"><label>Next Number</label><input id="s-next" type="number" value="${s.nextNumber || 1001}"></div>
      </div>
      <button class="btn-primary" onclick="App.saveSettings()">Save Settings</button>
    </div>`;
  },

  async saveSettings() {
    const data = {
      companyName: document.getElementById('s-name').value,
      companyEmail: document.getElementById('s-email').value,
      companyAddress: document.getElementById('s-address').value,
      companyPhone: document.getElementById('s-phone').value,
      currency: document.getElementById('s-currency').value,
      taxRate: parseFloat(document.getElementById('s-tax').value) || 0,
      invoicePrefix: document.getElementById('s-prefix').value,
      nextNumber: parseInt(document.getElementById('s-next').value) || 1001,
    };
    await fetch('/api/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    await this.loadData();
    this.render();
  },

  showInvoiceModal() {
    const clientOptions = this.clients.map(c => `<option value="${c.id}" data-name="${c.name}">${c.name}${c.company ? ` (${c.company})` : ''}</option>`).join('');
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'invoice-modal';
    modal.innerHTML = `
    <div class="modal">
      <h2>New Invoice</h2>
      <div class="form-row">
        <div class="form-group"><label>Client</label>
          <select id="inv-client"><option value="">Select client...</option>${clientOptions}</select>
        </div>
        <div class="form-group"><label>Due Date</label><input id="inv-due" type="date" value="${new Date(Date.now()+30*86400000).toISOString().split('T')[0]}"></div>
      </div>
      <div class="form-group"><label>Notes</label><textarea id="inv-notes" rows="2" placeholder="Payment terms, thank you note..."></textarea></div>
      <label style="font-size:.85rem;font-weight:500;color:var(--text-2);margin-bottom:8px;display:block">Line Items</label>
      <div class="line-items" id="line-items">
        <div class="line-item">
          <input placeholder="Description" class="li-desc">
          <input placeholder="Qty" type="number" value="1" class="li-qty">
          <input placeholder="Rate" type="number" value="0" class="li-rate">
          <div class="line-item-total">$0.00</div>
          <button class="remove-line" onclick="this.parentElement.remove();App.calcTotal()">&times;</button>
        </div>
      </div>
      <button class="btn-secondary btn-sm" onclick="App.addLineItem()">+ Add Line</button>
      <div class="invoice-totals">
        <div class="row"><span class="label">Subtotal</span><span id="inv-subtotal">$0.00</span></div>
        <div class="row"><span class="label">Tax (${this.settings.taxRate || 0}%)</span><span id="inv-tax">$0.00</span></div>
        <div class="row grand-total"><span class="label">Total</span><span id="inv-total">$0.00</span></div>
      </div>
      <div class="modal-actions">
        <button class="btn-secondary" onclick="document.getElementById('invoice-modal').remove()">Cancel</button>
        <button class="btn-primary" onclick="App.createInvoice()">Create Invoice</button>
      </div>
    </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('input', () => this.calcTotal());
  },

  addLineItem() {
    const container = document.getElementById('line-items');
    const div = document.createElement('div');
    div.className = 'line-item';
    div.innerHTML = `
      <input placeholder="Description" class="li-desc">
      <input placeholder="Qty" type="number" value="1" class="li-qty">
      <input placeholder="Rate" type="number" value="0" class="li-rate">
      <div class="line-item-total">$0.00</div>
      <button class="remove-line" onclick="this.parentElement.remove();App.calcTotal()">&times;</button>`;
    container.appendChild(div);
  },

  calcTotal() {
    let subtotal = 0;
    document.querySelectorAll('.line-item').forEach(li => {
      const qty = parseFloat(li.querySelector('.li-qty')?.value) || 0;
      const rate = parseFloat(li.querySelector('.li-rate')?.value) || 0;
      const lineTotal = qty * rate;
      subtotal += lineTotal;
      const totalEl = li.querySelector('.line-item-total');
      if (totalEl) totalEl.textContent = this.fmt(lineTotal);
    });
    const taxRate = this.settings.taxRate || 0;
    const tax = subtotal * (taxRate / 100);
    document.getElementById('inv-subtotal').textContent = this.fmt(subtotal);
    document.getElementById('inv-tax').textContent = this.fmt(tax);
    document.getElementById('inv-total').textContent = this.fmt(subtotal + tax);
  },

  async createInvoice() {
    const clientSelect = document.getElementById('inv-client');
    const clientId = clientSelect.value;
    const clientName = clientSelect.selectedOptions[0]?.dataset?.name || '';
    const items = [];
    document.querySelectorAll('.line-item').forEach(li => {
      items.push({
        description: li.querySelector('.li-desc')?.value || '',
        quantity: parseFloat(li.querySelector('.li-qty')?.value) || 0,
        rate: parseFloat(li.querySelector('.li-rate')?.value) || 0,
      });
    });
    const subtotal = items.reduce((s, i) => s + i.quantity * i.rate, 0);
    const tax = subtotal * ((this.settings.taxRate || 0) / 100);

    await fetch('/api/invoices', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        clientId, clientName, items,
        dueDate: document.getElementById('inv-due').value,
        notes: document.getElementById('inv-notes').value,
        subtotal, tax, total: subtotal + tax,
      }),
    });
    document.getElementById('invoice-modal').remove();
    await this.loadData();
    this.render();
  },

  async updateInvoiceStatus(id, status) {
    await fetch(`/api/invoices/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    await this.loadData();
  },

  async deleteInvoice(id) {
    if (!confirm('Delete this invoice?')) return;
    await fetch(`/api/invoices/${id}`, { method: 'DELETE' });
    await this.loadData();
    this.render();
  },

  showInvoicePreview(id) {
    const inv = this.invoices.find(i => i.id === id);
    if (!inv) return;
    const s = this.settings;
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'preview-modal';
    modal.innerHTML = `
    <div class="modal" style="max-width:800px">
      <div class="invoice-preview">
        <div class="header">
          <div>
            <div class="company-name">${s.companyName}</div>
            <div style="color:#666;font-size:.85rem">${(s.companyAddress || '').replace(/\n/g, '<br>')}</div>
            <div style="color:#666;font-size:.85rem">${s.companyEmail || ''}</div>
          </div>
          <div class="invoice-meta">
            <div class="invoice-number">${inv.number}</div>
            <div>Date: ${new Date(inv.createdAt).toLocaleDateString()}</div>
            <div>Due: ${inv.dueDate ? new Date(inv.dueDate).toLocaleDateString() : '—'}</div>
            <div style="margin-top:8px"><span class="badge badge-${inv.status}">${inv.status}</span></div>
          </div>
        </div>
        <div style="margin-bottom:24px">
          <div style="font-weight:600;margin-bottom:4px">Bill To:</div>
          <div>${inv.clientName || '—'}</div>
        </div>
        <table>
          <thead><tr><th>Description</th><th>Qty</th><th>Rate</th><th style="text-align:right">Amount</th></tr></thead>
          <tbody>${(inv.items || []).map(i => `<tr>
            <td>${i.description}</td>
            <td>${i.quantity}</td>
            <td>${this.fmt(i.rate)}</td>
            <td style="text-align:right">${this.fmt(i.quantity * i.rate)}</td>
          </tr>`).join('')}</tbody>
        </table>
        <div class="invoice-totals" style="border-color:#eee">
          <div class="row"><span class="label" style="color:#666">Subtotal</span><span>${this.fmt(inv.subtotal)}</span></div>
          <div class="row"><span class="label" style="color:#666">Tax</span><span>${this.fmt(inv.tax)}</span></div>
          <div class="row grand-total"><span class="label">Total</span><span>${this.fmt(inv.total)}</span></div>
        </div>
        ${inv.notes ? `<div style="margin-top:20px;padding-top:16px;border-top:1px solid #eee;color:#666;font-size:.85rem"><strong>Notes:</strong> ${inv.notes}</div>` : ''}
      </div>
      <div class="modal-actions">
        <button class="btn-secondary" onclick="document.getElementById('preview-modal').remove()">Close</button>
        <button class="btn-primary" onclick="App.printInvoice()">Print / Save PDF</button>
      </div>
    </div>`;
    document.body.appendChild(modal);
  },

  printInvoice() {
    const content = document.querySelector('.invoice-preview').innerHTML;
    const win = window.open('', '_blank');
    win.document.write(`<!DOCTYPE html><html><head><title>Invoice</title><style>
      body{font-family:-apple-system,system-ui,sans-serif;padding:40px;color:#1a1a1a}
      table{width:100%;border-collapse:collapse;margin:24px 0}
      th{text-align:left;font-size:.75rem;text-transform:uppercase;color:#666;padding:10px;border-bottom:2px solid #e5e5e5}
      td{padding:10px;border-bottom:1px solid #eee}
      .header{display:flex;justify-content:space-between;margin-bottom:40px}
      .company-name{font-size:1.5rem;font-weight:700}
      .invoice-meta{text-align:right;color:#666}
      .invoice-number{font-size:1.25rem;font-weight:700;color:#1a1a1a}
      .invoice-totals{text-align:right;padding:16px 0;border-top:1px solid #eee}
      .invoice-totals .row{display:flex;justify-content:flex-end;gap:24px;margin-bottom:6px}
      .invoice-totals .label{color:#666}
      .grand-total{font-size:1.25rem;font-weight:700}
      .badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.75rem;font-weight:600;text-transform:uppercase}
      .badge-draft{background:#eee;color:#666}.badge-sent{background:#e8e7ff;color:#6366f1}
      .badge-paid{background:#dcfce7;color:#22c55e}.badge-overdue{background:#fee2e2;color:#ef4444}
      @media print{body{padding:0}}
    </style></head><body>${content}</body></html>`);
    win.document.close();
    win.print();
  },

  showClientModal() {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'client-modal';
    modal.innerHTML = `
    <div class="modal">
      <h2>Add Client</h2>
      <div class="form-group"><label>Name *</label><input id="cl-name" placeholder="John Doe"></div>
      <div class="form-group"><label>Email</label><input id="cl-email" type="email" placeholder="john@example.com"></div>
      <div class="form-group"><label>Company</label><input id="cl-company" placeholder="Acme Inc."></div>
      <div class="form-group"><label>Address</label><textarea id="cl-address" rows="2" placeholder="123 Main St..."></textarea></div>
      <div class="form-group"><label>Phone</label><input id="cl-phone" placeholder="+1 555 0123"></div>
      <div class="modal-actions">
        <button class="btn-secondary" onclick="document.getElementById('client-modal').remove()">Cancel</button>
        <button class="btn-primary" onclick="App.createClient()">Add Client</button>
      </div>
    </div>`;
    document.body.appendChild(modal);
  },

  async createClient() {
    const name = document.getElementById('cl-name').value.trim();
    if (!name) return alert('Name is required');
    await fetch('/api/clients', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        email: document.getElementById('cl-email').value,
        company: document.getElementById('cl-company').value,
        address: document.getElementById('cl-address').value,
        phone: document.getElementById('cl-phone').value,
      }),
    });
    document.getElementById('client-modal').remove();
    await this.loadData();
    this.render();
  },

  async deleteClient(id) {
    if (!confirm('Delete this client?')) return;
    await fetch(`/api/clients/${id}`, { method: 'DELETE' });
    await this.loadData();
    this.render();
  },

  attachEvents() {},
};

App.init();
