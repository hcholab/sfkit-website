import asyncio
from unittest import mock

import pytest

from src.utils import api_functions


@pytest.mark.parametrize(
    "role, create_vm, delete_vm, status, action",
    [
        # the website's CP0 VM holds the internal IP every CP0 gets until it is deleted
        ("0", "No", "No", "Finished protocol!", "delete_instance"),
        # a failed CP0 is left running, with its logs
        ("0", "No", "No", "FAILED - Failed SF-SKAT protocol", None),
        ("0", "No", "No", "finishing SF-SKAT protocol", None),
        # a participant's own VM is deleted only if they asked for it
        ("1", "Yes", "Yes", "Finished protocol!", "delete_instance"),
        ("1", "Yes", "No", "Finished protocol!", "stop_instance"),
        ("1", "No", "No", "Finished protocol!", None),
    ],
)
def test_process_status_vm(role, create_vm, delete_vm, status, action):
    username = "Broad" if role == "0" else "user"
    doc_ref_dict = {
        "personal_parameters": {
            username: {"CREATE_VM": {"value": create_vm}, "DELETE_VM": {"value": delete_vm}},
        },
    }
    with (
        mock.patch.object(api_functions, "update_status", mock.AsyncMock()) as update_status,
        mock.patch.object(api_functions, "delete_instance", mock.AsyncMock()) as delete_instance,
        mock.patch.object(api_functions, "stop_instance", mock.AsyncMock()) as stop_instance,
    ):
        result = asyncio.run(
            api_functions.process_status(
                mock.Mock(), username, "study", f"status={status}", "doc_ref", doc_ref_dict, "project", role
            )
        )

    assert result == ({}, 200)
    assert update_status.call_args.args[1] == {"username": username, "status": status, "doc_ref": "doc_ref"}
    for name, instance_action in [("delete_instance", delete_instance), ("stop_instance", stop_instance)]:
        if name == action:
            instance_action.assert_called_once_with("study", "project", role)
        else:
            instance_action.assert_not_called()
