# Evaluates the Home Manager module against stubs of the Home Manager
# options it sets, on a Darwin and a Linux host platform, and checks the
# files and job it declares. Fails listing each test whose result differs.
{
  self,
  lib,
  pkgs,
  jq,
  runCommand,
}:
let
  inherit (lib) mkOption types;

  stubs = {
    options = {
      home.homeDirectory = mkOption { type = types.str; };
      home.profileDirectory = mkOption { type = types.str; };
      home.packages = mkOption {
        type = types.listOf types.package;
        default = [ ];
      };
      xdg.configHome = mkOption { type = types.str; };
      xdg.stateHome = mkOption { type = types.str; };
      xdg.configFile = mkOption {
        type = types.attrsOf types.anything;
        default = { };
      };
      launchd.agents = mkOption {
        type = types.attrsOf types.anything;
        default = { };
      };
      systemd.user = mkOption {
        type = types.attrsOf (types.attrsOf types.anything);
        default = { };
      };
    };
    config = {
      home.homeDirectory = "/home/u";
      home.profileDirectory = "/home/u/.nix-profile";
      xdg.configHome = "/home/u/.config";
      xdg.stateHome = "/home/u/.local/state";
    };
  };

  # pkgs, with the host platform claiming to be Darwin or Linux.
  onHost =
    isDarwin:
    pkgs
    // {
      stdenv = pkgs.stdenv // {
        hostPlatform = pkgs.stdenv.hostPlatform // {
          inherit isDarwin;
          isLinux = !isDarwin;
        };
      };
    };

  evaluate =
    isDarwin: settings:
    (lib.evalModules {
      modules = [
        stubs
        (import ../home-module.nix self)
        { services.jellyfin-settings = settings; }
      ];
      specialArgs.pkgs = onHost isDarwin;
    }).config;

  declared = {
    enable = true;
    url = "http://media.test:8096";
    encoding.H264Crf = 20;
    users.alice.SubtitleMode = "Always";
    libraries.Movies = {
      type = "movies";
      paths = [ "~/Video/Movies" ];
    };
    apiKey = {
      item = "item-id";
      title = "Jellyfin";
    };
    interval = 600;
    path = [
      "/a/bin"
      "/b/bin"
    ];
  };

  darwin = evaluate true declared;
  linux = evaluate false declared;
  settingsFile = darwin.xdg.configFile."jellyfin-settings/settings.json".source;
  exe = lib.getExe self.packages.${pkgs.stdenv.hostPlatform.system}.default;
  command = [
    exe
    "apply"
    "${settingsFile}"
    "--if-changed"
    "/home/u/.local/state/jellyfin-settings/applied.sha256"
    "--manifest"
    "/home/u/.config/secretspec/jellyfin.toml"
  ];

  failures = lib.runTests {
    testDisabledDeclaresNothing = {
      expr =
        let
          off = evaluate true { apiKey.item = "item-id"; };
        in
        {
          inherit (off.home) packages;
          inherit (off.xdg) configFile;
          inherit (off.launchd) agents;
        };
      expected = {
        packages = [ ];
        configFile = { };
        agents = { };
      };
    };

    testManifestReadsTheItemsFieldThroughTheProvider = {
      expr = darwin.xdg.configFile."secretspec/jellyfin.toml".text;
      expected = ''
        [project]
        name = "jellyfin"
        revision = "1.0"

        [profiles.default]
        JELLYFIN_API_KEY = { description = "Jellyfin API key (1Password: Jellyfin)", required = true, providers = ["onepassword-uncached"], ref = { item = "item-id", field = "credential" } }
      '';
    };

    testDarwinRunsALaunchdAgentOnly = {
      expr = {
        agent = darwin.launchd.agents.jellyfin-settings.config;
        systemd = darwin.systemd.user;
      };
      expected = {
        agent = {
          ProgramArguments = command;
          RunAtLoad = true;
          StartInterval = 600;
          ProcessType = "Background";
          EnvironmentVariables.PATH = "/a/bin:/b/bin";
          StandardOutPath = "/home/u/Library/Logs/jellyfin-settings.log";
          StandardErrorPath = "/home/u/Library/Logs/jellyfin-settings.log";
        };
        systemd = { };
      };
    };

    testLinuxRunsASystemdServiceAndTimerOnly = {
      expr = {
        inherit (linux.systemd.user) services timers;
        inherit (linux.launchd) agents;
      };
      expected = {
        services.jellyfin-settings = {
          Unit.Description = "Apply declared Jellyfin settings";
          Service = {
            Type = "oneshot";
            Environment = [ "PATH=/a/bin:/b/bin" ];
            ExecStart = lib.escapeShellArgs command;
          };
          Install.WantedBy = [ "default.target" ];
        };
        timers.jellyfin-settings = {
          Unit.Description = "Retry declared Jellyfin settings not yet applied";
          Timer.OnUnitActiveSec = "600s";
          Install.WantedBy = [ "timers.target" ];
        };
        agents = { };
      };
    };
  };

  expectedSettings = builtins.toFile "expected-settings.json" (
    builtins.toJSON {
      url = "http://media.test:8096";
      encoding.H264Crf = 20;
      users.alice.SubtitleMode = "Always";
      libraries.Movies = {
        type = "movies";
        paths = [ "~/Video/Movies" ];
      };
    }
  );
in
runCommand "jellyfin-settings-home-module" { nativeBuildInputs = [ jq ]; } ''
  ${lib.optionalString (failures != [ ]) ''
    cat <<'EOF'
    ${builtins.unsafeDiscardStringContext (builtins.toJSON failures)}
    EOF
    exit 1
  ''}
  # settings.json holds the declared settings and nothing else.
  diff <(jq -S . ${expectedSettings}) <(jq -S . ${settingsFile})
  touch $out
''
