import asyncio
import os
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List

import httpx
from google.cloud import firestore
from quart import Blueprint, Websocket, abort, current_app, websocket

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

# Environment variables
PORT = os.getenv("PORT", "8080")  # Set automatically by Cloud Run
ORIGIN = os.getenv("ORIGIN", "wss://sfkit-website-dev-bhj5a4wkqa-uc.a.run.app") # host.docker.internal:{PORT}  # e.g. ws://sfkit.terra.bio (/.org) # TODO: fix default
TERRA = os.getenv("TERRA", "")

# Header
AUTH_HEADER = "Authorization"  # In Terra, this is machine ID, in non-terra, this is a JWT?
STUDY_ID_HEADER = ("X-MPC-Study-ID") 

@bp.websocket("/ice")
async def handler():
    if websocket.headers.get("Origin") != ORIGIN:
        print(f"Unexpected Origin header: {websocket.headers.get('Origin')} != {ORIGIN}")
        await Message(MessageType.ERROR, "Unexpected Origin header").send(websocket)
        abort(401)

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


async def _get_user_id(ws):
    # sourcery skip: assign-if-exp, reintroduce-else, remove-unnecessary-else, swap-if-else-branches
    if TERRA:
        print(f"TERRA is {TERRA}")
        auth_header = ws.headers.get(AUTH_HEADER)
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://sam.dsde-dev.broadinstitute.org/register/user/v2/self/info",
                headers={
                    "Authorization": auth_header,
                },
            )
            if res.is_error: 
                return None
            return res.json()["userSubjectId"] # TODO: do same logic for authorization for other endpoints

    else: # try to extract from auth header (azure, google)
        return await _get_subject_id(ws)


async def _get_subject_id(ws) -> str:
    auth_header: str = ws.headers.get(AUTH_HEADER, "")
    if not auth_header:
        return None
    print(f"auth_header is {auth_header}")
    auth_key = auth_header.split(" ")[1]
    if not auth_key:
        await Message(MessageType.ERROR, "Unable_to_read_auth_key").send(ws)
    print(f"auth_key is {auth_key}")
    db: firestore.AsyncClient = current_app.config["DATABASE"]
    user_dict = (
        (await db.collection("users").document("auth_keys").get()).to_dict()[auth_key]
    )
    return user_dict["username"]
    # except Exception as e: # azure auth
    #     print("Trying to get subject ID from Azure")
    #     decoded_token = await verify_token(auth_header.split(" ")[1])
    #     return decoded_token["sub"]
    # except Exception as e: # google auth (machine ID)
    #     print("Trying to get subject ID from Google")
    #     # TODO: read e to see if google is what we want
    #     async with httpx.AsyncClient() as client:
    #         res = await client.get(
    #             "https://www.googleapis.com/oauth2/v3/tokeninfo",
    #             headers={
    #                 "Authorization": auth_header,
    #             },
    #         )
    #         if not res.is_error: 
    #             return str(
    #                 res.json()["sub"]
    #             )  
    #         await Message(
    #             MessageType.ERROR,
    #             f"Unable to fetch subject ID from Google: {res.status_code} {str(res.read())}",
    #         ).send()
    # return None

async def _get_study_participants(study_id: str) -> List[str]:
    db = current_app.config["DATABASE"]
    doc_ref_dict = (await db.collection("studies").document(study_id).get()).to_dict()
    return doc_ref_dict.get("participants", [])


def _get_pid(study: List[str], user_id: str) -> PID:
    return study.index(user_id) if user_id in study else -1
    
