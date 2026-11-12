# Expose the cycle host's view-mode and HD-pack scale in the pre-game recomp-ui launcher.
# The in-game runtime menu is a separate UI and is patched below.
set(_nes_ui_launcher "${NESRECOMP_ROOT}/runner/cyc/cyc_ui_launcher.c")
if(NOT EXISTS "${_nes_ui_launcher}")
    message(FATAL_ERROR "Pinned NESRecomp launcher source is missing: ${_nes_ui_launcher}")
endif()

file(READ "${_nes_ui_launcher}" _nes_ui_source)
set(_nes_ui_original "${_nes_ui_source}")

# The launcher supports a game-authored aspect vocabulary. This is what its
# Display -> Widescreen row actually renders; widescreen_supported alone is
# not consumed by the pinned launcher_ng Display renderer.
if(NOT _nes_ui_source MATCHES "s_view_mode_labels\\[\\]")
    set(_old "    static const char *const FDS_PATTERNS[] = { \"*.fds\", \"*.qd\" };\n")
    set(_new "    static const char *const FDS_PATTERNS[] = { \"*.fds\", \"*.qd\" };\n    static const char *const s_view_mode_labels[] = { \"Native\", \"16:9 Fixed\", \"Adaptive\" };\n#ifdef NESRECOMP_CYCLE_HDPACK\n    static const int s_hd_resolution_values[] = { 0, 1, 2, 4, 8, 16, 32, 64 };\n    static const char *const s_hd_resolution_labels[] = { \"Pack resolution\", \"1×\", \"2×\", \"4×\", \"8×\", \"16×\", \"32× (Experimental)\", \"64× (Experimental)\" };\n#endif\n")
    string(FIND "${_nes_ui_source}" "${_old}" _at)
    if(_at EQUAL -1)
        message(FATAL_ERROR "Cannot patch NESRecomp launcher: static UI vocabulary insertion point changed.")
    endif()
    string(REPLACE "${_old}" "${_new}" _nes_ui_source "${_nes_ui_source}")
endif()

# Round-trip the host's existing ViewMode value through recomp-ui's aspect
# selector and its existing internal_resolution field through the HD scale list.
if(NOT _nes_ui_source MATCHES "io->aspect_index = s->view_mode;")
    set(_old "    io->linear_filter = s->linear_filter;\n")
    set(_new "    io->linear_filter = s->linear_filter;\n    io->aspect_index = s->view_mode;\n#ifdef NESRECOMP_CYCLE_HDPACK\n    io->internal_resolution = s->hd_resolution;\n#endif\n")
    string(FIND "${_nes_ui_source}" "${_old}" _at)
    if(_at EQUAL -1)
        message(FATAL_ERROR "Cannot patch NESRecomp launcher: to-launcher Display hook changed.")
    endif()
    string(REPLACE "${_old}" "${_new}" _nes_ui_source "${_nes_ui_source}")
endif()

if(NOT _nes_ui_source MATCHES "s->view_mode = io->aspect_index")
    set(_old "    s->linear_filter = io->linear_filter != 0;\n")
    set(_new "    s->linear_filter = io->linear_filter != 0;\n    s->view_mode = io->aspect_index < 0 ? 0 : io->aspect_index > 2 ? 2 : io->aspect_index;\n#ifdef NESRECOMP_CYCLE_HDPACK\n    s->hd_resolution = (io->internal_resolution == 1 || io->internal_resolution == 2 || io->internal_resolution == 4 || io->internal_resolution == 8 || io->internal_resolution == 16 || io->internal_resolution == 32 || io->internal_resolution == 64) ? io->internal_resolution : 0;\n#endif\n")
    string(FIND "${_nes_ui_source}" "${_old}" _at)
    if(_at EQUAL -1)
        message(FATAL_ERROR "Cannot patch NESRecomp launcher: from-launcher Display hook changed.")
    endif()
    string(REPLACE "${_old}" "${_new}" _nes_ui_source "${_nes_ui_source}")
endif()

set(_old "    gi.widescreen_supported = 0;\n    (void)extras;\n")
set(_new "    gi.widescreen_supported = 0; /* use the explicit aspect vocabulary below */\n    gi.aspect_labels = s_view_mode_labels;\n    gi.num_aspect_labels = (int)(sizeof(s_view_mode_labels) / sizeof(s_view_mode_labels[0]));\n    gi.aspect_setting_label = \"Widescreen\";\n    gi.aspect_setting_help = \"Native keeps the original NES viewport. 16:9 Fixed expands the presentation; Adaptive follows the window. The added side margins are experimental.\";\n    gi.aspect_experimental = 1;\n#ifdef NESRECOMP_CYCLE_HDPACK\n    gi.has_supersampling = 1;\n    gi.internal_resolution_labels = s_hd_resolution_labels;\n    gi.internal_resolution_values = s_hd_resolution_values;\n    gi.num_internal_resolutions = (int)(sizeof(s_hd_resolution_values) / sizeof(s_hd_resolution_values[0]));\n    gi.internal_resolution_note = \"Controls the output scale of a compatible Mesen HD texture pack. The native 256x240 NES image is unchanged.\";\n#endif\n")
string(FIND "${_nes_ui_source}" "${_old}" _capability_at)
if(NOT _capability_at EQUAL -1)
    string(REPLACE "${_old}" "${_new}" _nes_ui_source "${_nes_ui_source}")
else()
    string(FIND "${_nes_ui_source}" "gi.aspect_labels = s_view_mode_labels;" _capability_new_at)
    if(_capability_new_at EQUAL -1)
        message(FATAL_ERROR "Cannot patch NESRecomp launcher: game display capability hook changed.")
    endif()
endif()

string(FIND "${_nes_ui_source}" "extras->set_view_mode(extras->ctx, settings->view_mode)" _apply_view_mode_at)
if(_apply_view_mode_at EQUAL -1)
    set(_old "    from_launcher(&io, settings, shortcuts, count);\n")
    set(_new "    from_launcher(&io, settings, shortcuts, count);\n    if (extras && extras->set_view_mode)\n        (void)extras->set_view_mode(extras->ctx, settings->view_mode);\n")
    string(FIND "${_nes_ui_source}" "${_old}" _at)
    if(_at EQUAL -1)
        message(FATAL_ERROR "Cannot patch NESRecomp launcher: settings-return hook changed.")
    endif()
    string(REPLACE "${_old}" "${_new}" _nes_ui_source "${_nes_ui_source}")
endif()

if(NOT _nes_ui_source STREQUAL _nes_ui_original)
    file(WRITE "${_nes_ui_launcher}" "${_nes_ui_source}")
endif()

message(STATUS "Excitebike: pre-game recomp-ui Display → Widescreen registered")
message(STATUS "Excitebike: pre-game recomp-ui HD resolution scale registered")

# Apply small, deterministic fixes to the pinned cycle runtime UI sources.
# The upstream submodules stay immutable in Git; this patch is applied before
# their targets are configured and compiled.

# Ensure the in-game Display page exposes the host's actual runtime view modes.
set(_cycle_menu "${NESRECOMP_ROOT}/runner/cyc/cyc_ui_menu.c")
if(NOT EXISTS "${_cycle_menu}")
    message(FATAL_ERROR "Pinned NESRecomp runtime menu source is missing: ${_cycle_menu}")
endif()
file(READ "${_cycle_menu}" _cycle_source)
set(_cycle_original "${_cycle_source}")

set(_old_view_modes [=[
    if (x && x->view_modes && x->set_view_mode) {
        std.features |= RECOMP_RUNTIME_UI_STANDARD_VIEW_MODE;
        std.view_modes = x->view_modes;
    }
]=])
set(_new_view_modes [=[
    if (x && x->get_view_mode && x->set_view_mode) {
        std.features |= RECOMP_RUNTIME_UI_STANDARD_VIEW_MODE;
        std.view_modes = x->view_modes
            ? x->view_modes
            : (RECOMP_RUNTIME_UI_VIEW_MODE_NATIVE |
               RECOMP_RUNTIME_UI_VIEW_MODE_FIXED_16_9 |
               RECOMP_RUNTIME_UI_VIEW_MODE_ADAPTIVE);
    }
]=])
string(FIND "${_cycle_source}" "${_old_view_modes}" _view_old_at)
if(NOT _view_old_at EQUAL -1)
    string(REPLACE "${_old_view_modes}" "${_new_view_modes}" _cycle_source "${_cycle_source}")
else()
    string(FIND "${_cycle_source}" "${_new_view_modes}" _view_new_at)
    if(_view_new_at EQUAL -1)
        message(FATAL_ERROR "Cannot patch NESRecomp runtime menu: View mode registration block changed.")
    endif()
endif()

if(NOT _cycle_source STREQUAL _cycle_original)
    file(WRITE "${_cycle_menu}" "${_cycle_source}")
endif()

# Fix the in-game settings panel. A section click must enter the section in
# both the narrow and two-column layouts. Hover can preview another section
# without accidentally leaving the current page-navigation state.
set(_runtime_ui "${NESRECOMP_RECOMP_UI}/src/common/backends/imgui/runtime_ui_imgui.cpp")
if(NOT EXISTS "${_runtime_ui}")
    message(FATAL_ERROR "Pinned recomp-ui runtime renderer is missing: ${_runtime_ui}")
endif()
file(READ "${_runtime_ui}" _runtime_source)
set(_runtime_original "${_runtime_source}")

set(_old_section [=[
void draw_sections(RecompRuntimeUi *ui, const LauncherTheme &theme,
                   bool enter_on_click) {
    for (size_t index = 0; index < ui->section_count; ++index) {
        ImGui::PushID(static_cast<int>(index));
        const bool selected = index == ui->section_index;
        const bool clicked = ImGui::Selectable(ui->sections[index], selected, 0,
                                               ImVec2(0.0f, theme.row_height));
        if ((clicked || ImGui::IsItemHovered()) &&
            (index != ui->section_index || (clicked && enter_on_click))) {
            const int was_in_section = ui->in_section;
            recomp_runtime_ui_enter_section(ui, index);
            if (!(clicked && enter_on_click)) ui->in_section = was_in_section;
        }
        ImGui::PopID();
    }
}
]=])
set(_new_section [=[
void draw_sections(RecompRuntimeUi *ui, const LauncherTheme &theme,
                   bool enter_on_click) {
    (void)enter_on_click;
    for (size_t index = 0; index < ui->section_count; ++index) {
        ImGui::PushID(static_cast<int>(index));
        const bool selected = index == ui->section_index;
        const bool clicked = ImGui::Selectable(ui->sections[index], selected, 0,
                                               ImVec2(0.0f, theme.row_height));
        const bool hovered = ImGui::IsItemHovered();
        if (clicked) {
            /* A click always opens the selected page, even if it was already highlighted. */
            recomp_runtime_ui_enter_section(ui, index);
        } else if (hovered && index != ui->section_index) {
            /* Hover previews a page but preserves the current navigation level. */
            const int was_in_section = ui->in_section;
            recomp_runtime_ui_enter_section(ui, index);
            ui->in_section = was_in_section;
        }
        ImGui::PopID();
    }
}
]=])
string(FIND "${_runtime_source}" "${_old_section}" _section_old_at)
if(NOT _section_old_at EQUAL -1)
    string(REPLACE "${_old_section}" "${_new_section}" _runtime_source "${_runtime_source}")
else()
    string(FIND "${_runtime_source}" "A click always opens the selected page" _section_new_at)
    if(_section_new_at EQUAL -1)
        message(FATAL_ERROR "Cannot patch recomp-ui runtime menu navigation: section renderer changed.")
    endif()
endif()

# Runtime setting descriptions must wrap inside their row rather than draw
# over values or outside the settings panel. Row height follows the wrapped
# description so the containing child can scroll normally.
set(_old_row_height [=[
        const float row_h = item->description && item->description[0]
                                ? theme.row_height + theme.spacing_sm
                                : theme.row_height;
]=])
set(_new_row_height [=[
        const float description_width = std::max(
            1.0f, ImGui::GetContentRegionAvail().x - theme.spacing_md * 2.0f);
        const ImVec2 description_size =
            item->description && item->description[0]
                ? ImGui::CalcTextSize(item->description, nullptr, false,
                                      description_width)
                : ImVec2(0.0f, 0.0f);
        const float row_h = theme.row_height +
            (description_size.y > 0.0f
                ? theme.spacing_sm + description_size.y
                : 0.0f);
]=])
string(FIND "${_runtime_source}" "${_old_row_height}" _row_old_at)
if(NOT _row_old_at EQUAL -1)
    string(REPLACE "${_old_row_height}" "${_new_row_height}" _runtime_source "${_runtime_source}")
else()
    string(FIND "${_runtime_source}" "const float description_width = std::max(" _row_new_at)
    if(_row_new_at EQUAL -1)
        message(FATAL_ERROR "Cannot patch recomp-ui runtime menu: setting row sizing changed.")
    endif()
endif()

set(_old_description [=[
        if (item->description && item->description[0]) {
            draw->AddText(ImVec2(start.x + theme.spacing_md,
                                start.y + theme.spacing_sm +
                                    ImGui::GetTextLineHeight() + 2.0f),
                          u32(theme.text_muted), item->description);
        }
]=])
set(_new_description [=[
        if (item->description && item->description[0]) {
            const ImVec2 description_pos(
                start.x + theme.spacing_md,
                start.y + theme.spacing_sm + ImGui::GetTextLineHeight() + 2.0f);
            const ImVec2 description_max(
                end.x - theme.spacing_md, start.y + row_h);
            draw->PushClipRect(description_pos, description_max, true);
            draw->AddText(ImGui::GetFont(), ImGui::GetFontSize(),
                          description_pos, u32(theme.text_muted),
                          item->description, nullptr, description_width);
            draw->PopClipRect();
        }
]=])
string(FIND "${_runtime_source}" "${_old_description}" _description_old_at)
if(NOT _description_old_at EQUAL -1)
    string(REPLACE "${_old_description}" "${_new_description}" _runtime_source "${_runtime_source}")
else()
    string(FIND "${_runtime_source}" "description_max(" _description_new_at)
    if(_description_new_at EQUAL -1)
        message(FATAL_ERROR "Cannot patch recomp-ui runtime menu: setting description renderer changed.")
    endif()
endif()

if(NOT _runtime_source STREQUAL _runtime_original)
    file(WRITE "${_runtime_ui}" "${_runtime_source}")
endif()


# Keep the HD texture-pack output-scale selector with the other Display options.
# This is the HD-pack rendering scale, not a claim that the NES framebuffer changes size.
set(_old_hd_row "add(\"cyc.hd.resolution\", \"Graphics\", \"HD resolution\",")
set(_new_hd_row "add(\"cyc.hd.resolution\", \"Display\", \"HD resolution\",")
string(FIND "${_cycle_source}" "${_old_hd_row}" _hd_row_old_at)
if(NOT _hd_row_old_at EQUAL -1)
    string(REPLACE "${_old_hd_row}" "${_new_hd_row}" _cycle_source "${_cycle_source}")
else()
    string(FIND "${_cycle_source}" "${_new_hd_row}" _hd_row_new_at)
    if(_hd_row_new_at EQUAL -1)
        message(FATAL_ERROR "Cannot patch NESRecomp runtime menu: HD resolution row changed.")
    endif()
endif()
if(NOT _cycle_source STREQUAL _cycle_original)
    file(WRITE "${_cycle_menu}" "${_cycle_source}")
endif()


# Give the generic resolution-vocabulary control the accurate title and help
# for this host: it selects the Mesen HD-pack output scale, not NES framebuffer
# or generic game-internal resolution.
set(_launcher_imgui "${NESRECOMP_RECOMP_UI}/src/common/backends/imgui/launcher_imgui.cpp")
if(NOT EXISTS "${_launcher_imgui}")
    message(FATAL_ERROR "Pinned recomp-ui launcher renderer is missing: ${_launcher_imgui}")
endif()
file(READ "${_launcher_imgui}" _launcher_imgui_source)
set(_launcher_imgui_original "${_launcher_imgui_source}")

set(_old_resolution_label "settings_fit_w(\"Internal resolution\", th, settings_widest_text(")
set(_new_resolution_label "settings_fit_w(\"HD resolution\", th, settings_widest_text(")
string(FIND "${_launcher_imgui_source}" "${_old_resolution_label}" _resolution_label_at)
if(NOT _resolution_label_at EQUAL -1)
    string(REPLACE "${_old_resolution_label}" "${_new_resolution_label}" _launcher_imgui_source "${_launcher_imgui_source}")
else()
    string(FIND "${_launcher_imgui_source}" "${_new_resolution_label}" _resolution_label_new_at)
    if(_resolution_label_new_at EQUAL -1)
        message(FATAL_ERROR "Cannot patch recomp-ui launcher: internal resolution label hook changed.")
    endif()
endif()

set(_old_resolution_row "row_label_right(\"Internal resolution\", th, iw);")
set(_new_resolution_row "row_label_right(\"HD resolution\", th, iw);")
string(FIND "${_launcher_imgui_source}" "${_old_resolution_row}" _resolution_row_at)
if(NOT _resolution_row_at EQUAL -1)
    string(REPLACE "${_old_resolution_row}" "${_new_resolution_row}" _launcher_imgui_source "${_launcher_imgui_source}")
else()
    string(FIND "${_launcher_imgui_source}" "${_new_resolution_row}" _resolution_row_new_at)
    if(_resolution_row_new_at EQUAL -1)
        message(FATAL_ERROR "Cannot patch recomp-ui launcher: HD resolution row label hook changed.")
    endif()
endif()

set(_old_resolution_tip [=[
        if (ImGui::IsItemHovered(ImGuiHoveredFlags_DelayNormal)) {
            ImGui::SetTooltip("%s", ui_text(
                "Renders the game at this height, not an upscale.\n"
                "Cost grows with the square of the scale.\n"
                "Match display uses your monitor's full resolution.\n"
                "Applies when the game starts.\n"
                "Auto renders at your monitor's resolution and steps down\n"
                "when the game would miss frames, then back up.\n"
                "Netplay: your view only; other players are unaffected."));
        }
]=])
set(_new_resolution_tip [=[
        if (ImGui::IsItemHovered(ImGuiHoveredFlags_DelayNormal)) {
            ImGui::SetTooltip("%s", ui_text(
                "Selects the output scale for a compatible Mesen HD texture pack.\n"
                "Pack resolution uses the pack's original scale.\n"
                "Higher scales require more GPU memory and rendering work.\n"
                "The native 256x240 NES hardware image remains unchanged.\n"
                "Applies when the game starts."));
        }
]=])
string(FIND "${_launcher_imgui_source}" "${_old_resolution_tip}" _resolution_tip_at)
if(NOT _resolution_tip_at EQUAL -1)
    string(REPLACE "${_old_resolution_tip}" "${_new_resolution_tip}" _launcher_imgui_source "${_launcher_imgui_source}")
else()
    string(FIND "${_launcher_imgui_source}" "Selects the output scale for a compatible Mesen HD texture pack." _resolution_tip_new_at)
    if(_resolution_tip_new_at EQUAL -1)
        message(FATAL_ERROR "Cannot patch recomp-ui launcher: internal resolution tooltip hook changed.")
    endif()
endif()
if(NOT _launcher_imgui_source STREQUAL _launcher_imgui_original)
    file(WRITE "${_launcher_imgui}" "${_launcher_imgui_source}")
endif()

message(STATUS "Excitebike: in-game Display → View mode registered")
message(STATUS "Excitebike: fixed runtime settings navigation and wrapped setting descriptions")
