.. _api:

API
===

.. py:class:: RedisEngine(min_length=2, prefix='ac', stop_words=None, \
                          cache_timeout=300, **conn_kwargs)

    :param integer min_length: the minimum length a phrase has to be to return meaningful
        search results
    :param string prefix: a prefix used for all keys stored in Redis to allow multiple
        "indexes" to exist and to make deletion easier.
    :param set stop_words: a ``set`` of stop words to remove from index/search data
    :param integer cache_timeout: how long to keep around search results
    :param conn_kwargs: any named parameters that should be used when connecting
        to Redis, e.g. ``host='localhost', port=6379``

    :py:class:`RedisEngine` is responsible for storing and searching data suitable
    for autocompletion.  There are many different options you can use to configure
    how autocomplete behaves, but the defaults are intended to provide good general
    performance for searching things like blog post titles and the like.

    The underlying data structure used to provide autocompletion is a sorted set,
    details are described `in this post <http://antirez.com/post/autocomplete-with-redis.html>`_.

    Usage:

    .. code-block:: python

        from redis_completion import RedisEngine
        engine = RedisEngine()

    .. py:method:: store(obj_id[, title=None[, data=None[, obj_type=None]]])

        :param obj_id: a unique identifier for the object
        :param title: a string to store in the index and allow autocompletion on,
            which, if not provided defaults to the given ``obj_id``
        :param data: any data you wish to store and return when a given title is
            searched for.  If not provided, defaults to the given ``title`` (or ``obj_id``)
        :param obj_type: an additional identifier for this object if multiple types are stored

        Store an object in the index and allow it to be searched for.

        Examples:

        .. code-block:: python

            engine.store('some phrase')
            engine.store('some other phrase')

        In the following example a list of blog entries is being stored in the
        index.  Note that arbitrary data can be stored in the index.  When a search
        is performed this data will be returned.

        .. code-block:: python

            for entry in Entry.select():
                engine.store(entry.id, entry.title, json.dumps({
                    'id': entry.id,
                    'published': entry.published,
                    'title': entry.title,
                    'url': entry.url,
                })

    .. py:method:: store_json(obj_id, title, data[, obj_type=None])

        Like :py:meth:`store` except ``data`` is automatically serialized as JSON
        before being stored in the index.  Best when used in conjunction with
        :py:meth:`search_json`.

    .. py:method:: exists(obj_id[, obj_type=None])

        :param obj_id: a unique identifier for the object
        :param obj_type: an additional identifier for this object if multiple types are stored

        Checks if the given object exists in the index

    .. py:method:: remove(obj_id[, obj_type=None])

        :param obj_id: a unique identifier for the object
        :param obj_type: an additional identifier for this object if multiple types are stored

        Removes the given object from the index.

    .. py:method:: boost(obj_id[, multiplier=1.1[, negative=False]])

        :param obj_id: a unique identifier for the object
        :param float multiplier: a float indicating how much to boost obj_id by, where
            greater than one will push to the front, less than will push to the back
        :param boolean negative: whether to push forward or backward (if negative, will
            simply inverse the multiplier)

        Boost the score of the given ``obj_id`` by the multiplier, then store the result
        in a special hash.  These stored "boosts" can later be recalled when searching
        by specifying ``autoboost=True``.

    .. py:method:: search(phrase[, limit=None[, filters=None[, mappers=None[, boosts=None[, autoboost=False]]]]])

        :param phrase: search the index for the given phrase
        :param limit: an integer indicating the number of results to limit the
            search to.
        :param filters: a list of callables which will be used to filter the search
            results before returning to the user.  Filters should take a single parameter,
            the ``data`` associated with a given object and should return either
            ``True`` or ``False``.  A ``False`` value returned by any of the filters
            will prevent a result from being returned.
        :param mappers: a list of callables which will be used to transform the
            raw data returned from the index.
        :param dict boosts: a mapping of type identifier -> float value -- if provided,
            results of a given id/type will have their scores multiplied by the corresponding
            float value, e.g. ``{'id1': 1.1, 'id2': 1.3, 'id3': .9}``
        :param boolean autoboost: automatically prepopulate boosts by looking at the
            stored boost information created using the :py:meth:`~RedisEngine.boost` api
        :rtype: A list containing data returned by the index

        .. note:: Mappers act upon data before it is passed to the filters

        Assume we have stored some interesting blog posts, encoding some metadata
        using JSON:

        .. code-block:: python

            >>> engine.search('python', mappers=[json.loads])
            [{'published': True, 'title': 'an entry about python', 'url': '/blog/1/'},
             {'published': False, 'title': 'using redis with python', 'url': '/blog/3/'}]

    .. py:method:: search_json(phrase[, limit=None[, filters=None[, mappers=None[, boosts=None[, autoboost=False]]]]])

        Like :py:meth:`search` except ``json.loads`` is inserted as the very first
        mapper.  Best when used in conjunction with :py:meth:`store_json`.

    .. py:method:: flush([everything=False[, batch_size=1000]])

        Clears all data from the database.  By default will only delete keys that are
        associated with the given engine (based on its prefix), but if ``everything`` is
        ``True``, then the entire database will be flushed.  The latter is faster.

        :param boolean everything: whether to delete the entire current redis db
        :param int batch_size: number of keys to delete at-a-time
