# mongo-geoipdb

========

Quick and dirty created a geo IP MongoDB database from [MaxMind](http://dev.maxmind.com/geoip/geoip2/geolite2/).
Please keep in mind that this has been created for my educational purposes !

Do _NOT_ use this in production.
You might want to take a look at [node-maxmind](https://github.com/runk/node-maxmind) for exemple.

## Installation and Usage

In a python [virtualenv](https://virtualenv.pypa.io/en/stable/):

```bash
# Install requirements
pip install -r requirements.txt

# Then create a new database
python populate_db.py -n

# Or to update a database
python populate_db.py -u
```

See `python populate_db.py` for other options.

## Webserver

Query the database with a simple Node Express or Python/WSGI app.

```bash
# Express
cd webserver/express && npm install .
node server.js

# Or UWSGI
cd webserver/python_wsgi && pip install -r requirements.txt
/path/to/virtualenv/bin/uwsgi /path/to/project/webserver/uwsgi/uwsgi.ini
```

On another terminal

```bash
curl localhost:8000/<ip>
# Or
curl localhost:8000/exemple.com
```
