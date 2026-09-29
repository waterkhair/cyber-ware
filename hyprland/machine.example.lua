-- Copy to ~/.config/hypr/hyprland.local.lua and edit for this machine.
-- The main config loads that file before the shared modules.

-- Optional NVIDIA device selection. Point this symlink at the intended DRM card:
--   ~/.config/hypr/nvidia-gpu -> /dev/dri/by-path/pci-....-card
local home = os.getenv("HOME") or ""
local drm_device = home .. "/.config/hypr/nvidia-gpu"
if os.getenv("CYBER_WARE_USE_NVIDIA_DRM") == "1" then
    hl.env("AQ_DRM_DEVICES", drm_device)
end

-- Optional monitor override. Replace the output/mode/scale with values for
-- this display; leave commented to let Hyprland choose its preferred mode.
-- hl.monitor({
--     output = "DP-1",
--     mode = "preferred",
--     position = "auto",
--     scale = 1,
-- })
