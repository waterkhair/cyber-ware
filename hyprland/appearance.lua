-- Shared cyber-ware palette. The user command writes `synthwave`, `greenline`, or `husky`
-- to ~/.config/cyber-ware/theme; absent/invalid values keep synthwave default.
local home = os.getenv("HOME") or ""
local config_home = os.getenv("XDG_CONFIG_HOME") or (home .. "/.config")
local theme_file = io.open(config_home .. "/cyber-ware/theme", "r")
local theme = "synthwave"
if theme_file then
    local selected = theme_file:read("*l")
    theme_file:close()
    if selected == "greenline" or selected == "synthwave" or selected == "husky" then theme = selected end
end

local palettes = {
    synthwave = {
        active = { colors = { "rgba(00e5ffff)", "rgba(8b5cf6ff)" }, angle = 45 },
        inactive = "rgba(7f8ca366)",
        group_active = { colors = { "rgba(00b8ff99)", "rgba(8b5cf699)" }, angle = 45 },
        group_inactive = "rgba(8b5cf644)",
        locked_active = "rgba(ff2e9388)",
        locked_inactive = "rgba(ff2e9344)",
        groupbar_active = { colors = { "rgba(00b8ff33)", "rgba(8b5cf633)" }, angle = 45 },
        groupbar_inactive = "rgba(8b5cf61a)",
        groupbar_locked_active = "rgba(ff2e9333)",
        groupbar_locked_inactive = "rgba(ff2e931a)",
    },
    greenline = {
        active = { colors = { "rgba(8df0a6ff)", "rgba(5bd67dff)" }, angle = 45 },
        inactive = "rgba(5bd67d66)",
        group_active = { colors = { "rgba(8df0a6aa)", "rgba(5bd67d99)" }, angle = 45 },
        group_inactive = "rgba(5bd67d44)",
        locked_active = "rgba(f1c66d88)",
        locked_inactive = "rgba(f1c66d44)",
        groupbar_active = { colors = { "rgba(8df0a633)", "rgba(5bd67d33)" }, angle = 45 },
        groupbar_inactive = "rgba(5bd67d1a)",
        groupbar_locked_active = "rgba(f1c66d33)",
        groupbar_locked_inactive = "rgba(f1c66d1a)",
    },
    husky = {
        active = { colors = { "rgba(ffffffff)", "rgba(bbbbbbff)" }, angle = 45 },
        inactive = "rgba(aaaaaa66)",
        group_active = { colors = { "rgba(ffffffaa)", "rgba(bbbbbb99)" }, angle = 45 },
        group_inactive = "rgba(aaaaaa44)",
        locked_active = "rgba(dddddd88)",
        locked_inactive = "rgba(dddddd44)",
        groupbar_active = { colors = { "rgba(ffffff33)", "rgba(bbbbbb33)" }, angle = 45 },
        groupbar_inactive = "rgba(aaaaaa1a)",
        groupbar_locked_active = "rgba(dddddd33)",
        groupbar_locked_inactive = "rgba(dddddd1a)",
    },
}
local palette = palettes[theme]
hl.config({
    general = {
        gaps_in = 4,
        gaps_out = 8,
        border_size = 2,
        col = {
            active_border = palette.active,
            inactive_border = palette.inactive,
        },
        layout = "dwindle",
    },
    decoration = {
        rounding = 8,
        shadow = { enabled = false },
        blur = { enabled = false },
    },
    animations = { enabled = true },
    misc = { disable_hyprland_logo = true, background_color = "rgba(000000ff)" },
    dwindle = { preserve_split = true },
    xwayland = { force_zero_scaling = true },
    input = { accel_profile = "flat", touchpad = { natural_scroll = true } },
})

hl.config({
    group = {
        col = {
            border_active = palette.group_active,
            border_inactive = palette.group_inactive,
            border_locked_active = palette.locked_active,
            border_locked_inactive = palette.locked_inactive,
        },
        groupbar = {
            col = {
                active = palette.groupbar_active,
                inactive = palette.groupbar_inactive,
                locked_active = palette.groupbar_locked_active,
                locked_inactive = palette.groupbar_locked_inactive,
            },
        },
    },
})

hl.curve("cyber_ware_fast", { type = "bezier", points = { { 0.16, 1 }, { 0.3, 1 } } })
for _, leaf in ipairs({ "windows", "windowsIn", "windowsOut", "workspaces", "workspacesIn", "workspacesOut" }) do
    hl.animation({ leaf = leaf, enabled = true, speed = 1.5, bezier = "cyber_ware_fast" })
end
for _, leaf in ipairs({ "specialWorkspace", "specialWorkspaceIn", "specialWorkspaceOut" }) do
    hl.animation({ leaf = leaf, enabled = true, speed = 1.5, bezier = "cyber_ware_fast", style = "fade" })
end
