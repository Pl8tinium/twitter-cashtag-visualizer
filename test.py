import pymongo

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["db"]
mentions_db = mydb["mentions"]

mydict = { "name": "John", "address": "Highway 37" }

x = mentions_db.insert_one(mydict)

print(x)