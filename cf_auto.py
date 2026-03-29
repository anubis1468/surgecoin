"""
SurgeCoin Cloudflare One-File Automation
- Generates Cloudflare Worker backend (KV-powered)
- Writes wrangler.toml
- Writes worker.py
- Deploys via `wrangler deploy`
- Verifies health

Requirements:
    - Python 3
    - Cloudflare Wrangler CLI installed (`npm install -g wrangler`)
    - Cloudflare account + API token configured for Wrangler
"""

import json
import subprocess
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
CF_DIR = ROOT / "backend_cf"
SRC_DIR = CF_DIR / "src"
WORKER_NAME = "surgecoin-backend"
KV_BINDING = "SURGECOIN_DB"


def log(msg: str):
    print(msg)


def write_wrangler():
    CF_DIR.mkdir(parents=True, exist_ok=True)
    content = f"""name = "{WORKER_NAME}"
main = "src/worker.py"
compatibility_date = "2024-09-01"

[[kv_namespaces]]
binding = "{KV_BINDING}"
id = "{KV_BINDING}"
"""
    (CF_DIR / "wrangler.toml").write_text(content, encoding="utf-8")
    log("[OK] wrangler.toml written.")


def write_worker():
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    code = f"""import json

async def handle_request(request, env, ctx):
    url = request.url
    method = request.method
    path = url.split("/", 3)[-1] if "/" in url else ""

    if path.startswith("users/"):
        return await handle_users(request, env, path[len("users/"):], method)
    if path.startswith("wallet/"):
        return await handle_wallet(request, env, path[len("wallet/"):], method)
    if path.startswith("mining/"):
        return await handle_mining(request, env, path[len("mining/"):], method)
    if path.startswith("referral/"):
        return await handle_referral(request, env, path[len("referral/"):], method)

    return json_response({{"detail": "Not found"}}, 404)


def json_response(data, status=200):
    return Response(
        json.dumps(data),
        status=status,
        headers={{"Content-Type": "application/json"}},
    )


async def handle_users(request, env, subpath, method):
    telegram_id = subpath.strip("/")
    key = f"user:{{telegram_id}}"
    kv = env.{KV_BINDING}

    if method == "GET":
        raw = await kv.get(key)
        if raw is None:
            user = {{"telegram_id": telegram_id, "created": True}}
            await kv.put(key, json.dumps(user))
        else:
            user = json.loads(raw)
        return json_response(user)

    return json_response({{"detail": "Method not allowed"}}, 405)


async def handle_wallet(request, env, subpath, method):
    telegram_id = subpath.strip("/")
    kv = env.{KV_BINDING}
    key = f"wallet:{{telegram_id}}"

    if method == "GET":
        raw = await kv.get(key)
        if raw is None:
            wallet = {{"telegram_id": telegram_id, "balance": 0}}
            await kv.put(key, json.dumps(wallet))
        else:
            wallet = json.loads(raw)
        return json_response(wallet)

    return json_response({{"detail": "Method not allowed"}}, 405)


async def handle_mining(request, env, subpath, method):
    parts = subpath.strip("/").split("/")
    if len(parts) != 2 or parts[1] != "start":
        return json_response({{"detail": "Not found"}}, 404)

    telegram_id = parts[0]
    kv = env.{KV_BINDING}
    key = f"mining:{{telegram_id}}"

    if method == "POST":
        session = {{"telegram_id": telegram_id, "status": "mining_started"}}
        await kv.put(key, json.dumps(session))
        return json_response(session)

    return json_response({{"detail": "Method not allowed"}}, 405)


async def handle_referral(request, env, subpath, method):
    parts = subpath.strip("/").split("/")
    if len(parts) != 2 or parts[1] != "link":
        return json_response({{"detail": "Not found"}}, 404)

    telegram_id = parts[0]
    link = f"https://t.me/SurgeCoinBot?start=ref{{telegram_id}}"
    return json_response({{"telegram_id": telegram_id, "link": link}})


async def main(request, env, ctx):
    return await handle_request(request, env, ctx)
"""
    (SRC_DIR / "worker.py").write_text(code, encoding="utf-8")
    log("[OK] worker.py written.")


def deploy_worker():
    log("[*] Deploying Cloudflare Worker via wrangler...")
    subprocess.run(
        ["wrangler", "deploy"],
        cwd=str(CF_DIR),
        check=True
    )
    log("[OK] wrangler deploy finished.")


def check_health():
    url = f"https://{WORKER_NAME}.workers.dev/users/1"
    log(f"[*] Checking health: {url}")
    time.sleep(5)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            log(f"[OK] Status: {resp.status}")
            log(f"[OK] Body: {body}")
            return resp.status == 200
    except Exception as e:
        log(f"[ERR] Health check failed: {e}")
        return False


def main():
    log("=== SurgeCoin Cloudflare Backend Automation ===")
    write_wrangler()
    write_worker()
    deploy_worker()
    ok = check_health()
    if ok:
        log("=== DONE: Cloudflare Worker is LIVE ===")
    else:
        log("=== WARNING: Worker deployed but health check failed ===")


if __name__ == "__main__":
    main()
