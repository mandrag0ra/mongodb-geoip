let express = require("express");
let MongoClient = require("mongodb").MongoClient;
let helmet = require("helmet");
let net = require("net");
let dns = require("dns");

let app = express();
app.use(helmet());

function ip2Long(ip) {
  var ipl = 0;
  ip.split(".").forEach(function(octet) {
    ipl <<= 8;
    ipl += parseInt(octet);
  });
  return ipl >>> 0;
}

function dns2ip(url, cb) {
  dns.resolve4(url, function(err, address) {
    if (err) {
      console.log(url + " is possibly available: " + err);
      cb(err);
      return;
    }
    console.log("Domain ip is: ", address[0]);
    address = address[0];
    cb(address);
  });
}

async function search(db, ip_to_long, res) {
  try {
    const ip = await db.collection("ips").findOne(
      {
        start: { $lte: ip_to_long },
        end: { $gte: ip_to_long },
      },
      {
        geoname_id: 1,
        is_anonymous_proxy: 1,
        is_satellite_provider: 1,
        latitude: 1,
        longitude: 1,
        postal_code: 1,
        _id: 0,
      }
    );

    const geo = await db.collection("geos").findOne(
      {
        _id: ip["geoname_id"].toString(),
      },
      {
        geoname_id: 0,
        continent_code: 0,
        locale_code: 0,
        metro_code: 0,
        subdivision_2_name: 0,
        _id: 0,
      }
    );

    const asn = await db.collection("asns").findOne(
      {
        start: { $lte: ip_to_long },
        end: { $gte: ip_to_long },
      },
      {
        name: 1,
        number: 1,
        _id: 0,
      }
    );
    delete ip.geoname_id;
    return Object.assign(asn, geo, ip);
  } catch (e) {
    return "None";
  }
}

app.param("ip", function(req, res, next, ip) {
  if (net.isIP(ip)) {
    req.qip = ip;
    next();
  } else {
    console.log("Request is a domain ?");
    dns2ip(ip, function(address) {
      if (net.isIP(address)) {
        req.qip = address;
        next();
      } else {
        res.setHeader("Content-Type", "text/plain");
        res.status("404").send("Not found !");
        res.end();
      }
    });
  }
});

app.get("/", function(req, res) {
  if (req.headers["x-forwarded-for"]) {
    ip = req.headers["x-forwarded-for"];
  } else if (req.connection && req.connection.remoteAddress) {
    ip = req.connection.remoteAddress;
  }

  if (net.isIP(ip)) {
    console.log("Query Client IP is: " + ip);
    ip_to_long = ip2Long(ip);
    MongoClient.connect("mongodb://localhost:27017/geoip", function(err, db) {
      if (err) throw err;

      search(db, ip_to_long).then(function(result) {
        if (result == "None") {
          res.setHeader("Content-Type", "text/plain");
          res.status("404").send("Not found !");
        }
        const dict_ip = {};
        dict_ip.ip = ip;
        result = Object.assign(result, dict_ip);
        res.setHeader("Content-Type", "application/json");
        res.send(result);
      });
    });
  } else {
    res.setHeader("Content-Type", "text/plain");
    res.status("404").send("Not found !");
  }
});

app.get("/:ip", function(req, res) {
  ip = req.qip;
  console.log("Search in DB for: ", req.qip);
  if (net.isIP(ip)) {
    console.log("Query IP is: " + ip);
    ip_to_long = ip2Long(ip);
    MongoClient.connect("mongodb://localhost:27017/geoip", function(err, db) {
      if (err) throw err;

      search(db, ip_to_long).then(function(result) {
        if (result == "None") {
          res.setHeader("Content-Type", "text/plain");
          res.status("404").send("Not found !");
        }

        const dict_ip = {};
        dict_ip.ip = ip;
        result = Object.assign(result, dict_ip);
        res.setHeader("Content-Type", "application/json");
        res.send(result);
      });
    });
  } else {
    res.setHeader("Content-Type", "text/plain");
    res.status("404").send("Not found !");
  }
});

app.use(function(req, res, next) {
  res.setHeader("Content-Type", "text/plain");
  res.status("404").send("Not found !");
});

app.listen(8000, function() {
  console.log("Listening on port 8000");
});
