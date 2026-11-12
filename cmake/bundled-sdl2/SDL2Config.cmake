# Package bridge for the in-tree SDL2 static target.
# SDL2 itself is added from the pinned SDL2 submodule by the root CMakeLists.
if(NOT TARGET SDL2::SDL2)
    message(FATAL_ERROR
        "Bundled SDL2 target is missing. Ensure SDL2 is configured before NESRecomp.")
endif()
set(SDL2_FOUND TRUE)
set(SDL2_VERSION "2.32.10")
set(SDL2_VERSION_STRING "2.32.10")
