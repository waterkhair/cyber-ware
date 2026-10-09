-- cyber-ware Hyprland configuration entry point.
-- Optional machine-specific overrides live in ~/.config/hypr/hyprland.local.lua.
local home = os.getenv("HOME") or ""
local config_home = os.getenv("XDG_CONFIG_HOME") or (home .. "/.config")
-- qt6ct also accepts the qt5ct plugin name, covering both Qt generations.
-- Machine-local overrides below can replace these portable defaults.
hl.env("QT_QPA_PLATFORMTHEME", "qt5ct")
hl.env("XCURSOR_THEME", "breeze_cursors")
hl.env("XCURSOR_SIZE", "24")
local local_config_path = config_home .. "/hypr/hyprland.local.lua"
local local_config_file = io.open(local_config_path, "r")
if local_config_file then
    local_config_file:close()
    local local_config, err = loadfile(local_config_path)
    if not local_config then error(err) end
    local_config()
end

require("hyprland.appearance")
require("hyprland.windows")
require("hyprland.autostart")
require("hyprland.keybindings")
