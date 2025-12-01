# AI-SOC Setup Guide

Complete setup instructions for deploying the AI-Augmented Security Operations Center.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Detailed Setup](#detailed-setup)
4. [Troubleshooting](#troubleshooting)
5. [First-Time Access](#first-time-access)

---

## Prerequisites

### System Requirements

**Minimum:**
- 16GB RAM
- 4 CPU cores
- 100GB available disk space
- Docker Engine 23.0.15+
- Docker Compose 2.20.2+

**Recommended:**
- 32GB RAM
- 8 CPU cores
- 250GB SSD
- Ubuntu 22.04 LTS / macOS 13+ / Windows 11 with WSL2

### Software Requirements

- **Docker Engine**: [Install Docker](https://docs.docker.com/engine/install/)
- **Docker Compose**: [Install Docker Compose](https://docs.docker.com/compose/install/)
- **Git**: For cloning the repository
- **OpenSSL**: For certificate generation (usually pre-installed)

---

## Quick Start

For users who want to get up and running immediately:

```bash
# 1. Clone the repository
git clone <repository-url>
cd AI_SOC

# 2. Run the automated setup script
./scripts/setup-configs.sh

# 3. Edit the .env file with secure passwords
nano .env  # or use your preferred editor

# 4. (Linux only) Set kernel parameters
sudo sysctl -w vm.max_map_count=262144

# 5. Start the SIEM stack
cd docker-compose
docker-compose -f phase1-siem-core.yml up -d

# 6. Access the dashboard
# Open browser: https://localhost:443
# Login: admin / [INDEXER_PASSWORD from .env]
```

---

## Detailed Setup

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd AI_SOC
```

### Step 2: Run Configuration Setup

The setup script will:
- Create all required configuration directories
- Generate `.env` from `.env.example`
- Verify essential configuration files
- Generate SSL certificates
- Check system requirements

```bash
./scripts/setup-configs.sh
```

**Expected Output:**
```
================================
AI-SOC Configuration Setup
================================

[Step 1/5] Creating configuration directories...
[CREATED] Directory: config/wazuh-indexer/certs
[CREATED] Directory: config/wazuh-manager/certs
...

[Step 2/5] Checking environment configuration...
[CREATED] .env file from template
[ACTION REQUIRED] Edit .env and set secure passwords!

[Step 3/5] Verifying core configuration files...
[OK] config/wazuh-indexer/opensearch.yml
[OK] config/wazuh-manager/ossec.conf
...

[Step 4/5] Checking SSL certificates...
[INFO] SSL certificates not found. Generating...
[OK] Root CA generated
[OK] Wazuh Indexer certificates generated
...

[Step 5/5] Verifying system requirements...
[OK] Docker installed (version: 24.0.7)
[OK] Docker Compose installed (version: 2.23.0)
...
```

### Step 3: Configure Environment Variables

Edit the `.env` file and replace all `CHANGE_ME` values with secure passwords:

```bash
nano .env  # or use vim, code, etc.
```

**Critical Variables to Set:**

```bash
# Wazuh Credentials
INDEXER_PASSWORD=YourSecurePassword123!
API_PASSWORD=YourSecurePassword456!

# PostgreSQL (if using Phase 2+)
POSTGRES_PASSWORD=YourSecurePassword789!

# Redis (if using Phase 2+)
REDIS_PASSWORD=YourSecurePassword012!
```

**Generate Secure Passwords:**

```bash
# Linux/Mac
openssl rand -base64 32

# Windows PowerShell
[System.Convert]::ToBase64String((1..32|%{Get-Random -Max 256}))

# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 4: System Tuning (Linux Only)

OpenSearch/Wazuh Indexer requires increasing the virtual memory map count:

```bash
# Temporary (until reboot)
sudo sysctl -w vm.max_map_count=262144

# Permanent
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### Step 5: Configure Network Interface

Edit `.env` to set the network interface for packet capture:

```bash
# Find your network interface
ip addr show        # Linux
ifconfig            # macOS
ipconfig /all       # Windows

# Set in .env
MONITOR_INTERFACE=eth0  # Replace with your interface
```

**Common Interface Names:**
- Linux: `eth0`, `ens33`, `enp0s3`
- macOS: `en0`, `en1`
- Windows (WSL2): `eth0`

### Step 6: Start the SIEM Stack

```bash
cd docker-compose
docker-compose -f phase1-siem-core.yml up -d
```

**Monitor Startup:**

```bash
# Watch container logs
docker-compose -f phase1-siem-core.yml logs -f

# Check container status
docker-compose -f phase1-siem-core.yml ps
```

**Expected Startup Time:** 3-5 minutes for all services to be healthy.

### Step 7: Verify Deployment

```bash
# Check all containers are running
docker-compose -f phase1-siem-core.yml ps

# Should show all services as "Up" or "Up (healthy)"
```

**Health Check Commands:**

```bash
# Wazuh Indexer
curl -k -u admin:$INDEXER_PASSWORD https://localhost:9200/_cluster/health

# Wazuh Manager
curl http://localhost:55000/health

# Wazuh Dashboard
curl -k https://localhost:443/status
```

---

## First-Time Access

### Wazuh Dashboard

**URL:** `https://localhost:443`

**Default Credentials:**
- Username: `admin`
- Password: `[INDEXER_PASSWORD from .env]`

**Note:** You'll see a browser security warning for self-signed certificates. This is expected. Click "Advanced" and proceed.

### Service Ports

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Wazuh Dashboard | 443 | HTTPS | Web UI |
| Wazuh Indexer | 9200 | HTTPS | REST API |
| Wazuh Manager API | 55000 | HTTP | Management API |
| Wazuh Agent Enrollment | 1515 | TCP | Agent registration |
| Wazuh Agent Connection | 1514 | TCP | Agent communication |
| Syslog | 514 | UDP | Syslog ingestion |

---

## Troubleshooting

### Common Issues

#### 1. Docker Containers Won't Start

**Symptom:** Containers exit immediately or show "Exited (1)" status.

**Solution:**

```bash
# Check logs for specific service
docker-compose -f phase1-siem-core.yml logs wazuh-indexer

# Common causes:
# - Missing .env file → Run setup-configs.sh
# - vm.max_map_count too low (Linux) → sudo sysctl -w vm.max_map_count=262144
# - Missing SSL certificates → Run ./scripts/generate-certs.sh
```

#### 2. "Config File Not Found" Errors

**Symptom:** Docker mount errors like `cannot mount config file`.

**Solution:**

```bash
# Verify config files exist
ls -la config/suricata/suricata.yaml
ls -la config/wazuh-indexer/opensearch.yml

# If missing, ensure you cloned the repo correctly
git pull origin master

# Re-run setup
./scripts/setup-configs.sh
```

#### 3. Certificate Errors

**Symptom:** Services can't connect due to SSL/TLS errors.

**Solution:**

```bash
# Regenerate certificates
rm -rf config/*/certs/*
rm -rf config/root-ca/*
./scripts/generate-certs.sh
```

#### 4. Permission Denied Errors

**Symptom:** Container logs show permission errors.

**Solution:**

```bash
# Fix certificate permissions
chmod 600 config/*/certs/*-key.pem
chmod 644 config/*/certs/*.pem

# Fix script permissions
chmod +x scripts/*.sh
```

#### 5. Wazuh Indexer Won't Start

**Symptom:** `wazuh-indexer` container exits or unhealthy.

**Check:**

```bash
# 1. Verify vm.max_map_count (Linux)
sysctl vm.max_map_count  # Should be >= 262144

# 2. Check available memory
free -h  # Should have 4GB+ free

# 3. Check logs
docker logs wazuh-indexer
```

#### 6. Network Interface Not Found (Suricata/Zeek)

**Symptom:** Suricata or Zeek containers fail with "interface not found".

**Solution:**

```bash
# 1. Find your network interface
ip addr show  # Linux
ifconfig      # macOS

# 2. Update .env
MONITOR_INTERFACE=eth0  # Replace with your interface

# 3. Restart containers
docker-compose -f phase1-siem-core.yml restart suricata zeek
```

#### 7. "Cannot Connect to Dashboard"

**Symptom:** Browser can't reach `https://localhost:443`.

**Check:**

```bash
# 1. Verify dashboard is running
docker ps | grep wazuh-dashboard

# 2. Check if port is bound
netstat -an | grep 443  # Linux/Mac
netstat -an | findstr 443  # Windows

# 3. Check container logs
docker logs wazuh-dashboard
```

### Advanced Diagnostics

**View All Container Logs:**
```bash
docker-compose -f phase1-siem-core.yml logs --tail=100
```

**Restart Specific Service:**
```bash
docker-compose -f phase1-siem-core.yml restart wazuh-indexer
```

**Complete Reset (CAUTION: Deletes all data):**
```bash
docker-compose -f phase1-siem-core.yml down -v
./scripts/setup-configs.sh
docker-compose -f phase1-siem-core.yml up -d
```

---

## Post-Deployment Configuration

### 1. Deploy Wazuh Agents

To monitor additional systems, deploy Wazuh agents:

```bash
# Linux agent installation
curl -so wazuh-agent.deb https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.8.2-1_amd64.deb
sudo WAZUH_MANAGER='<manager-ip>' dpkg -i wazuh-agent.deb
sudo systemctl daemon-reload
sudo systemctl enable wazuh-agent
sudo systemctl start wazuh-agent
```

### 2. Configure Custom Rules

Add custom detection rules:

```bash
# Create custom rule file
nano config/wazuh-manager/rules/local_rules.xml

# Restart Wazuh Manager to apply
docker-compose -f phase1-siem-core.yml restart wazuh-manager
```

### 3. Configure Alerting

Edit alert destinations in Wazuh Dashboard:
1. Navigate to **Settings** → **Configuration**
2. Configure email/Slack notifications
3. Set alert thresholds

### 4. Import Security Datasets (Optional)

For testing and ML training:

```bash
# Download datasets
cd datasets
./download-cicids2017.sh  # If script exists

# Configure log ingestion path in docker-compose
```

---

## Security Best Practices

1. **Change Default Passwords:** Never use example passwords in production
2. **Enable Firewall:** Restrict access to dashboard and API ports
3. **Use Valid SSL Certificates:** Replace self-signed certs with CA-issued for production
4. **Regular Updates:** Keep Docker images and configs updated
5. **Backup Regularly:** Backup `.env`, configs, and Wazuh data volumes
6. **Monitor Logs:** Regularly review Wazuh alerts and system logs
7. **Network Segmentation:** Deploy SIEM on isolated management network
8. **Rotate Credentials:** Change passwords every 90 days

---

## Maintenance Commands

### Backup

```bash
# Backup configuration
tar -czf ai-soc-config-backup-$(date +%Y%m%d).tar.gz config/ .env

# Backup Docker volumes
docker run --rm -v wazuh-indexer-data:/data -v $(pwd):/backup ubuntu tar -czf /backup/wazuh-data-backup-$(date +%Y%m%d).tar.gz /data
```

### Update Services

```bash
# Pull latest images
docker-compose -f phase1-siem-core.yml pull

# Restart with new images
docker-compose -f phase1-siem-core.yml up -d
```

### Monitor Resource Usage

```bash
# Container stats
docker stats

# Disk usage
docker system df
```

---

## Getting Help

- **Documentation:** See `README.md` for architecture details
- **Wazuh Docs:** https://documentation.wazuh.com/
- **Docker Logs:** `docker-compose -f phase1-siem-core.yml logs -f`
- **Issues:** Check existing GitHub issues or create a new one

---

## Next Steps

After successful deployment:

1. **Configure Data Sources:** Set up log forwarding from monitored systems
2. **Deploy Agents:** Install Wazuh agents on endpoints
3. **Customize Rules:** Add organization-specific detection rules
4. **Set Up Alerts:** Configure notification channels (email, Slack, etc.)
5. **Phase 2 Deployment:** Deploy AI/ML capabilities (see `docker-compose/phase2-ml-pipeline.yml`)

---

**Last Updated:** 2025-12-01
**Version:** 1.0.0
