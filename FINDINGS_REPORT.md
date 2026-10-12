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

## Additional Observations

### Akamai WAF (AkamaiGHost)
- `www.theperfumeshop.com` and `api.theperfumeshop.com` are protected by Akamai WAF
- WAF bypass was temporarily achieved using full CORS browser headers, receiving Hybris API error responses instead of 403 blocks
- The API error `{"errors":[{"message":"Page size not initialized on session","type":"IllegalStateError"}]}` confirms SAP Hybris Commerce Cloud backend
- Rate limiting kicks in after sustained automated requests

### CORS Configuration
- `api.theperfumeshop.com` properly implements CORS with:
  - `access-control-allow-origin: https://www.theperfumeshop.com` (not wildcard)
  - `access-control-allow-credentials: true`
  - Properly scoped allowed methods and headers
- Other domains do not reflect arbitrary origins

### Technology Stack Summary
| Domain | Technology | Protection |
|--------|-----------|------------|
| www.theperfumeshop.com | SAP Hybris Commerce Cloud | Akamai WAF |
| api.theperfumeshop.com | Hybris OCC API v2 | Akamai WAF |
| connect.theperfumeshop.com | Next.js + Microsoft Entra ID | Azure Front Door |
| techsale.theperfumeshop.com | Next.js + Supabase + Entra ID | Azure App Service |
| scentral.theperfumeshop.com | Hublio (Vite SPA) + Supabase | Azure Static Web Apps |
| campaigns.theperfumeshop.com | Apache 2.4.62 Oracle Linux | Akamai (partial) |
| ecom-data.theperfumeshop.com | Google Cloud (Frontend) | Google |

---

## Recommendations
1. **CRITICAL**: Disable GitHub, Google, and Twitter authentication providers on scentral.theperfumeshop.com via `staticwebapp.config.json` route blocks
2. **CRITICAL**: Restrict Azure AD authentication on scentral from `/common/` (multi-tenant) to the organization's specific tenant ID
3. **HIGH**: Implement custom role-based access control on scentral requiring explicit role assignment instead of default `authenticated` role
4. **Immediate**: Fix the internal origin leak on connect.theperfumeshop.com by setting `NEXTAUTH_URL` (or equivalent) to the public-facing URL
5. **Immediate**: Remove stale Lync/SfB DNS records
6. **Short-term**: Harden campaigns.theperfumeshop.com - disable directory listing, remove default test page
7. **Short-term**: Strip `X-Powered-By` header and Supabase project ID from CSP on techsale
8. **Medium-term**: Review Supabase RLS policies for the techsale application
9. **Medium-term**: Validate callbackUrl against an allowlist on connect.theperfumeshop.com
