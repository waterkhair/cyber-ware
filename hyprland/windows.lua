-- Application-specific window behavior belongs in hyprland.local.lua.
-- Keep shared rules focused on generic workspaces and cyber-ware tools.

hl.workspace_rule({ workspace = "4", default_name = "Streaming", animation = "none" })
hl.workspace_rule({ workspace = "5", default_name = "Manga", animation = "none" })
hl.workspace_rule({ workspace = "special:Games", animation = "fade" })
hl.workspace_rule({ workspace = "special:Comms", animation = "fade" })
hl.workspace_rule({ workspace = "special:Radio", animation = "fade" })
hl.workspace_rule({
    workspace = "1",
    default_name = "Deck",
    animation = "none",
    default = true,
    persistent = true,
})

for name, size in pairs({
    wiremix = { 1100, 720 },
    btop = { 1200, 800 },
    impala = { 1100, 720 },
    bluetui = { 1100, 720 },
    yazi = { 1400, 900 },
}) do
    hl.window_rule({
        name = "cyber-console-" .. name,
        match = { class = "^org\\.cyber-ware\\.cyber-console\\." .. name .. "$" },
        float = true,
        size = size,
        center = true,
    })
end

hl.layer_rule({
    name = "wallpaper-no-animation",
    match = { namespace = "^mpvpaper$" },
    no_anim = true,
})
hl.window_rule({
    name = "cyber-wall-floating-picker",
    match = { class = "^org\\.cyber-ware\\.cyber-wall$" },
    float = true,
    size = { 1100, 820 },
    center = true,
    border_size = 2,
    animation = "none",
})
hl.window_rule({
    name = "cyber-wave-floating-picker",
    match = { class = "^org\\.cyber-ware\\.cyber-wave$" },
    workspace = "special:Radio silent",
    float = true,
    size = { 1050, 720 },
    center = true,
    border_size = 2,
    animation = "none",
})

