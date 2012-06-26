from redis import Redis

from redis_completion.base import BaseEngine, AGGRESSIVE_STOP_WORDS, DEFAULT_STOP_WORDS


class RedisEngine(BaseEngine):
    """
    References
    ----------

    http://antirez.com/post/autocomplete-with-redis.html
    http://stackoverflow.com/questions/1958005/redis-autocomplete/1966188#1966188
    http://patshaughnessy.net/2011/11/29/two-ways-of-using-redis-to-build-a-nosql-autocomplete-search-index
    """
    def __init__(self, min_length=2, prefix='ac', stop_words=None, cache_timeout=300, **conn_kwargs):
        super(RedisEngine, self).__init__(min_length, prefix, stop_words)

        self.conn_kwargs = conn_kwargs
        self.client = self.get_client()

        self.cache_timeout = cache_timeout

        self.data_key = '%s:d' % self.prefix
        self.title_key = '%s:t' % self.prefix
        self.search_key = lambda k: '%s:s:%s' % (self.prefix, k)

    def get_client(self):
        return Redis(**self.conn_kwargs)

    def flush(self, everything=False, batch_size=1000):
        if everything:
            return self.client.flushdb()

        # this could be expensive :-(
        keys = self.client.keys('%s:*' % self.prefix)

        # batch keys
        for i in range(0, len(keys), batch_size):
            self.client.delete(*keys[i:i+batch_size])

    def store(self, obj_id, title=None, data=None):
        pipe = self.client.pipeline()

        if title is None:
            title = obj_id
        if data is None:
            data = title

        title_score = self.score_key(self.create_key(title))

        pipe.hset(self.data_key, obj_id, data)
        pipe.hset(self.title_key, obj_id, title)

        for word in self.clean_phrase(title):
            for partial_key in self.autocomplete_keys(word):
                pipe.zadd(self.search_key(partial_key), obj_id, title_score)

        pipe.execute()

    def exists(self, obj_id):
        return self.client.hexists(self.data_key, obj_id)

    def remove(self, obj_id):
        obj_id = str(obj_id)
        title = self.client.hget(self.title_key, obj_id) or ''
        keys = []

        for word in self.clean_phrase(title):
            for partial_key in self.autocomplete_keys(word):
                key = self.search_key(partial_key)
                if not self.client.zrange(key, 1, 2):
                    self.client.delete(key)
                else:
                    self.client.zrem(key, obj_id)

        # finally, remove the data from the data key
        self.client.hdel(self.data_key, obj_id)
        self.client.hdel(self.title_key, obj_id)

    def search(self, phrase, limit=None, filters=None, mappers=None):
        """
        Wrap our search & results with prefixing
        """
        cleaned = self.clean_phrase(phrase)
        if not cleaned:
            return []

        new_key = self.search_key('|'.join(cleaned))
        if not self.client.exists(new_key):
            self.client.zinterstore(new_key, map(self.search_key, cleaned))
            self.client.expire(new_key, self.cache_timeout)

        ct = 0
        data = []

        # grab the data for each object
        for obj_id in self.client.zrange(new_key, 0, -1):
            raw_data = self.client.hget(self.data_key, obj_id)
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
