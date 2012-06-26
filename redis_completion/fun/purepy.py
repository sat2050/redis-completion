import operator

from redis_completion.base import BaseEngine
from redis_completion.fun.skiplist import SkipList


class PythonEngine(BaseEngine):
    def __init__(self, min_length=2, prefix='ac', stop_words=None):
        super(PythonEngine, self).__init__(min_length, prefix, stop_words)
        self.data = {}
        self.index = {}

    def flush(self):
        self.data = {}
        self.index = {}

    def store(self, obj_id, title=None, data=None):
        if title is None:
            title = obj_id
        if data is None:
            data = title

        title_score = self.score_key(self.create_key(title))
        self.data[obj_id] = (title, data)

        for word in self.clean_phrase(title):
            for partial_key in self.autocomplete_keys(word):
                if partial_key not in self.index:
                    self.index[partial_key] = SkipList(1024)
                self.index[partial_key].insert(obj_id, title_score)

    def exists(self, obj_id):
        return obj_id in self.data

    def remove(self, obj_id):
        title, raw_data = self.data[obj_id]

        for word in self.clean_phrase(title):
            for key in self.autocomplete_keys(word):
                if self.index[key].size == 1:
                    del(self.index[key])
                else:
                    self.index[key].remove(obj_id)

        del(self.data[obj_id])

    def search(self, phrase, limit=None, filters=None, mappers=None):
        """
        Wrap our search & results with prefixing
        """
        cleaned = self.clean_phrase(phrase)
        if not cleaned:
            return []

        skiplists = [self.index.get(key, SkipList(1)) for key in cleaned]
        result_skiplist = reduce(operator.and_, skiplists)
        ct = 0
        data = []

        # grab the data for each object
        for obj_id, score in result_skiplist:
            title, raw_data = self.data[obj_id]
            if not raw_data:
                continue

            if mappers:
                for m in mappers:
                    raw_data = m(raw_data)

            if filters:
                passes = True
                for f in filters:
                    if not f(raw_data):
                        passes = False
                        break

                if not passes:
                    continue

            data.append(raw_data)
            ct += 1
            if limit and ct == limit:
                break

        return data
