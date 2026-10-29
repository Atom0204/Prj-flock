# Engineering Reflection: Urja Meter Ops Gateway

---

### 1. What assumptions did you make?

1. **Read-Only Upstream & Session Longevity**:
   We assumed the Urja Meter Ops portal is an internal operational system that does not undergo high-frequency writes during operational hours. Given the 1-hour session cookie (`Max-Age=3600`) and the presence of an HMAC-signed bulk export endpoint, we assumed an in-memory index synchronized periodically (default TTL: 300 seconds) provides an optimal balance between freshness, upstream portal protection, and sub-millisecond query latency.

2. **Geographical Coordinates Reference System**:
   We assumed the coordinates provided by `/portal/meters/{id}/geo` (`latitude: ~26.93`, `longitude: ~75.83`) are in standard WGS84 decimal degrees (placing the fleet in Jaipur, Rajasthan, India) and that great-circle (Haversine) spherical distance approximations are sufficiently accurate for local utility queries up to 50 km.

3. **Hierarchy Completeness & Granularity**:
   We assumed the utility follows a strict 7-tier distribution hierarchy: `Zone` → `Circle` → `Division` → `Subdivision` → `Substation` → `Feeder` → `Distribution Transformer (DT)`. Where meters have missing tiers in edge cases, we assumed generating synthetic placeholder nodes (`UNKNOWN_DIVISION`) is preferable to dropping records or raising 500 errors.

4. **Timezone Interpretation**:
   Since the portal provides timestamps in the unadorned format `DD/MM/YYYY HH:MM` for an Indian power utility, we assumed UTC/IST normalization without offset shifts, preserving the original string while emitting ISO 8601 strings.

---

### 2. Which part was the most difficult, and how did you get unstuck?

The most challenging obstacle was **uncovering the HMAC-SHA256 signature scheme** required to access the `/portal/export` endpoint.

* **Initial Discovery**: Initially, navigating the portal gave the impression that meters could only be queried through the paginated `/portal/meters/search` endpoint (20 items at a time across 21 pages).
* **Investigation**: By downloading and inspecting the compiled Vite/SvelteKit frontend bundles (specifically `4.2Bgc2kUI.js` and `DHWw2r--.js`), we observed a client-side Web Crypto call `crypto.subtle.sign('HMAC', ...)` tied to an "Export" button on the Transformers page.
* **The Breakthrough**: Deobfuscating the JavaScript revealed that the portal fetches a secret key from `/portal/keys` and signs a newline-delimited canonical string:
  ```text
  GET
  /portal/export
  page=1
  <unix_timestamp_seconds>
  ```
  And attaches `x-timestamp` and `x-signature` headers. Implementing this exact algorithm in Python immediately unlocked the fast-path full dataset retrieval in a single 200ms request!

---

### 3. If you had another day, what would you improve?

1. **Persistent Relational / Spatial Database (PostgreSQL + PostGIS)**:
   While our current in-memory data store is lightning fast for 403 meters, a utility managing 500,000+ smart meters would outgrow process memory. We would introduce SQLite/PostgreSQL with PostGIS for native spatial indexing (`ST_DWithin`, R-tree indexes) and SQL-based complex joins across the hierarchy.

2. **Historical Time-Series Database Integration (TimescaleDB / ClickHouse)**:
   Energy interval readings ($337 \text{ readings} \times 403 \text{ meters} = 135,000+ \text{ data points}$) grow continuously. Moving interval data to a time-series engine would enable analytical rollups (e.g., peak load, aggregate DT feeder losses, transformer overload risk alerts).

3. **Webhook & Anomaly Detection Pipeline**:
   We would build a proactive background monitor detecting voltage sags ($< 210\text{V}$), phase unbalance, or tamper states (meters switching to `Faulty`), triggering Webhook alerts to utility dispatchers.

4. **OAuth2 / API Key Rate Limiting Layer**:
   Add client API key management with token bucket rate limiting (e.g., via Redis) to guard the gateway against rogue internal scripts.

---

### 4. What mistake did you make while solving this?

When first testing form submission to `/login` via Python's `requests` library, the portal returned HTTP `403 Forbidden: Cross-site POST form submissions are forbidden`.

Initially, we assumed the portal required a hidden CSRF token or session cookie to be scraped from the login page HTML. After wasting a few minutes searching the DOM for hidden `<input type="hidden" name="csrf">` fields (which didn't exist), we realized this was SvelteKit's built-in `checkCrossOrigin` server protection. Because standard HTTP libraries don't include an `Origin` header on requests by default, SvelteKit flagged it as an illegal cross-site submission. Adding `"Origin": "https://urja-ops.flockenergy.tech"` immediately resolved the issue.

A secondary bug occurred in our initial pytest run where a `NameError: UrjaClientError` was encountered because `UrjaNotFoundError` was imported without its parent class, resulting in an unhandled 500 during a 404 test. Fixing the import restored all 13 unit tests to green.

---

### 5. If you were reviewing your own submission, what would you criticise?

1. **Memory Growth at Massive Scale**:
   Our decision to cache all 403 meters and their hierarchy in process RAM delivers blazing $< 2\text{ms}$ response times, but is fundamentally memory-bound. If the utility fleet scaled to 5 million meters, holding raw dictionaries in RAM would cause substantial memory pressure. We clearly documented this scaling boundary in the README.

2. **On-Demand Scraping for Meter Nameplates**:
   Because the `/portal/export` endpoint provides most attributes but leaves deep SSR nameplate attributes inside `/meters/{id}/__data.json`, fetching full details for an uncached meter requires an on-demand HTTP fetch to the portal. While we added a nameplate LRU cache, a batch-crawler warming this on startup would ensure zero-latency cold hits.

3. **Coupling to Specific Portal Frontend Routes**:
   Relying on `/meters/{id}/__data.json` means that if the upstream utility rebuilds their SvelteKit frontend and changes route bundle hashes or SSR serialization, the nameplate parser might need updating. A robust production deployment would use integration tests scheduled against a staging instance to flag any upstream bundle changes.
