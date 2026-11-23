import unittest
from unittest.mock import patch

from scripts import fpk, fnpack_index


def published_release(slug, version, date="2026-11-23T02:47:00Z"):
    app = fpk.APPS[slug]
    return {
        "tag_name": f"{slug}-v{version}",
        "draft": False,
        "prerelease": False,
        "published_at": date,
        "assets": [
            {
                "name": f"{app.package_id}_{version}_{arch}.fpk",
                "state": "uploaded",
                "digest": "sha256:" + char * 64,
                "size": 100 + number,
            }
            for number, (arch, char) in enumerate(zip(app.assets, "ab"))
        ],
    }


class IndexTests(unittest.TestCase):
    def test_versions_and_architecture_downloads_match_the_fpk(self):
        index = fnpack_index.generate_index("owner/FnDepot", [
            published_release("kavita", "0.9.1.4"),
            published_release("slskd", "0.26.2"),
            published_release("kavita", "0.9.1.10", "2026-11-22T02:47:00Z"),
        ])

        self.assertEqual(index["schema_version"], "2")
        self.assertEqual(index["source_info"], {
            "name": "Jadeiin",
            "author": "Jadeiin",
            "homepage": "https://github.com/owner/FnDepot",
        })
        self.assertEqual(set(index["apps"]), {"Jadeiin.Kavita", "slskd"})
        kavita = index["apps"]["Jadeiin.Kavita"]
        self.assertEqual(kavita["display_name"], "Kavita")
        self.assertEqual(kavita["icon_url"], "apps/kavita/icon-256.png")
        self.assertEqual(kavita["readme_url"], "apps/kavita/README.md")
        self.assertEqual(list(kavita["releases"]), ["0.9.1010", "0.9.1004"])
        self.assertEqual(kavita["releases"]["0.9.1004"]["packages"], {
            "x86": {
                "download_url": "https://github.com/owner/FnDepot/releases/download/kavita-v0.9.1.4/Jadeiin.Kavita_0.9.1.4_x86.fpk",
                "sha256": "a" * 64,
                "size": 100,
            },
            "arm": {
                "download_url": "https://github.com/owner/FnDepot/releases/download/kavita-v0.9.1.4/Jadeiin.Kavita_0.9.1.4_arm.fpk",
                "sha256": "b" * 64,
                "size": 101,
            },
        })

    def test_ignores_unpublished_and_incomplete_releases(self):
        stable = published_release("slskd", "0.26.2")
        draft = dict(published_release("slskd", "0.26.3"), draft=True)
        prerelease = dict(published_release("slskd", "0.26.4"), prerelease=True)
        unrelated = dict(published_release("slskd", "0.26.5"), tag_name="v0.26.5")
        incomplete = published_release("slskd", "0.26.6")
        incomplete["assets"].pop()
        missing_digest = published_release("slskd", "0.26.7")
        missing_digest["assets"][0]["digest"] = None

        index = fnpack_index.generate_index("owner/FnDepot", [
            draft, prerelease, unrelated, incomplete, missing_digest, stable,
        ])
        self.assertEqual(set(index["apps"]), {"slskd"})
        self.assertEqual(list(index["apps"]["slskd"]["releases"]), ["0.26.2"])

    def test_adding_an_app_uses_its_declared_architectures(self):
        app = fpk.App(
            repo="example/service", package_id="example.service", display_name="Example",
            maintainer="Example", description="Example app", port=8000, executable="server",
            assets={"arm": "server-linux-arm64.tar.gz"},
        )
        with patch.dict(fpk.APPS, {"example": app}):
            release = published_release("example", "1.2.3")
            index = fnpack_index.generate_index("owner/FnDepot", [release])
        entry = index["apps"]["example.service"]
        self.assertEqual(entry["platform"], ["arm"])
        self.assertEqual(entry["categories"], ["系统工具"])
        self.assertEqual(set(entry["releases"]["1.2.3"]["packages"]), {"arm"})


if __name__ == "__main__":
    unittest.main()
