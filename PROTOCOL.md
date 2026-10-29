# Reverse-Engineering Protocol Documentation: Urja Meter Ops Portal

This document outlines the internal architecture, network protocols, authentication mechanisms, data models, and reverse-engineered behavior of the legacy **Urja Meter Ops** portal (`https://urja-ops.flockenergy.tech`).

---

## 1. System Overview & Technology Stack

The Urja Meter Ops portal is an internal web application used by utility operations teams to inspect smart meter telemetry, verify electrical distribution hierarchy, and review interval energy readings.

Inspection of client bundles and server responses revealed the underlying technology stack:
* **Frontend Framework**: **SvelteKit** (compiled with Vite, utilizing modern Svelte 5 runes and client-side page routing under `_app/immutable/`).
* **Authentication Provider**: **Better-Auth** (`__Secure-better-auth.session_token`).
* **Server-Side Rendering**: SvelteKit SSR delivering HTML with embedded dehydrated state (`node_ids: [0, 2, 5]`) and dehydrated route data accessible via `/__data.json` endpoints serialized with the **Devalue** protocol.
* **Internal API Namespace**: `/portal/*` (JSON-backed endpoints).

---

## 2. Authentication & Session Lifecycle

### 2.1 The Login Flow
* **Endpoint**: `POST /login`
* **Content-Type**: `application/x-www-form-urlencoded`
* **Form Parameters**:
  * `email` (string): The operator's email (e.g., `operator@urja.local`). *Note: The prompt specified "Username", but the actual HTML input name is `email`.*
  * `password` (string): Operator password (`urja-ops-2026`).

### 2.2 SvelteKit CSRF Protection (Key Quirk)
Initial direct `POST` requests via script resulted in HTTP **403 Forbidden** with the body:
```text
Cross-site POST form submissions are forbidden
```
**Root Cause**: SvelteKit strictly validates the `Origin` header against the application host for all form actions to mitigate CSRF attacks. Automated clients that omit the `Origin` header (such as standard curl or unconfigured HTTP client libraries) are immediately rejected.
**Resolution**: The client must explicitly send:
```http
Origin: https://urja-ops.flockenergy.tech
Referer: https://urja-ops.flockenergy.tech/login
```

### 2.3 Session Cookie & Token Expiry
Upon valid authentication, the portal responds with HTTP `200 OK` (or `303 See Other`) and JSON:
```json
{
  "type": "redirect",
  "status": 303,
  "location": "/meters"
}
```
Along with the `Set-Cookie` header:
```http
Set-Cookie: __Secure-better-auth.session_token=<SESSION_TOKEN>; Max-Age=3600; Path=/; HttpOnly; Secure; SameSite=Lax
```
* **Cookie Lifetime**: Exactly 3,600 seconds (1 hour).
* **Unauthorized Behavior**: Unauthenticated requests or expired sessions to `/portal/*` yield:
  ```json
  HTTP/1.1 401 Unauthorized
  {"error": "unauthorized", "message": "A valid session is required."}
  ```
* **Gateway Mitigation**: Our `UrjaClient` implements token expiry tracking with a 120-second safety buffer and transparent 401-intercepting automatic re-login with mutex locking.

---

## 3. Discovered Endpoints & Protocols

Reverse-engineering the compiled JavaScript chunks (`5.C4dYcCRt.js`, `4.2Bgc2kUI.js`, `6.l777LXKL.js`) uncovered the following operational routes:

### 3.1 Meter Directory Search
* **Endpoint**: `GET /portal/meters/search?q={query}&page={page}`
* **Response**:
  ```json
  {
    "data": [
      {
        "meterId": "J100000",
        "serialNo": "SE33962",
        "make": "HPL",
        "phaseType": "single",
        "installStatus": "Decommissioned",
        "dtCode": "DT-001"
      }
    ],
    "total": 403,
    "page": 1,
    "pageSize": 20
  }
  ```
* **Characteristics**:
  * Paginates 20 records per page.
  * Free-text search on `q` matches against meter ID, hardware serial number, and make.

### 3.2 Distribution Transformers (DTs)
* **Endpoint**: `GET /portal/dts?page={page}`
* **Response**:
  ```json
  {
    "data": [
      {
        "code": "DT-001",
        "name": "Malviya Nagar DT 1",
        "feederCode": "F-001",
        "capacityKva": 100
      }
    ],
    "total": 40,
    "page": 1,
    "pageSize": 20
  }
  ```
* **Characteristics**:
  * Total of 40 distribution transformers across 2 pages.
  * Maps each DT to a parent `feederCode` and rated `capacityKva`.

### 3.3 Cryptographic Key Distribution
* **Endpoint**: `GET /portal/keys`
* **Response**:
  ```json
  {
    "data": {
      "signingSecret": "I3dZPPf5CgTp7JyGNMI8i6z8LFR7TmSR"
    }
  }
  ```
* **Purpose**: Distributes an HMAC-SHA256 shared secret used by the browser to sign bulk export requests.

### 3.4 Cryptographically Signed Bulk Export (The Fast Path)
* **Endpoint**: `GET /portal/export?page=1`
* **Required Headers**:
  * `x-timestamp`: Unix epoch timestamp in seconds (e.g., `1730187900`).
  * `x-signature`: Hex-encoded HMAC-SHA256 signature.
* **Signing Algorithm**:
  ```text
  canonical_string = f"{HTTP_METHOD}\n{PATH}\n{QUERY_STRING}\n{TIMESTAMP}"
  signature = HMAC_SHA256(key=signingSecret, message=canonical_string).hexdigest()
  ```
  *Example*: For `GET`, `/portal/export`, `page=1`, timestamp `1730187900`:
  ```text
  GET
  /portal/export
  page=1
  1730187900
  ```
* **Payload Structure**:
  Returns all **403 smart meters in a single HTTP response**, containing comprehensive metadata:
  ```json
  {
    "total": 403,
    "data": [
      {
        "meterId": "J100000",
        "serialNo": "SE33962",
        "make": "HPL",
        "phaseType": "single",
        "installStatus": "Decommissioned",
        "installType": "Whole Current",
        "build": "legacy",
        "dtCode": "DT-001",
        "hierarchy": {
          "zone": { "name": "Jaipur Zone 1", "code": "Z-01" },
          "circle": { "name": "Circle 1", "code": "C-01" },
          "division": { "name": "Division 1", "code": "D-01" },
          "subdivision": { "name": "Subdivision 1", "code": "SD-01" },
          "substation": { "name": "Substation 1", "code": "SS-01" },
          "feeder": { "name": "Feeder 1", "code": "F-001" },
          "dt": { "name": "Malviya Nagar DT 1", "code": "DT-001" }
        },
        "geo": {
          "lat": 26.938961002479868,
          "lng": 75.83095696146852
        }
      }
    ]
  }
  ```

### 3.5 Meter Geolocation Coordinates
* **Endpoint**: `GET /portal/meters/{meterId}/geo`
* **Response**:
  ```json
  {
    "data": {
      "latitude": "26.938961002479868",
      "longitude": "75.83095696146852"
    }
  }
  ```
* **Error**: Returns `404 Not Found` with `{"error": "not_found", "message": "Meter not found"}` if the meter does not exist.

### 3.6 Interval Energy Consumption Readings
* **Endpoint**: `GET /portal/meters/{meterId}/energy`
* **Response**:
  ```json
  {
    "data": [
      {
        "timestamp": "23/06/2026 23:30",
        "kwh": "48438.74",
        "kvah": "52313.84",
        "voltR": "226"
      },
      ...
    ]
  }
  ```
* **Characteristics**:
  * Typical meter logs 337 readings covering 7 days of 30-minute intervals ($7 \times 48 = 336 + 1$ boundary reading).
  * Timestamps use the human-readable format `DD/MM/YYYY HH:MM`.
  * Readings are returned as strings (`"48438.74"`, `"226"`) rather than native floating-point numbers.

---

## 4. Discovered Quirks, Surprises & Inconsistencies

### 4.1 Schema Divergence: `legacy` vs `v2` Telemetry Builds
When inspecting individual meter detail pages (`/meters/{id}/__data.json`), we discovered two mutually incompatible data representations generated by different generations of smart meters:

1. **`legacy` Build (238 meters)**:
   * Attributes are stored in an array of parameter objects:
     ```json
     "detail": {
       "data": [
         { "parameterName": "Meter ID", "parameterValue": "J100000" },
         { "parameterName": "Serial No", "parameterValue": "SE33962" },
         { "parameterName": "Make", "parameterValue": "HPL" },
         { "parameterName": "Phase Type", "parameterValue": "single" },
         { "parameterName": "Installation Status", "parameterValue": "Decommissioned" },
         { "parameterName": "Installation Type", "parameterValue": "Whole Current" }
       ]
     }
     ```
2. **`v2` Build (165 meters)**:
   * Attributes are packaged as an escaped JSON string nested under `classData`:
     ```json
     "detail": {
       "classData": "{\"installed_meter\":{\"MeterId\":\"J100004\",\"SerialNo\":\"SE65293\",\"Make\":\"Genus\",\"PhaseType\":\"single\",\"InstallationStatus\":\"Faulty\",\"InstallationType\":\"CT Operated\"}}"
     }
     ```
* **How our API service handles this**: Our `MeterService` transparently normalizes both schemas into a consistent `nameplate_attributes` dictionary so API consumers never have to deal with raw format discrepancies.

### 4.2 Non-Standard Timestamp Formatting
The energy telemetry uses Indian/UK standard date strings (`DD/MM/YYYY HH:MM`) without timezone indicators. Our API parses these into strict ISO 8601 UTC strings (`YYYY-MM-DDTHH:MM:00Z`) while preserving the original timestamp for auditability.

### 4.3 Meter Reading Cadence Variations
While modern smart meters report 337 readings across the 7-day period (30-minute interval profile), certain legacy meters (such as `J100050`) report only daily cumulative totals (8 readings across 8 days). Our energy summary engine handles varying sampling frequencies without crashing.

### 4.4 Data String Types
Numeric fields such as `latitude`, `longitude`, `kwh`, `kvah`, and `voltR` are returned by the portal as strings (e.g. `"226"`, `"48438.74"`). Our Pydantic models automatically cast and validate them as typed Python floats.
