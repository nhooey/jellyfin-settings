{
  description = "jellyfin-settings dev-shell skill set — an isolated sub-flake invoked at RUNTIME by the root devShell, never a root input. It takes skillspkgs' `applications` combination plus the Python skill, and those sources live only in THIS flake's lock, so the root flake stays a leaf with zero skill inputs and transitive consumers never drag the skill mesh in.";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    systems.url = "github:nix-systems/default";

    # `agent-skill-flake` is the builder library, not a skill — it provides
    # `mkDevshellSkillsFlake`.
    agent-skill-flake = {
      url = "github:nhooey/agent-skill-flake";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Every input below this divider is a skill source.

    # skillspkgs' `applications` combination, the skill set this repository
    # shares with the rest of its family.
    skillspkgs-combinations = {
      url = "github:nhooey/skillspkgs?dir=sources/combinations";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Python style. This repository is Python-first, and the rest of the
    # applications family doesn't use Python.
    python-skills = {
      url = "github:nhooey/python-skills";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        agent-skill-flake.follows = "agent-skill-flake";
      };
    };
  };

  outputs =
    {
      nixpkgs,
      agent-skill-flake,
      ...
    }@inputs:
    agent-skill-flake.lib.mkDevshellSkillsFlake {
      inherit nixpkgs;
      systems = import inputs.systems;
      name = "jellyfin-settings-skills";
      sources = [
        { source = inputs.skillspkgs-combinations.combinations.applications; }
        {
          # The package in src/ and its tests are Python.
          source = inputs.python-skills;
          skills = [ "python-hygiene-functional-style" ];
        }
      ];
    };
}
