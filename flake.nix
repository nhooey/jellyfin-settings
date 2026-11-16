{
  description = "jellyfin-settings: declare Jellyfin's settings and apply them through its REST API";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };
    systems.url = "github:nix-systems/default";
    agent-skill-flake = {
      url = "github:nhooey/agent-skill-flake";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      flake-parts,
      systems,
      ...
    }@inputs:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = import systems;
      imports = [
        inputs.agent-skill-flake.flakeModules.devshellSkills
        inputs.treefmt-nix.flakeModule
      ];

      agent-skill-flake.devshellSkills = {
        # Not `jellyfin-settings`: the dev shell puts a launcher by its name
        # on PATH, which would shadow the command of that name.
        name = "jellyfin-settings-dev";
        motd = ''
          {bold}{14}🎬 Entering the jellyfin-settings dev shell{reset}
          Run {bold}menu{reset} to list available commands.
        '';
      };

      # services.jellyfin-settings, for Home Manager:
      #     imports = [ inputs.jellyfin-settings.homeModules.default ];
      #     services.jellyfin-settings = { enable = true; apiKey.item = "<id>"; ... };
      flake.homeModules.default = import ./nix/home-module.nix self;

      perSystem =
        { pkgs, self', ... }:
        let
          python = pkgs.python3.withPackages (
            ps:
            self'.packages.default.dependencies
            ++ [
              ps.pytest
              ps.respx
            ]
          );
        in
        {
          # The unit tests run in the package's build.
          packages.default = pkgs.callPackage ./nix/package.nix { };

          checks.package = self'.packages.default;

          checks.home-module = pkgs.callPackage ./nix/tests/home-module.nix { inherit self; };

          checks.ruff = pkgs.runCommand "jellyfin-settings-ruff" { nativeBuildInputs = [ pkgs.ruff ]; } ''
            cd ${./.}
            bash ${./scripts/lint.sh}
            touch $out
          '';

          treefmt = {
            projectRootFile = "flake.nix";
            programs.nixfmt.enable = true;
            programs.ruff-format.enable = true;
          };

          devshells.default = {
            packages = [
              python
              pkgs.ruff
            ];
            env = [
              {
                name = "PYTHONPATH";
                eval = "$PRJ_ROOT/src";
              }
            ];
            commands = [
              {
                category = "run";
                name = "jellyfin-settings";
                help = "the command, run from the source tree (apply, diff, config show)";
                command = ''python -m jellyfin_settings "$@"'';
              }
              {
                category = "test";
                name = "lint";
                help = "ruff's lint and format checks";
                command = ''cd "$PRJ_ROOT" && ${pkgs.bash}/bin/bash scripts/lint.sh'';
              }
              {
                category = "test";
                name = "tests";
                help = "run the unit tests against the source tree";
                command = ''cd "$PRJ_ROOT" && python -m pytest "$@"'';
              }
            ];
          };
        };
    };
}
