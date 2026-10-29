import os
import markdown
import subprocess

REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
README_PATH = os.path.join(REPO_DIR, "README.md")
PROTOCOL_PATH = os.path.join(REPO_DIR, "PROTOCOL.md")
REFLECTION_PATH = os.path.join(REPO_DIR, "REFLECTION.md")

with open(README_PATH, "r", encoding="utf-8") as f:
    readme_md = f.read()

with open(PROTOCOL_PATH, "r", encoding="utf-8") as f:
    protocol_md = f.read()

with open(REFLECTION_PATH, "r", encoding="utf-8") as f:
    reflection_md = f.read()

md_extensions = ["extra", "tables", "fenced_code", "codehilite", "toc"]

readme_html = markdown.markdown(readme_md, extensions=md_extensions)
protocol_html = markdown.markdown(protocol_md, extensions=md_extensions)
reflection_html = markdown.markdown(reflection_md, extensions=md_extensions)

full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Flock Energy - Engineering Take-Home Submission</title>
  <style>
    @page {{
      size: A4;
      margin: 18mm 16mm 18mm 16mm;
      @bottom-right {{
        content: counter(page);
      }}
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      color: #1e293b;
      line-height: 1.55;
      font-size: 10.5pt;
      background: #ffffff;
      margin: 0;
      padding: 0;
    }}
    .cover-banner {{
      background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
      color: #ffffff;
      padding: 2.5rem 2rem;
      border-radius: 12px;
      margin-bottom: 2rem;
      box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }}
    .cover-title {{
      font-size: 24pt;
      font-weight: 800;
      margin: 0 0 0.5rem 0;
      letter-spacing: -0.02em;
    }}
    .cover-subtitle {{
      font-size: 13pt;
      color: #93c5fd;
      font-weight: 500;
      margin-bottom: 1.5rem;
    }}
    .github-callout {{
      background: #ffffff;
      color: #0f172a;
      padding: 1.25rem 1.5rem;
      border-radius: 8px;
      border-left: 6px solid #2563eb;
      margin-top: 1rem;
    }}
    .github-link {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
      font-size: 12pt;
      font-weight: 700;
      color: #2563eb;
      word-break: break-all;
      text-decoration: none;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.75rem;
      margin-top: 1rem;
      font-size: 9.5pt;
    }}
    .section-divider {{
      page-break-before: always;
      margin-top: 2rem;
      padding-top: 1.5rem;
      border-top: 2px solid #e2e8f0;
    }}
    h1 {{
      font-size: 18pt;
      font-weight: 700;
      color: #0f172a;
      border-bottom: 2px solid #e2e8f0;
      padding-bottom: 0.4rem;
      margin-top: 1.5rem;
      margin-bottom: 1rem;
    }}
    h2 {{
      font-size: 14pt;
      font-weight: 600;
      color: #1e3a8a;
      margin-top: 1.25rem;
      margin-bottom: 0.5rem;
    }}
    h3 {{
      font-size: 11.5pt;
      font-weight: 600;
      color: #334155;
      margin-top: 1rem;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 1rem 0;
      font-size: 9pt;
    }}
    th, td {{
      border: 1px solid #cbd5e1;
      padding: 6px 10px;
      text-align: left;
    }}
    th {{
      background-color: #f1f5f9;
      font-weight: 600;
      color: #334155;
    }}
    tr:nth-child(even) {{
      background-color: #f8fafc;
    }}
    code {{
      font-family: "SFMono-Regular", Consolas, monospace;
      background: #f1f5f9;
      padding: 0.15em 0.35em;
      border-radius: 4px;
      font-size: 9pt;
      color: #0f172a;
    }}
    pre {{
      background: #0f172a;
      color: #f8fafc;
      padding: 1rem;
      border-radius: 8px;
      overflow-x: auto;
      font-size: 8.5pt;
      line-height: 1.45;
      margin: 1rem 0;
    }}
    pre code {{
      background: transparent;
      color: inherit;
      padding: 0;
    }}
    blockquote {{
      border-left: 4px solid #3b82f6;
      margin: 1rem 0;
      padding: 0.5rem 1rem;
      background: #eff6ff;
      color: #1e40af;
      border-radius: 0 6px 6px 0;
    }}
    ul, ol {{
      margin: 0.5rem 0 1rem 1.5rem;
      padding: 0;
    }}
    li {{
      margin-bottom: 0.25rem;
    }}
  </style>
</head>
<body>

  <div class="cover-banner">
    <div class="cover-title">Flock Energy — Engineering Take-Home Submission</div>
    <div class="cover-subtitle">Urja Meter Ops Clean API Gateway & Reverse-Engineering Protocol</div>
    
    <div class="github-callout">
      <div style="font-size: 10pt; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; color: #64748b; margin-bottom: 4px;">
        Public GitHub Repository Link
      </div>
      <a href="https://github.com/Atom0204/Prj-flock" class="github-link">https://github.com/Atom0204/Prj-flock</a>
      <div style="font-size: 8.5pt; color: #475569; margin-top: 6px;">
        Clone command: <code>git clone https://github.com/Atom0204/Prj-flock.git</code>
      </div>
    </div>

    <div class="meta-grid">
      <div><strong>Candidate:</strong> Atom0204 (shivamkashyap0204@gmail.com)</div>
      <div><strong>Role:</strong> Backend / Full-Stack Engineer Take-Home</div>
      <div><strong>Target System:</strong> Urja Meter Ops (https://urja-ops.flockenergy.tech)</div>
      <div><strong>Stack:</strong> Python 3.12, FastAPI, Pydantic v2, Pytest, Leaflet, Chart.js</div>
    </div>
  </div>

  <div>
    <h2>Submission Table of Contents</h2>
    <ul>
      <li><strong>Part 1: Front-Door Guide (README)</strong> — Architecture, installation, how to run, sample requests, trade-offs, and scaling analysis.</li>
      <li><strong>Part 2: Reverse-Engineering Protocol (PROTOCOL.md)</strong> — Detailed analysis of portal auth, SvelteKit CSRF headers, 1-hour session tokens, HMAC-SHA256 export signing, and legacy vs v2 schema normalization.</li>
      <li><strong>Part 3: Engineering Reflection (REFLECTION.md)</strong> — Complete answers to all evaluation reflection prompts (assumptions, obstacles, what would be improved with another day, mistakes made, self-critique).</li>
      <li><strong>Part 4: Optional Extensions Delivered</strong> — Full implementation of all 6 optional extensions (Network hierarchy tree, local query/search layer, geospatial Haversine proximity, session auto-recovery, HMAC bulk fast-path, and modern dashboard UI).</li>
    </ul>
  </div>

  <div class="section-divider"></div>
  <h1>Part 1: Project README & System Guide</h1>
  {readme_html}

  <div class="section-divider"></div>
  <h1>Part 2: PROTOCOL.md — Reverse Engineering Analysis</h1>
  {protocol_html}

  <div class="section-divider"></div>
  <h1>Part 3: REFLECTION.md — Engineering Reflection & Self-Critique</h1>
  {reflection_html}

</body>
</html>
"""

html_path = os.path.join(REPO_DIR, "submission_document.html")
pdf_path = os.path.join(REPO_DIR, "Flock_Energy_Take_Home_Submission.pdf")

with open(html_path, "w", encoding="utf-8") as f:
    f.write(full_html)

print(f"Generated HTML at {html_path}")

# Run Edge to print to PDF
edge_paths = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
]

browser_exe = next((p for p in edge_paths if os.path.exists(p)), None)

if browser_exe:
    cmd = [
        browser_exe,
        "--headless",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={pdf_path}",
        html_path
    ]
    print(f"Generating PDF using {os.path.basename(browser_exe)}...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1000:
        print(f"SUCCESS: Created PDF at {pdf_path} (size: {os.path.getsize(pdf_path)} bytes)")
    else:
        print("PDF generation returned:", res.stderr)
else:
    print("Browser executable not found.")
