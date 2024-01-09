import asyncio
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List

from quart import Blueprint, Websocket, abort, current_app, websocket
from quart_cors import websocket_cors

from src.api_utils import get_websocket_origin
from src.auth import get_user_id, get_cli_user
from src.utils import constants

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

    async def send(self, ws: Websocket):
        msg = asdict(self)
        for key, value in msg.items():
            if isinstance(value, Enum):
                msg[key] = value.value
        await ws.send_json(msg)

    @staticmethod
    async def receive(ws: Websocket):
        msg = await ws.receive_json()
        print("Received", msg)
        msg["type"] = MessageType(msg["type"])
        return Message(**msg)

# in-memory stores for Websockets
study_barriers: Dict[str, asyncio.Barrier] = {}
study_parties: Dict[str, Dict[PID, Websocket]] = {}

# Header
STUDY_ID_HEADER = ("X-MPC-Study-ID")

@bp.websocket("/ice")
@websocket_cors(allow_origin=get_websocket_origin())
async def handler():
    user_id = await _get_user_id(websocket)
    if not user_id:
        await Message(MessageType.ERROR, "Missing authentication").send(websocket)
        abort(401)

    study_id = websocket.headers.get(STUDY_ID_HEADER)
    if not study_id:
        await Message(MessageType.ERROR, f"Missing {STUDY_ID_HEADER} header").send(websocket)
        abort(400)

    study_participants = await _get_study_participants(study_id)

    pid = _get_pid(study_participants, user_id)
    if pid < 0:
        await Message(
            MessageType.ERROR, f"User {user_id} is not in study {study_id}"
        ).send(websocket)
        abort(403)

    parties = study_parties.setdefault(study_id, {})
    if pid in parties:
        await Message(
            MessageType.ERROR,
            f"Party {pid} is already connected to study {study_id}",
        ).send(websocket)
        abort(409)

    try:
        # store the current websocket for the party
        parties[pid] = websocket._get_current_object()
        print(f"Registered websocket for party {pid}")

        # using a study-specific barrier,
        # wait until all participants in a study are connected,
        # and then initiate the ICE protocol for it
        barrier = study_barriers.setdefault(study_id, asyncio.Barrier(len(study_participants)))
        async with barrier:
            if pid == 0:
                print(f"{pid}: All parties have connected:", ", ".join(str(k) for k in parties))

            while True:
                print(f"pid: {pid}, parties: {parties}")
                # read the next message and override its PID
                # (this prevents PID spoofing)
                msg = await Message.receive(websocket)
                msg.sourcePID = pid
                msg.studyID = study_id

                # and send it to the other party
                if msg.targetPID < 0:
                    await Message(
                        MessageType.ERROR, f"Missing target PID: {msg}"
                    ).send(websocket)
                    continue
                elif msg.targetPID not in parties or msg.targetPID == pid:
                    print(f"Unexpected message is {msg}. Parties are {parties}")
                    await Message(
                        MessageType.ERROR,
                        f"Unexpected target id {msg.targetPID}",
                    ).send(websocket)
                    continue
                else:
                    target_ws = parties[msg.targetPID]
                    await msg.send(target_ws)
    except Exception as e:
        print(f"Terminal connection error for party {pid} in study {study_id}: {e.with_traceback()}")
    finally:
        del parties[pid]
        print(f"Party {pid} disconnected from study {study_id}")


async def _get_user_id(ws: Websocket):
    # sourcery skip: assign-if-exp, reintroduce-else, remove-unnecessary-else, swap-if-else-branches
    if constants.TERRA:
        return await get_user_id(ws)
    else:
        user = await get_cli_user(ws)
        if user:
            return user["username"]
        else:
            await Message(MessageType.ERROR, "Unable_to_read_auth_key").send(ws)


async def _get_study_participants(study_id: str) -> List[str]:
    db = current_app.config["DATABASE"]
    doc_ref_dict = (await db.collection("studies").document(study_id).get()).to_dict()
    return doc_ref_dict.get("participants", [])


def _get_pid(study: List[str], user_id: str) -> PID:
    return study.index(user_id) if user_id in study else -1

