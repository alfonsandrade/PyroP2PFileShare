import os
import threading
import time
import random
import logging
from Pyro5.api import expose, Daemon, Proxy, locate_ns

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

@expose
class Peer:
    def __init__(self, name, peer_names, ns_host="localhost", ns_port=9090):
        self.name = name
        self.peer_names = peer_names
        self.ns_host = ns_host
        self.ns_port = ns_port
        self.epoch = 0
        self.voted_epochs = set()
        self.vote_lock = threading.Lock()
        self.is_tracker = False
        self.index = {}
        self.dir = os.path.join(os.getcwd(), name)
        os.makedirs(self.dir, exist_ok=True)
        for i in range(random.randint(1, 5)):
            fn = f"test_{i}.txt"
            with open(os.path.join(self.dir, fn), "w") as f:
                f.write(f"dummy from {name} file {i}")
        self.files = sorted(os.listdir(self.dir))
        self.heartbeat_ts = time.time()
        threading.Thread(target=self._monitor_files, daemon=True).start()
        threading.Thread(target=self._monitor, daemon=True).start()

    def ping(self, msg):
        return f"{self.name} got: {msg}"

    def get_file_list(self):
        return list(self.files)

    def create_test_file(self, content):
        fn = f"{self.name}_test_{int(time.time())}.txt"
        path = os.path.join(self.dir, fn)
        with open(path, "w") as f:
            f.write(content)
        logging.info(f"{self.name} created file: {fn}")
        self.files.append(fn)
        self.files.sort()
        if self.is_tracker:
            self.index[self.name] = list(self.files)
        else:
            try:
                tracker = self._get_tracker_proxy()
                tracker.update_files(self.name, list(self.files))
            except:
                pass
        return fn

    def file_transfer(self, file_name):
        path = os.path.join(self.dir, file_name)
        with open(path, "rb") as f:
            return f.read()

    def request_vote(self, candidate, epoch):
        with self.vote_lock:
            if epoch > self.epoch and epoch not in self.voted_epochs:
                self.voted_epochs.add(epoch)
                self.epoch = epoch
                logging.info(f"{self.name} votes for {candidate} in epoch {epoch}")
                return True
        return False

    def declare_winner(self, epoch):
        self.is_tracker = True
        self.epoch = epoch
        ns = locate_ns(self.ns_host, self.ns_port)
        uri = self._daemon.uriFor(self)
        ns.register(f"Tracker_Epoca_{epoch}", uri)
        logging.info(f"{self.name} elected as tracker, epoch={epoch}")
        for peer in self.peer_names:
            try:
                p = Proxy(ns.lookup(f"peer.{peer}"))
                self.index[peer] = p.get_file_list()
            except:
                pass
        threading.Thread(target=self._send_heartbeat, daemon=True).start()
        return True

    def update_files(self, peer_name, files):
        if not self.is_tracker:
            raise RuntimeError("not a tracker")
        self.index[peer_name] = list(files)
        logging.info(f"tracker updated files of {peer_name}: {files}")
        return True

    def query(self, filename):
        if not self.is_tracker:
            raise RuntimeError("not a tracker")
        results = []
        ns = locate_ns(self.ns_host, self.ns_port)
        for peer, flist in self.index.items():
            if filename in flist:
                try:
                    results.append(ns.lookup(f"peer.{peer}"))
                except:
                    pass
        return results

    def heartbeat(self, epoch):
        if epoch == self.epoch:
            self.heartbeat_ts = time.time()
        return True

    def _get_tracker_proxy(self):
        ns = locate_ns(self.ns_host, self.ns_port)
        trackers = ns.list(prefix="Tracker_Epoca_")
        if not trackers:
            raise RuntimeError("no tracker")
        latest = max(trackers.keys(), key=lambda k: int(k.rsplit("_", 1)[1]))
        return Proxy(trackers[latest])

    def _monitor_files(self):
        prev = set(self.files)
        while True:
            time.sleep(1)
            current = set(os.listdir(self.dir))
            if current != prev:
                self.files = sorted(current)
                logging.info(f"{self.name} dir change: {self.files}")
                try:
                    if self.is_tracker:
                        self.index[self.name] = list(self.files)
                    else:
                        self._get_tracker_proxy().update_files(self.name, list(self.files))
                except:
                    pass
                prev = current

    def _monitor(self):
        ns = locate_ns(self.ns_host, self.ns_port)
        while len(ns.list(prefix="peer.")) < len(self.peer_names):
            time.sleep(0.05)
        while True:
            if not self.is_tracker:
                interval = random.uniform(0.15, 0.3)
                if time.time() - self.heartbeat_ts > interval:
                    logging.info(f"{self.name} missing heartbeat → election")
                    self.start_election()
            time.sleep(0.1)

    def start_election(self):
        self.epoch += 1
        votes = 1
        ns = locate_ns(self.ns_host, self.ns_port)
        for peer in self.peer_names:
            if peer == self.name:
                continue
            try:
                p = Proxy(ns.lookup(f"peer.{peer}"))
                if p.request_vote(self.name, self.epoch):
                    votes += 1
            except:
                pass
        if votes >= len(self.peer_names) // 2 + 1:
            self.declare_winner(self.epoch)

    def _send_heartbeat(self):
        while self.is_tracker:
            ns = locate_ns(self.ns_host, self.ns_port)
            for peer in self.peer_names:
                try:
                    Proxy(ns.lookup(f"peer.{peer}")).heartbeat(self.epoch)
                except:
                    pass
            time.sleep(0.1)

def start(name, host, port, peer_names, ns_host="localhost", ns_port=9090):
    daemon = Daemon(host=host, port=port)
    peer = Peer(name, peer_names, ns_host, ns_port)
    peer._daemon = daemon
    uri = daemon.register(peer)
    locate_ns(ns_host, ns_port).register(f"peer.{name}", uri)
    try:
        peer._get_tracker_proxy().update_files(name, peer.files)
    except:
        logging.info("no tracker → election")
        threading.Thread(target=peer.start_election, daemon=True).start()
    return daemon, uri
