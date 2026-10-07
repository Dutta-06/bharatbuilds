"""template.yaml must agree with the code about the table and the functions."""

from pathlib import Path

import yaml

from backend.db import TABLE_KEYS

ROOT = Path(__file__).resolve().parents[2]


class CfnLoader(yaml.SafeLoader):
    pass


def _tag(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


CfnLoader.add_multi_constructor("!", _tag)


def template():
    return yaml.load((ROOT / "template.yaml").read_text(), Loader=CfnLoader)


def test_table_keys_match_code():
    props = template()["Resources"]["MainTable"]["Properties"]
    assert props["AttributeDefinitions"] == TABLE_KEYS["AttributeDefinitions"]
    assert props["KeySchema"] == TABLE_KEYS["KeySchema"]
    gsi = props["GlobalSecondaryIndexes"][0]
    assert gsi["IndexName"] == "GSI1" and gsi["KeySchema"] == TABLE_KEYS["GlobalSecondaryIndexes"][0]["KeySchema"]


def test_every_function_dir_is_in_the_template():
    uris = {r["Properties"]["CodeUri"].strip("/") for r in template()["Resources"].values()
            if r["Type"] == "AWS::Serverless::Function"}
    dirs = {f"functions/{p.name}" for p in (ROOT / "functions").iterdir() if p.is_dir()
            if not p.name.startswith("__")}
    assert dirs <= uris
