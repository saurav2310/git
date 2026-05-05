The Core Idea: Content‑Addressable Storage
Most databases store data by location (e.g., "file at path X").
Git stores data by content — the name of an object is a hash of its content.

----------------------------------------------
text
hash = SHA1( content )
----------------------------------------------

That means:

If you change a single byte, the hash changes completely.

If two files have identical content, they are stored only once.

Every object (file, directory, commit) is retrieved by its hash.

This is the only data structure Git has: a key‑value store where the key is the hash and the value is the object.