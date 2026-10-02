from datetime import datetime, timezone
from hashlib import sha256

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
import os


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")

if not MONGODB_URI:
    raise RuntimeError(
        "MONGODB_URI is missing from .env"
    )


# ============================================================
# MONGODB
# ============================================================

client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=10000,
)

db = client["filtersco_customer"]

users_collection = db["users"]
bookings_collection = db["bookings"]
support_collection = db["support_messages"]


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="FiltersCo Backend",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# MODELS
# ============================================================


class RegisterRequest(BaseModel):
    firstName: str
    lastName: str
    email: str
    phone: str
    password: str


class BookingCreate(BaseModel):
    email: str
    firstName: str = ""
    lastName: str = ""
    phone: str = ""
    product: str
    address: str
    city: str
    date: str
    time: str
    status: str = "Pending"


class BookingStatusUpdate(BaseModel):
    status: str


class SupportCreate(BaseModel):
    firstName: str
    lastName: str
    phone: str
    email: str
    message: str


class SupportReply(BaseModel):
    reply: str


# ============================================================
# HELPER FUNCTIONS
# ============================================================


def serialize_document(document):
    """
    Convert MongoDB ObjectId and datetime values
    into JSON-friendly values.
    """

    if document is None:
        return None

    result = {}

    for key, value in document.items():

        if isinstance(value, ObjectId):
            result[key] = str(value)

        elif isinstance(value, datetime):
            result[key] = value.isoformat()

        else:
            result[key] = value

    return result


def hash_password(password: str) -> str:
    """
    Temporary password hashing.
    For production use Argon2 or bcrypt.
    """

    return sha256(
        password.encode("utf-8")
    ).hexdigest()


# ============================================================
# ROOT
# ============================================================


@app.get("/")
def root():
    return {
        "success": True,
        "message": "FiltersCo backend is running"
    }


# ============================================================
# DATABASE TEST
# ============================================================


@app.get("/database-test")
def database_test():

    try:
        client.admin.command("ping")

        return {
            "success": True,
            "message": "MongoDB connected successfully"
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# CUSTOMER REGISTRATION
# ============================================================


@app.post("/register")
def register_user(
    user: RegisterRequest
):

    email = user.email.strip().lower()

    existing_user = users_collection.find_one(
        {
            "email": email
        }
    )

    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    user_data = {
        "firstName": user.firstName.strip(),
        "lastName": user.lastName.strip(),
        "email": email,
        "phone": user.phone.strip(),
        "password": hash_password(
            user.password
        ),
        "createdAt": datetime.now(
            timezone.utc
        ),
    }

    result = users_collection.insert_one(
        user_data
    )

    return {
        "success": True,
        "message": "Registration successful",
        "userId": str(result.inserted_id),
    }


# ============================================================
# CREATE BOOKING
# ============================================================


@app.post("/bookings")
def create_booking(
    booking: BookingCreate
):

    try:

        email = booking.email.strip().lower()

        booking_data = {
            "email": email,
            "firstName": booking.firstName.strip(),
            "lastName": booking.lastName.strip(),
            "phone": booking.phone.strip(),
            "product": booking.product.strip(),
            "address": booking.address.strip(),
            "city": booking.city.strip(),
            "date": booking.date.strip(),
            "time": booking.time.strip(),
            "status": booking.status.strip()
            or "Pending",
            "createdAt": datetime.now(
                timezone.utc
            ),
        }

        result = bookings_collection.insert_one(
            booking_data
        )

        return {
            "success": True,
            "message": "Demo booked successfully",
            "bookingId": str(
                result.inserted_id
            ),
        }

    except Exception as e:

        print(
            "BOOKING CREATE ERROR:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# CUSTOMER BOOKING HISTORY
# ============================================================


@app.get("/bookings/{email}")
def get_customer_bookings(
    email: str
):

    try:

        decoded_email = email.strip().lower()

        bookings = bookings_collection.find(
            {
                "email": decoded_email
            }
        ).sort(
            "createdAt",
            -1
        )

        result = []

        for booking in bookings:

            result.append(
                serialize_document(
                    booking
                )
            )

        return result

    except Exception as e:

        print(
            "CUSTOMER BOOKINGS ERROR:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# ADMIN - GET ALL BOOKINGS
# ============================================================


@app.get("/admin/bookings")
def get_all_bookings():

    try:

        bookings = bookings_collection.find().sort(
            "createdAt",
            -1
        )

        result = []

        for booking in bookings:

            result.append(
                serialize_document(
                    booking
                )
            )

        return result

    except Exception as e:

        print(
            "ADMIN BOOKINGS ERROR:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# ADMIN - UPDATE BOOKING STATUS
# ============================================================


@app.put(
    "/admin/bookings/{booking_id}/status"
)
def update_booking_status(
    booking_id: str,
    status_data: BookingStatusUpdate
):

    try:

        # Validate ObjectId

        if not ObjectId.is_valid(
            booking_id
        ):

            raise HTTPException(
                status_code=400,
                detail="Invalid booking ID"
            )

        allowed_statuses = [
            "Pending",
            "Confirmed",
            "Completed",
            "Cancelled",
        ]

        status = (
            status_data.status.strip()
        )

        if status not in allowed_statuses:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid booking status. "
                    "Allowed values: "
                    + ", ".join(
                        allowed_statuses
                    )
                ),
            )

        result = bookings_collection.update_one(
            {
                "_id": ObjectId(
                    booking_id
                )
            },
            {
                "$set": {
                    "status": status,
                    "updatedAt": datetime.now(
                        timezone.utc
                    ),
                }
            },
        )

        if result.matched_count == 0:

            raise HTTPException(
                status_code=404,
                detail="Booking not found"
            )

        return {
            "success": True,
            "message": (
                "Booking status updated successfully"
            ),
            "bookingId": booking_id,
            "status": status,
        }

    except HTTPException:

        raise

    except Exception as e:

        print(
            "BOOKING STATUS ERROR:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# CUSTOMER SUPPORT - CREATE MESSAGE
# ============================================================


@app.post("/support")
def create_support_message(
    support: SupportCreate
):

    try:

        support_data = {
            "firstName": support.firstName.strip(),
            "lastName": support.lastName.strip(),
            "phone": support.phone.strip(),
            "email": support.email.strip().lower(),
            "message": support.message.strip(),
            "reply": "",
            "status": "Pending",
            "createdAt": datetime.now(
                timezone.utc
            ),
        }

        if not support_data["message"]:

            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty"
            )

        result = support_collection.insert_one(
            support_data
        )

        return {
            "success": True,
            "message": (
                "Support message sent successfully"
            ),
            "messageId": str(
                result.inserted_id
            ),
        }

    except HTTPException:

        raise

    except Exception as e:

        print(
            "SUPPORT CREATE ERROR:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# ADMIN - GET SUPPORT MESSAGES
# ============================================================


@app.get("/admin/support")
def get_all_support_messages():

    try:

        messages = support_collection.find().sort(
            "createdAt",
            -1
        )

        result = []

        for message in messages:

            result.append(
                serialize_document(
                    message
                )
            )

        return result

    except Exception as e:

        print(
            "ADMIN SUPPORT ERROR:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# CUSTOMER - GET SUPPORT MESSAGES
# ============================================================


@app.get("/support/{email}")
def get_customer_support_messages(
    email: str
):

    try:

        decoded_email = (
            email.strip().lower()
        )

        messages = support_collection.find(
            {
                "email": decoded_email
            }
        ).sort(
            "createdAt",
            -1
        )

        result = []

        for message in messages:

            result.append(
                serialize_document(
                    message
                )
            )

        return result

    except Exception as e:

        print(
            "CUSTOMER SUPPORT ERROR:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# ADMIN - REPLY TO SUPPORT MESSAGE
# ============================================================


@app.post(
    "/admin/support/{message_id}/reply"
)
def reply_to_support(
    message_id: str,
    reply_data: SupportReply
):

    try:

        # Validate ObjectId

        if not ObjectId.is_valid(
            message_id
        ):

            raise HTTPException(
                status_code=400,
                detail="Invalid support message ID"
            )

        reply = (
            reply_data.reply.strip()
        )

        if not reply:

            raise HTTPException(
                status_code=400,
                detail="Reply cannot be empty"
            )

        result = support_collection.update_one(
            {
                "_id": ObjectId(
                    message_id
                )
            },
            {
                "$set": {
                    "reply": reply,
                    "status": "Replied",
                    "repliedAt": datetime.now(
                        timezone.utc
                    ),
                }
            },
        )

        if result.matched_count == 0:

            raise HTTPException(
                status_code=404,
                detail="Support message not found"
            )

        return {
            "success": True,
            "message": (
                "Reply sent successfully"
            ),
            "messageId": message_id,
            "status": "Replied",
        }

    except HTTPException:

        raise

    except Exception as e:

        print(
            "SUPPORT REPLY ERROR:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# STARTUP
# ============================================================


@app.on_event("startup")
def startup_event():

    try:

        client.admin.command("ping")

        print(
            "======================================"
        )
        print(
            "FiltersCo Backend Started"
        )
        print(
            "MongoDB Connected"
        )
        print(
            "Database: filtersco_customer"
        )
        print(
            "======================================"
        )

    except Exception as e:

        print(
            "MongoDB connection error:",
            e
        )