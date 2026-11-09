"""GitHub releases and CurseForge author uploads."""

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


RECEIPT = re.compile(r"\n?<!-- seasonhudtweaks-curseforge (\{[^\n]*\}) -->")


def uploads_in(body):
    matches = RECEIPT.findall(body or "")
    if len(matches) > 1:
        raise ValueError("Multiple CurseForge receipts in the release body")
    receipts = json.loads(matches[0]) if matches else {}
    if not isinstance(receipts, dict) or any(
        not re.fullmatch(r"[a-f0-9]{64}", digest) or type(file_id) is not int or file_id <= 0
        for digest, file_id in receipts.items()
    ):
        raise ValueError("Invalid CurseForge receipts in the release body")
    return receipts


def with_uploads(notes, receipts):
    if not receipts:
        return notes
    return notes + "\n\n<!-- seasonhudtweaks-curseforge " + json.dumps(receipts, sort_keys=True) + " -->"


class GitHub:
    def __init__(self, token, api_url):
        self.token = token
        self.api_url = api_url.rstrip("/")

    def request(self, method, endpoint, data=None, *, missing_ok=False):
        url = endpoint if endpoint.startswith("https://") else self.api_url + endpoint
        binary = isinstance(data, bytes)
        body = data if binary else json.dumps(data).encode() if data is not None else None
        request = Request(url, data=body, method=method, headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/octet-stream" if binary else "application/json",
            "User-Agent": "SeasonHud-Tweaks-release",
        })
        try:
            with urlopen(request, timeout=60) as response:
                content = response.read()
                return json.loads(content) if content else None
        except HTTPError as error:
            if missing_ok and error.code == 404:
                return None
            raise RuntimeError(f"GitHub {method} {endpoint}: HTTP {error.code}") from None


def find_release(api, base, tag):
    # The release list includes drafts left by interrupted uploads.
    page = 1
    while True:
        releases = api.request("GET", f"{base}/releases?per_page=100&page={page}")
        for release in releases:
            if release["tag_name"] == tag:
                return release
        if len(releases) < 100:
            return None
        page += 1


class CurseForge:
    PROJECT = 1506134

    def __init__(self, token):
        if not token:
            raise ValueError("Add the CurseForge author token as the CURSEFORGE_TOKEN Actions secret")
        self.token = token

    def request(self, endpoint, body=None, content_type="application/json"):
        request = Request("https://minecraft.curseforge.com/api/" + endpoint, data=body, headers={
            "X-Api-Token": self.token,
            "Content-Type": content_type,
            "User-Agent": "SeasonHud-Tweaks-release",
        })
        try:
            with urlopen(request, timeout=120) as response:
                return json.load(response)
        except HTTPError as error:
            detail = error.read(4096).decode("utf-8", errors="replace")
            detail = " ".join(detail.replace(self.token, "[redacted]").split())[:500]
            raise RuntimeError(f"CurseForge {endpoint}: HTTP {error.code} {detail}") from None
        except URLError as error:
            raise RuntimeError(f"CurseForge {endpoint}: {error.reason}") from None

    def version_ids(self, ports):
        versions = self.request("game/versions")
        types = self.request("game/version-types")
        loaders = {"fabric": "Fabric", "forge": "Forge", "neoforge": "NeoForge"}

        def resolve(name, category):
            type_ids = {row["id"] for row in types if row["slug"].lower().startswith(category)}
            matches = {row["id"] for row in versions if row["name"] == name and row["gameVersionTypeID"] in type_ids}
            if len(matches) != 1:
                raise ValueError(f"Cannot uniquely resolve CurseForge {category} version {name}: {sorted(matches)}")
            return matches.pop()

        client_id = resolve("Client", "environment")
        return {
            port["id"]: [resolve(version, "minecraft") for version in port["minecraft"]]
            + [resolve(loaders[port["loader"]], "modloader"), client_id]
            for port in ports
        }

    def upload(self, filename, jar, metadata):
        boundary = "seasonhudtweaks-" + uuid4().hex
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n'
            'Content-Type: application/json\r\n\r\n'
        ).encode() + json.dumps(metadata).encode() + (
            f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            'Content-Type: application/java-archive\r\n\r\n'
        ).encode() + jar + f"\r\n--{boundary}--\r\n".encode()
        result = self.request(f"projects/{self.PROJECT}/upload-file", body, f"multipart/form-data; boundary={boundary}")
        file_id = result.get("id") if isinstance(result, dict) else None
        if type(file_id) is not int or file_id <= 0:
            raise RuntimeError("CurseForge upload did not return a valid file ID")
        return file_id