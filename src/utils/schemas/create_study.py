create_study_schema = {
    "type": "object",
    "properties": {
        "study_type": {"type": "string", "pattern": "^[0-9a-zA-Z\\-]*$", "maxLength": 100},
        "setup_configuration": {"type": "string", "pattern": "^[0-9a-zA-Z\\-]*$", "maxLength": 100},
        "title": {"type": "string", "pattern": "^[^<>]*$", "maxLength": 100},
        "demo_study": {"type": "boolean"},
        "private_study": {"type": "boolean"},
        "description": {"type": "string", "pattern": "^[^<>]*$", "maxLength": 1000},
        "study_information": {"type": "string", "pattern": "^[^<>]*$", "maxLength": 1000},
    },
    "required": [
        "study_type",
        "setup_configuration",
        "title",
        "demo_study",
        "private_study",
        "description",
        "study_information",
    ],
    "additionalProperties": False,
}
