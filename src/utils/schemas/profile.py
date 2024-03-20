profile_schema = {
    "type": "object",
    "properties": {
        "displayName": {"type": "string", "pattern": "^[^<>]*$", "maxLength": 1000},
        "about": {"type": "string", "pattern": "^[^<>]*$", "maxLength": 1000},
    },
    "required": ["displayName", "about"],
    "additionalProperties": False,
}
