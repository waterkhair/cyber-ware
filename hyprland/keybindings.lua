local navMod = "CTRL + SUPER"
local moveMod = "CTRL + SUPER + ALT"
local home = os.getenv("HOME") or ""
local config_home = os.getenv("XDG_CONFIG_HOME") or (home .. "/.config")
local bin_file = io.open(config_home .. "/cyber-ware/bin-path", "r")
local configured_bin = bin_file and bin_file:read("*l") or nil
if bin_file then bin_file:close() end
local user_bin = os.getenv("CYBER_WARE_BIN") or configured_bin or (home .. "/.local/bin")

local function shell_quote(value)
    return "'" .. value:gsub("'", "'\\''") .. "'"
end

local function executable_file(path)
    local probe = io.popen("test -x " .. shell_quote(path) .. " && printf yes")
    if not probe then return false end
    local result = probe:read("*a")
    probe:close()
    return result == "yes"
end
local function local_command(name, args)
    return user_bin .. "/" .. name .. (args and (" " .. args) or "")
end
local function local_command_available(name)
    return executable_file(local_command(name))
end
local function system_command_path(name)
    -- Avoid shelling out during config parsing: Hyprland's embedded Lua may
    -- not inherit the same shell environment as a terminal. Resolve against
    -- PATH directly and return an absolute path for exec_cmd as well.
    local search_path = (os.getenv("PATH") or "") .. ":/usr/local/bin:/usr/bin:/bin"
    for directory in search_path:gmatch("[^:]+") do
        local candidate = directory .. "/" .. name
        if executable_file(candidate) then return candidate end
    end
    return nil
end
local function bind_local_command(modifiers, key, name, args, description)
    if local_command_available(name) then
        hl.bind(modifiers .. " + " .. key, hl.dsp.exec_cmd(local_command(name, args)), { description = description })
    end
end

-- Requires the matching cyber-ware components and local helper commands.
local terminal
for _, candidate in ipairs({ "ghostty", "kitty", "foot", "alacritty", "wezterm" }) do
    terminal = system_command_path(candidate)
    if terminal then break end
end
if terminal then
    hl.bind(navMod .. " + T", hl.dsp.exec_cmd(terminal), { description = "Open terminal" })
end
bind_local_command(navMod, "B", "cyber-console", "bluetui", "Toggle floating Bluetui")
bind_local_command(navMod, "V", "cyber-console", "wiremix", "Toggle floating Wiremix")
bind_local_command(navMod, "O", "cyber-console", "btop", "Toggle floating btop")
bind_local_command(moveMod, "W", "cyber-wall", nil, "Toggle wallpaper picker")
local zen_browser = system_command_path("zen-browser")
if zen_browser then
    hl.bind(navMod .. " + Z", hl.dsp.exec_cmd(zen_browser), { description = "Open Zen Browser" })
end
bind_local_command(navMod, "I", "cyber-console", "impala", "Toggle floating Impala")
bind_local_command(navMod, "Y", "cyber-console", "yazi", "Toggle floating Yazi")

hl.bind(navMod .. " + D", function() hl.dispatch(hl.dsp.focus({ workspace = "1" })) end, { description = "Focus Deck" })
hl.bind(navMod .. " + C", function() hl.dispatch(hl.dsp.workspace.toggle_special("Comms")) end, { description = "Toggle Comms" })
hl.bind(navMod .. " + G", function() hl.dispatch(hl.dsp.workspace.toggle_special("Games")) end, { description = "Toggle Games" })
hl.bind(navMod .. " + S", function() hl.dispatch(hl.dsp.focus({ workspace = "4" })) end, { description = "Focus Streaming" })
hl.bind(navMod .. " + M", function() hl.dispatch(hl.dsp.focus({ workspace = "5" })) end, { description = "Focus Manga" })
hl.bind(navMod .. " + 1", hl.dsp.focus({ workspace = "1" }), { description = "Focus Deck (workspace 1)" })
hl.bind(moveMod .. " + 1", hl.dsp.window.move({ workspace = "1" }), { description = "Move window to Deck" })
hl.bind(moveMod .. " + D", hl.dsp.window.move({ workspace = "1" }), { description = "Move window to Deck" })
hl.bind(moveMod .. " + M", hl.dsp.window.move({ workspace = "5" }), { description = "Move window to Manga" })
hl.bind(moveMod .. " + C", hl.dsp.window.move({ workspace = "special:Comms" }), { description = "Move window to Comms" })
hl.bind(moveMod .. " + G", hl.dsp.window.move({ workspace = "special:Games" }), { description = "Move window to Games" })
hl.bind(moveMod .. " + S", hl.dsp.window.move({ workspace = "4" }), { description = "Move window to Streaming" })
bind_local_command("SUPER", "Space", "cyber-deck", nil, "Toggle application launcher")
bind_local_command(moveMod, "T", "cyber-ware", "--theme-picker", "Choose cyber-ware theme")
local deck_config_file = io.open(config_home .. "/cyber-deck/config.json", "r")
if deck_config_file then
    local deck_config = deck_config_file:read("*a")
    deck_config_file:close()
    if deck_config:match('"clipboard_enabled"%s*:%s*true') then
        bind_local_command("SUPER", "V", "cyber-deck", "--clipboard", "Open clipboard history")
    end
end
bind_local_command(moveMod, "P", "cyber-scan", nil, "Capture and annotate a region")
if system_command_path("wlogout") then
    hl.bind(moveMod .. " + BackSpace", hl.dsp.exec_cmd("sh -c 'pgrep -x wlogout >/dev/null || exec wlogout --protocol layer-shell --buttons-per-row 5 --margin-left 220 --margin-right 220 --margin-top 600 --margin-bottom 600 --column-spacing 16 --row-spacing 0 --show-binds'"), { description = "Open power menu" })
end
hl.bind(navMod .. " + X", hl.dsp.window.close(), { description = "Close active window" })
bind_local_command(moveMod, "Escape", "cyber-jackout", nil, "Cleanly exit Hyprland")

for key, direction in pairs({ H = "left", L = "right", K = "up", J = "down" }) do
    hl.bind(navMod .. " + " .. key, hl.dsp.focus({ direction = direction }))
    hl.bind(moveMod .. " + " .. key, hl.dsp.window.move({ direction = direction }))
end
for _, direction in ipairs({ "left", "right", "up", "down" }) do
    hl.bind(navMod .. " + " .. direction, hl.dsp.focus({ monitor = direction }))
    hl.bind(moveMod .. " + " .. direction, hl.dsp.window.move({ monitor = direction }))
end
for workspace = 2, 9 do
    hl.bind(navMod .. " + " .. workspace, hl.dsp.focus({ workspace = workspace }))
    hl.bind(moveMod .. " + " .. workspace, hl.dsp.window.move({ workspace = workspace }))
end

local workspaceCycle = { "1", "4", "5" }
local function cycleWorkspace(delta, move_window)
    local active = hl.get_active_workspace()
    local current = active and tostring(active.id) or "1"
    local index = 1
    for i, name in ipairs(workspaceCycle) do
        if name == current then index = i; break end
    end
    local next_index = ((index - 1 + delta) % #workspaceCycle) + 1
    local target = workspaceCycle[next_index]
    if move_window then
        hl.dispatch(hl.dsp.window.move({ workspace = target }))
    else
        hl.dispatch(hl.dsp.focus({ workspace = target }))
    end
end
hl.bind(navMod .. " + Comma", function() cycleWorkspace(-1, false) end)
hl.bind(navMod .. " + Period", function() cycleWorkspace(1, false) end)
hl.bind(moveMod .. " + Comma", function() cycleWorkspace(-1, true) end)
hl.bind(moveMod .. " + Period", function() cycleWorkspace(1, true) end)
hl.bind(navMod .. " + Space", hl.dsp.focus({ workspace = "previous" }))

hl.bind(navMod .. " + Return", hl.dsp.window.fullscreen({ mode = "maximized", action = "toggle" }))
hl.bind(moveMod .. " + Return", hl.dsp.window.fullscreen({ mode = "fullscreen", action = "toggle" }))
hl.bind(moveMod .. " + F", hl.dsp.window.float({ action = "toggle" }))
hl.bind(navMod .. " + Minus", hl.dsp.layout("splitratio -0.1"))
hl.bind(navMod .. " + Equal", hl.dsp.layout("splitratio +0.1"))
hl.bind(moveMod .. " + Minus", hl.dsp.window.resize({ x = 0, y = -50, relative = true }))
hl.bind(moveMod .. " + Equal", hl.dsp.window.resize({ x = 0, y = 50, relative = true }))
hl.bind("CTRL + SUPER + mouse:273", hl.dsp.window.resize(), { mouse = true })
hl.bind(moveMod .. " + E", hl.dsp.window.center())
hl.bind(moveMod .. " + Space", hl.dsp.group.toggle(), { description = "Toggle window group" })
hl.bind("SUPER + H", hl.dsp.group.prev(), { description = "Previous window in group" })
hl.bind("SUPER + L", hl.dsp.group.next(), { description = "Next window in group" })
hl.bind(navMod .. " + BracketLeft", hl.dsp.window.move({ direction = "left", group_aware = true }))
hl.bind(navMod .. " + BracketRight", hl.dsp.window.move({ direction = "right", group_aware = true }))
