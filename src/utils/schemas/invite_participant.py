invite_participant_schema = {
    "type": "object",
    "properties": {
        "study_id": {
            "type": "string",
            "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[4][0-9a-fA-F]{3}-[89ABab][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$",
        },
        "inviter_id": {
            "type": "string",
            "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[4][0-9a-fA-F]{3}-[89ABab][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$",
        },
        "invitee_email": {"type": "string", "format": "email"},
        "message": {"type": "string", "pattern": "^[^<>]*$", "maxLength": 1000},
    },
    "required": ["study_id", "inviter_id", "invitee_email"],
    "additionalProperties": False,
}
