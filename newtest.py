from db import MessagesCollection, Messages, collection, movie_collection
import uuid



random_id = uuid.uuid4().hex[:24]
# doc = collection.insert_one({"id": random_id})

# db_data = Messages(random_id)
# insert_id = db_data.collection["_id"]
# print(insert_id)


# db_base = Messages("8940ac690faf45c2beca7518")
# db_data = db_base.collection
# # db_data["name"] = "fef"
# print(db_data)

# movies = collection.find({}, {"movie_name": 1, "_id": 0}).sort("movie_name", 1)

# movie_list = [m["movie_name"] for m in movies]


# count = collection.count_documents({})
# m = Messages()
# print(m)

# print(type(collection.count_documents({})))


request_movie = "ballon"

movie_doc = movie_collection.find_one({"name": request_movie})

#TODO: not found auto delete msg     
if not movie_doc:
    print("not exists")
else:
    print("exists")


if movie_doc and ("message_id" in movie_doc):
    _id = movie_doc["message_id"]

    db_message = Messages(_id).collection
    print(db_message)
    del db_message

    db_message = Messages(_id).collection
    print(db_message)