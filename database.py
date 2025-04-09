from pymongo import MongoClient
from dotenv import load_dotenv
import os
import bcrypt
import datetime

load_dotenv()

class Database:
    def __init__(self):
        self.client = MongoClient(os.getenv('MONGODB_URI'))
        self.db = self.client.discord_bot
        self.orders = self.db.orders
        self.users = self.db.users
        self.admins = self.db.admins
        self._initialize_admins()

    def _initialize_admins(self):
        # Predefined admin credentials
        admin_credentials = [
            {"username": "saif", "password": "S@1"},
            {"username": "mohammad", "password": "hamoudy@2009"}
        ]
        
        # Only add if they don't exist
        for admin in admin_credentials:
            if not self.admins.find_one({"username": admin["username"]}):
                hashed = bcrypt.hashpw(admin["password"].encode('utf-8'), bcrypt.gensalt())
                self.admins.insert_one({
                    "username": admin["username"],
                    "password": hashed,
                    "discord_id": None,
                    "is_logged_in": False
                })

    def register_user(self, username, password, discord_id):
        if self.users.find_one({"username": username}):
            return False, "Username already exists"
        
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        self.users.insert_one({
            "username": username,
            "password": hashed,
            "discord_id": discord_id,
            "is_logged_in": False
        })
        return True, "Registration successful"

    def login_user(self, username, password, discord_id):
        user = self.users.find_one({"username": username})
        if not user:
            return False, "User not found"
        
        if not bcrypt.checkpw(password.encode('utf-8'), user['password']):
            return False, "Invalid password"
        
        self.users.update_one(
            {"username": username},
            {"$set": {"is_logged_in": True, "discord_id": discord_id}}
        )
        return True, "Login successful"

    def logout_user(self, discord_id):
        self.users.update_one(
            {"discord_id": discord_id},
            {"$set": {"is_logged_in": False}}
        )

    def is_logged_in(self, discord_id):
        user = self.users.find_one({"discord_id": discord_id})
        return user and user.get("is_logged_in", False)

    def login_admin(self, username, password, discord_id):
        admin = self.admins.find_one({"username": username})
        if not admin:
            return False, "Invalid credentials"
        
        if not bcrypt.checkpw(password.encode('utf-8'), admin['password']):
            return False, "Invalid credentials"
        
        self.admins.update_one(
            {"username": username},
            {"$set": {"is_logged_in": True, "discord_id": discord_id}}
        )
        return True, "Login successful"

    def logout_admin(self, discord_id):
        self.admins.update_one(
            {"discord_id": discord_id},
            {"$set": {"is_logged_in": False}}
        )

    def is_admin_logged_in(self, discord_id):
        admin = self.admins.find_one({"discord_id": discord_id})
        return admin and admin.get("is_logged_in", False)

    def add_order(self, order_id: int, url: str, user_id: int):
        self.orders.insert_one({
            "order_id": order_id,
            "url": url,
            "user_id": user_id,
            "created_at": datetime.now()
        })

    def get_all_orders(self):
        return list(self.orders.find({}, {"_id": 0}))

    def get_user_orders(self, user_id: int):
        return list(self.orders.find({"user_id": user_id}, {"_id": 0}))

    def get_order(self, order_id: int):
        return self.orders.find_one({"order_id": order_id}, {"_id": 0})

    def delete_order(self, order_id: int):
        self.orders.delete_one({"order_id": order_id})

    def update_order_status(self, order_id, status):
        return self.orders.update_one(
            {"order_id": order_id},
            {"$set": {"status": status}}
        ) 