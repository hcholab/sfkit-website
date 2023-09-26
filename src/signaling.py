import asyncio
import os
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Awaitable, Callable, Dict, List

import httpx
from quart import Blueprint, abort, copy_current_websocket_context, current_app, websocket

from src.auth import verify_token

bp = Blueprint("signaling", __name__, url_prefix="/api")

PID = int


class MessageType(Enum):
    CANDIDATE = "candidate"
    CREDENTIAL = "credential"
    CERTIFICATE = "certificate"
    ERROR = "error"


@dataclass
class Message:
    type: MessageType
    data: str = ""
    studyID: str = ""
    sourcePID: PID = -1
    targetPID: PID = -1

    async def send(self, ws=websocket):
        msg = asdict(self)
        for key, value in msg.items():
            if isinstance(value, Enum):
                msg[key] = value.value
        await ws.send_json(msg)

    @staticmethod
    async def receive():
        msg = await websocket.receive_json()
        print("Received", msg)
        msg["type"] = MessageType(msg["type"])
        return Message(**msg)

# in-memory stores for Websockets
study_barriers: Dict[str, asyncio.Barrier] = {}
study_parties: Dict[str, Dict[PID, Callable[[Message], Awaitable[None]]]] = {}

# Environment variables
PORT = os.getenv("PORT", "8000")  # Set automatically by Cloud Run
ORIGIN = os.getenv("ORIGIN", f"ws://host.docker.internal:{PORT}")  # e.g. ws://sfkit.terra.bio (/.org)
TERRA = os.getenv("TERRA", "y")

# Header
AUTH_HEADER = "Authorization"  # Only on NON-Terra;
USER_ID_HEADER = "OIDC_CLAIM_USER_ID"  # Only on Terra (extracted from authorization header by Apache)
STUDY_ID_HEADER = (
    "X-MPC-Study-ID"  # Study ID sent in header # TODO: make UUID for study
)

@bp.websocket("/ice")
async def handler():
    if websocket.headers.get("Origin") != ORIGIN:
        await Message(MessageType.ERROR, "Unexpected Origin header").send()
        abort(401)

    user_id = await _get_user_id()
    if not user_id:
        await Message(MessageType.ERROR, "Missing authentication").send()
        abort(401)

    study_id = websocket.headers.get(STUDY_ID_HEADER)
    if not study_id:
        await Message(MessageType.ERROR, f"Missing {STUDY_ID_HEADER} header").send()
        abort(400)

    study_participants = await _get_study_participants(study_id)

    pid = _get_pid(study_participants, user_id)
    if pid < 0:
        await Message(
            MessageType.ERROR, f"User {user_id} is not in study {study_id}"
        ).send()
        abort(403)

    parties = study_parties.setdefault(study_id, {})
    if pid in parties:
        await Message(
            MessageType.ERROR,
            f"Party {pid} is already connected to study {study_id}",
        ).send()
        abort(409)

    try:
        # store the current websocket send method for the party
        @copy_current_websocket_context
        async def ws_send(msg: Message):
            await msg.send()

        parties[pid] = ws_send
        print(f"Registered websocket for party {pid}")

        # using a study-specific barrier,
        # wait until all participants in a study are connected,
        # and then initiate the ICE protocol for it
        barrier = study_barriers.setdefault(study_id, asyncio.Barrier(len(study_participants)))
        async with barrier:
            if pid == 0:
                print("All parties have connected:", ", ".join(str(k) for k in parties))

            while True:
                # read the next message and override its PID
                # (this prevents PID spoofing)
                msg = await Message.receive()
                msg.sourcePID = pid
                msg.studyID = study_id

                # and send it to the other party
                if msg.targetPID < 0:
                    await Message(
                        MessageType.ERROR, f"Missing target PID: {msg}"
                    ).send()
                    continue
                elif msg.targetPID not in parties or msg.targetPID == pid:
                    await Message(
                        MessageType.ERROR,
                        f"Unexpected target id {msg.targetPID}",
                    ).send()
                    continue
                else:
                    target_send = parties[msg.targetPID]
                    await target_send(msg)
    except Exception as e:
        print(f"Terminal connection error for party {pid} in study {study_id}: {e}")
    finally:
        del parties[pid]
        print(f"Party {pid} disconnected from study {study_id}")


async def _get_user_id():
    if TERRA:
        # when running as a Terra service behind Apache proxy,
        # the proxy will take care of extracting JWT "sub" claim
        # into this header automatically
        return websocket.headers.get(USER_ID_HEADER)
    else: # try to extract from auth header (azure, google)
        return await _get_subject_id()


async def _get_subject_id() -> str:
    auth_header: str = websocket.headers.get(AUTH_HEADER, "")
    if not auth_header:
        return None
    try: # azure auth
        print("Trying to get subject ID from Azure")
        decoded_token = await verify_token(auth_header.split(" ")[1])
        return decoded_token["sub"]
    except Exception as e: # google auth (machine ID)
        print("Trying to get subject ID from Google")
        # TODO: read e to see if google is what we want
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://www.googleapis.com/oauth2/v3/tokeninfo",
                headers={
                    "Authorization": auth_header,
                },
            )
            if not res.is_error: 
                return str(
                    res.json()["sub"]
                )  
            await Message(
                MessageType.ERROR,
                f"Unable to fetch subject ID from Google: {res.status_code} {str(res.read())}",
            ).send()
    return None
    # TODO: add option using auth_key

async def _get_study_participants(study_id: str) -> List[str]:
    db = current_app.config["DATABASE"]
    doc_ref_dict = (await db.collection("studies").document(study_id).get()).to_dict()
    return doc_ref_dict.get("participants", [])


def _get_pid(study: List[str], user_id: str) -> PID:
    return study.index(user_id) if user_id in study else -1
    