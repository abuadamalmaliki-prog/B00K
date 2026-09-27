const http = require('http');
const crypto = require('crypto');

const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY;
const STRIPE_WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET;
const APP_URL = process.env.APP_URL || 'http://localhost:3000';

function stripeRequest(method, path, data) {
  return new Promise((resolve, reject) => {
    const postData = data ? new URLSearchParams(data).toString() : '';
    const options = {
      hostname: 'api.stripe.com',
      port: 443,
      path: `/v1/${path}`,
      method,
      headers: {
        'Authorization': `Bearer ${STRIPE_SECRET_KEY}`,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(postData),
      },
    };
    const req = http.request({ ...options, protocol: 'https:' }, res => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(body)); } catch { resolve(body); }
      });
    });
    req.on('error', reject);
    req.write(postData);
    req.end();
  });
}

const StripeIntegration = {
  async createCheckoutSession(invoiceId, invoice) {
    if (!STRIPE_SECRET_KEY) return { error: 'Stripe not configured. Set STRIPE_SECRET_KEY env var.' };
    const lineItems = (invoice.items || []).map((item, i) => ({
      [`line_items[${i}][price_data][currency]`]: 'usd',
      [`line_items[${i}][price_data][product_data][name]`]: item.description,
      [`line_items[${i}][price_data][unit_amount]`]: Math.round(item.rate * 100),
      [`line_items[${i}][quantity]`]: item.quantity,
    }));

    const params = {
      mode: 'payment',
      success_url: `${APP_URL}/payment-success?invoice=${invoiceId}`,
      cancel_url: `${APP_URL}/payment-cancel?invoice=${invoiceId}`,
      'metadata[invoice_id]': invoiceId,
      'metadata[invoice_number]': invoice.number,
    };
    lineItems.forEach(li => Object.assign(params, li));

    return stripeRequest('POST', 'checkout/sessions', params);
  },

  async createSubscriptionCheckout(plan) {
    if (!STRIPE_SECRET_KEY) return { error: 'Stripe not configured' };
    const prices = {
      pro: process.env.STRIPE_PRO_PRICE_ID,
      business: process.env.STRIPE_BIZ_PRICE_ID,
    };
    if (!prices[plan]) return { error: 'Invalid plan' };

    return stripeRequest('POST', 'checkout/sessions', {
      mode: 'subscription',
      'line_items[0][price]': prices[plan],
      'line_items[0][quantity]': 1,
      success_url: `${APP_URL}/subscribe-success`,
      cancel_url: `${APP_URL}/pricing`,
    });
  },

  verifyWebhook(payload, signature) {
    if (!STRIPE_WEBHOOK_SECRET) return null;
    const elements = signature.split(',').reduce((acc, el) => {
      const [key, val] = el.split('=');
      acc[key] = val;
      return acc;
    }, {});
    const signedPayload = `${elements.t}.${payload}`;
    const expected = crypto.createHmac('sha256', STRIPE_WEBHOOK_SECRET).update(signedPayload).digest('hex');
    return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(elements.v1 || ''));
  },
};

module.exports = StripeIntegration;
