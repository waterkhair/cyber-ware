local home = os.getenv("TEST_HOME")
local repo = os.getenv("TEST_REPO")
local config = home .. "/.config"
local bin = home .. "/.local/bin"
local names = { "waybar", "mako", "makoctl", "xsettingsd", "cyber-wall", "cyber-deck", "wl-paste", "cliphist" }
local available = {}
for _, name in ipairs(names) do available[bin .. "/" .. name] = true end
local running = { waybar = true, mako = true }
local watcher = false
local commands = {}
local handlers = {}
local dispatches = 0
local time = 100

os.getenv = function(name)
    if name == "HOME" then return home end
    if name == "XDG_CONFIG_HOME" then return config end
    if name == "PATH" then return bin end
    if name == "TEST_HOME" then return home end
    if name == "TEST_REPO" then return repo end
    return nil
end
os.time = function() return time end
os.execute = function() error("autostart must not synchronously wait for portal services") end
io.open = function(path)
    if path == config .. "/cyber-ware/bin-path" then
        return { read = function() return bin end, close = function() end }
    end
    if path == config .. "/cyber-deck/config.json" then
        return { read = function() return '{"clipboard_enabled": true}' end, close = function() end }
    end
    if path == config .. "/hypr/hypridle.conf" then return nil end
    if available[path] then return { close = function() end } end
    return nil
end
io.popen = function(command)
    local result
    local quoted = command:match("pgrep %-x %-%- '([^']+)'")
    if quoted then result = running[quoted] and "0" or "1"
    elseif command:match("pgrep %-f") then result = watcher and "0" or "1"
    else result = "1" end
    return { read = function() return result end, close = function() end }
end

hl = {
    on = function(event, callback) handlers[event] = callback end,
    exec_cmd = function(command)
        commands[#commands + 1] = command
        for _, name in ipairs({ "mpvpaper" }) do
            if command:find(name, 1, true) then running[name] = true end
        end
        if command:find("/cyber-wall", 1, true) then running.mpvpaper = true end
        if command:find("wl-paste", 1, true) then watcher = true end
    end,
    dispatch = function() dispatches = dispatches + 1 end,
    dsp = { focus = function() return {} end },
}

dofile(os.getenv("TEST_REPO") .. "/hyprland/autostart.lua")
assert(handlers["hyprland.start"], "startup handler registered")
assert(handlers["config.reloaded"], "reload handler registered")
handlers["hyprland.start"]()
handlers["config.reloaded"]()
time = time + 3
handlers["config.reloaded"]()

local function count(pattern)
    local total = 0
    for _, command in ipairs(commands) do if command:find(pattern, 1, true) then total = total + 1 end end
    return total
end
if count("/cyber-wall' --set --restore") ~= 1 then
    for _, command in ipairs(commands) do io.stderr:write(command, "\n") end
end
assert(count("/cyber-wall' --set --restore") == 1, "saved wallpaper is restored once")
assert(count("session-start.sh") == 1, "login helper is queued once, never on reload")
assert(count("wl-paste' --watch") == 1, "clipboard watcher is not duplicated")
assert(count("pkill -USR2") == 1, "running Waybar refreshes at login, not on unrelated config reloads")
assert(count("makoctl reload") == 3, "running Mako refreshes on startup and each config reload")
assert(dispatches == 1, "workspace focus only happens at session startup")
running.waybar = false
handlers["config.reloaded"]()
assert(count("/waybar'") == 1, "reload still recovers a missing Waybar")
print("PASS: reload activation restores wallpaper, refreshes managed services, and avoids duplicate processes.")
