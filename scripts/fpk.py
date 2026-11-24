#!/usr/bin/env python3
"""Resolve upstream releases and package their Linux binaries for fnOS."""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Optional
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
ARCHES = {"x86": 62, "arm": 183}
PACKAGE_REVISION_BASE = 100
FNPACK_VERSION = "1.3.3"
FNPACK_DOWNLOADS = {
    ("Linux", "x86_64"): (
        "linux-amd64", "1464d6aa9b995ebecb263c5ec60f0f4a7cbf45e0ce887836755fd65abd647d1e",
    ),
    ("Darwin", "arm64"): (
        "darwin-arm64", "2f933c55ec1bdd1f18aa175ce916cb571ae021f18a6d137edfdd7e8333877648",
    ),
}
HOOKS = (
    "install_init", "install_callback", "upgrade_init", "upgrade_callback",
    "uninstall_init", "uninstall_callback", "config_init", "config_callback",
)


class Category(str, Enum):
    MEDIA = "影音娱乐"
    SYSTEM_TOOLS = "系统工具"
    DEVELOPMENT = "编程开发"
    AI = "AI赋能"
    LIFESTYLE = "生活服务"
    SMART_HOME = "智能智控"
    EDUCATION = "教育学习"
    GAMES = "游戏地带"
    DRIVERS = "硬件驱动"


@dataclass(frozen=True)
class App:
    repo: str
    package_id: str
    display_name: str
    maintainer: str
    description: str
    executable: str
    assets: dict[str, str]
    port: Optional[int] = None
    version_parts: int = 3
    categories: list[Category] = field(default_factory=lambda: [Category.SYSTEM_TOOLS])
    package_user: str = ""
    package_revision: int = 0
    runtime_assets: dict[str, dict] = field(default_factory=dict)


def load_apps(directory):
    apps = {}
    package_ids = set()
    for config in sorted(directory.glob("*/app.json")):
        slug = config.parent.name
        if slug == "all" or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
            raise ValueError(f"Invalid application directory: {config.parent}")
        with config.open(encoding="utf-8") as source:
            fields = json.load(source)
        if "categories" in fields:
            categories = fields["categories"]
            if not isinstance(categories, list) or not 1 <= len(categories) <= 2:
                raise ValueError(f"Expected one or two FnDepot categories in {config}")
            try:
                fields["categories"] = [Category(category) for category in categories]
            except ValueError as error:
                raise ValueError(f"Invalid FnDepot category in {config} ({error})") from error
        app = App(**fields)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", app.package_id) or app.package_id in package_ids:
            raise ValueError(f"Expected a valid, unique package_id in {config}")
        if not app.assets or app.assets.keys() - ARCHES.keys():
            raise ValueError(f"Expected x86 or arm release assets in {config}")
        if app.runtime_assets.keys() - app.assets.keys():
            raise ValueError(f"Runtime asset has no matching application architecture in {config}")
        if app.version_parts not in (3, 4):
            raise ValueError(f"Expected version_parts of 3 or 4 in {config}")
        if type(app.package_revision) is not int or not 0 <= app.package_revision < PACKAGE_REVISION_BASE:
            raise ValueError(f"Expected package_revision between 0 and 99 in {config}")
        apps[slug] = app
        package_ids.add(app.package_id)
    return apps


APPS = load_apps(ROOT / "apps")


def versions(app_name, tag, package_revision=0):
    parts = APPS[app_name].version_parts
    version = tag.removeprefix("v")
    fields = version.split(".")
    if len(fields) not in {3, parts} or any(not re.fullmatch(r"0|[1-9][0-9]*", field) for field in fields):
        raise ValueError(f"Unsupported stable version for {app_name}: {tag!r}")
    if not 0 <= package_revision < PACKAGE_REVISION_BASE:
        raise ValueError(f"Unsupported package revision for {app_name}: {package_revision}")

    major, minor, patch = (int(field) for field in fields[:3])
    if parts == 4:
        revision = int(fields[3]) if len(fields) == 4 else 0
        if revision >= 1000:
            raise ValueError(f"Version revision exceeds mapping range for {app_name}: {tag}")
        patch = patch * 1000 + revision
    if package_revision:
        # Leave room for package-only fixes and keep the old mapping for existing tags.
        patch = patch * PACKAGE_REVISION_BASE + package_revision
    return version, f"{major}.{minor}.{patch}"


def release_version(upstream_version, package_revision):
    return f"{upstream_version}-r{package_revision}" if package_revision else upstream_version


def package_filename(app, upstream_version, arch, package_revision=0):
    return f"{app.package_id}_{release_version(upstream_version, package_revision)}_{arch}.fpk"


def release_metadata(repo, tag):
    endpoint = "latest" if not tag else f"tags/{quote(tag, safe='')}"
    url = f"https://api.github.com/repos/{repo}/releases/{endpoint}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "native-fnos-fpk"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(url, headers=headers), timeout=60) as response:
        return json.load(response)


def resolve(app_name, release):
    app = APPS[app_name]
    tag = release["tag_name"]
    if release.get("draft") or release.get("prerelease"):
        raise ValueError(f"Expected a stable release, got {app.repo} {tag}")
    upstream_version, version = versions(app_name, tag, app.package_revision)
    upstream_assets = {asset["name"]: asset for asset in release["assets"]}
    assets = {}

    for arch, template in app.assets.items():
        name = template.format(tag=tag, version=upstream_version)
        asset = upstream_assets.get(name, {})
        digest = asset.get("digest") or ""
        url = f"https://github.com/{app.repo}/releases/download/{tag}/{quote(name, safe='')}"
        if asset.get("state") != "uploaded" or asset.get("browser_download_url") != url:
            raise ValueError(f"Missing or unexpected upstream asset: {name}")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest) or not asset.get("size"):
            raise ValueError(f"Missing upstream size or SHA-256: {name}")
        assets[arch] = {"name": name, "url": url, "sha256": digest[7:], "size": asset["size"]}

    plan = {
        "app": app_name,
        "tag": tag,
        "release_tag": f"{app_name}-v{release_version(upstream_version, app.package_revision)}",
        "upstream_version": upstream_version,
        "version": version,
        "source_url": f"https://github.com/{app.repo}/tree/{tag}",
        "assets": assets,
    }
    if app.runtime_assets:
        plan["runtime_assets"] = app.runtime_assets
    return plan


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def payload_checksum(stream):
    digest = hashlib.md5()  # fnOS manifest uses MD5 for app.tgz.
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def download(url, path):
    request = Request(url, headers={"User-Agent": "native-fnos-fpk"})
    with urlopen(request, timeout=120) as response, path.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)


def verified_asset(asset, staging, asset_dir):
    name = asset["name"]
    if not name or name == ".." or Path(name).name != name:
        raise ValueError(f"Invalid upstream asset name: {name!r}")
    archive = (asset_dir or staging) / name
    if asset_dir is None:
        download(asset["url"], archive)
    if archive.stat().st_size != asset["size"] or sha256(archive) != asset["sha256"]:
        raise ValueError(f"Upstream asset size or SHA-256 mismatch: {name}")
    return archive


def fnpack_binary(location, staging):
    if location:
        return location.resolve(strict=True)
    host = (platform.system(), platform.machine())
    if host not in FNPACK_DOWNLOADS:
        raise ValueError(f"Pass --fnpack with a local fnpack {FNPACK_VERSION} binary for {host}")
    suffix, expected = FNPACK_DOWNLOADS[host]
    path = staging / "fnpack"
    download(f"https://static2.fnnas.com/fnpack/fnpack-{FNPACK_VERSION}-{suffix}", path)
    if sha256(path) != expected:
        raise ValueError(f"Invalid SHA-256 for fnpack {FNPACK_VERSION} ({suffix})")
    path.chmod(0o755)
    return path


def check_archive_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"Invalid path in upstream archive: {name!r}")


def unpack(archive_path, destination):
    if archive_path.name.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as archive:
            for item in archive.infolist():
                check_archive_path(item.filename)
                mode = item.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError(f"Unexpected symlink in upstream ZIP: {item.filename}")
                extracted = Path(archive.extract(item, destination))
                if not item.is_dir() and mode & 0o111:
                    extracted.chmod(0o755)
    else:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            for item in members:
                check_archive_path(item.name)
                if not (item.isreg() or item.isdir()):
                    raise ValueError(f"Unexpected entry in upstream tarball: {item.name}")
                item.mode &= 0o777
            archive.extractall(destination, members)


def check_binary(binary, arch):
    with binary.open("rb") as stream:
        header = stream.read(20)
    if header[:6] != b"\x7fELF\x02\x01" or int.from_bytes(header[18:20], "little") != ARCHES[arch]:
        raise ValueError(f"{binary.name} is not a Linux {arch} executable")


def create_package(plan, arch, directory, upstream_archive, runtime_archive=None):
    slug = plan["app"]
    app = APPS[slug]
    template = ROOT / "apps" / slug
    app_dir = directory / "app"
    payload_dir = app_dir / "payload"
    cmd_dir = directory / "cmd"
    config_dir = directory / "config"
    wizard_dir = directory / "wizard"
    images_dir = app_dir / "ui" / "images"
    for path in (cmd_dir, config_dir, wizard_dir):
        path.mkdir(parents=True)

    with tempfile.TemporaryDirectory(dir=directory.parent) as extracted:
        unpack(upstream_archive, extracted)
        binaries = [file for file in Path(extracted).rglob(app.executable) if file.is_file()]
        if len(binaries) != 1:
            raise ValueError(f"Expected exactly one {app.executable} in {upstream_archive.name}")
        check_binary(binaries[0], arch)
        binaries[0].chmod(0o755)
        shutil.move(binaries[0].parent, payload_dir)
        # A flat archive may leave the executable in the mode-0700 staging directory.
        payload_dir.chmod(0o755)

    bundled_assets = [plan["assets"][arch]]
    if runtime_archive is not None:
        runtime_dir = payload_dir / "runtime"
        runtime_dir.mkdir()
        unpack(runtime_archive, runtime_dir)
        bundled_assets.append(plan["runtime_assets"][arch])

    license_file = template / "LICENSE"
    if license_file.is_file():
        shutil.copyfile(license_file, app_dir / "LICENSE")
    shutil.copyfile(template / "service.sh", app_dir / "service.sh")
    manifest = {
        "appname": app.package_id,
        "version": plan["version"],
        "display_name": app.display_name,
        "desc": app.description,
        "platform": arch,
        "source": "thirdparty",
        "maintainer": app.maintainer,
        "maintainer_url": f"https://github.com/{app.repo}",
        "ctl_stop": "true",
        "checkport": "false" if app.port is None else "true",
        "disable_authorization_path": "false",
        "changelog": f"Upstream {plan['tag']}",
    }
    provenance = [f"{plan['source_url']}\n"]
    provenance.extend(f"{asset['url']}\nSHA-256: {asset['sha256']}\n" for asset in bundled_assets)
    (app_dir / "UPSTREAM.txt").write_text("".join(provenance), encoding="utf-8")
    username = app.package_user or app.package_id.replace("-", "_")
    privilege = {"defaults": {"run-as": "package"}, "username": username, "groupname": username}
    (config_dir / "privilege").write_text(json.dumps(privilege) + "\n", encoding="utf-8")
    (config_dir / "resource").write_text("{}\n", encoding="utf-8")
    if app.port is not None:
        app_name = f"{app.package_id}.Application"
        manifest.update(desktop_uidir="ui", desktop_applaunchname=app_name, service_port=app.port)
        images_dir.mkdir(parents=True)
        ui = {".url": {app_name: {
            "title": app.display_name, "icon": "images/icon_{0}.png", "type": "url",
            "protocol": "http", "port": str(app.port), "url": "/", "allUsers": False,
        }}}
        (images_dir.parent / "config").write_text(json.dumps(ui, indent=2) + "\n", encoding="utf-8")

    (directory / "manifest").write_text(
        "".join(f"{key}={value}\n" for key, value in manifest.items()), encoding="utf-8",
    )

    for size, name in ((64, "ICON.PNG"), (256, "ICON_256.PNG")):
        icon = template / f"icon-{size}.png"
        shutil.copyfile(icon, directory / name)
        if app.port is not None:
            shutil.copyfile(icon, images_dir / f"icon_{size}.png")

    shutil.copyfile(ROOT / "packaging" / "main", cmd_dir / "main")
    for hook in HOOKS:
        (cmd_dir / hook).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    for target_dir in (cmd_dir, wizard_dir):
        overrides = template / target_dir.name
        if overrides.is_dir():
            shutil.copytree(overrides, target_dir, dirs_exist_ok=True)
    for hook in cmd_dir.iterdir():
        hook.chmod(0o755)


def build_community_package(project, output):
    payload = project / "app.tgz"
    with tarfile.open(payload, "w:gz", compresslevel=6) as archive:
        for entry in sorted((project / "app").iterdir()):
            archive.add(entry, arcname=entry.name)

    with payload.open("rb") as stream, (project / "manifest").open("a", encoding="utf-8") as manifest:
        manifest.write(f"checksum={payload_checksum(stream)}\n")

    with tarfile.open(output, "w:gz", compresslevel=1) as archive:
        for entry in sorted(project.iterdir()):
            if entry.name != "app":
                archive.add(entry, arcname=entry.name)


def verify_package(path, plan, arch):
    if not path.is_file():
        raise ValueError(f"fnpack did not produce {path.name}")
    with tarfile.open(path, "r:gz") as archive:
        if not all(archive.getmember(name).isfile() for name in ("manifest", "app.tgz", "cmd/main")):
            raise ValueError(f"Incomplete FPK archive: {path.name}")
        if not archive.getmember("cmd/main").mode & 0o111:
            raise ValueError(f"Lifecycle script is not executable: {path.name}")
        with archive.extractfile("manifest") as manifest_file:
            lines = manifest_file.read().decode().splitlines()
            fields = dict(tuple(value.strip() for value in line.split("=", 1)) for line in lines if "=" in line)
        with archive.extractfile("app.tgz") as payload:
            checksum = payload_checksum(payload)
    if fields.get("checksum") != checksum:
        raise ValueError(f"Incorrect app.tgz checksum in {path.name}")
    package_id = APPS[plan["app"]].package_id
    if (fields.get("appname"), fields.get("version"), fields.get("platform")) != (package_id, plan["version"], arch):
        raise ValueError(f"Unexpected manifest in {path.name}")


def build(args):
    with args.plan.open(encoding="utf-8") as source:
        plan = json.load(source)
    slug = plan["app"]
    app = APPS[slug]
    upstream_version, version = versions(slug, plan["tag"], app.package_revision)
    release_tag = f"{slug}-v{release_version(upstream_version, app.package_revision)}"
    if (plan["upstream_version"], plan["version"], plan["release_tag"]) != (upstream_version, version, release_tag):
        raise ValueError("Build plan versions do not match the current app configuration. Run resolve again.")
    if plan.get("runtime_assets", {}) != app.runtime_assets:
        raise ValueError("Build plan runtime assets do not match the current app configuration. Run resolve again.")
    all_arches = args.arch in ("all", "both")
    arches = tuple(app.assets) if all_arches else (args.arch,)
    if not all_arches and args.arch not in app.assets:
        raise ValueError(f"{slug} does not publish upstream assets for {args.arch}")
    default_output = Path("dist") / release_tag
    if not all_arches:
        default_output /= args.arch
    output = (args.out or default_output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if (args.key is None) != (args.cert is None):
        raise ValueError("Supply both --key and --cert for a signed package")
    if args.community and args.key:
        raise ValueError("Community packages do not use a developer key and certificate")
    signing = ["--nosign"]
    if args.key:
        signing = ["--key", str(args.key.resolve(strict=True)), "--cert", str(args.cert.resolve(strict=True))]

    with tempfile.TemporaryDirectory(prefix=".fpk-build-", dir=output.parent) as temporary:
        staging = Path(temporary)
        fnpack = None if args.community else fnpack_binary(args.fnpack, staging)
        packages = []
        for arch in arches:
            with tempfile.TemporaryDirectory(dir=staging) as work_dir:
                work = Path(work_dir)
                upstream_archive = verified_asset(plan["assets"][arch], work, args.asset_dir)
                runtime_asset = app.runtime_assets.get(arch)
                runtime_archive = verified_asset(runtime_asset, work, args.asset_dir) if runtime_asset else None

                project = work / "package"
                create_package(plan, arch, project, upstream_archive, runtime_archive)
                actual = work / f"{app.package_id}.fpk"
                if args.community:
                    build_community_package(project, actual)
                else:
                    subprocess.run([fnpack, "build", "--directory", project, *signing],
                                   cwd=work, env={**os.environ, "COPYFILE_DISABLE": "1"}, check=True)
                verify_package(actual, plan, arch)
                package = staging / package_filename(app, upstream_version, arch, app.package_revision)
                actual.rename(package)
                packages.append(package)

        sums = staging / "SHA256SUMS"
        sums.write_text("".join(f"{sha256(package)}  {package.name}\n" for package in packages), encoding="utf-8")
        output.mkdir(parents=True, exist_ok=True)
        for item in (*packages, sums):
            item.replace(output / item.name)
            print(output / item.name, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="list available applications")
    listing.add_argument("app", nargs="?", choices=("all", *APPS), default="all")
    listing.add_argument("--json", action="store_true", help="emit a JSON array for the build matrix")

    detect = commands.add_parser("resolve", help="resolve a stable upstream release to a build plan")
    detect.add_argument("app", choices=APPS)
    detect.add_argument("--tag", help="upstream release tag (defaults to latest stable)")
    detect.add_argument("--metadata", type=Path, help="local GitHub Release JSON for offline resolution")

    package = commands.add_parser("build", help="package the architectures declared by a build plan")
    package.add_argument("plan", type=Path)
    package.add_argument("--arch", choices=("all", "both", *ARCHES), default="all")
    package.add_argument("--out", type=Path)
    package.add_argument("--asset-dir", type=Path, help="directory containing predownloaded upstream archives")
    package.add_argument("--fnpack", type=Path)
    package.add_argument("--community", action="store_true", help="build a community FPK without developer signing")
    package.add_argument("--key", type=Path)
    package.add_argument("--cert", type=Path)

    args = parser.parse_args()
    try:
        if args.command == "list":
            apps = list(APPS) if args.app == "all" else [args.app]
            if not apps:
                raise ValueError("No applications found under apps/*/app.json")
            print(json.dumps(apps) if args.json else "\n".join(apps))
        elif args.command == "resolve":
            if args.metadata:
                with args.metadata.open(encoding="utf-8") as source:
                    release = json.load(source)
            else:
                release = release_metadata(APPS[args.app].repo, args.tag)
            plan = resolve(args.app, release)
            if args.tag and plan["tag"] != args.tag:
                raise ValueError(f"Expected upstream tag {args.tag!r}, found {plan['tag']!r}")
            print(json.dumps(plan, indent=2))
        else:
            build(args)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError, tarfile.TarError, zipfile.BadZipFile) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
