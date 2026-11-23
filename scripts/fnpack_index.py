"""Generate the FnDepot V2 source index from published GitHub Releases."""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote

from scripts.fpk import APPS, ROOT, package_filename, release_version, versions


def release_packages(app, upstream_version, package_revision, release, repo_url):
    assets = {asset["name"]: asset for asset in release["assets"] if asset["state"] == "uploaded"}
    packages = {}
    for arch in app.assets:
        name = package_filename(app, upstream_version, arch, package_revision)
        asset = assets.get(name, {})
        digest = asset.get("digest") or ""
        size = asset.get("size")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest) or type(size) is not int or size <= 0:
            return {}
        packages[arch] = {
            "download_url": f"{repo_url}/releases/download/{release['tag_name']}/{quote(name, safe='')}",
            "sha256": digest.removeprefix("sha256:"),
            "size": size,
        }
    return packages


def generate_index(repository, releases):
    owner = repository.split("/", 1)[0]
    repo_url = f"https://github.com/{repository}"
    app_releases = {slug: {} for slug in APPS}

    # Preserve the first published package if two upstream tags map to the same FPK version.
    for release in sorted(releases, key=lambda item: (item.get("published_at") or "", item["tag_name"])):
        if release["draft"] or release["prerelease"] or not release.get("published_at"):
            continue
        slug, _, tag = release["tag_name"].rpartition("-v")
        if slug not in APPS:
            continue
        tag, _, revision = tag.partition("-r")
        try:
            package_revision = int(revision) if revision else 0
            upstream_version, version = versions(slug, tag, package_revision)
        except ValueError:
            continue
        full_version = release_version(upstream_version, package_revision)
        if release["tag_name"] != f"{slug}-v{full_version}" or version in app_releases[slug]:
            continue
        packages = release_packages(APPS[slug], upstream_version, package_revision, release, repo_url)
        if packages:
            app_releases[slug][version] = {
                "updated_at": release["published_at"],
                "changelog": f"Upstream v{upstream_version}" + (f" · FPK r{package_revision}" if package_revision else ""),
                "packages": packages,
            }

    apps = {}
    for slug, app in APPS.items():
        app_versions = app_releases[slug]
        if not app_versions:
            continue
        ordered = sorted(app_versions, key=lambda version: tuple(map(int, version.split("."))), reverse=True)
        entry = {
            "display_name": app.display_name,
            "desc": app.description,
            "platform": list(app.assets),
            "categories": app.categories,
            "icon_url": f"apps/{slug}/icon-256.png",
            "maintainer": app.maintainer,
            "maintainer_url": f"https://github.com/{app.repo}",
            "distributor": owner,
            "distributor_url": repo_url,
            "run_as": "package",
            "install_type": "",
            "is_docker": False,
            "service_port": "" if app.port is None else str(app.port),
            "releases": {version: app_versions[version] for version in ordered[:100]},
        }
        if (ROOT / "apps" / slug / "README.md").is_file():
            entry["readme_url"] = f"apps/{slug}/README.md"
        apps[app.package_id] = entry

    return {
        "schema_version": "2",
        "source_info": {"name": "Jadeiin", "author": "Jadeiin", "homepage": repo_url},
        "apps": apps,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", metavar="OWNER/REPO")
    parser.add_argument("releases", type=Path, help="JSON array from the GitHub Releases REST API")
    parser.add_argument("--out", type=Path, default=Path("fnpack.json"))
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("repository must use the OWNER/REPO format")
    try:
        with args.releases.open(encoding="utf-8") as source:
            releases = json.load(source)
        if not isinstance(releases, list):
            raise ValueError("Expected a JSON array of GitHub Releases")
        index = generate_index(args.repository, releases)
        args.out.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
