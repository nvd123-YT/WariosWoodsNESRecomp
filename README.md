# Wario's Woods Recompiled Builder

A cross-platform **local-build launcher** for the NES version of Wario's Woods, built on [NESRecomp](https://github.com/mstan/nesrecomp), [recomp-ui](https://github.com/RetroPortingToolKit/recomp-ui), and a pinned SDL2 source dependency.

> **Bring your own NES ROM.** This project targets the NES release, not the separate SNES version. The ROM picker requires an MMC3 / Mapper 4 cartridge. The downloadable applications do not contain a ROM, ROM-derived generated C source, or a prebuilt playable game; the native game is generated and compiled locally from a compatible `.nes` ROM you are legally entitled to use.

## Separate platform downloads

Every successful push to `main` runs the three platform builds. After all three succeed, GitHub creates a **new release** containing three separate assets:

- **macOS ARM64:** `WariosWoodsRecomp-macOS-ARM64.dmg` — contains `WariosWoodsRecomp.app`.
- **Windows x64:** `WariosWoodsRecomp-Windows-x64.exe`.
- **Linux x64:** `WariosWoodsRecomp-Linux-x64.AppImage`.

The release does not combine these downloads into one source ZIP. Previous releases are never replaced or deleted; each new successful push receives a unique tag and a new release page.

## What each launcher includes

Each platform package contains the launcher UI and its local-build resources:

- A bundled Python runtime for the launcher.
- Portable CMake and a managed Python runtime for build-time tooling.
- Full pinned NESRecomp and recomp-ui source trees, including NESRecomp's Mods runtime/package generators and recomp-ui's Dear ImGui sources and launcher assets.
- SDL2 source, built statically as part of the local game build.
- Wario's Woods game configuration, host integration, widescreen presentation hook, and bundled Mods integration.

The compiled game identifies itself as **Wario's Woods** in recomp-ui and its window title. The Mods screen includes NESRecomp's **Replay Capture** package (enabled by default; recordings stay local) and **Twitch Chat** package (optional and disabled by default; requires the separate chat bridge).

The launcher extracts these resources into the user's application-data directory, clears macOS Gatekeeper quarantine only from the bundled build-tool folders, asks for a local ROM, runs CMake, compiles the native game, and starts it. CMake and Python are bundled; the platform C/C++ compiler and SDK are still supplied by the operating system.

## Cartridge and save compatibility

The retail NES cartridges use **MMC3 / Mapper 4**. The common North American and European cartridges use battery-backed PRG RAM; the runtime supports the standard MMC3 mapper and cartridge NVRAM path. The launcher rejects ROMs whose headers do not identify Mapper 4, which helps prevent accidentally selecting the SNES version or an unrelated NES game.

For battery-backed cartridges, the cycle runtime automatically loads and writes the game's battery save in a `saves` folder beside the native executable. The launcher keeps its build and save folders in the operating system's per-user application-data location, so saves remain there when the launcher package is updated. Save files are local and are never uploaded by the release workflow.

## Video enhancements

The original NES hardware image remains **256×240**. The shared presentation layer provides the same display controls as the Excitebike builder:

- **Pre-game recomp-ui launcher:** open **Settings → Display** before choosing **PLAY**. **Widescreen** offers Native, 16:9 Fixed and Adaptive.
- **In-game runtime menu:** press Escape and open **Display** to change **View mode** and **HD resolution**.
- **HD resolution:** offers Pack resolution and 1× through 64× output scales for a compatible, user-supplied Mesen HD texture pack. It changes the HD-pack rendering scale, not the NES hardware framebuffer.
- **Integer scaling:** remains available for crisp whole-pixel scaling.

The widened side margins are experimental reconstruction from captured PPU state, not a change to the original game logic. Wario's Woods is a different title from the source project, so the widescreen view needs visual playtesting with the selected ROM; use **Native** for the most faithful original presentation. No HD texture pack is included, and this is not a generic switch that turns the NES framebuffer into an arbitrary 4K/8K image.

## Operating-system requirements

A platform compiler and SDK are still required:

- **macOS:** Apple Silicon Mac and Xcode Command Line Tools (`xcode-select --install`).
- **Windows:** Windows x64 and Visual Studio 2022 with the *Desktop development with C++* workload.
- **Linux:** x86_64, GCC or Clang, Make, OpenGL development files, and the desktop window/audio development headers for the distribution.

The launcher reports build errors in its output window. CMake and Python do not need to be installed separately.

## Using a release

1. Download the asset matching your operating system.
2. Open the DMG and move `WariosWoodsRecomp.app` to Applications on macOS. On Windows, run the EXE. On Linux, make the AppImage executable and open it.
3. Select your compatible Wario's Woods NES `.nes` ROM in the launcher.
4. Choose **Build Wario's Woods & Play**. The first local build compiles the pinned runtime and generated game code; later launches reuse the matching build.

On macOS, the app is not Developer ID notarized. If Gatekeeper blocks it, use Finder's Open context-menu action and review the macOS security prompt.

On Linux, the AppImage uses the x86_64 Type 2 format. If FUSE is unavailable, extract the AppImage with its `--appimage-extract` option and launch `AppRun` from the extracted directory.

## Reproducible source build

Clone the source and all pinned dependencies:

```bash
git clone --recurse-submodules https://github.com/nvd123-YT/WariosWoodsNESRecomp.git
cd WariosWoodsNESRecomp
```

macOS / Linux:

```bash
bash setup.sh
bash tools/build.sh "/absolute/path/to/WariosWoods.nes"
```

Windows PowerShell:

```powershell
.\setup.bat
powershell -ExecutionPolicy Bypass -File .\tools\build.ps1 "C:\Games\WariosWoods.nes"
```

## CI and release safety

The public workflow builds the launcher and native runner on macOS ARM64, Windows x64, and Linux x64. CI uses a synthetic test cartridge only; it does not use a copyrighted Wario's Woods ROM or publish ROM-derived output. The three downloadable packages contain the launcher, portable CMake, managed Python, pinned source dependencies, and game project code—but no ROM, generated game code, saves, or compiled playable copy of Wario's Woods.

Release publishing runs only after all three platform jobs and package checks pass. Each successful push receives a unique tag of the form `build-RUN-ATTEMPT-COMMIT`, preserving older release pages and their download counters.

## Repository contents

- `launcher.py` — cross-platform ROM picker and local-build UI, including the Mapper 4 check.
- `CMakeLists.txt` and `game.toml` — native recompilation project and Wario's Woods identity.
- `src/warioswoods_host.c` — title host integration and display hook.
- `nesrecomp/`, `recomp-ui/`, `SDL2/` — pinned dependency submodules.
- `tools/package_builder.py` — creates the ROM-free resources embedded in each launcher.
- `.github/workflows/source-release.yml` — three-platform build and unique-release workflow.

No ROMs, generated game code, local saves, or compiled playable game are committed or published.
