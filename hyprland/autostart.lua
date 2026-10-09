-- Adapt this list to the applications and services installed on the machine.
local home = os.getenv("HOME") or ""
local config_home = os.getenv("XDG_CONFIG_HOME") or (home .. "/.config")
local bin_file = io.open(config_home .. "/cyber-ware/bin-path", "r")
local configured_bin = bin_file and bin_file:read("*l") or nil
if bin_file then bin_file:close() end
local user_bin = os.getenv("CYBER_WARE_BIN") or configured_bin or (home .. "/.local/bin")

local function command_path(command)
    if command:sub(1, 1) == "/" then
        local file = io.open(command, "rb")
        if file then
            file:close()
            return command
        end
        return nil
    end

    -- Resolve without a shell so startup checks work the same from Hyprland
    -- as they do in an interactive terminal.
    local search_path = (os.getenv("PATH") or "") .. ":/usr/local/bin:/usr/bin:/bin"
    for directory in search_path:gmatch("[^:]+") do
        local candidate = directory .. "/" .. command
        local file = io.open(candidate, "rb")
        if file then
            file:close()
            return candidate
        end
    end
    return nil
end

local function shell_quote(value)
    return "'" .. value:gsub("'", "'\\''") .. "'"
end

local function process_running(name)
    local probe = io.popen("pgrep -x -- " .. shell_quote(name) .. " >/dev/null 2>&1; printf '%s' \"$?\"")
    if not probe then return false end
    local result = probe:read("*a")
    probe:close()
    return result == "0"
end

local function command_running(pattern)
    local probe = io.popen("pgrep -f -- " .. shell_quote(pattern) .. " >/dev/null 2>&1; printf '%s' \"$?\"")
    if not probe then return false end
    local result = probe:read("*a")
    probe:close()
    return result == "0"
end

local function start_if_available(command, executable, process_name, refresh_waybar)
    local path = command_path(executable)
    if not path then return end

    if command:sub(1, #executable) == executable then
        command = shell_quote(path) .. command:sub(#executable + 1)
    end
    if process_running(process_name or executable:match("([^/]+)$")) then
        if refresh_waybar then
            hl.exec_cmd("pkill -USR2 -x -- " .. shell_quote(process_name) .. " >/dev/null 2>&1 || true")
        elseif process_name == "mako" and command_path("makoctl") then
            hl.exec_cmd("makoctl reload >/dev/null 2>&1 || true")
        end
        return
    end
    hl.exec_cmd(command)
end

local function refresh_session_services(refresh_waybar)
    -- Waybar already handles workspace events. Only explicitly refresh it at
    -- login; theme/config installers perform their own reload when needed.
    start_if_available("waybar", "waybar", "waybar", refresh_waybar)
    start_if_available("mako", "mako", "mako")
    start_if_available("xsettingsd", "xsettingsd", "xsettingsd")
    start_if_available("env QT_QPA_PLATFORMTHEME=qt6ct /usr/lib/hyprpolkitagent/hyprpolkitagent", "/usr/lib/hyprpolkitagent/hyprpolkitagent", "hyprpolkitagent")
    start_if_available(user_bin .. "/cyber-wall --set --restore", user_bin .. "/cyber-wall", "mpvpaper")
    local idle_config = io.open(config_home .. "/hypr/hypridle.conf", "r")
    if idle_config then
        idle_config:close()
        start_if_available("hypridle", "hypridle", "hypridle")
    end
    local deck_config = io.open(config_home .. "/cyber-deck/config.json", "r")
    local clipboard_enabled = false
    local deck_command = io.open(user_bin .. "/cyber-deck", "rb")
    local deck_installed = deck_command ~= nil
    if deck_command then deck_command:close() end
    if deck_config then
        local contents = deck_config:read("*a")
        deck_config:close()
        clipboard_enabled = contents:match('"clipboard_enabled"%s*:%s*true') ~= nil
    end
    local wl_paste = command_path("wl-paste")
    local cliphist = command_path("cliphist")
    if deck_installed and clipboard_enabled and wl_paste and cliphist and not command_running("[w]l-paste --watch.*cliphist.*store") then
        hl.exec_cmd(shell_quote(wl_paste) .. " --watch " .. shell_quote(cliphist) .. " store")
    end
end

hl.on("hyprland.start", function()
    refresh_session_services(true)
    hl.dispatch(hl.dsp.focus({ workspace = "1" }))
    -- The helper waits for compositor readiness and repairs portals outside
    -- the event loop, then launches login apps. Reload only refreshes services.
    hl.exec_cmd("sh " .. shell_quote(config_home .. "/hypr/hyprland/session-start.sh"))
end)
hl.on("config.reloaded", function() refresh_session_services(false) end)
