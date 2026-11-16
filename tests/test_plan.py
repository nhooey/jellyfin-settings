import copy

from jellyfin_settings.plan import Plan, plan


def expand(p):
    return p.replace("~", "/home/u", 1)


STATE = {
    "encoding": {"H264Crf": 23, "HardwareAccelerationType": "none", "Other": 1},
    "users": [{"Name": "u", "Id": "42", "Configuration": {"SubtitleMode": "Default", "X": 0}}],
    "folders": [{"Name": "Movies", "Locations": ["/home/u/Video/Movies"]}],
}


def test_matching_settings_plan_nothing():
    settings = {
        "encoding": {"H264Crf": 23},
        "users": {"u": {"SubtitleMode": "Default"}},
        "libraries": {"Movies": {"type": "movies", "paths": ["~/Video/Movies"]}},
    }
    assert plan(STATE, settings, expand) == Plan()


def test_encoding_posts_whole_config_with_unlisted_keys_kept():
    p = plan(STATE, {"encoding": {"H264Crf": 20}}, expand)
    assert p.drift == ("encoding.H264Crf: Jellyfin has 23, declared 20",)
    (r,) = p.requests
    assert (r.method, r.path) == ("POST", "/System/Configuration/encoding")
    assert r.body == {"H264Crf": 20, "HardwareAccelerationType": "none", "Other": 1}


def test_user_configuration_posted_by_id():
    (r,) = plan(STATE, {"users": {"u": {"SubtitleMode": "Always"}}}, expand).requests
    assert r.path == "/Users/42/Configuration"
    assert r.body == {"SubtitleMode": "Always", "X": 0}


def test_unknown_user_is_skipped_not_requested():
    p = plan(STATE, {"users": {"nobody": {"X": 1}}}, expand)
    assert (p.requests, p.drift) == ((), ())
    assert p.skipped == ("users.nobody: no such Jellyfin user",)


def test_new_library_and_path_then_one_scan():
    settings = {
        "libraries": {
            "Movies": {"type": "movies", "paths": ["~/Video/Movies", "~/More"]},
            "Music": {"type": "music", "paths": ["~/Music"]},
        }
    }
    p = plan(STATE, settings, expand)
    assert p.drift == ("libraries.Movies: lacks path /home/u/More", "libraries.Music: missing in Jellyfin")
    assert [(r.method, r.path, r.body) for r in p.requests] == [
        (
            "POST",
            "/Library/VirtualFolders/Paths?refreshLibrary=false",
            {"Name": "Movies", "PathInfo": {"Path": "/home/u/More"}},
        ),
        (
            "POST",
            "/Library/VirtualFolders?name=Music&collectionType=music&refreshLibrary=false",
            {"LibraryOptions": {"PathInfos": [{"Path": "/home/u/Music"}]}},
        ),
        ("POST", "/Library/Refresh", None),
    ]


def test_plan_leaves_its_inputs_unchanged():
    settings = {
        "encoding": {"H264Crf": 1},
        "users": {"u": {"X": 2}},
        "libraries": {"Movies": {"type": "movies", "paths": ["~/More"]}},
    }
    state, wanted = copy.deepcopy(STATE), copy.deepcopy(settings)
    plan(state, wanted, expand)
    assert (state, wanted) == (STATE, settings)
