from pymongo import MongoClient
from mongogettersetter import MongoGetterSetter

client = MongoClient("mongodb://sachin:Passwordbot@localhost:27017/")
db = client["bot"]
collection = db["employee"]

# Wrapper for MongoDB Collection with metaclass, use this inside your actual class.
class EmployeeCollection(metaclass=MongoGetterSetter):
    def __init__(self, _id):
        self._filter_query = {"id": _id} # or the ObjectID, at your convinence
        self._collection = collection # Should be a pymongo.MongoClient[database].collection

class Employee:
    def __init__(self, _id):
        self._filter_query = {"id": _id}
        self._collection = collection
        self.collection = EmployeeCollection(_id)

        # Create a new document if it doesn't exist
        if self.collection.get() is None:
            self._collection.insert_one(self._filter_query)
    
    def someOtherOperation(self):
        self.collection.hello = "Hello World"



        