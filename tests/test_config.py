"""The shipped defaults and how a settings file merges over them."""

import json

import pytest

from jellyfin_settings import config


def load(settings):
    return config.load(json.dumps(settings).encode())


def test_defaults_name_every_setting():
    assert config.defaults() == {
        "url": "http://localhost:8096",
        "encoding": {},
        "users": {},
        "libraries": {},
    }


def test_empty_settings_give_exactly_the_defaults():
    assert load({}) == config.defaults()


def test_a_sparse_file_changes_only_its_keys():
    assert load({"encoding": {"H264Crf": 20}}) == {**config.defaults(), "encoding": {"H264Crf": 20}}


def test_maps_merge_by_key_and_lists_replace():
    base = {"a": {"x": 1, "y": [1, 2]}, "b": 2}
    assert config.deep_merge(base, {"a": {"y": [3]}}) == {"a": {"x": 1, "y": [3]}, "b": 2}


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"urll": "http://x"}, "unknown key 'urll'"),
        ({"libraries": {"M": {"type": "movies"}}}, "libraries.M: needs exactly the keys paths, type"),
        ({"libraries": {"M": {"type": "movies", "paths": [], "x": 1}}}, "libraries.M: needs exactly"),
        ({"libraries": []}, "libraries must be a map"),
        ({"libraries": None}, "libraries must be a map, not null"),
        ({"users": None}, "users must be a map, not null"),
        ({"encoding": []}, "encoding must be a map, not a list"),
        ({"url": 5}, "url must be a string, not int"),
        ({"users": {"u": "Always"}}, "users.u must be a map, not a string"),
        ({"libraries": {"M": {"type": "movies", "paths": "~/M"}}}, "libraries.M: type must be a string"),
        ({"libraries": {"M": {"type": None, "paths": []}}}, "libraries.M: type must be a string"),
        ({"libraries": {"M": {"type": "movies", "paths": [1]}}}, "paths a list of strings"),
    ],
)
def test_settings_outside_the_defaults_shape_are_refused(settings, message):
    with pytest.raises(config.SettingsError, match=message):
        load(settings)


def test_a_file_not_holding_an_object_is_refused():
    with pytest.raises(config.SettingsError, match="JSON object"):
        config.load(b"[]")
