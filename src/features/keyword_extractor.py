from sklearn.feature_extraction.text import TfidfVectorizer


def extract_keywords(texts: list[str], top_n: int = 5):
    # This identifies words that are important to THIS article
    # but not common across all articles (the 'subject' of the article)
    vectorizer = TfidfVectorizer(max_features=1000, stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out()

    results = []
    for i in range(len(texts)):
        row = tfidf_matrix.getrow(i).toarray()[0]
        top_indices = row.argsort()[-top_n:][::-1]
        results.append([feature_names[idx] for idx in top_indices if row[idx] > 0])
    return results
