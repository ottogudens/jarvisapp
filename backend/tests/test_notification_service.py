from types import SimpleNamespace

from backend.notification_service import matches, parse_mqtt_payload


def rule(**values):
    return SimpleNamespace(
        json_path=values.get("json_path"),
        operator=values.get("operator", "equals"),
        expected_value=values.get("expected_value", ""),
    )


def test_mqtt_json_payload_and_nested_condition():
    payload = parse_mqtt_payload('{"device":{"state":"offline"}}')
    assert matches(rule(json_path="device.state", expected_value="offline"), payload)


def test_numeric_and_plain_text_conditions():
    assert matches(rule(json_path="temperature", operator="greater_than", expected_value="30"), {"temperature": 30.1})
    assert matches(rule(operator="contains", expected_value="alarm"), "alarm activated")
    assert not matches(rule(json_path="temperature", operator="less_than", expected_value="20"), {"temperature": 22})
