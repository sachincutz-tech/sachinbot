from pymongo import MongoClient
from mongogettersetter import MongoGetterSetter

client = MongoClient("mongodb://sachin:Passwordbot@localhost:27017/")
db = client["bot"]
collection = db["messages"]
movie_collection = db["movieslist"]

# Wrapper for MongoDB Collection with metaclass, use this inside your actual class.
class MessagesCollection(metaclass=MongoGetterSetter):
    def __init__(self, _id):
        self._filter_query = {"_id": _id} # or the ObjectID, at your convinence
        self._collection = collection # Should be a pymongo.MongoClient[database].collection

class Messages:
    def __init__(self, _id):
        self._filter_query = {"_id": _id}
        self._collection = collection
        self.collection = MessagesCollection(_id)

        # Create a new document if it doesn't exist
        if self.collection.get() is None:
            self._collection.insert_one(self._filter_query)


class MoviesListCollection(metaclass=MongoGetterSetter):
    def __init__(self, _id):
        self._filter_query = {"_id": _id} # or the ObjectID, at your convinence
        self._collection = movie_collection # Should be a pymongo.MongoClient[database].collection

class MoviesList:
    def __init__(self, _id):
        self._filter_query = {"_id": _id}
        self._collection = movie_collection
        self.collection = MoviesListCollection(_id)

        # Create a new document if it doesn't exist
        if self.collection.get() is None:
            self._collection.insert_one(self._filter_query)
