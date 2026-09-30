-- Adapt this list to the applications and services installed on the machine.
local home = os.getenv("HOME") or ""
local user_bin = os.getenv("CYBER_WARE_BIN") or (home .. "/.local/bin")

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

local function start_if_available(command, executable)
    local path = command_path(executable)
    if not path then return end

    if command:sub(1, #executable) == executable then
        command = path .. command:sub(#executable + 1)
    end
    hl.exec_cmd(command)
end

hl.on("hyprland.start", function()
    start_if_available("/usr/lib/pam_kwallet_init", "/usr/lib/pam_kwallet_init")
    start_if_available("waybar", "waybar")
    start_if_available("mako", "mako")
    start_if_available("env QT_QPA_PLATFORMTHEME=qt6ct /usr/lib/hyprpolkitagent/hyprpolkitagent", "/usr/lib/hyprpolkitagent/hyprpolkitagent")
    start_if_available(user_bin .. "/cyber-wall --set --restore", user_bin .. "/cyber-wall")
    start_if_available("hypridle", "hypridle")
    local wl_paste = command_path("wl-paste")
    local cliphist = command_path("cliphist")
    if wl_paste and cliphist then
        hl.exec_cmd(wl_paste .. " --watch " .. cliphist .. " store")
    end
    start_if_available("opendeck --hide", "opendeck")
    start_if_available("discord", "discord")
    start_if_available("steam", "steam")
    hl.dispatch(hl.dsp.focus({ workspace = "1" }))
end)
