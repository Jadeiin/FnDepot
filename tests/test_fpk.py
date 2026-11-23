import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from scripts import fpk


def release_for(app_name, tag):
    app = fpk.APPS[app_name]
    assets = []
    for template in app.assets.values():
        name = template.format(tag=tag, version=tag.removeprefix("v"))
        assets.append({
            "name": name,
            "state": "uploaded",
            "size": 10,
            "digest": "sha256:" + "a" * 64,
            "browser_download_url": f"https://github.com/{app.repo}/releases/download/{tag}/{quote(name, safe='')}",
        })
    return {"tag_name": tag, "draft": False, "prerelease": False, "assets": assets}


class UpstreamTests(unittest.TestCase):
    def test_added_application_supplies_its_own_architecture_and_asset_name(self):
        config = {
            "repo": "example/service",
            "package_id": "example",
            "display_name": "Example",
            "maintainer": "Example",
            "description": "Example native service",
            "port": 8000,
            "executable": "server",
            "assets": {"arm": "server-{tag}-aarch64.tar.gz"},
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "example"
            directory.mkdir()
            (directory / "app.json").write_text(json.dumps(config))
            apps = fpk.load_apps(root)

        with patch.dict(fpk.APPS, apps, clear=True):
            plan = fpk.resolve("example", release_for("example", "v1.2.3"))

        self.assertEqual(list(apps), ["example"])
        self.assertEqual(list(plan["assets"]), ["arm"])
        self.assertEqual(plan["assets"]["arm"]["name"], "server-v1.2.3-aarch64.tar.gz")
        self.assertEqual(plan["version"], "1.2.3")

    def test_kavita_revision_is_kept_in_release_and_ordered_in_manifest(self):
        plan = fpk.resolve("kavita", release_for("kavita", "v0.9.1.4"))
        self.assertEqual(plan["release_tag"], "kavita-v0.9.1.4-r2")
        self.assertEqual(plan["version"], "0.9.100402")
        self.assertEqual(plan["upstream_version"], "0.9.1.4")
        self.assertEqual(plan["assets"]["arm"]["name"], "kavita-linux-arm64.tar.gz")
        tags = ("v0.9.1", "v0.9.1.3", "v0.9.1.4", "v0.9.2", "v0.10.0")
        mapped = [tuple(map(int, fpk.versions("kavita", tag)[1].split("."))) for tag in tags]
        self.assertEqual(mapped, sorted(set(mapped)))
        builds = [("v0.9.1.4", 0), ("v0.9.1.4", 1), ("v0.9.1.4", 2), ("v0.9.1.5", 1)]
        mapped = [tuple(map(int, fpk.versions("kavita", tag, revision)[1].split("."))) for tag, revision in builds]
        self.assertEqual(mapped, sorted(set(mapped)))

    def test_slskd_version_and_asset_name(self):
        plan = fpk.resolve("slskd", release_for("slskd", "0.26.2"))
        self.assertEqual(plan["version"], "0.26.201")
        self.assertEqual(plan["release_tag"], "slskd-v0.26.2-r1")
        self.assertEqual(plan["assets"]["x86"]["name"], "slskd-0.26.2-linux-x64.zip")

    def test_release_without_verified_assets_is_rejected(self):
        release = release_for("slskd", "0.26.2")
        release["assets"][0]["digest"] = None
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            fpk.resolve("slskd", release)


class PackageTests(unittest.TestCase):
    def test_slskd_payload_is_accessible_to_the_package_user(self):
        plan = fpk.resolve("slskd", release_for("slskd", "0.26.2"))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            upstream = directory / "slskd-0.26.2-linux-arm64.zip"
            elf = b"\x7fELF\x02\x01" + bytes(12) + (183).to_bytes(2, "little")
            with zipfile.ZipFile(upstream, "w") as archive:
                archive.writestr("slskd", elf)

            output = directory / "package"
            fpk.create_package(plan, "arm", output, upstream)
            self.assertEqual((output / "app/payload").stat().st_mode & 0o777, 0o755)

    def test_headless_agent_package_keeps_wizards_without_a_desktop_url(self):
        plan = fpk.resolve("beszel-agent", release_for("beszel-agent", "v0.21.2"))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            upstream = directory / plan["assets"]["x86"]["name"]
            elf = b"\x7fELF\x02\x01" + bytes(12) + (62).to_bytes(2, "little")
            with tarfile.open(upstream, "w:gz") as archive:
                binary = tarfile.TarInfo("beszel-agent")
                binary.size = len(elf)
                archive.addfile(binary, io.BytesIO(elf))

            output = directory / "package"
            fpk.create_package(plan, "x86", output, upstream)
            package = directory / "beszel-agent.fpk"
            fpk.build_community_package(output, package)
            fpk.verify_package(package, plan, "x86")
            with tarfile.open(package, "r:gz") as archive:
                manifest = archive.extractfile("manifest").read().decode()
                self.assertIn("checkport=false\n", manifest)
                for field in ("desktop_uidir", "desktop_applaunchname", "service_port"):
                    self.assertNotIn(f"{field}=", manifest)
                self.assertEqual(json.load(archive.extractfile("wizard/install")),
                                 json.load(archive.extractfile("wizard/config")))
                with tarfile.open(fileobj=archive.extractfile("app.tgz"), mode="r|gz") as payload:
                    self.assertNotIn("ui/config", payload.getnames())

    def test_kavita_archive_contains_a_directory_and_executable_with_same_name(self):
        plan = fpk.resolve("kavita", release_for("kavita", "v0.9.1.4"))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            upstream = directory / "kavita-linux-arm64.tar.gz"
            elf = b"\x7fELF\x02\x01" + bytes(12) + (183).to_bytes(2, "little")
            with tarfile.open(upstream, "w:gz") as archive:
                root = tarfile.TarInfo("Kavita/")
                root.type = tarfile.DIRTYPE
                root.mode = 0o755
                archive.addfile(root)
                binary = tarfile.TarInfo("Kavita/Kavita")
                binary.size = len(elf)
                archive.addfile(binary, io.BytesIO(elf))

            output = directory / "package"
            fpk.create_package(plan, "arm", output, upstream)
            self.assertEqual((output / "app/payload/Kavita").read_bytes(), elf)
            self.assertIn("appname=Kavita\n", (output / "manifest").read_text())
            self.assertEqual(json.loads((output / "config/privilege").read_text()), {
                "defaults": {"run-as": "package"},
                "username": "Kavita",
                "groupname": "Kavita",
            })
            package = directory / "Kavita.fpk"
            fpk.build_community_package(output, package)
            fpk.verify_package(package, plan, "arm")
            with tarfile.open(package, "r:gz") as archive:
                with tarfile.open(fileobj=archive.extractfile("app.tgz"), mode="r|gz") as payload:
                    self.assertIn("payload/Kavita", payload.getnames())

    def test_kavita_launch_secures_pid_file_and_handles_a_restricted_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary).resolve()
            target = fixture / "target"
            payload = target / "payload"
            data = fixture / "data"
            runtime = fixture / "tmp"
            tools = fixture / "bin"
            for directory in (payload / "config", data / "config", tools):
                directory.mkdir(parents=True)
            (payload / "Kavita").touch(mode=0o755)
            config = data / "config" / "appsettings.json"
            config.write_text('{"Port":5000}\n')
            shutil.copyfile(fpk.ROOT / "apps/kavita/service.sh", target / "service.sh")

            (tools / "start-stop-daemon").write_text(
                '#!/bin/sh\n'
                'pid_file="$TRIM_PKGTMP/service.pid"\n'
                'case "$1" in\n'
                '    --status)\n'
                '        test -f "$TRIM_PKGTMP/started" || exit 3\n'
                '        if [ -n "$(find "$pid_file" -perm -0002)" ]; then\n'
                '            echo "start-stop-daemon: matching on world-writable pidfile is insecure" >&2\n'
                '            exit 2\n'
                '        fi ;;\n'
                '    --start)\n'
                '        uname -s > "$TRIM_PKGTMP/uname" || exit 127\n'
                '        if [ ! -f "$pid_file" ]; then\n'
                '            touch "$pid_file" && chmod 666 "$pid_file" || exit 1\n'
                '        fi\n'
                '        printf "1234\\n" > "$pid_file"\n'
                '        printf "%s\\n" "$@" > "$TRIM_PKGTMP/started" ;;\n'
                'esac\n'
            )
            for name in ("flock", "sleep"):
                (tools / name).write_text("#!/bin/sh\nexit 0\n")
            for executable in tools.iterdir():
                executable.chmod(0o755)
            for name in ("mkdir", "rm", "ln", "find", "touch", "chmod"):
                (tools / name).symlink_to(shutil.which(name))

            env = {**os.environ, "PATH": str(tools),
                   "TRIM_APPDEST": str(target), "TRIM_PKGVAR": str(data), "TRIM_PKGTMP": str(runtime)}
            result = subprocess.run(
                ["/bin/sh", fpk.ROOT / "packaging/main", "start"],
                env=env, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((runtime / "service.pid").stat().st_mode & 0o777, 0o600)
            self.assertEqual((runtime / "uname").read_text().strip(), os.uname().sysname)
            launch = (runtime / "started").read_text().splitlines()
            self.assertEqual(launch[launch.index("--chdir") + 1], str(runtime / "kavita-runtime"))
            link = runtime / "kavita-runtime" / "config"
            self.assertEqual(link.resolve(), data / "config")
            self.assertEqual(config.read_text(), '{"Port":5000}\n')


if __name__ == "__main__":
    unittest.main()
