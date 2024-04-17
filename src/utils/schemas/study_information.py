study_information_schema = {
    "type": "object",
    "properties": {
        "description": {"type": "string", "pattern": "^[^<>]*$", "maxLength": 1000},
        "information": {"type": "string", "pattern": "^[^<>]*$", "maxLength": 1000},
    },
    "required": ["description", "information"],
    "additionalProperties": False,
}
