# Deployment Guide — vectoryz v0.1

Plug-and-play deployment of vectoryz on a Hetzner-equivalent VM.

## Hardware recommendations

vectoryz runs Ollama (LLM-inference) + Python (wrapper + audit-stack).
The LLM-inference is the heavy load; everything else is light.

### Minimum (text-only + small models)

| Component | Spec |
|---|---|
| CPU | 8 vCPU (AMD/Intel modern) |
| RAM | 32 GB |
| GPU | optional — CPU-inference works for 7B-class |
| Disk | 100 GB SSD (models + state) |
| Network | 1 Gbit/s (web-search latency-sensitive) |
| OS | Ubuntu 24.04 LTS / Debian 13 |

**Equivalent on Hetzner**: CCX23 (8 vCPU, 32 GB RAM, AMD-dedicated) — ~25€/month.
Models: qwen2.5:7b or llama3.1:8b. Response-time ~5-15s deep-tier.

### Recommended (production-grade quality)

| Component | Spec |
|---|---|
| CPU | 16 vCPU |
| RAM | 64 GB |
| GPU | Nvidia L4 / A10 / RTX 4000 Ada (24 GB VRAM) |
| Disk | 250 GB NVMe |
| Network | 1 Gbit/s + IPv6 |
| OS | Ubuntu 24.04 LTS |

**Equivalent on Hetzner**: GEX44 / GX44 (GPU-class) — ~200€/month.
Models: dolphin-mixtral:8x7b or larger. Response-time ~2-5s deep-tier.

### Cloud-provider alternatives (Hetzner-equivalent class)

- **Hetzner Cloud** (German, EU, DSGVO-friendly) — recommended
- **OVHcloud** (French, EU)
- **Scaleway** (French, EU)
- **DigitalOcean** (US, lower latency only for non-EU users)
- **AWS EC2** g5.xlarge (GPU) — overkill, but works
- **Self-hosted bare-metal** — best price/performance for >2 servers

For DSGVO-compliant EU-hosting: **stick to Hetzner / OVH / Scaleway**.

## Software stack

| Layer | Software | Why |
|---|---|---|
| OS | Ubuntu 24.04 LTS | LTS, broad support |
| LLM-inference | Ollama (llama.cpp underneath) | simple model-registry + GPU-auto |
| Reverse proxy + TLS | Caddy v2 | auto Let's Encrypt, no boilerplate |
| Python runtime | 3.10+ | matches pyproject.toml requires-python |
| Database | SQLite (via stdlib) | zero-ops, embedded |
| Process supervisor | systemd | distro-default |

## Setup walkthrough

```bash
# 1. Server prep (Ubuntu 24.04)
sudo apt update && sudo apt install -y python3-venv python3-pip sqlite3 curl

# 2. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama

# 3. Pull a model (start with qwen2.5:7b for minimum-spec)
ollama pull qwen2.5:7b
# (for production: ollama pull dolphin-mixtral:8x7b — needs 24GB+ RAM)

# 4. Install Caddy
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/setup.deb.sh' | sudo -E bash
sudo apt install -y caddy
sudo systemctl enable --now caddy

# 5. Install vectoryz
mkdir -p /opt/vectoryz && cd /opt/vectoryz
python3 -m venv .venv
.venv/bin/pip install vectoryz==0.1.0
# (or from source: .venv/bin/pip install -e /path/to/vectoryz-source/)

# 6. Create state-db directory
sudo mkdir -p /var/lib/vectoryz
sudo chown vectoryz:vectoryz /var/lib/vectoryz

# 7. Install systemd unit
sudo cp examples/systemd/vectoryz.service.example /etc/systemd/system/vectoryz.service
# Edit /etc/systemd/system/vectoryz.service — set DEFAULT_MODEL to your model
sudo systemctl daemon-reload
sudo systemctl enable --now vectoryz

# 8. Configure Caddy reverse-proxy
sudo cp examples/caddy/Caddyfile.example /etc/caddy/Caddyfile
sudo vim /etc/caddy/Caddyfile  # replace yoursite.example with YOUR domain
sudo systemctl reload caddy

# 9. Site-init (your impressum/datenschutz/branding)
cd examples/static-www
cp site.config.example site.config
vim site.config  # fill in YOUR_DOMAIN, YOUR_LEGAL_NAME, etc.
./init_site.sh
sudo cp -r _output/* /var/www/vectoryz/

# 10. DNS: point yoursite.example → YOUR_SERVER_IP (A + AAAA records)
# Caddy auto-issues Let's Encrypt cert on first reload.

# 11. Verify
curl https://yoursite.example/api/version
```

## Languages

vectoryz v0.1 ships with **German** as primary UI-language (impressum,
datenschutz, doctrine-strings). Other languages welcome as user-contributions:

- Pipeline-modules are language-aware (Babel-Cascade FastText lid.176
  detects 176 languages), but UX-text in static-www is German-only at v0.1.
- To localize: copy `examples/static-www/index.html` etc. to `index.<lang>.html`
  and translate. Then add language-selector to your deployed `index.html`.
- Per [[smartfaul]]-doctrine: efficient + safe at v0.1; multi-lang-UX later
  release.

## Per [[brand_priority_fetch_doctrine]] (v0.2+)

Once your deployment is stable, consider adding brand-priority-fetch:
when users query for branded-entities (products, bands, companies),
the system probes `<brand>.com` FIRST before generic web-search.
This defends against [[doff_faul_pattern]] (search-result-fixation).

## Compliance notes

- **DSGVO** (EU): the package + Caddy config + reverse-proxy give you the
  technical baseline. You're responsible for: legal-entity, impressum,
  datenschutzerklärung, cookie-discipline, DSA-§17/§20 endpoints.
- **AI-act** (EU, in-effect 2025+): vectoryz outputs are flagged as AI
  via factampel + tribunal-tags. Watermarking / source-attribution
  is built into the answer-format. Verify per-jurisdiction obligations.
- **License**: vectoryz is MIT — your derivative-deployment is yours.

## Per [[wer-fehler-findet]]-challenge

This deployment-guide IS v0.1 — there will be errors. Found something
unclear / wrong / underspecified? File an issue.
