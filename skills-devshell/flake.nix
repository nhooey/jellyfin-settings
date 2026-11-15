{
  description = "jellyfin-settings dev-shell skill set — an isolated sub-flake invoked at RUNTIME by the root devShell, never a root input. The skill sources (coding-agent, git, Nix flake, Python, shell, writing and Markdown hygiene) live only in THIS flake's lock, so the root flake stays a leaf with zero skill inputs and transitive consumers never drag the skill mesh in.";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    systems.url = "github:nix-systems/default";

    # `agent-skill-flake` is the builder library, not a skill — it provides
    # `mkDevshellSkillsFlake`. Followed by every skill source below so the
    # whole tree shares one evaluation.
    agent-skill-flake = {
      url = "github:nhooey/agent-skill-flake";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Every input below this divider is a skill source.

    # Running headless in a checkout, a tidy scratchpad, and the
    # cross-repository plan's graph.
    coding-agent-skills = {
      url = "github:nhooey/coding-agent-skills/overnight-skills";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        agent-skill-flake.follows = "agent-skill-flake";
      };
    };

    # Markdown hygiene, for the README, docs/ and the skills this repo ships.
    document-skills = {
      url = "github:nhooey/document-skills/overnight-skills";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        agent-skill-flake.follows = "agent-skill-flake";
      };
    };

    # Git and GitHub hygiene, policy and workflow; picked below.
    git-skills = {
      url = "github:nhooey/git-skills/overnight-skills";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        agent-skill-flake.follows = "agent-skill-flake";
      };
    };

    # Only nix-flakes, which this repo's flake.nix follows.
    nix-skills = {
      url = "github:nhooey/nix-skills/overnight-skills";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        agent-skill-flake.follows = "agent-skill-flake";
      };
    };

    # Python style, for the package in src/ and its tests.
    python-skills = {
      url = "github:nhooey/python-skills/overnight-skills";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        agent-skill-flake.follows = "agent-skill-flake";
      };
    };

    # Safe shell commands: named deletes, PIDs, no machine-wide changes.
    shell-skills = {
      url = "github:nhooey/shell-skills/overnight-skills";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        agent-skill-flake.follows = "agent-skill-flake";
      };
    };

    # Prose hygiene, for the README, docs/ and commit messages.
    writing-skills = {
      url = "github:nhooey/writing-skills/overnight-skills";
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
      coding-agent-skills,
      document-skills,
      git-skills,
      nix-skills,
      python-skills,
      shell-skills,
      writing-skills,
      ...
    }@inputs:
    agent-skill-flake.lib.mkDevshellSkillsFlake {
      inherit nixpkgs;
      systems = import inputs.systems;
      name = "jellyfin-settings-skills";
      sources = [
        {
          source = coding-agent-skills;
          skills = [
            "coding-agent-headless-in-checkout"
            "coding-agent-plans-as-graph"
            "coding-agent-scratchpad-scripts"
          ];
        }
        { source = document-skills; }
        {
          source = git-skills;
          # All but git-hygiene-conventional-commits: this repo's subjects
          # are plain sentences, not `type(scope):` prefixes.
          skills = [
            "git-hygiene-avoid-sweeping-operations"
            "git-hygiene-branch-naming"
            "git-hygiene-commit-message-format"
            "git-hygiene-gitignore"
            "git-hygiene-no-history-in-tracked-files"
            "git-hygiene-push-force-safely"
            "git-hygiene-ssh-remotes"
            "git-workflow-curate-unpushed"
            "git-workflow-inspect-before-commit"
            "git-workflow-push-mode"
            "git-workflow-tidy-branches"
            "github-hygiene-gh-cli-gotchas"
            "github-hygiene-pull-request-mirrors-commit"
            "github-hygiene-refer-to-issues-and-pull-requests"
            "github-policy-auto-delete-merged-branches"
            "github-policy-codeowners"
            "github-policy-merge-commits-only"
            "github-policy-protect-default-branch"
            "github-workflow-browser-draft-preview"
            "github-workflow-pull-request-changeset-prompt"
            "github-workflow-pull-request-stacked"
            "github-workflow-pull-request-status-line"
            "github-workflow-pull-request-watcher"
            "github-workflow-repo-activity"
          ];
        }
        {
          source = nix-skills;
          skills = [ "nix-flakes" ];
        }
        { source = python-skills; }
        { source = shell-skills; }
        { source = writing-skills; }
      ];
    };
}
