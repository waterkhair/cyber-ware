-- Application window rules and workspace defaults.
hl.window_rule({
    name = "zen-picture-in-picture",
    match = { class = "^zen$", title = "^Picture-in-Picture$" },
    float = true,
})

hl.window_rule({
    name = "steam-window",
    match = { class = "^steam$" },
    workspace = "special:Games silent",
    float = true,
    animation = "none",
})
hl.window_rule({
    name = "steam-game-window",
    match = { class = "^(steam_app_.*|gamescope)$" },
    workspace = "special:Games silent",
    float = false,
    animation = "none",
})
hl.window_rule({
    name = "steam-dialog",
    match = {
        class = "^steam$",
        title = "^(Properties|Settings|Steam Settings|Friends List|Friends & Chat|.*Properties.*|.*Settings.*|.*Dialog.*|.*Confirm.*)$",
    },
    float = true,
    center = true,
    animation = "none",
})
hl.window_rule({
    name = "discord-window",
    match = { class = "^discord$" },
    workspace = "special:Comms silent",
    float = false,
    animation = "none",
})
hl.window_rule({
    name = "obs-window",
    match = { class = "^com\\.obsproject\\.Studio$" },
    workspace = "4 silent",
    animation = "none",
})
hl.window_rule({
    name = "obs-dialog",
    match = {
        class = "^com\\.obsproject\\.Studio$",
        title = "^(Properties for .+|Filters for .+|Add Source|Create/Select Source|Settings)$",
    },
    float = true,
    center = true,
    animation = "none",
})

hl.workspace_rule({ workspace = "4", default_name = "Streaming", animation = "none" })
hl.workspace_rule({ workspace = "5", default_name = "Manga", animation = "none" })
hl.workspace_rule({ workspace = "special:Games", animation = "fade" })
hl.workspace_rule({ workspace = "special:Comms", animation = "fade" })
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

-- LastPass changes its Zen title after mapping; float the extension popup.
hl.on("window.title", function(window)
    if window == nil or window.class ~= "zen" then return end
    if not window.title:match("^Extension:.*LastPass.*$") then return end
    hl.dispatch(hl.dsp.window.float({ action = "set", window = window }))
    hl.dispatch(hl.dsp.window.resize({ x = 400, y = 305, relative = false, window = window }))
    local cursor = hl.get_cursor_pos()
    if cursor ~= nil then
        hl.dispatch(hl.dsp.window.move({ x = cursor.x, y = cursor.y, relative = false, window = window }))
    end
end)
