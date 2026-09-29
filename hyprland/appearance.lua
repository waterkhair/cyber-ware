-- Compact dark desktop defaults with a restrained cyan/violet accent.
hl.config({
    general = {
        gaps_in = 4,
        gaps_out = 8,
        border_size = 2,
        col = {
            active_border = { colors = { "rgba(00e5ffff)", "rgba(8b5cf6ff)" }, angle = 45 },
            inactive_border = "rgba(7f8ca366)",
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
            border_active = { colors = { "rgba(00b8ff99)", "rgba(8b5cf699)" }, angle = 45 },
            border_inactive = "rgba(8b5cf644)",
            border_locked_active = "rgba(ff2e9388)",
            border_locked_inactive = "rgba(ff2e9344)",
        },
        groupbar = {
            col = {
                active = { colors = { "rgba(00b8ff33)", "rgba(8b5cf633)" }, angle = 45 },
                inactive = "rgba(8b5cf61a)",
                locked_active = "rgba(ff2e9333)",
                locked_inactive = "rgba(ff2e931a)",
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
