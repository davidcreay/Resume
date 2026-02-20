import json
import yaml
from resume_cli import converters


def test_yaml_to_json(tmp_path):
    d = tmp_path / "test.yaml"
    d.write_text("name: John Doe")

    result = converters.yaml_to_json(d)
    assert json.loads(result)["name"] == "John Doe"


def test_json_to_yaml(tmp_path):
    d = tmp_path / "test.json"
    d.write_text('{"name": "John Doe"}')

    result = converters.json_to_yaml(d)
    assert "name: John Doe" in result