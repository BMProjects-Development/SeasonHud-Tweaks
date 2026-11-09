# Build and release

Use JDK 21 for Gradle. The mixins target SeasonHud methods and do not use Minecraft mappings. The Forge 1.17.1 port uses Forge’s overlay event and resolves the inventory lookup against that game’s Forge runtime names.

```sh
./gradlew build verifyPorts releaseBundle releaseSources
```

On Windows, use `gradlew.bat`. Use `-Pport=forge-1.16.5` with `build verifyPorts` to work on a single port. Release files go into `build/release`. Use a clean build directory for release packaging.

## Compatibility

[ports.json](ports.json) holds the release matrix, loader metadata, Minecraft versions, and the pinned upstream SeasonHud JAR and checksum for each port. The matrix follows the JAR metadata and available loader and dependency releases. The archived Fabric SeasonHud files tagged for 1.20.3 lack a compatible release of their required Forge Config API Port. The Fabric files tagged for 1.20.5 require Minecraft 1.20.6. Forge has no 1.20.5 build, and the NeoForge SeasonHud file for 1.20.6 requires NeoForge 20.6. The upstream 1.20.2–1.20.3 Forge file uses Forge classes. NeoForge 1.20.1 uses the Forge-compatible artifact.

`verifyPorts` uses Mixin to transform the actual upstream Calendar class for each mixin-based port. It checks the exact redirect count and confirms that the detailed display gate still calls its original config getter. For Forge 1.17.1 it checks the three referenced overlays against the archived JAR. These checks run outside Minecraft.

When validating in Minecraft, test an empty inventory, the first hotbar slot, a main inventory slot, the offhand, and a supported accessory slot. Remove the calendar while the HUD is visible, then verify that it hides. Repeat with SeasonHud’s **Requires Calendar** setting off and on, using the normal HUD and a supported minimap. For client-only multiplayer, connect to a server without SeasonHud Tweaks.

## Publishing

Update `mod_version` and add matching notes at `changelogs/<version>.md`. GitHub Actions runs on pushes and pull requests. Successful builds of the current default branch or a matching `v<version>` tag publish. The workflow verifies the full matrix, uploads the current version’s artifacts to a draft, then makes the release public. A rebuild of the same version updates only that release and its tag.

The release job uses `GITHUB_TOKEN` and the repository’s `CURSEFORGE_TOKEN` author API secret. CurseForge gets only playable JARs and their exact Minecraft, loader, and client tags. The GitHub release notes record accepted CurseForge upload IDs so a rerun can resume an interrupted set. CurseForge files become public after its review.
