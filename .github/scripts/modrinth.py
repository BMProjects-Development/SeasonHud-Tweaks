"""Publish the tested client JARs to the existing Modrinth project."""

from hashlib import sha512
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


PROJECT = "PHI4JTHb"
PROJECT_URL = "https://modrinth.com/mod/seasonhud-tweaks"


class Modrinth:
    def __init__(self, token):
        if not token:
            raise ValueError("Add the Modrinth token as the MODRINTH_TOKEN Actions secret")
        self.token = token

    def request(self, endpoint, body=None, content_type="application/json"):
        request = Request("https://api.modrinth.com/v2/" + endpoint, data=body, headers={
            "Authorization": self.token,
            "Content-Type": content_type,
            "User-Agent": "BMProjects-Development/SeasonHud-Tweaks (GitHub Actions)",
        })
        try:
            with urlopen(request, timeout=120) as response:
                return json.load(response)
        except HTTPError as error:
            detail = error.read(4096).decode("utf-8", errors="replace")
            detail = " ".join(detail.replace(self.token, "[redacted]").split())[:500]
            raise RuntimeError(f"Modrinth {endpoint}: HTTP {error.code} {detail}") from None
        except URLError as error:
            raise RuntimeError(f"Modrinth {endpoint}: {error.reason}") from None

    def create_version(self, filename, jar, metadata):
        boundary = "seasonhudtweaks-" + uuid4().hex
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="data"\r\n'
            'Content-Type: application/json\r\n\r\n'
        ).encode() + json.dumps(metadata).encode() + (
            f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="jar"; filename="{filename}"\r\n'
            'Content-Type: application/java-archive\r\n\r\n'
        ).encode() + jar + f"\r\n--{boundary}--\r\n".encode()
        return self.request("version", body, f"multipart/form-data; boundary={boundary}")


def version_metadata(port, version, notes):
    loader = {"fabric": "Fabric", "forge": "Forge", "neoforge": "NeoForge"}[port["loader"]]
    games = port["minecraft"]
    game = games[0] if len(games) == 1 else f"{games[0]}–{games[-1]}"
    upstream = "iDiIfZLX" if port["loader"] == "fabric" else "VNjUn3NA"
    dependencies = [{"project_id": upstream, "dependency_type": "required"}]
    if port.get("overlayEvent"):
        # Modrinth does not host the archived Forge 1.17.1 release of SeasonHud.
        dependencies = []
        notes += (
            "\n\nForge 1.17.1 requires the archived [SeasonHud 1.2.5]"
            "(https://www.curseforge.com/minecraft/mc-mods/seasonhud/files/4357038)"
            " and its dependency [Serene Seasons]"
            "(https://www.curseforge.com/minecraft/mc-mods/serene-seasons/files/3433685)."
        )
    return {
        "project_id": PROJECT,
        "name": f"SeasonHud Tweaks {version} (Minecraft {game}, {loader})",
        "version_number": f"{version}+{port['id']}",
        "changelog": notes,
        "dependencies": dependencies,
        "game_versions": games,
        "loaders": [port["loader"]],
        "version_type": "beta" if "-" in version else "release",
        "featured": False,
        "status": "listed",
        "environment": "client_only",
        "file_parts": ["jar"],
        "primary_file": "jar",
    }


def matches(remote, metadata, digest):
    dependencies = {
        (dep.get("project_id"), dep.get("version_id"), dep["dependency_type"])
        for dep in remote["dependencies"]
    }
    return (
        remote["project_id"] == PROJECT
        and remote["status"] == metadata["status"]
        and remote["environment"] == metadata["environment"]
        and remote["version_type"] == metadata["version_type"]
        and set(remote["loaders"]) == set(metadata["loaders"])
        and set(remote["game_versions"]) == set(metadata["game_versions"])
        and dependencies == {(dep["project_id"], None, "required") for dep in metadata["dependencies"]}
        and any(file["primary"] and file["hashes"].get("sha512") == digest for file in remote["files"])
    )


def publish_modrinth(client, version, notes, artifacts):
    existing = {
        release["version_number"]: release
        for release in client.request(f"project/{PROJECT}/version")
    }
    published = 0
    for port, path in artifacts:
        jar = path.read_bytes()
        digest = sha512(jar).hexdigest()
        metadata = version_metadata(port, version, notes)
        number = metadata["version_number"]
        remote = existing.get(number)
        if remote and not matches(remote, metadata, digest):
            # Give a rebuilt JAR a distinct version without replacing an existing download.
            number = f"{number}.{digest[:12]}"
            metadata["version_number"] = number
            remote = existing.get(number)
        if remote is None:
            remote = client.create_version(path.name, jar, metadata)
            published += 1
        if not matches(remote, metadata, digest):
            raise ValueError(f"Modrinth returned different files or metadata for {number}")
        print(f"{path.name}: {PROJECT_URL}/version/{remote['id']}", flush=True)
    print(f"Published {published} new Modrinth versions: {PROJECT_URL}/versions", flush=True)
