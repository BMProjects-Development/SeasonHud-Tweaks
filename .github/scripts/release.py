"""Validate, package and publish the complete tested port matrix."""

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from urllib.parse import quote, urlencode
from zipfile import ZipFile

from hosting import CurseForge, GitHub, find_release, uploads_in, with_uploads


ROOT = Path(__file__).resolve().parents[2]
MOD = "seasonhudtweaks"
NAME = "SeasonHud Tweaks"
VERSION = re.compile(r"(\d+\.\d+\.\d+)(?:-[0-9A-Za-z.-]+)?")


def release_inputs():
    property_match = re.search(r"(?m)^mod_version=(\S+)$", (ROOT / "gradle.properties").read_text())
    if not property_match or not VERSION.fullmatch(property_match.group(1)):
        raise ValueError("Invalid mod_version in gradle.properties")
    version = property_match.group(1)
    notes = (ROOT / "changelogs" / f"{version}.md").read_text(encoding="utf-8").strip()
    if not notes:
        raise ValueError(f"Add release notes in changelogs/{version}.md")
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/") and ref != f"refs/tags/v{version}":
        raise ValueError("Tag must match mod_version in gradle.properties")
    ports = json.loads((ROOT / "ports.json").read_text(encoding="utf-8"))
    if not ports or len(ports) != len({port["id"] for port in ports}):
        raise ValueError("Port IDs must be unique")
    return version, notes, ports


def artifact_name(version, port):
    return f"{MOD}-{port['id']}-{version}.jar"


def validate_metadata(jar, version, port):
    config_name = f"{MOD}.mixins.json"
    if port["loader"] == "fabric":
        metadata = json.loads(jar.read("fabric.mod.json"))
        if (metadata["id"], metadata["version"], metadata["environment"], metadata["mixins"]) != (
            MOD, version, "client", [config_name],
        ) or metadata["depends"]["minecraft"] != [f"={game}" for game in port["minecraft"]]:
            raise ValueError(f"Invalid Fabric metadata in {jar.filename}")
    else:
        metadata = tomllib.loads(jar.read(port["metadata"]).decode())
        (mod,) = metadata["mods"]
        dependencies = {dep["modId"]: dep for dep in metadata["dependencies"][MOD]}
        if (mod["modId"], mod["version"]) != (MOD, version) or (
            dependencies["minecraft"]["versionRange"] != port["minecraftRange"]
            or dependencies["seasonhud"]["side"] != "CLIENT"
        ):
            raise ValueError(f"Invalid Forge or NeoForge metadata in {jar.filename}")
        if port["modLoader"] == "neoforge":
            registered = metadata.get("mixins") == [{"config": config_name}]
        else:
            registered = f"MixinConfigs: {config_name}" in jar.read("META-INF/MANIFEST.MF").decode()
        if registered == bool(port.get("overlayEvent")):
            raise ValueError(f"Incorrect mixin registration in {jar.filename}")


def validate_artifacts(directory, version, ports):
    jar_names = {artifact_name(version, port) for port in ports}
    bundle = f"{MOD}-{version}.zip"
    sources = f"{MOD}-{version}-sources.jar"
    expected = jar_names | {bundle, sources}
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != expected:
        raise ValueError(f"Unexpected artifact set. Missing {sorted(expected - actual)}, extra {sorted(actual - expected)}")
    for port in ports:
        path = directory / artifact_name(version, port)
        with ZipFile(path) as jar:
            validate_metadata(jar, version, port)
            if port.get("overlayEvent"):
                if f"{MOD}.mixins.json" in jar.namelist():
                    raise ValueError(f"{path.name} should use the Forge overlay event")
                jar.read("org/bmp/seasonhudtweaks/forge/SeasonOverlayGate.class")
                continue
            config = json.loads(jar.read(f"{MOD}.mixins.json"))
            mixins = [port["mixin"], "ClassicCalendarMixin"] if "classic" in port else [port["mixin"]]
            if config["client"] != mixins or config.get("mixins") or config.get("server"):
                raise ValueError(f"{path.name} contains the wrong mixins")
            for mixin in mixins:
                jar.read(config["package"].replace(".", "/") + f"/{mixin}.class")
    with ZipFile(directory / bundle) as archive:
        archived_jars = {name.removeprefix("mods/") for name in archive.namelist() if name.endswith(".jar")}
        if archived_jars != jar_names:
            raise ValueError("Release ZIP has the wrong set of playable JARs")
        for name in jar_names:
            if archive.read(f"mods/{name}") != (directory / name).read_bytes():
                raise ValueError(f"Release ZIP has a different copy of {name}")
        for name in (f"changelogs/{version}.md", "docs/en.md", "docs/ru.md"):
            archive.read(name)
    with ZipFile(directory / sources) as archive:
        if not any(name.endswith("/CalendarMixin.java") for name in archive.namelist()):
            raise ValueError("Sources JAR is missing the main mixin")
    return {name: sha256((directory / name).read_bytes()).hexdigest() for name in sorted(expected)}


def is_current(api, base, ref, sha):
    # Resolve a branch or tag explicitly. A branch and a tag can share a name.
    ref_path = quote(ref.removeprefix("refs/"), safe="/")
    remote = api.request("GET", f"{base}/git/ref/{ref_path}", missing_ok=True)
    if remote is None:
        return False
    obj = remote["object"]
    while obj["type"] == "tag":
        obj = api.request("GET", f"{base}/git/tags/{obj['sha']}")["object"]
    return obj["sha"] == sha


def stable_version(tag):
    match = VERSION.fullmatch(tag.removeprefix("v"))
    if not match or "-" in tag:
        return ()
    return tuple(map(int, match.group(1).split(".")))


def publish_github(api, base, version, notes, sha, ref, directory, digests):
    tag = f"v{version}"
    existing = find_release(api, base, tag)
    uploads = uploads_in(existing.get("body")) if existing else {}
    tag_ref = f"refs/tags/{tag}"
    expected_assets = {name: f"sha256:{digest}" for name, digest in digests.items()}
    if existing and not existing["draft"] and is_current(api, base, tag_ref, sha):
        actual_assets = {asset["name"]: asset.get("digest") for asset in existing["assets"]}
        if actual_assets == expected_assets:
            return existing

    if existing and existing.get("immutable"):
        raise ValueError(f"Release {tag} is immutable and cannot be replaced")
    prerelease = "-" in version
    latest = api.request("GET", f"{base}/releases/latest", missing_ok=True)
    make_latest = not prerelease and (
        latest is None or latest["tag_name"] == tag or stable_version(tag) > stable_version(latest["tag_name"])
    )
    draft = {
        "tag_name": tag,
        "target_commitish": sha,
        "name": f"{NAME} {version}",
        "body": with_uploads(notes, uploads),
        "draft": True,
        "prerelease": prerelease,
    }
    if existing:
        release = api.request("PATCH", f"{base}/releases/{existing['id']}", draft)
        for asset in release["assets"]:
            api.request("DELETE", f"{base}/releases/assets/{asset['id']}")
    else:
        release = api.request("POST", f"{base}/releases", draft)

    upload_url = release["upload_url"].split("{", 1)[0]
    for name, digest in digests.items():
        asset = api.request("POST", upload_url + "?" + urlencode({"name": name}), (directory / name).read_bytes())
        if asset.get("digest") != f"sha256:{digest}":
            raise ValueError(f"GitHub received a different checksum for {name}")

    if not is_current(api, base, ref, sha):
        raise ValueError("Remote ref changed during staging. The release remains a draft.")
    if not is_current(api, base, tag_ref, sha):
        if api.request("GET", f"{base}/git/ref/tags/{tag}", missing_ok=True):
            api.request("PATCH", f"{base}/git/refs/tags/{tag}", {"sha": sha, "force": True})
        else:
            api.request("POST", f"{base}/git/refs", {"ref": tag_ref, "sha": sha})
    return api.request("PATCH", f"{base}/releases/{release['id']}", {
        "draft": False, "make_latest": "true" if make_latest else "false",
    })


def publish_curseforge(api, base, release, client, version, notes, directory, ports, digests):
    receipts = uploads_in(release.get("body"))
    pending = [port for port in ports if digests[artifact_name(version, port)] not in receipts]
    if not pending:
        return
    game_versions = client.version_ids(pending)
    for port in pending:
        name = artifact_name(version, port)
        digest = digests[name]
        loader = {"fabric": "Fabric", "forge": "Forge", "neoforge": "NeoForge"}[port["loader"]]
        slug = "seasonhud-fabric" if port["loader"] == "fabric" else "seasonhud"
        games = port["minecraft"]
        game = games[0] if len(games) == 1 else f"{games[0]}–{games[-1]}"
        # Use the digest in the filename to distinguish rebuilds with the same version.
        filename = f"{Path(name).stem}-{digest[:12]}.jar"
        file_id = client.upload(filename, (directory / name).read_bytes(), {
            "displayName": f"{NAME} {version} ({game}, {loader})",
            "changelog": notes,
            "changelogType": "markdown",
            "gameVersions": game_versions[port["id"]],
            "releaseType": "beta" if "-" in version else "release",
            "isMarkedForManualRelease": False,
            "relations": {"projects": [{"slug": slug, "type": "requiredDependency"}]},
        })
        print(f"CurseForge accepted {name} for review: https://www.curseforge.com/minecraft/mc-mods/seasonhud-tweaks/files/{file_id}", flush=True)
        receipts[digest] = file_id
        api.request("PATCH", f"{base}/releases/{release['id']}", {"body": with_uploads(notes, receipts)})


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("check", "verify", "publish"):
        raise ValueError("Usage: release.py check|verify|publish")
    action = sys.argv[1]
    version, notes, ports = release_inputs()
    if action == "check":
        if output := os.environ.get("GITHUB_OUTPUT"):
            with open(output, "a", encoding="utf-8") as handle:
                handle.write(f"version={version}\n")
        print(f"Validated {len(ports)} ports for {NAME} {version}")
        return
    directory = ROOT / ("release" if action == "publish" else "build/release")
    digests = validate_artifacts(directory, version, ports)
    if action == "verify":
        print(f"Validated {len(digests)} release artifacts")
        return

    api = GitHub(os.environ["GH_TOKEN"], os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    base = f"/repos/{os.environ['GITHUB_REPOSITORY']}"
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    ref = os.environ["GITHUB_REF"]
    default_branch = api.request("GET", base)["default_branch"]
    if ref not in (f"refs/heads/{default_branch}", f"refs/tags/v{version}"):
        raise ValueError("Only the default branch or matching version tag can publish")
    if not is_current(api, base, ref, sha):
        print("Skipped an outdated build. The remote ref has advanced.")
        return
    client = CurseForge(os.environ.get("CURSEFORGE_TOKEN", ""))
    release = publish_github(api, base, version, notes, sha, ref, directory, digests)
    print(f"Published {release['html_url']}", flush=True)
    if is_current(api, base, ref, sha):
        publish_curseforge(api, base, release, client, version, notes, directory, ports, digests)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        sys.exit(str(error))
