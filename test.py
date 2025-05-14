import threading
import time
from Pyro5.api import locate_ns, Proxy
import ultimatePeer

peer_names = [f"peer{i}" for i in range(1, 6)]
ports = list(range(50000, 50000 + len(peer_names)))
uris = {}

def runner(name, port):
    daemon, uri = ultimatePeer.start(name, "localhost", port, peer_names)
    uris[name] = uri
    daemon.requestLoop()

for n, p in zip(peer_names, ports):
    threading.Thread(target=runner, args=(n, p), daemon=True).start()
    time.sleep(0.1)

while len(uris) < len(peer_names):
    time.sleep(0.05)

ns = locate_ns("localhost", 9090)
trackers = ns.list(prefix="Tracker_Epoca_")
print("Trackers:", trackers)
if not trackers:
    print("No tracker elected")
    exit(1)
epoch = max(trackers, key=lambda k: int(k.rsplit("_",1)[1]))
track = Proxy(trackers[epoch])

p1 = Proxy(uris["peer1"])
fn = p1.create_test_file("hello")
print("Created", fn, "on peer1")

owners = track.query(fn)
print("Owners of", fn, ":", owners)
if not owners:
    print("No owner for", fn)
    exit(1)

peer = Proxy(owners[0])
data = peer.file_transfer(fn)

if isinstance(data, str):
    data = data.encode()  # força reconversão para bytes

if not isinstance(data, (bytes, bytearray)):
    raise TypeError(f"Expected bytes, got {type(data)}")

with open("received_" + fn, "wb") as f:
    f.write(data)

print("Received and saved as", f"received_{fn}")