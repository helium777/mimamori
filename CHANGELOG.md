## v0.2.3 (2025-04-13)

### 🐛🚑️ Fixes

- improve the download process when the temporary folder and the binary folder are on different filesystems

### 📝💡 Documentation

- update README

## v0.2.2 (2025-04-12)

### 🐛🚑️ Fixes

- remove aliases when cleanup

### ♻️ Refactorings

- remove ServiceSettings from main settings

### 💚👷 CI & Build

- update checkout step to use personal access token

### 📝💡 Documentation

- recommend to use `--yes` in readme

## v0.2.1 (2025-04-12)

### 🐛🚑️ Fixes

- add no_proxy environment variable to proxy settings

### 💚👷 CI & Build

- using PAT instead of `github.token`

## v0.2.0 (2025-04-12)

### ✨ Features

- add proxy selection feature

### 🐛🚑️ Fixes

- backup old configuration file on invalid settings
- make cleanup command to delete service file

### ♻️ Refactorings

- simplify proxy grid column addition
- enhance settings initialization
- improve proxy status display and connectivity checks
- improve setup logic

### docs

- add caution note about `pp` command

### fix

- update proxy command instructions in setup function
- add user-agent header (Clash)
- support base64 encoded subscription content

### 🎨🏗️ Style & Architecture

- minor

### 💚👷 CI & Build

- fix requirement error for cz-gitmoji
- setup github actions

### 🚨 Linting

- lint

### 🧑‍💻 Developer Experience

- setup commitizen
