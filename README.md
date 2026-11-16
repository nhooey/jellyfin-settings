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

The module's options, under `services.jellyfin-settings`:

| Option             | Default                                                | Sets                                                           |
| ------------------ | ------------------------------------------------------ | -------------------------------------------------------------- |
| `enable`           | `false`                                                | whether the job runs                                           |
| `url`              | unset: the command's default, `http://localhost:8096`  | Jellyfin's base URL                                            |
| `encoding`         | `{ }`                                                  | keys of `/System/Configuration/encoding`                       |
| `users.<name>`     | `{ }`                                                  | keys of that user's configuration                              |
| `libraries.<name>` | `{ }`                                                  | `type` (Jellyfin's collection type) and `paths` (`~/` is home) |
| `apiKey.provider`  | `onepassword-uncached`                                 | the SecretSpec provider alias the key is read through          |
| `apiKey.item`      | none, required                                         | ID of the 1Password item holding the key                       |
| `apiKey.field`     | `credential`                                           | label of the item's field holding the key                      |
| `apiKey.title`     | `""`                                                   | the item's title, for the manifest's description               |
| `interval`         | `900`                                                  | seconds between retry runs                                     |
| `path`             | the user's profile, the system's, Homebrew's, the OS's | the job's PATH; it must find `secretspec` and `op`             |

## When the settings are applied

A launchd agent on macOS, or a systemd user timer on Linux, runs
`jellyfin-settings apply --if-changed STAMP`, where STAMP is
`$XDG_STATE_HOME/jellyfin-settings/applied.sha256`:

- **When it loads:** right after a switch that changes the settings, since its arguments name the
  settings file.
- **Every 15 minutes** (`interval`): to apply settings a run couldn't, because Jellyfin wasn't running or
  the key couldn't be read.

A run returns at once when the settings' hash matches the one the last successful run wrote to STAMP,
so it reads the key, and 1Password asks, only when there's something to apply. It runs outside the
switch, so a 1Password approval never holds a switch up. Its log is
`~/Library/Logs/jellyfin-settings.log` on macOS.

## The command

| Command                                    | Does                                                                                         |
| ------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `jellyfin-settings apply SETTINGS`         | sends what differs; exits 0 when Jellyfin or the key isn't there, to retry                   |
| `jellyfin-settings diff SETTINGS`          | prints what Jellyfin has that differs from SETTINGS; exits 1 on drift, 2 when it can't check |
| `jellyfin-settings config show SETTINGS`   | prints SETTINGS merged over the shipped defaults                                             |
| `jellyfin-settings config show --defaults` | prints the shipped defaults file                                                             |

| Option                 | Commands        | Does                                                                                       |
| ---------------------- | --------------- | ------------------------------------------------------------------------------------------ |
| `--dry-run`            | `apply`         | prints the requests instead of sending them                                                |
| `--if-changed STAMP`   | `apply`         | does nothing when STAMP holds the settings' hash; writes it on success                     |
| `--secretspec COMMAND` | `apply`, `diff` | the secretspec command to read the key with; `secretspec` by default                       |
| `--manifest PATH`      | `apply`, `diff` | the manifest declaring `JELLYFIN_API_KEY`; `~/.config/secretspec/jellyfin.toml` by default |

`SETTINGS` is the JSON file the module writes, `~/.config/jellyfin-settings/settings.json`. So
`jellyfin-settings diff ~/.config/jellyfin-settings/settings.json` shows what the dashboard has changed.

Every setting's default is in `src/jellyfin_settings/defaults.json`, which ships in the package, and
SETTINGS names only what it changes: maps merge key by key, other values replace, and a key the defaults
don't have makes `apply` and `diff` exit 2. An empty `{}` runs on the defaults.

## How it's built

`plan.py` is pure: it maps Jellyfin's state and the declared settings to the drift and the requests that
remove it, with no I/O. `jellyfin.py` reads the state and sends requests with httpx, and `cli.py` is
the typer command. `nix flake check` runs the unit tests (pytest, with respx mocking Jellyfin),
evaluates the Home Manager module on Darwin and Linux, and runs ruff.
