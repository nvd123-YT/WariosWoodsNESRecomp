cmake_minimum_required(VERSION 3.20)
project(WariosWoodsRecomp C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(NESRECOMP_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/nesrecomp" CACHE PATH
    "Path to the NESRecomp framework checkout")
set(NESRECOMP_RECOMP_UI "${CMAKE_CURRENT_SOURCE_DIR}/recomp-ui" CACHE STRING
    "Path to the shared recomp-ui checkout")
set(SDL2_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/SDL2" CACHE PATH
    "Path to the pinned SDL2 source checkout")
set(NESRECOMP_ROM "" CACHE FILEPATH
    "User-supplied Wario's Woods ROM used for local native code generation")

foreach(required
    "${NESRECOMP_ROOT}/runner/cyc/project.cmake"
    "${NESRECOMP_RECOMP_UI}/recomp_ui.cmake"
    "${SDL2_SOURCE_DIR}/CMakeLists.txt"
    "${CMAKE_CURRENT_SOURCE_DIR}/game.toml")
    if(NOT EXISTS "${required}")
        message(FATAL_ERROR
            "Required source is missing: ${required}. Run setup.sh or setup.bat to initialize dependencies.")
    endif()
endforeach()

if(NOT EXISTS "${NESRECOMP_ROM}")
    message(FATAL_ERROR
        "A local Wario's Woods ROM is required. Configure with -DNESRECOMP_ROM=/absolute/path/to/Wario's Woods.nes. ROMs are not distributed.")
endif()

# Build SDL2 from the pinned source submodule as a static library. This removes
# the need for a separately installed SDL2 SDK or runtime DLL/dylib at build
# time. Native platform SDKs and a C/C++ compiler are still supplied by the OS.
set(SDL_SHARED OFF CACHE BOOL "Build SDL2 shared library" FORCE)
set(SDL_STATIC ON CACHE BOOL "Build SDL2 static library" FORCE)
set(SDL_TEST OFF CACHE BOOL "Build SDL2 tests" FORCE)
set(SDL_TESTS OFF CACHE BOOL "Build SDL2 test suite" FORCE)
add_subdirectory("${SDL2_SOURCE_DIR}" "${CMAKE_BINARY_DIR}/_deps/sdl2-build" EXCLUDE_FROM_ALL)

# NESRecomp's cycle runner calls find_package(SDL2 CONFIG). This small config
# bridges that lookup to the SDL2::SDL2 alias created by SDL's in-tree build.
set(SDL2_DIR "${CMAKE_CURRENT_SOURCE_DIR}/cmake/bundled-sdl2" CACHE PATH
    "Bundled SDL2 package bridge" FORCE)

include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/apply_nesrecomp_patches.cmake")

# Include at file scope: project.cmake detects the pinned recomp-ui checkout,
# validates its ROM-picker/runtime-menu ABI, and enables C++ integration.
include("${NESRECOMP_ROOT}/runner/cyc/project.cmake")

nesrecomp_add_cycle_game(WariosWoodsRecomp
    ROM "${NESRECOMP_ROM}"
    GAME_CONFIG "${CMAKE_CURRENT_SOURCE_DIR}/game.toml"
    MODS
    HD_PACKS
    GAME_ID "warioswoods-nes"
    HOST_EXTRAS "${CMAKE_CURRENT_SOURCE_DIR}/src/warioswoods_host.c"
)

get_target_property(_warioswoods_sdl WariosWoodsRecomp NESRECOMP_CYC_SDL)
if(NOT _warioswoods_sdl)
    message(FATAL_ERROR "SDL2 static runner integration failed.")
endif()
if(NOT NESRECOMP_CYC_RECOMP_UI_ROOT)
    message(FATAL_ERROR
        "The pinned recomp-ui revision is missing the NES cycle-host launcher/runtime integration.")
endif()

message(STATUS "Wario's Woods: bundled SDL2 static library enabled")
message(STATUS "Wario's Woods: recomp-ui launcher and runtime menu enabled")
message(STATUS "Wario's Woods: ROM-derived native code remains in the local build directory")
