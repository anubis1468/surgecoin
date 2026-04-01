from pathlib import Path
import textwrap
import json

ROOT = Path(__file__).resolve().parent
GM_ROOT = ROOT / "surgecoin_gm_full"

SCRIPTS = GM_ROOT / "scripts"
DOCS    = GM_ROOT / "docs"
DESIGN  = GM_ROOT / "design"


def ensure_dirs():
    for p in [GM_ROOT, SCRIPTS, DOCS, DESIGN]:
        p.mkdir(parents=True, exist_ok=True)


def write_design():
    game_design = textwrap.dedent("""
    # SurgeCoin – GameMaker Idle Miner

    Core Loop
    ---------
    - Tap to mine SurgeCoin.
    - Buy boosts to multiply taps or passive income.
    - Referrals increase passive income and give one-time bonuses.
    - Progress is saved locally and can sync with backend.

    Rooms
    -----
    - rm_mine      : main mining screen.
    - rm_wallet    : balance + boosts.
    - rm_referrals : referral info.
    - rm_settings  : options.

    Objects
    -------
    - obj_controller        : global state, passive income, boosts, sync.
    - obj_ui_button_mine    : tap button.
    - obj_ui_wallet_label   : shows balance.
    - obj_ui_boost_timer    : shows active boost + remaining time.
    - obj_coin_fx           : coin burst FX.
    """).strip() + "\n"

    economy = {
        "currency": "SurgeCoin",
        "base_tap_value": 1,
        "base_passive_per_sec": 0,
        "boosts": [
            {"id": "tap_x2_30", "name": "Tap x2 (30s)", "multiplier": 2, "duration_sec": 30},
            {"id": "tap_x5_20", "name": "Tap x5 (20s)", "multiplier": 5, "duration_sec": 20},
        ],
        "referral": {
            "bonus_per_referral": 10,
            "passive_per_referral": 0.1,
        }
    }

    (DESIGN / "game_design.md").write_text(game_design, encoding="utf-8")
    (DESIGN / "economy.json").write_text(json.dumps(economy, indent=2), encoding="utf-8")


def write_script(name: str, body: str):
    (SCRIPTS / f"{name}.gml").write_text(body.strip() + "\n", encoding="utf-8")


def write_gml_scripts():
    # obj_controller Create
    controller_create = textwrap.dedent("""
    /// obj_controller – Create

    global.surge_balance      = 0;
    global.tap_value          = 1;
    global.tap_multiplier     = 1;
    global.passive_per_sec    = 0;

    global.boost_active       = false;
    global.boost_end_time     = 0;
    global.boost_multiplier   = 1;

    global.referral_count     = 0;
    global.referral_bonus_per = 10;
    global.referral_passive   = 0.1;

    global.save_slot          = "surgecoin_save";

    global.last_passive_step  = current_time;

    global.backend_url        = "https://surgecoin-backend.workers.dev";
    global.sync_in_progress   = false;

    global.shake_power        = 0;
    """)
    write_script("obj_controller_Create", controller_create)

    # obj_controller Step
    controller_step = textwrap.dedent("""
    /// obj_controller – Step

    // Passive income
    var now = current_time;
    var elapsed_ms = now - global.last_passive_step;
    if (elapsed_ms >= 1000) {
        var seconds = elapsed_ms / 1000;
        global.surge_balance += global.passive_per_sec * seconds;
        global.last_passive_step = now;
    }

    // Boost expiration
    if (global.boost_active && current_time >= global.boost_end_time) {
        global.boost_active     = false;
        global.tap_multiplier   = 1;
        global.boost_multiplier = 1;
    }
    """)
    write_script("obj_controller_Step", controller_step)

    # obj_controller End Step (screenshake)
    controller_end_step = textwrap.dedent("""
    /// obj_controller – End Step (screenshake)

    if (global.shake_power > 0) {
        var cam = view_camera[0];
        var base_x = 0;
        var base_y = 0;

        var off_x = irandom_range(-global.shake_power, global.shake_power);
        var off_y = irandom_range(-global.shake_power, global.shake_power);

        camera_set_view_pos(cam, base_x + off_x, base_y + off_y);

        global.shake_power -= 0.5;
        if (global.shake_power < 0) global.shake_power = 0;
    }
    """)
    write_script("obj_controller_EndStep", controller_end_step)

    # obj_controller Async HTTP
    controller_async_http = textwrap.dedent("""
    /// obj_controller – Async HTTP

    var status = ds_map_find_value(async_load, "status");
    if (status != 0) {
        global.sync_in_progress = false;
        exit;
    }

    if (ds_map_exists(async_load, "result")) {
        var json = ds_map_find_value(async_load, "result");
        var map  = json_decode(json);

        if (ds_map_exists(map, "balance"))        global.surge_balance   = ds_map_find_value(map, "balance");
        if (ds_map_exists(map, "tap_value"))      global.tap_value       = ds_map_find_value(map, "tap_value");
        if (ds_map_exists(map, "tap_multiplier")) global.tap_multiplier  = ds_map_find_value(map, "tap_multiplier");
        if (ds_map_exists(map, "passive_per_sec"))global.passive_per_sec = ds_map_find_value(map, "passive_per_sec");
        if (ds_map_exists(map, "referral_count")) global.referral_count  = ds_map_find_value(map, "referral_count");

        ds_map_destroy(map);
    }

    global.sync_in_progress = false;
    """)
    write_script("obj_controller_AsyncHTTP", controller_async_http)

    # scr_mine_coin
    scr_mine_coin = textwrap.dedent("""
    /// @function scr_mine_coin()

    if (!variable_global_exists("surge_balance")) global.surge_balance = 0;
    if (!variable_global_exists("tap_value")) global.tap_value = 1;
    if (!variable_global_exists("tap_multiplier")) global.tap_multiplier = 1;

    var gain = global.tap_value * global.tap_multiplier;
    global.surge_balance += gain;

    // FX
    if (sprite_exists(spr_coin_fx)) {
        instance_create_layer(mouse_x, mouse_y, "Instances", obj_coin_fx);
    }
    scr_shake(3);
    """)
    write_script("scr_mine_coin", scr_mine_coin)

    # scr_apply_boost
    scr_apply_boost = textwrap.dedent("""
    /// @function scr_apply_boost(boost_id)
    /// @param boost_id

    var boost_id = argument0;

    var duration_ms = 0;
    var mult        = 1;

    switch (boost_id) {
        case "tap_x2_30":
            mult        = 2;
            duration_ms = 30 * 1000;
            break;

        case "tap_x5_20":
            mult        = 5;
            duration_ms = 20 * 1000;
            break;

        default:
            show_debug_message("Unknown boost: " + string(boost_id));
            return;
    }

    global.boost_active     = true;
    global.boost_multiplier = mult;
    global.tap_multiplier   = mult;
    global.boost_end_time   = current_time + duration_ms;
    """)
    write_script("scr_apply_boost", scr_apply_boost)

    # scr_add_referral
    scr_add_referral = textwrap.dedent("""
    /// @function scr_add_referral()

    if (!variable_global_exists("referral_count")) global.referral_count = 0;
    if (!variable_global_exists("referral_bonus_per")) global.referral_bonus_per = 10;
    if (!variable_global_exists("referral_passive")) global.referral_passive = 0.1;

    global.referral_count += 1;

    global.surge_balance += global.referral_bonus_per;

    global.passive_per_sec = global.referral_count * global.referral_passive;
    """)
    write_script("scr_add_referral", scr_add_referral)

    # scr_save_game
    scr_save_game = textwrap.dedent("""
    /// @function scr_save_game()

    var map = ds_map_create();

    ds_map_add(map, "surge_balance",    global.surge_balance);
    ds_map_add(map, "tap_value",        global.tap_value);
    ds_map_add(map, "tap_multiplier",   global.tap_multiplier);
    ds_map_add(map, "passive_per_sec",  global.passive_per_sec);
    ds_map_add(map, "referral_count",   global.referral_count);

    var json = json_encode(map);
    ds_map_destroy(map);

    var fname = global.save_slot + ".sav";
    var buffer = buffer_create(string_length(json), buffer_grow, 1);
    buffer_write(buffer, buffer_text, json);
    buffer_save(buffer, fname);
    buffer_delete(buffer);
    """)
    write_script("scr_save_game", scr_save_game)

    # scr_load_game
    scr_load_game = textwrap.dedent("""
    /// @function scr_load_game()

    var fname = global.save_slot + ".sav";
    if (!file_exists(fname)) exit;

    var buffer = buffer_load(fname);
    var json   = buffer_read(buffer, buffer_text);
    buffer_delete(buffer);

    var map = json_decode(json);

    global.surge_balance   = ds_map_find_value(map, "surge_balance");
    global.tap_value       = ds_map_find_value(map, "tap_value");
    global.tap_multiplier  = ds_map_find_value(map, "tap_multiplier");
    global.passive_per_sec = ds_map_find_value(map, "passive_per_sec");
    global.referral_count  = ds_map_find_value(map, "referral_count");

    ds_map_destroy(map);
    """)
    write_script("scr_load_game", scr_load_game)

    # scr_sync_push
    scr_sync_push = textwrap.dedent("""
    /// @function scr_sync_push()

    if (global.sync_in_progress) exit;
    global.sync_in_progress = true;

    var payload_map = ds_map_create();
    ds_map_add(payload_map, "balance",        global.surge_balance);
    ds_map_add(payload_map, "tap_value",      global.tap_value);
    ds_map_add(payload_map, "tap_multiplier", global.tap_multiplier);
    ds_map_add(payload_map, "passive_per_sec",global.passive_per_sec);
    ds_map_add(payload_map, "referral_count", global.referral_count);

    var json = json_encode(payload_map);
    ds_map_destroy(payload_map);

    var url = global.backend_url + "/sync";
    var headers = ds_map_create();
    ds_map_add(headers, "Content-Type", "application/json");

    var buffer = buffer_create(string_length(json), buffer_grow, 1);
    buffer_write(buffer, buffer_text, json);

    http_request(url, "POST", headers, buffer);

    buffer_delete(buffer);
    ds_map_destroy(headers);
    """)
    write_script("scr_sync_push", scr_sync_push)

    # scr_sync_pull
    scr_sync_pull = textwrap.dedent("""
    /// @function scr_sync_pull()

    if (global.sync_in_progress) exit;
    global.sync_in_progress = true;

    var url = global.backend_url + "/state";
    http_request(url, "GET");
    """)
    write_script("scr_sync_pull", scr_sync_pull)

    # scr_shake
    scr_shake = textwrap.dedent("""
    /// @function scr_shake(power)
    global.shake_power = max(global.shake_power, argument0);
    """)
    write_script("scr_shake", scr_shake)

    # obj_ui_boost_timer Draw
    boost_timer_draw = textwrap.dedent("""
    /// obj_ui_boost_timer – Draw

    if (!global.boost_active) exit;

    var remaining_ms = global.boost_end_time - current_time;
    if (remaining_ms < 0) remaining_ms = 0;

    var remaining_sec = floor(remaining_ms / 1000);

    draw_set_color(c_yellow);
    draw_text(x, y, "Boost: x" + string(global.tap_multiplier) + " (" + string(remaining_sec) + "s)");
    """)
    write_script("obj_ui_boost_timer_Draw", boost_timer_draw)

    # obj_ui_wallet_label Draw
    wallet_label_draw = textwrap.dedent("""
    /// obj_ui_wallet_label – Draw

    draw_set_color(c_white);
    draw_text(x, y, "Balance: " + string(floor(global.surge_balance)) + " SC");
    """)
    write_script("obj_ui_wallet_label_Draw", wallet_label_draw)

    # obj_coin_fx events (Create/Step/Draw)
    coin_fx_create = textwrap.dedent("""
    /// obj_coin_fx – Create
    image_alpha = 1;
    vsp = -2;
    """)
    write_script("obj_coin_fx_Create", coin_fx_create)

    coin_fx_step = textwrap.dedent("""
    /// obj_coin_fx – Step
    y += vsp;
    image_alpha -= 0.05;
    if (image_alpha <= 0) instance_destroy();
    """)
    write_script("obj_coin_fx_Step", coin_fx_step)

    coin_fx_draw = textwrap.dedent("""
    /// obj_coin_fx – Draw
    draw_set_alpha(image_alpha);
    draw_self();
    draw_set_alpha(1);
    """)
    write_script("obj_coin_fx_Draw", coin_fx_draw)


def write_docs():
    notes = textwrap.dedent("""
    SurgeCoin – GameMaker Automation Pack
    =====================================

    Generated by: generate_surgecoin_gamemaker_full.py

    What you get
    ------------
    - design/game_design.md      → high-level design.
    - design/economy.json        → base economy.
    - scripts/*.gml              → controller, mining, boosts, save/load, sync, FX, UI.

    How to wire in GameMaker
    ------------------------
    1. Create objects:
       - obj_controller
       - obj_ui_button_mine
       - obj_ui_wallet_label
       - obj_ui_boost_timer
       - obj_coin_fx

    2. For obj_controller:
       - Create Event   → paste scripts/obj_controller_Create.gml
       - Step Event     → paste scripts/obj_controller_Step.gml
       - End Step Event → paste scripts/obj_controller_EndStep.gml
       - Async HTTP     → paste scripts/obj_controller_AsyncHTTP.gml

    3. For obj_ui_button_mine:
       - Left Pressed event → call scr_mine_coin()

    4. For obj_ui_wallet_label:
       - Draw Event → paste scripts/obj_ui_wallet_label_Draw.gml

    5. For obj_ui_boost_timer:
       - Draw Event → paste scripts/obj_ui_boost_timer_Draw.gml

    6. For obj_coin_fx:
       - Create Event → scripts/obj_coin_fx_Create.gml
       - Step Event   → scripts/obj_coin_fx_Step.gml
       - Draw Event   → scripts/obj_coin_fx_Draw.gml

    7. Create scripts in GameMaker:
       - scr_mine_coin
       - scr_apply_boost
       - scr_add_referral
       - scr_save_game
       - scr_load_game
       - scr_sync_push
       - scr_sync_pull
       - scr_shake
       Paste the corresponding .gml files from scripts/.

    8. Place in rm_mine:
       - obj_controller
       - obj_ui_button_mine
       - obj_ui_wallet_label
       - obj_ui_boost_timer

    9. Backend
       - Your Cloudflare Worker should expose:
         - POST /sync  → accepts JSON { balance, tap_value, tap_multiplier, passive_per_sec, referral_count }
         - GET  /state → returns same JSON shape.
    """).strip() + "\n"

    (DOCS / "integration_notes.txt").write_text(notes, encoding="utf-8")


def main():
    print("=== SurgeCoin → GameMaker full pack generator ===")
    ensure_dirs()
    write_design()
    write_gml_scripts()
    write_docs()
    print(f"[OK] Generated full pack at: {GM_ROOT}")


if __name__ == "__main__":
    main()

