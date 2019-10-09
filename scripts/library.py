# A dictionary which maps keys to integers.
class counting_dict(object):
    def __init__(self):
        self._data = {}

    def __getitem__(self, key):
        if key not in self._data:
            self._data[key] = 0
        return self._data[key]

    def __setitem__(self, key, value):
        if type(value) is not int:
            raise TypeError("Only integer objects are supported")
        self._data[key] = value

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return f"{self._data}"

    def keys(self):
        return self._data.keys()

# A list with only unique entries.
class unique_list(object):
    def __init__(self):
        self._data = []

    def __len__(self):
        return len(self._data)

    def __getitem__(self, key):
        return self._data[key]

    def insert(self, key):
        if key not in self._data:
            self._data.append(key)

    def __repr__(self):
        return f"{self._data}"
