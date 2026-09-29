-- Adapt this list to the applications and services installed on the machine.
local home = os.getenv("HOME") or ""
local user_bin = os.getenv("CYBER_WARE_BIN") or (home .. "/.local/bin")

local function command_available(command)
    local ok, _, code = os.execute("command -v " .. command .. " >/dev/null 2>&1")
    return ok == true or ok == 0 or code == 0
end

local function start_if_available(command, executable)
    if command_available(executable) then hl.exec_cmd(command) end
end

hl.on("hyprland.start", function()
    start_if_available("/usr/lib/pam_kwallet_init", "/usr/lib/pam_kwallet_init")
    start_if_available("waybar", "waybar")
    start_if_available("mako", "mako")
    start_if_available("env QT_QPA_PLATFORMTHEME=qt6ct /usr/lib/hyprpolkitagent/hyprpolkitagent", "/usr/lib/hyprpolkitagent/hyprpolkitagent")
    start_if_available(user_bin .. "/cyber-wall --set --restore", user_bin .. "/cyber-wall")
    start_if_available("hypridle", "hypridle")
    if command_available("wl-paste") and command_available("cliphist") then
        hl.exec_cmd("wl-paste --watch cliphist store")
    end
    start_if_available("opendeck --hide", "opendeck")
    start_if_available("discord", "discord")
    start_if_available("steam", "steam")
    hl.dispatch(hl.dsp.focus({ workspace = "1" }))
end)
