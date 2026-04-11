# Polymarket VPS Read-Only Setup (Best Option)

This sets up **monitoring-only** access from AI Holding Company to your Polymarket VPS.

Goal:
- Pull `bot.log`, `paper_trades.csv`, optional `bot_state.db` and `.env`
- Read service status (`systemctl is-active polymarket-bot`)
- No write/sudo control from the holding-company side

## 1) Local machine (Windows) - create SSH key

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\ai_capital_vps" -C "ai-capital-readonly"
Get-Content "$env:USERPROFILE\.ssh\ai_capital_vps.pub"
```

Copy the printed public key text.

## 2) VPS - create read-only user and authorize key

Run on VPS as your admin user:

```bash
sudo adduser --disabled-password --gecos "" aicg_ro
sudo mkdir -p /home/aicg_ro/.ssh
sudo chmod 700 /home/aicg_ro/.ssh
sudo bash -c 'cat > /home/aicg_ro/.ssh/authorized_keys'
# paste public key, then Ctrl+D
sudo chmod 600 /home/aicg_ro/.ssh/authorized_keys
sudo chown -R aicg_ro:aicg_ro /home/aicg_ro/.ssh
```

Grant read-only access to bot artifacts:

```bash
sudo apt-get update && sudo apt-get install -y acl
sudo setfacl -m u:aicg_ro:rx /home/ubuntu
sudo setfacl -m u:aicg_ro:rx /home/ubuntu/polymarket-bot
sudo setfacl -m u:aicg_ro:r /home/ubuntu/polymarket-bot/bot.log
sudo setfacl -m u:aicg_ro:r /home/ubuntu/polymarket-bot/paper_trades.csv
sudo setfacl -m u:aicg_ro:r /home/ubuntu/polymarket-bot/bot_state.db
sudo setfacl -m u:aicg_ro:r /home/ubuntu/polymarket-bot/.env
```

## 3) Local machine - test read-only access

```powershell
ssh -i "$env:USERPROFILE\.ssh\ai_capital_vps" aicg_ro@YOUR_VPS_IP "whoami && systemctl is-active polymarket-bot || true"
scp -i "$env:USERPROFILE\.ssh\ai_capital_vps" "aicg_ro@YOUR_VPS_IP:/home/ubuntu/polymarket-bot/bot.log" "$env:TEMP\polymarket_bot.log"
```

## 4) Enable in AI Holding Company config

Edit [config/projects.yaml](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/config/projects.yaml):

- `trading_bots -> polymarket -> remote_readonly -> enabled: true`
- Set:
  - `host`
  - `user` (`aicg_ro`)
  - `ssh_key_path` (`C:/Users/james/.ssh/ai_capital_vps`)

## 5) Run heartbeat with VPS data

```powershell
cd "C:\Users\james\OneDrive\Documents\Manganda LTD\AI Models\ai-holding-company"
python scripts/tool_router.py daily_brief --force
```

Check:
- [reports/daily_brief_latest.md](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/reports/daily_brief_latest.md)
- `## Remote Sync` section
- `data_source=remote_cache` for `polymarket`

## Safety note

`execute` is blocked when `remote_readonly.read_only: true` is enabled.
