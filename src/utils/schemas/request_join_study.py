request_join_study_schema = {
    "type": "object",
    "properties": {
        "message": {"type": "string", "pattern": "^[^<>]*$", "maxLength": 1000},
    },
    "required": ["message"],
    "additionalProperties": False,
}
