from datetime import datetime, timezone
from hashlib import sha256
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
import os
import re


load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is missing")

client = MongoClient(
    MONGODB_URI,
    serverSelectionTimeoutMS=10000,
    connectTimeoutMS=20000,
    socketTimeoutMS=20000,
)

db = client["filtersco_customer"]

users_collection = db["users"]
bookings_collection = db["bookings"]
support_collection = db["support_messages"]


app = FastAPI(
    title="FiltersCo Backend",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def serialize_document(document):
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
    return sha256(
        password.encode("utf-8")
    ).hexdigest()


@app.on_event("startup")
def startup_event():
    try:
        client.admin.command("ping")

        print("FiltersCo Backend Started")
        print("MongoDB Connected")
        print("Database: filtersco_customer")

    except Exception as error:
        print("MongoDB connection error:", error)


@app.get("/")
def root():
    return {
        "message": "FiltersCo Backend is running",
        "database": "filtersco_customer",
        "status": "online",
    }


@app.get("/database-test")
def database_test():
    try:
        client.admin.command("ping")

        return {
            "status": "success",
            "message": "MongoDB Connected",
            "database": "filtersco_customer",
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


@app.post("/register")
def register_user(request: RegisterRequest):

    first_name = request.firstName.strip()
    last_name = request.lastName.strip()
    email = request.email.strip().lower()
    phone = request.phone.strip()
    password = request.password.strip()

    if not first_name:
        raise HTTPException(
            status_code=400,
            detail="First name is required",
        )

    if not last_name:
        raise HTTPException(
            status_code=400,
            detail="Last name is required",
        )

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Email is required",
        )

    if not phone:
        raise HTTPException(
            status_code=400,
            detail="Phone is required",
        )

    if not password:
        raise HTTPException(
            status_code=400,
            detail="Password is required",
        )

    existing_user = users_collection.find_one(
        {
            "email": email
        }
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )

    user_data = {
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
        "phone": phone,
        "password": hash_password(password),
        "createdAt": datetime.now(timezone.utc),
    }

    result = users_collection.insert_one(
        user_data
    )

    return {
        "message": "Registration successful",
        "userId": str(result.inserted_id),
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
        "phone": phone,
    }


@app.post("/bookings")
def create_booking(booking: BookingCreate):

    email = booking.email.strip().lower()

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Email is required",
        )

    if not booking.product.strip():
        raise HTTPException(
            status_code=400,
            detail="Product is required",
        )

    if not booking.address.strip():
        raise HTTPException(
            status_code=400,
            detail="Address is required",
        )

    if not booking.city.strip():
        raise HTTPException(
            status_code=400,
            detail="City is required",
        )

    if not booking.date.strip():
        raise HTTPException(
            status_code=400,
            detail="Date is required",
        )

    if not booking.time.strip():
        raise HTTPException(
            status_code=400,
            detail="Time is required",
        )

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
        "status": booking.status.strip() or "Pending",
        "createdAt": datetime.now(timezone.utc),
    }

    result = bookings_collection.insert_one(
        booking_data
    )

    return {
        "message": "Demo booked successfully",
        "bookingId": str(result.inserted_id),
        "booking": serialize_document(booking_data),
    }


@app.get("/bookings/{email}")
def get_customer_bookings(email: str):

    customer_email = email.strip().lower()

    if not customer_email:
        return []

    bookings = list(
        bookings_collection.find(
            {
                "email": {
                    "$regex": "^" + re.escape(customer_email) + "$",
                    "$options": "i",
                }
            }
        ).sort(
            "createdAt",
            -1,
        )
    )

    return [
        serialize_document(booking)
        for booking in bookings
    ]


@app.get("/admin/bookings")
def get_all_bookings():

    bookings = list(
        bookings_collection.find().sort(
            "createdAt",
            -1,
        )
    )

    return [
        serialize_document(booking)
        for booking in bookings
    ]


@app.put("/admin/bookings/{booking_id}/status")
def update_booking_status(
    booking_id: str,
    update: BookingStatusUpdate,
):

    if not ObjectId.is_valid(booking_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid booking ID",
        )

    status = update.status.strip()

    allowed_statuses = [
        "Pending",
        "Confirmed",
        "Completed",
        "Cancelled",
    ]

    if status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid status. Allowed values: "
                "Pending, Confirmed, Completed, Cancelled"
            ),
        )

    result = bookings_collection.update_one(
        {
            "_id": ObjectId(booking_id)
        },
        {
            "$set": {
                "status": status,
                "updatedAt": datetime.now(timezone.utc),
            }
        },
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )

    updated_booking = bookings_collection.find_one(
        {
            "_id": ObjectId(booking_id)
        }
    )

    return {
        "message": "Booking status updated successfully",
        "booking": serialize_document(
            updated_booking
        ),
    }


@app.post("/support")
def create_support_message(
    support: SupportCreate,
):

    first_name = support.firstName.strip()
    last_name = support.lastName.strip()
    phone = support.phone.strip()
    email = support.email.strip().lower()
    message = support.message.strip()

    if not first_name:
        raise HTTPException(
            status_code=400,
            detail="First name is required",
        )

    if not last_name:
        raise HTTPException(
            status_code=400,
            detail="Last name is required",
        )

    if not phone:
        raise HTTPException(
            status_code=400,
            detail="Phone is required",
        )

    if not email:
        raise HTTPException(
            status_code=400,
            detail="Email is required",
        )

    if not message:
        raise HTTPException(
            status_code=400,
            detail="Message is required",
        )

    support_data = {
        "firstName": first_name,
        "lastName": last_name,
        "phone": phone,
        "email": email,
        "message": message,
        "reply": "",
        "status": "Pending",
        "createdAt": datetime.now(timezone.utc),
    }

    result = support_collection.insert_one(
        support_data
    )

    return {
        "message": "Support message sent successfully",
        "messageId": str(result.inserted_id),
        "support": serialize_document(
            support_data
        ),
    }


@app.get("/admin/support")
def get_all_support_messages():

    messages = list(
        support_collection.find().sort(
            "createdAt",
            -1,
        )
    )

    return [
        serialize_document(message)
        for message in messages
    ]


@app.get("/support/{email}")
def get_customer_support_messages(
    email: str,
):

    customer_email = email.strip().lower()

    messages = list(
        support_collection.find(
            {
                "email": {
                    "$regex": "^" + re.escape(customer_email) + "$",
                    "$options": "i",
                }
            }
        ).sort(
            "createdAt",
            -1,
        )
    )

    return [
        serialize_document(message)
        for message in messages
    ]


@app.post("/admin/support/{message_id}/reply")
def reply_to_support(
    message_id: str,
    support_reply: SupportReply,
):

    if not ObjectId.is_valid(message_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid support message ID",
        )

    reply = support_reply.reply.strip()

    if not reply:
        raise HTTPException(
            status_code=400,
            detail="Reply cannot be empty",
        )

    result = support_collection.update_one(
        {
            "_id": ObjectId(message_id)
        },
        {
            "$set": {
                "reply": reply,
                "status": "Replied",
                "repliedAt": datetime.now(timezone.utc),
            }
        },
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Support message not found",
        )

    updated_message = support_collection.find_one(
        {
            "_id": ObjectId(message_id)
        }
    )

    return {
        "message": "Reply sent successfully",
        "support": serialize_document(
            updated_message
        ),
    }
