def run(dry_run: bool = False):
    from database.repositories import get_unprocessed_topic_articles, update_article_topics
    from features.keyword_extractor import extract_keywords
    from features.topic_classifier import classify_topics

    articles = get_unprocessed_topic_articles()
    labels = ["Politics", "Technology", "Sports", "Business", "Health", "Science"]

    # 1. Batch Keywords (TF-IDF is fast)
    bodies = [a.get("body", "") for a in articles]
    all_keywords = extract_keywords(bodies)

    # 2. Sequential Topics (Transformers are heavy)
    updates = []
    for idx, article in enumerate(articles):
        topic, score = classify_topics(article["body"], labels)
        updates.append(
            {
                "url": article["url"],
                "topic_label": topic,
                "topic_score": score,
                "keywords": all_keywords[idx],
            }
        )

    if not dry_run:
        update_article_topics(updates)
