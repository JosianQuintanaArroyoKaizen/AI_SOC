# AI-SOC Quick Start Guide

Get your AI-Augmented Security Operations Center running in **under 5 minutes**.

---

## Prerequisites

- **Docker** 23.0.15+ and **Docker Compose** 2.20.2+
- **16GB RAM** minimum (32GB recommended)
- **Linux**, **macOS**, or **Windows with WSL2**
- **100GB** available disk space

---

## Installation Steps

### 1. Clone Repository

```bash
git clone <repository-url>
cd AI_SOC
```

### 2. Run Setup Script

This automated script will:
- Create all required directories
- Generate SSL certificates
- Create `.env` from template
- Verify system requirements

```bash
./scripts/setup-configs.sh
```

### 3. Configure Passwords

Edit `.env` and replace **all** `CHANGE_ME` values with secure passwords:

```bash
nano .env  # or use your preferred editor
```

**Critical variables to set:**
- `INDEXER_PASSWORD` - Wazuh Indexer/Dashboard login
- `API_PASSWORD` - Wazuh API access

**Generate secure passwords:**
```bash
# Linux/macOS
openssl rand -base64 32

# Windows PowerShell
[System.Convert]::ToBase64String((1..32|%{Get-Random -Max 256}))
```

### 4. System Tuning (Linux Only)

```bash
# Required for OpenSearch/Wazuh Indexer
sudo sysctl -w vm.max_map_count=262144

# Make permanent
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### 5. Start Services

```bash
cd docker-compose
docker-compose -f phase1-siem-core.yml up -d
```

**Startup time:** 3-5 minutes

### 6. Verify Deployment

```bash
# Check service status
docker-compose -f phase1-siem-core.yml ps

# All services should show "Up" or "Up (healthy)"
```

### 7. Access Dashboard

**URL:** `https://localhost:443`

**Login:**
- Username: `admin`
- Password: [Your `INDEXER_PASSWORD` from `.env`]

**Note:** Accept the browser security warning for self-signed certificates.

---

## What's Next?

1. **Deploy Agents** - Install Wazuh agents on systems you want to monitor
2. **Configure Data Sources** - Set up log forwarding from your infrastructure
3. **Customize Rules** - Add organization-specific detection rules
4. **Set Up Alerts** - Configure email/Slack notifications
5. **Explore ML Pipeline** - Deploy Phase 2 for AI-powered threat detection

---

## Troubleshooting

**Containers won't start?**
```bash
# Check logs
docker-compose -f phase1-siem-core.yml logs

# Common fixes:
# - Verify .env has no CHANGE_ME values
# - On Linux: sudo sysctl -w vm.max_map_count=262144
# - Re-run: ./scripts/setup-configs.sh
```

**Can't access dashboard?**
```bash
# Verify dashboard is running
docker ps | grep wazuh-dashboard

# Check if it's healthy
docker-compose -f phase1-siem-core.yml ps
```

**Need more help?**
- See **[SETUP.md](SETUP.md)** for detailed troubleshooting
- Check **[Documentation Site](https://research.onyxlab.ai/)**

---

## Service Ports

| Service | Port | URL |
|---------|------|-----|
| Wazuh Dashboard | 443 | https://localhost:443 |
| Wazuh Indexer API | 9200 | https://localhost:9200 |
| Wazuh Manager API | 55000 | http://localhost:55000 |

---

## Common Commands

```bash
# Start services
docker-compose -f docker-compose/phase1-siem-core.yml up -d

# Stop services
docker-compose -f docker-compose/phase1-siem-core.yml down

# View logs
docker-compose -f docker-compose/phase1-siem-core.yml logs -f

# Restart specific service
docker-compose -f docker-compose/phase1-siem-core.yml restart wazuh-manager

# Check service health
docker-compose -f docker-compose/phase1-siem-core.yml ps
```

---

## Complete Documentation

For detailed information, see:

- **[SETUP.md](SETUP.md)** - Comprehensive setup guide with troubleshooting
- **[README.md](README.md)** - Project overview and research context
- **[Documentation Site](https://research.onyxlab.ai/)** - Full technical documentation

---

**Questions?** Contact: abdul.bari8019@coyote.csusb.edu
