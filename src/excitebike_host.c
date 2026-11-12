/*
 * Excitebike's presentation extensions for NESRecomp's cycle host.
 *
 * The PPU continues to simulate and draw its native 256x240 frame. In a wide
 * view this compositor samples the nametables using the per-scanline scroll
 * state NESRecomp recorded, then adds the neighbouring background outside the
 * native viewport. The original 256x240 picture is copied back unchanged.
 */
#include "cyc_host_extras.h"
#include "cyc_render.h"
#include "cyc_video.h"
#include "recomp_runtime_ui.h"

#include <stdint.h>
#include <string.h>

static uint8_t s_background_opaque[CYC_VIDEO_MAX_WIDTH * 240];

static int wrap_coordinate(int value, int modulus)
{
    value %= modulus;
    return value < 0 ? value + modulus : value;
}

static uint32_t background_pixel(int screen_x, int world_x, int world_y,
                                 uint8_t mask, uint16_t pattern_table,
                                 int *opaque)
{
    *opaque = 0;
    if (!(mask & 0x08) || (screen_x >= 0 && screen_x < 8 && !(mask & 0x02)))
        return cyc_render_color(0);

    world_x = wrap_coordinate(world_x, 512);
    world_y = wrap_coordinate(world_y, 480);

    const int nt_x = world_x >> 8;
    const int nt_y = world_y / 240;
    const int tile_x = (world_x & 255) >> 3;
    const int tile_y = (world_y % 240) >> 3;
    const uint16_t nt_base = (uint16_t)(0x2000 + nt_y * 0x800 + nt_x * 0x400);
    const uint8_t tile = cyc_render_nametable(
        (uint16_t)(nt_base + tile_y * 32 + tile_x));
    const uint8_t attr = cyc_render_nametable(
        (uint16_t)(nt_base + 0x3C0 + (tile_y >> 2) * 8 + (tile_x >> 2)));
    const unsigned shift = ((tile_y & 2) ? 4u : 0u) + ((tile_x & 2) ? 2u : 0u);
    const unsigned palette = (attr >> shift) & 3u;
    const uint16_t pattern = (uint16_t)(pattern_table + tile * 16u + (world_y & 7));
    const unsigned bit = 7u - (unsigned)(world_x & 7);
    const uint8_t lo = cyc_render_chr(pattern);
    const uint8_t hi = cyc_render_chr((uint16_t)(pattern + 8));
    const unsigned pixel = ((lo >> bit) & 1u) | (((hi >> bit) & 1u) << 1);

    if (!pixel) return cyc_render_color(0);
    *opaque = 1;
    uint8_t color = cyc_render_palette((int)(palette * 4u + pixel));
    if (mask & 0x01) color &= 0x30; /* PPU greyscale mode */
    return cyc_render_color_value(color);
}

static int place_excited_sprite(int slot, int x, int y, int *out_x, void *user)
{
    (void)slot;
    (void)y;
    (void)user;
    *out_x = cyc_video_native_x0() + x;
    return 1;
}

static int compose_excitebike_widescreen(uint32_t *out, int width, int height,
                                         int native_x0, const uint32_t *native,
                                         void *user)
{
    (void)user;
    if (!out || !native || height != 240 || width < 256 ||
        width > CYC_VIDEO_MAX_WIDTH || native_x0 < 0 ||
        native_x0 + 256 > width)
        return 0;

    const uint8_t *native_opaque = cyc_frame_bg_opaque();
    for (int y = 0; y < 240; ++y) {
        const int scroll_x = cyc_render_line_scroll_x(y);
        const int scroll_y = cyc_render_line_scroll_y(y);
        const uint16_t pattern_table = cyc_render_line_bg_table(y);
        const uint8_t mask = cyc_render_line_mask(y);
        for (int x = 0; x < width; ++x) {
            const int screen_x = x - native_x0;
            const size_t at = (size_t)y * (size_t)width + (size_t)x;
            if (screen_x >= 0 && screen_x < 256) {
                s_background_opaque[at] =
                    native_opaque ? native_opaque[(size_t)y * 256u + (size_t)screen_x] : 0;
                continue;
            }

            int opaque = 0;
            out[at] = background_pixel(screen_x, scroll_x + screen_x,
                                       scroll_y, mask, pattern_table, &opaque);
            s_background_opaque[at] = (uint8_t)opaque;
        }
    }

    /* Reuse the engine's OAM/pattern-table sprite renderer so priority,
     * flips, 8x16 sprites and the NES sprite limit follow the captured frame. */
    cyc_render_sprites(out, width, height, native_x0,
                       s_background_opaque, place_excited_sprite, NULL);

    /* Never redraw the original viewport: it remains the exact native NES
     * image, including mid-scanline effects that a side-margin reconstruction
     * cannot reproduce. */
    for (int y = 0; y < 240; ++y) {
        memcpy(&out[(size_t)y * (size_t)width + (size_t)native_x0],
               &native[(size_t)y * 256u], 256u * sizeof(uint32_t));
    }
    return 1;
}

static void excitebike_power_on(void *ctx)
{
    (void)ctx;
    cyc_render_set_compositor(compose_excitebike_widescreen, NULL);
}

static int excitebike_get_view_mode(void *ctx)
{
    (void)ctx;
    switch (cyc_video_mode()) {
    case NES_VIDEO_16_9:
        return RECOMP_RUNTIME_UI_VIEW_FIXED_16_9;
    case NES_VIDEO_STOCK:
        return RECOMP_RUNTIME_UI_VIEW_NATIVE;
    default:
        return RECOMP_RUNTIME_UI_VIEW_ADAPTIVE;
    }
}

static bool excitebike_set_view_mode(void *ctx, int mode)
{
    (void)ctx;
    switch (mode) {
    case RECOMP_RUNTIME_UI_VIEW_NATIVE:
        cyc_video_set_mode(NES_VIDEO_STOCK);
        return true;
    case RECOMP_RUNTIME_UI_VIEW_FIXED_16_9:
        cyc_video_set_mode(NES_VIDEO_16_9);
        return true;
    case RECOMP_RUNTIME_UI_VIEW_ADAPTIVE:
        cyc_video_set_mode(NES_VIDEO_FIT);
        return true;
    default:
        return false;
    }
}

static const CycHostOption excitebike_options[] = {
    { "--widescreen", true, "stock, 16:9, 21:9, 32:9 or fit" },
};

static bool excitebike_option(void *ctx, const char *name, const char *value)
{
    (void)ctx;
    int mode;
    if (!name || strcmp(name, "--widescreen") || !nes_video_geometry_parse(value, &mode))
        return false;
    cyc_video_set_mode(mode);
    return true;
}

const CycHostExtras *cyc_host_extras(void)
{
    static const CycHostExtras extras = {
        .power_on = excitebike_power_on,
        .view_modes = RECOMP_RUNTIME_UI_VIEW_MODE_NATIVE |
                      RECOMP_RUNTIME_UI_VIEW_MODE_FIXED_16_9 |
                      RECOMP_RUNTIME_UI_VIEW_MODE_ADAPTIVE,
        .get_view_mode = excitebike_get_view_mode,
        .set_view_mode = excitebike_set_view_mode,
        .options = excitebike_options,
        .option_count = sizeof(excitebike_options) / sizeof(excitebike_options[0]),
        .option = excitebike_option,
    };
    return &extras;
}
