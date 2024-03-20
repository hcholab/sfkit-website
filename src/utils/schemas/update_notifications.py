update_notifications_schema = {
    "type": "object",
    "properties": {"notification": {"type": "string", "pattern": "^[^<>]*$", "maxLength": 1000}},
    "required": ["notification"],
    "additionalProperties": False,
}
