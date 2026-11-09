# Home Manager module: services.jellyfin-settings. Declares Jellyfin's
# encoding settings, per-user settings and libraries, and applies them
# through Jellyfin's REST API from a background job: a launchd agent on
# macOS, a systemd user timer on Linux.
#
# The job runs when it's loaded, so right after a switch that changes the
# settings (its arguments name the settings file, so it reloads), and then
# every `interval` seconds. Each run returns at once when the settings'
# hash matches the last successful run, so it reads the API key only when
# there is something to apply. When Jellyfin isn't running, or the key
# can't be read, the run changes nothing and the next one tries again. It
# runs outside the switch, so waiting for a 1Password approval never holds
# a switch up.
self:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.jellyfin-settings;
  inherit (lib) mkEnableOption mkOption types;
  package = self.packages.${pkgs.stdenv.hostPlatform.system}.default;

  settingsFile = (pkgs.formats.json { }).generate "jellyfin-settings.json" {
    inherit (cfg)
      url
      encoding
      users
      libraries
      ;
  };
  manifest = "${config.xdg.configHome}/secretspec/jellyfin.toml";
  command = [
    (lib.getExe package)
    "apply"
    "${settingsFile}"
    "--if-changed"
    "${config.xdg.stateHome}/jellyfin-settings/applied.sha256"
    "--manifest"
    manifest
  ];
  path = lib.concatStringsSep ":" cfg.path;
in
{
  options.services.jellyfin-settings = {
    enable = mkEnableOption "applying declared Jellyfin settings through its REST API";

    url = mkOption {
      type = types.str;
      default = "http://localhost:8096";
      description = "Jellyfin's base URL.";
    };

    encoding = mkOption {
      type = types.attrsOf types.anything;
      default = { };
      example = {
        HardwareAccelerationType = "videotoolbox";
        H264Crf = 20;
      };
      description = "Keys of Jellyfin's encoding configuration (`/System/Configuration/encoding`) to set.";
    };

    users = mkOption {
      type = types.attrsOf (types.attrsOf types.anything);
      default = { };
      example = {
        alice = {
          SubtitleLanguagePreference = "eng";
          SubtitleMode = "Always";
        };
      };
      description = "Per Jellyfin user name, keys of that user's configuration to set.";
    };

    libraries = mkOption {
      type = types.attrsOf (
        types.submodule {
          options = {
            type = mkOption {
              type = types.enum [
                "movies"
                "tvshows"
                "music"
                "musicvideos"
                "homevideos"
                "boxsets"
                "books"
                "mixed"
              ];
              description = "Jellyfin's collection type for the library.";
            };
            paths = mkOption {
              type = types.listOf types.str;
              description = "The library's folders; `~/` is the user's home.";
            };
          };
        }
      );
      default = { };
      description = "Libraries by name. Missing ones are added and scanned; none is removed.";
    };

    apiKey = {
      provider = mkOption {
        type = types.str;
        default = "onepassword-uncached";
        description = ''
          The SecretSpec provider alias to read the key through, such as a
          user-global alias in ~/.config/secretspec/config.toml.
        '';
      };
      item = mkOption {
        type = types.str;
        description = "ID of the 1Password item holding the Jellyfin API key.";
      };
      field = mkOption {
        type = types.str;
        default = "credential";
        description = "Label of the item's field holding the key.";
      };
      title = mkOption {
        type = types.str;
        default = "";
        description = "The item's title, for the SecretSpec manifest's description.";
      };
    };

    interval = mkOption {
      type = types.ints.positive;
      default = 900;
      description = "Seconds between runs that retry settings not yet applied.";
    };

    path = mkOption {
      type = types.listOf types.str;
      default = [
        "${config.home.profileDirectory}/bin"
        "/run/current-system/sw/bin"
        "/opt/homebrew/bin"
        "/usr/local/bin"
        "/usr/bin"
        "/bin"
      ];
      defaultText = lib.literalMD "the user's profile, the system's, Homebrew's, then the OS's";
      description = "The job's PATH, which must find `secretspec` and what its provider runs, such as `op`.";
    };
  };

  config = lib.mkIf cfg.enable (
    lib.mkMerge [
      {
        home.packages = [ package ];

        xdg.configFile."jellyfin-settings/settings.json".source = settingsFile;

        xdg.configFile."secretspec/jellyfin.toml".text = ''
          [project]
          name = "jellyfin"
          revision = "1.0"

          [profiles.default]
          JELLYFIN_API_KEY = { description = "Jellyfin API key${
            lib.optionalString (cfg.apiKey.title != "") " (1Password: ${cfg.apiKey.title})"
          }", required = true, providers = ["${cfg.apiKey.provider}"], ref = { item = "${cfg.apiKey.item}", field = "${cfg.apiKey.field}" } }
        '';
      }

      (lib.mkIf pkgs.stdenv.hostPlatform.isDarwin {
        launchd.agents.jellyfin-settings = {
          enable = true;
          # Runs jellyfin-settings directly, not through `/bin/sh -c
          # "wait4path …"`, so Login Items & Extensions lists it as
          # "jellyfin-settings" rather than "sh". A run that starts before
          # the store is mounted fails, and StartInterval tries again.
          waitForNixStore = false;
          config = {
            ProgramArguments = command;
            RunAtLoad = true;
            StartInterval = cfg.interval;
            ProcessType = "Background";
            EnvironmentVariables.PATH = path;
            StandardOutPath = "${config.home.homeDirectory}/Library/Logs/jellyfin-settings.log";
            StandardErrorPath = "${config.home.homeDirectory}/Library/Logs/jellyfin-settings.log";
          };
        };
      })

      (lib.mkIf pkgs.stdenv.hostPlatform.isLinux {
        systemd.user.services.jellyfin-settings = {
          Unit.Description = "Apply declared Jellyfin settings";
          Service = {
            Type = "oneshot";
            Environment = [ "PATH=${path}" ];
            ExecStart = lib.escapeShellArgs command;
          };
          Install.WantedBy = [ "default.target" ];
        };
        systemd.user.timers.jellyfin-settings = {
          Unit.Description = "Retry declared Jellyfin settings not yet applied";
          Timer.OnUnitActiveSec = "${toString cfg.interval}s";
          Install.WantedBy = [ "timers.target" ];
        };
      })
    ]
  );
}
