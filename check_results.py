import pymongo

# --- Configuration ---
MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "nlp_clean"
COLLECTION_NAME = "articles"
NUM_TO_SHOW = 5
# ---------------------


def check_results():
    """Connects to MongoDB and prints a few analyzed articles."""
    print(f"Connecting to MongoDB at {MONGO_URI}...")
    try:
        client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.server_info()  # Will raise an exception if connection fails
    except pymongo.errors.ServerSelectionTimeoutError as err:
        print("\\n--- MONGODB CONNECTION FAILED ---")
        print(f"Error: {err}")
        print("Please ensure your docker-compose stack is running ('docker-compose up').")
        return

    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    print(
        f"\\nFetching {NUM_TO_SHOW} articles from '{DB_NAME}.{COLLECTION_NAME}' where 'topic_label' exists..."
    )

    # Find articles that have been processed by our new job
    results = collection.find({"topic_label": {"$exists": True}}).limit(NUM_TO_SHOW)

    count = 0
    for article in results:
        count += 1
        print(f"\\n--- Article {count} ---")
        print(f"  Title: {article.get('title', 'N/A')}")
        print(f"  URL:   {article.get('url', 'N/A')}")
        print(
            f"  Topic: {article.get('topic_label', 'N/A')} (Score: {article.get('topic_score', 0.0):.2f})"
        )
        print(f"  Keywords: {', '.join(article.get('keywords', []))}")
        print("-" * (15 + len(str(count))))

    if count == 0:
        print("\\nNo articles with topics found.")
        print("Did the 'analyze' job run successfully and process any articles?")

    client.close()


if __name__ == "__main__":
    check_results()
