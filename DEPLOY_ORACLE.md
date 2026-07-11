# Deploying E.D.I.T.H.'s server to Oracle Cloud (Japan instance)

This moves the server from Vercel (serverless, confirmed-working but not
built for persistent WebSocket sessions) to your existing Oracle Cloud VM
— a real, always-running process. This closes the instance-recycling
risk that became real once continuous streaming (/ws/live-stream)
started working.

## 1. SSH into your Japan instance

```
ssh -i /path/to/your/private-key.pem opc@<your-instance-public-ip>
```
(username is `opc` for Oracle Linux images, `ubuntu` for Ubuntu images —
use whichever matches what you actually provisioned)

## 2. Install Docker on the instance, if not already present

```
sudo apt-get update
sudo apt-get install -y docker.io git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```
(log out and back in after the usermod, or run `newgrp docker`, for the
group change to take effect without a full reboot)

## 3. Get the code onto the instance

Simplest: push your project to a GitHub repo (you likely already have
one from the Vercel deployment), then on the instance:
```
git clone https://github.com/YOUR_USERNAME/edith.git
cd edith
```

## 4. Set your real secrets as environment variables

Create a `.env` file directly on the instance (never commit this):
```
cat > .env << 'ENVEOF'
GEMINI_API_KEY=your-real-key-here
DEEPGRAM_API_KEY=your-real-key-here
ELEVENLABS_API_KEY=your-real-key-here
ELEVENLABS_VOICE_ID=uYXf8XasLslADfZ2MB4u
ENVEOF
```

## 5. Build and run the container

```
docker build -t edith-server .
docker run -d \
  --name edith \
  --restart unless-stopped \
  --env-file .env \
  -p 8000:8000 \
  edith-server
```
`--restart unless-stopped` means Docker itself will restart the
container if it crashes or the VM reboots — the actual "no more silent
instance recycling" guarantee this whole move was for.

## 6. Open the port in Oracle's firewall (a REAL, common gotcha)

Oracle Cloud instances have TWO layers of firewall — the OS's own
iptables/firewalld, AND a separate Oracle-managed "Security List"/
"Network Security Group" at the cloud console level. Both need port 8000
(or whichever port you choose) opened, or the container can be running
perfectly and still be completely unreachable from outside.

On the instance itself:
```
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || sudo service iptables save 2>/dev/null
```

In the Oracle Cloud Console: navigate to your instance's VCN → Security
Lists (or Network Security Groups, if configured that way) → Add Ingress
Rule → Source CIDR `0.0.0.0/0` → Destination Port Range `8000` → TCP.

## 7. Test it

```
curl http://<your-instance-public-ip>:8000/
```
Should return `{"status": "E.D.I.T.H. server is running", ...}` — the
same health check that worked on Vercel.

## 8. Update the frontend

In EdithHUD.jsx, change:
```
const DEFAULT_WS_URL = 'wss://edith-flame.vercel.app/ws';
```
to your new instance's address. NOTE: without a domain name and a
reverse proxy (nginx) terminating real TLS, this will be `ws://` (not
secure `wss://`) and a raw IP:port — genuinely fine for testing, but
browsers may show a "mixed content" warning if EdithHUD itself is served
over https. A real domain + Let's Encrypt certificate + nginx reverse
proxy is the natural next step for a fully clean setup, but isn't
required just to get this working and tested.

## Honest, known gaps in this first deployment

- No HTTPS/WSS yet (see step 8) — fine for testing, worth fixing before
  calling this "production."
- No process beyond Docker's own --restart flag watching container
  health — fine for now, a more real setup might add a proper health
  check/monitoring later.
- This hasn't been run end-to-end by anyone yet — same honest caveat as
  every other new piece of infrastructure in this project. Expect to hit
  at least one real snag (most likely candidates: the Oracle firewall
  step above, since that's a very commonly-missed gotcha specifically
  with Oracle Cloud; or a dependency needing a system library not yet
  installed on the base image).
