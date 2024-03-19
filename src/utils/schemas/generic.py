generic_schema = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "anyOf": [
                {
                    "type": "string",
                    "pattern": "^[0-9a-zA-Z\\-_,./\\s?!]*$",
                    "maxLength": 1000,
                },
                {"type": "boolean"},
                {"type": "number"},
            ]
        }
    },
    "additionalProperties": False,
    "maxProperties": 100,
}
