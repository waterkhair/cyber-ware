# Git and GitHub setup

This is the Git setup for the umbrella `cyber-ware` repository. Initialize
Git from the repository root (`~/Projects/Hyprland/cyber-ware`), not from
inside a component such as `cyber-wall`; components are directories in this
single repository, not nested Git repositories.

## Local credential storage

On the author's CachyOS system, global Git configuration selects the
`libsecret` credential helper (`credential.helper=libsecret`). The `libsecret`,
`gcr-4`, `kwallet`, and `kwallet-pam` packages are installed. The intended flow
is for Git's helper to store HTTPS credentials through the Secret Service API,
with the desktop wallet protecting the stored secret. A temporary `secret-tool`
store/lookup test was reported to work.

Check only the helper setting (this does not reveal credentials):

```sh
git config --global --show-origin --get credential.helper
```

Do not use `git credential fill` or `secret-tool lookup` as a diagnostic in a
terminal you may share or record: those commands print the stored secret.
Never put a token in a remote URL, shell command, script, or repository file.

On another Linux desktop, install Git, `libsecret`, and a Secret Service
provider integrated with its keyring. Configure Git with
`git config --global credential.helper libsecret`. Confirm the wallet is
available/unlocked in the graphical session before relying on automatic
credential retrieval. Package names and wallet integration vary by distro and
desktop.

## First push

Create an empty GitHub repository named `cyber-ware` under the `WaterKhair`
account. Then, from `~/Projects/Hyprland/cyber-ware`:

```sh
git init -b main
git add README.md LICENSE docs cyber-wall
git status --short
git diff --cached
git commit -m "Initial cyber-ware setup"
git remote add origin https://github.com/WaterKhair/cyber-ware.git
git push -u origin main
```

Review the staged file list and diff before committing. As more setup files or
components are added, stage those intentionally and inspect them too. Never
add access tokens, private keys, wallet data, or machine-specific wallpaper
state. The component `.gitignore` excludes Python bytecode and virtual
environments; it is not a substitute for reviewing staged files.

For HTTPS pushes, GitHub requires a personal access token (PAT) for
authentication. Enter it only at Git's password prompt; the configured
credential helper should offer to save it to the desktop secret store. If a
token is exposed, revoke it in GitHub and create a replacement with only the
permissions needed. Deleting a local copy alone does not invalidate it.
