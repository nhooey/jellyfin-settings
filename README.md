# jellyfin-settings

Declare Jellyfin's settings in Nix and apply them through Jellyfin's REST API.

Jellyfin keeps its settings in XML files and a database that its dashboard rewrites, so they can't be
declared as files. This flake's Home Manager module declares them as options instead, and a background
job sends them to Jellyfin's API:

- **Encoding settings:** any key of `/System/Configuration/encoding`, such as hardware acceleration and
  CRF.
- **Per-user settings:** any key of a user's configuration, such as subtitle language and mode.
- **Libraries:** added with their folders and scanned when missing; a folder missing from one is added.

Only the keys you list are changed, so anything else set in the dashboard stays. Nothing is ever
removed.

## Use

```nix
{
  inputs.jellyfin-settings.url = "github:nhooey/jellyfin-settings";
  # In a Home Manager configuration:
  imports = [ inputs.jellyfin-settings.homeModules.default ];
  services.jellyfin-settings = {
    enable = true;
    apiKey = { item = "<1Password item ID>"; title = "<its title>"; };
    encoding = { HardwareAccelerationType = "videotoolbox"; H264Crf = 20; };
    users.alice = { SubtitleLanguagePreference = "eng"; SubtitleMode = "Always"; };
    libraries.Movies = { type = "movies"; paths = [ "~/Video/Movies" ]; };
  };
}
```

The API key is read through [SecretSpec](https://secretspec.dev) from 1Password, by item ID, through the
provider alias `apiKey.provider` names (`onepassword-uncached` by default, from the user-global
`~/.config/secretspec/config.toml`). The module writes the manifest to
`~/.config/secretspec/jellyfin.toml`. The key is never written anywhere else or printed.

## When the settings are applied

A launchd agent on macOS, or a systemd user timer on Linux, runs `jellyfin-settings apply --if-changed`:

- **When it loads:** right after a switch that changes the settings, since its arguments name the
  settings file.
- **Every 15 minutes** (`interval`): to apply settings a run couldn't, because Jellyfin wasn't running or
  the key couldn't be read.

A run returns at once when the settings' hash matches the last successful run, so it reads the key, and
1Password asks, only when there's something to apply. It runs outside the switch, so a 1Password
approval never holds a switch up. Its log is `~/Library/Logs/jellyfin-settings.log` on macOS.

## The command

| Command                                    | Does                                                                         |
| ------------------------------------------ | ---------------------------------------------------------------------------- |
| `jellyfin-settings apply SETTINGS`         | sends what differs; `--dry-run` prints the requests instead                  |
| `jellyfin-settings diff SETTINGS`          | prints what Jellyfin has that differs from SETTINGS; exits 1 when any does   |

`SETTINGS` is the JSON file the module writes, `~/.config/jellyfin-settings/settings.json`. So
`jellyfin-settings diff ~/.config/jellyfin-settings/settings.json` shows what the dashboard has changed.

## How it's built

`plan.py` is pure: it maps Jellyfin's state and the declared settings to the drift and the requests that
remove it, with no I/O. `jellyfin.py` reads the state and sends requests with httpx, and `cli.py` is
the typer command. `nix flake check` runs the unit tests (pytest, with respx mocking Jellyfin) and ruff.
