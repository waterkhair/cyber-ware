# installer regression checks

Run from the repository root:

```sh
sh tests/test_autostart.sh
python3 tests/test_session_start.py
python3 tests/test_lock_include.py
sh tests/test_install_transaction.sh
sh tests/test_stream_bootstrap.sh
sh tests/test_jackout_layout.sh
for component in cyber-wall cyber-signal cyber-console cyber-panel cyber-deck; do
    PYTHONPATH="$component/src" python3 -m unittest discover -s "$component/tests"
done
```

These checks use temporary configuration directories and mocked compositor
calls. They do not install into your desktop or invoke logout, reboot,
suspend, or poweroff. The transaction test uses `script` (util-linux) for the
interactive uninstall confirmation; that assertion is skipped when it is absent.
Shell tests require the installer dependencies, including Lua. Python tests
use the standard library's unittest runner.
The session startup tests need permission to create a temporary Unix socket;
all service, compositor, and application commands are mocked. They cover delayed
readiness, backend and frontend recovery, failure gating, and apps opened during
startup. Wallet initialization is disabled and logs stay in temporary state.
Lock tests cover custom configuration directories, missing includes on upgrade,
symlink refusal, failed image rendering, and rollback after publication errors.

Coverage includes reload activation, duplicate-process checks, managed power
actions, copy/validation failure rollback, reinstall/uninstall baselines,
edited machine overrides, symlink collisions, custom command prefixes, and
streamed installs from a stale checkout. Active-format checks cover a legacy
session despite a `.lua` file on disk, a Lua session alongside a dormant
`.conf`, unavailable IPC, errors returned with status zero, a failed pause
of automatic reload, and reload of the wrong entry point. The TTY bootstrap
test has no reachable compositor.

These are automated regression checks, not an end-to-end compositor test.
Before release, install in a minimal running **Lua-configured** Hyprland
session and confirm monitor settings, terminal access, selected services,
wallpaper restoration, and repeated activation without duplicate processes.
Legacy running sessions are rejected with migration instructions; an offline
installation becomes active at the next login.
