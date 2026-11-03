# The `jellyfin-settings` command, with its unit tests run in the build.
{ lib, python3Packages }:
python3Packages.buildPythonApplication {
  pname = "jellyfin-settings";
  version = "0.1.0";
  pyproject = true;
  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../pyproject.toml
      ../src
      ../tests
    ];
  };
  build-system = [ python3Packages.hatchling ];
  dependencies = with python3Packages; [
    httpx
    toolz
    typer
  ];
  nativeCheckInputs = with python3Packages; [
    pytestCheckHook
    respx
  ];
  pythonImportsCheck = [ "jellyfin_settings" ];
  meta = {
    description = "Declare Jellyfin's settings and apply them through its REST API";
    license = lib.licenses.mit;
    mainProgram = "jellyfin-settings";
  };
}
