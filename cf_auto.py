def write_wrangler_toml():
    wrangler_toml = f"""
name = "{worker_name}"
main = "src/worker.py"
compatibility_date = "2024-12-01"
compatibility_flags = ["python_workers"]

[kv_namespaces]
binding = "{kv_binding}"
id = ""
"""
    with open("backend_cf/wrangler.toml", "w") as f:
        f.write(wrangler_toml)
    print("[OK] wrangler.toml written.")

