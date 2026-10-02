"""Deploy Foodwise at /foodwise while preserving the Wenjin Caddy routes."""
from __future__ import annotations
import hashlib
import pathlib
import shlex
import time
import uuid
import paramiko
import requests

HOST = "118.89.195.253"
ROOT = pathlib.Path(__file__).resolve().parents[1]
JAR = ROOT / "build/libs/foodwise-0.0.1-SNAPSHOT.jar"
SSH = pathlib.Path.home() / ".ssh"
TAG = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
BACKUPS = "/opt/foodwise/backups"
JAR_OLD = f"{BACKUPS}/foodwise-{TAG}.jar"
CADDY_OLD = f"/etc/caddy/Caddyfile.foodwise-backup-{TAG}"
DROPIN = "/etc/systemd/system/foodwise.service.d/context-path.conf"
DROPIN_OLD = f"{BACKUPS}/context-path-{TAG}.conf"
STAGE_JAR = f"/tmp/foodwise-{TAG}.jar"
STAGE_CADDY = f"/tmp/Caddyfile-foodwise-{TAG}"
STAGE_DROPIN = f"/tmp/foodwise-context-{TAG}.conf"


def change_caddy(original: str) -> str:
    health = "\t@foodwise_health path /api/health\n\thandle @foodwise_health {\n\t\treverse_proxy 127.0.0.1:8082\n\t}\n"
    api = "\t@foodwise_api path /api/v1/*\n\thandle @foodwise_api {\n\t\treverse_proxy 127.0.0.1:8082\n\t}\n"
    old_fallback = "\thandle {\n\t\treverse_proxy 127.0.0.1:8082\n\t}\n}"
    if not original.startswith(":80 {\n"):
        raise RuntimeError("Unexpected Caddy site layout")
    first, sep, second = original.partition("\n:8088 {")
    if not sep or "/wenjin/*" not in first:
        raise RuntimeError("Wenjin or default Caddy route is unavailable")
    if "@foodwise path /foodwise/*" in first:
        expected_proxy = "\thandle @foodwise {\n\t\treverse_proxy 127.0.0.1:8082\n\t}"
        expected_fallback = "\thandle {\n\t\tredir * /foodwise/ 302\n\t}\n}"
        if first.count(expected_proxy) != 1 or first.count(expected_fallback) != 1:
            raise RuntimeError("Existing Foodwise prefix route differs from expected configuration")
        return original
    if first.count(old_fallback) != 1:
        raise RuntimeError("Default Caddy route changed")
    first = first.replace(health, "", 1).replace(api, "", 1)
    prefix = ("\tredir /foodwise /foodwise/ 308\n"
              "\t@foodwise path /foodwise/*\n"
              "\thandle @foodwise {\n\t\treverse_proxy 127.0.0.1:8082\n\t}\n")
    first = first.replace(":80 {\n", ":80 {\n" + prefix, 1)
    first = first.replace(old_fallback, "\thandle {\n\t\tredir * /foodwise/ 302\n\t}\n}", 1)
    return first + sep + second


def main():
    if not JAR.is_file():
        raise RuntimeError("Build the JAR before deployment")
    jar_hash = hashlib.sha256(JAR.read_bytes()).hexdigest()
    client = paramiko.SSHClient()
    client.load_host_keys(str(SSH / "known_hosts"))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(HOST, username="ubuntu", key_filename=str(SSH / "aliyun_deploy"),
                   look_for_keys=False, allow_agent=False, timeout=10)
    sftp = client.open_sftp()

    def run(command: str, strict=True):
        _, out, err = client.exec_command(command, timeout=120)
        code = out.channel.recv_exit_status()
        output = out.read().decode("utf-8", "replace")
        error = err.read().decode("utf-8", "replace")
        if strict and code:
            raise RuntimeError(f"Remote command failed ({code}): {command.split()[0]}: {error[:250]}")
        return code, output

    prepared = False
    changed = False
    prior_dropin = False
    try:
        original_caddy = run("sudo -n cat /etc/caddy/Caddyfile")[1]
        updated_caddy = change_caddy(original_caddy)
        prior_dropin = run(f"sudo -n test -e {shlex.quote(DROPIN)}", False)[0] == 0
        print("Uploading JAR and validating Caddy routing...", flush=True)
        sftp.put(str(JAR), STAGE_JAR)
        with sftp.open(STAGE_CADDY, "wb") as file:
            file.write(updated_caddy.encode("utf-8"))
        with sftp.open(STAGE_DROPIN, "wb") as file:
            file.write(b"[Service]\nEnvironment=FOODWISE_CONTEXT_PATH=/foodwise\n")
        if run(f"sha256sum {shlex.quote(STAGE_JAR)}")[1].split()[0] != jar_hash:
            raise RuntimeError("Upload SHA-256 mismatch")
        run(f"sudo -n caddy validate --config {shlex.quote(STAGE_CADDY)}")
        print("Staged configuration and JAR hash verified.", flush=True)

        run(f"sudo -n install -d -m 700 {BACKUPS}")
        run(f"sudo -n cp -a /opt/foodwise/foodwise.jar {shlex.quote(JAR_OLD)}")
        run(f"sudo -n cp -a /etc/caddy/Caddyfile {shlex.quote(CADDY_OLD)}")
        if prior_dropin:
            run(f"sudo -n cp -a {shlex.quote(DROPIN)} {shlex.quote(DROPIN_OLD)}")
        run(f"sudo -n bash -o pipefail -c 'mysqldump --single-transaction foodwise | gzip > {BACKUPS}/foodwise-db-{TAG}.sql.gz'")
        run(f"sudo -n chmod 600 {BACKUPS}/foodwise-db-{TAG}.sql.gz")
        run(f"sudo -n gzip -t {BACKUPS}/foodwise-db-{TAG}.sql.gz")
        prepared = True
        print("Foodwise JAR, database and Caddy backups complete.", flush=True)

        run("sudo -n install -d -m 755 /etc/systemd/system/foodwise.service.d")
        run(f"sudo -n install -m 644 {shlex.quote(STAGE_DROPIN)} {shlex.quote(DROPIN)}")
        run(f"sudo -n install -m 644 {shlex.quote(STAGE_JAR)} /opt/foodwise/foodwise.jar")
        changed = True
        run("sudo -n systemctl daemon-reload && sudo -n systemctl restart foodwise")
        for attempt in range(30):
            code, body = run("curl -fsS --max-time 3 http://127.0.0.1:8082/foodwise/api/health", False)
            if code == 0 and '"UP"' in body:
                break
            time.sleep(2)
        else:
            raise RuntimeError("Foodwise failed its prefixed health check")
        print("Foodwise healthy on /foodwise; switching Caddy.", flush=True)

        if run("sudo -n cat /etc/caddy/Caddyfile")[1] != original_caddy:
            raise RuntimeError("Caddy config changed during deployment; refusing to overwrite it")
        run(f"sudo -n install -m 644 {shlex.quote(STAGE_CADDY)} /etc/caddy/Caddyfile")
        run("sudo -n caddy reload --config /etc/caddy/Caddyfile")
        origin = "http://" + HOST
        def check(path, status, marker="", accept="*/*"):
            response = requests.get(origin + path, headers={"Accept": accept},
                                    allow_redirects=False, timeout=10)
            if response.status_code != status or (marker and marker not in response.text):
                raise RuntimeError(
                    f"HTTP check failed for {path}: {response.status_code}, "
                    f"redirect={response.headers.get('Location', '')}"
                )
            return response
        check("/foodwise/api/health", 200, '"UP"')
        check("/foodwise/login", 200, 'content="/foodwise/"')
        if "/foodwise/" not in check("/", 302).headers.get("Location", ""):
            raise RuntimeError("Root path does not redirect to Foodwise")
        for asset in ["/foodwise/build/app.js", "/foodwise/build/app.css",
                      "/foodwise/css/app.css", "/foodwise/images/brand-logo-blue-transparent.png"]:
            check(asset, 200)
        redirect = check("/foodwise/app/dashboard", 302, accept="text/html")
        if "/foodwise/login" not in redirect.headers.get("Location", ""):
            raise RuntimeError("Login redirect escaped Foodwise path")
        check("/wenjin/", 200)
        check("/wenjin/api/health", 200)
        run("sudo -n systemctl is-active foodwise")
        run("sudo -n systemctl is-active wenjin")
        print("DEPLOYED", origin + "/foodwise/login", flush=True)
        print("WENJIN_OK", origin + "/wenjin/", flush=True)
        print("JAR_SHA256", jar_hash, flush=True)
        print("BACKUP_TAG", TAG, flush=True)
    except Exception:
        if prepared and changed:
            print("Deployment failed; restoring Foodwise and Caddy backups...", flush=True)
            rollback = [
                f"sudo -n install -m 644 {shlex.quote(JAR_OLD)} /opt/foodwise/foodwise.jar",
                f"sudo -n install -m 644 {shlex.quote(DROPIN_OLD)} {shlex.quote(DROPIN)}"
                if prior_dropin else f"sudo -n rm -f {shlex.quote(DROPIN)}",
                "sudo -n systemctl daemon-reload && sudo -n systemctl restart foodwise",
            ]
            current_caddy = run("sudo -n cat /etc/caddy/Caddyfile")[1]
            if current_caddy == updated_caddy:
                rollback[0:0] = [
                    f"sudo -n install -m 644 {shlex.quote(CADDY_OLD)} /etc/caddy/Caddyfile",
                    "sudo -n caddy reload --config /etc/caddy/Caddyfile",
                ]
            elif current_caddy != original_caddy:
                print("ROLLBACK WARNING Caddy changed externally; preserving current configuration", flush=True)
            for command in rollback:
                try:
                    run(command)
                except Exception as error:
                    print("ROLLBACK WARNING", str(error)[:250], flush=True)
        raise
    finally:
        for staged in [STAGE_JAR, STAGE_CADDY, STAGE_DROPIN]:
            try:
                sftp.remove(staged)
            except OSError:
                pass
        sftp.close()
        client.close()

if __name__ == "__main__":
    main()
