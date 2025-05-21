import os
import threading
import time
import random
import logging
import Pyro5
from Pyro5.api import expose, Daemon, Proxy, locate_ns

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
Pyro5.config.COMMTIMEOUT=0.1

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
            fn = f"peer{name}_test_{i}.txt"
            with open(os.path.join(self.dir, fn), "w") as f:
                f.write(f"dummy from {name} file {i}")
        self.files = sorted(os.listdir(self.dir))
        self.heartbeat_ts = time.time()
        self.interval_for_elect = random.uniform(2, 5)
        threading.Thread(target=self._monitor_files, daemon=True).start()
        threading.Thread(target=self._monitor, daemon=True).start()
        self.heartbeatCounter = 0

    def ping(self, msg):
        return f"{self.name} got: {msg}"

    def get_file_list(self):
        return list(self.files)

    def file_transfer(self, file_name):
        path = os.path.join(self.dir, file_name)
        with open(path, "rb") as f:
            return f.read()

    def request_vote(self, candidate, epoch):
        self.heartbeat_ts = time.time()
        with self.vote_lock:
            if epoch > self.epoch and epoch not in self.voted_epochs:
                self.voted_epochs.add(epoch)
                logging.info(f"({str(time.time())}) {self.name} votes for {candidate} in epoch {epoch}")
                return True
            else:
                logging.debug(f"({str(time.time())}) {self.name} is_tracker ({self.is_tracker}) rejects vote for {candidate} in epoch {epoch}. current epoch {self.epoch}. voted epochs {self.voted_epochs}")
        return False

    def declare_winner(self, epoch):
        self.is_tracker = True
        self.epoch = epoch
        ns = locate_ns(self.ns_host, self.ns_port)
        uri = self._daemon.uriFor(self)
        ns.register(f"Tracker_Epoca_{epoch}", uri)
        logging.info(f"({str(time.time())}) {self.name} elected as tracker, epoch={epoch}")
        threading.Thread(target=self._send_heartbeat, daemon=True).start()
        return True

    def update_files(self, peer_name, files):
        if not self.is_tracker:
            raise RuntimeError("not a tracker")
        self.index[peer_name] = list(files)
        logging.debug(f"tracker updated files of {peer_name}: {files}")
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
        self.heartbeat_ts = time.time()
        self.heartbeatCounter += 1
        if self.heartbeatCounter > 20:
            # logging.debug(f"({str(time.time())}) {self.name} heartbeat counter exceeded in epoch {epoch}")
            self.heartbeatCounter = 0

        if epoch > self.epoch:
            self.epoch = epoch
            self.set_not_tracker()
            self._get_tracker_proxy().update_files(self.name, list(self.files))

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
                logging.debug(f"{self.name} dir change: {self.files}")
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
                if time.time() - self.heartbeat_ts > self.interval_for_elect:
                    logging.info(f"({str(time.time())}) {self.name} missing heartbeat → election")
                    self.start_election()
            time.sleep(0.1)

    def start_election(self):
        votes = 1
        self.voted_epochs.add(self.epoch + 1)
        totalPeersOnline = 0
        ns = locate_ns(self.ns_host, self.ns_port)
        for peer in self.peer_names:
            if peer == self.name:
                totalPeersOnline += 1
                continue
            try:
                p = Proxy(ns.lookup(f"peer.{peer}"))
                if p.request_vote(self.name, self.epoch + 1):
                    votes += 1

                logging.debug(f"({str(time.time())}) {self.name} missing heartbeat → election request to {peer}")
                totalPeersOnline += 1
            except:
                pass

        logging.debug(f"({str(time.time())}) {self.name} votes: {votes}/{totalPeersOnline}")
        if votes >= totalPeersOnline // 2 + 1:
            self.declare_winner(self.epoch + 1)

    def _send_heartbeat(self):
        while self.is_tracker:
            ns = locate_ns(self.ns_host, self.ns_port)
            for peer in self.peer_names:
                try:
                    Proxy(ns.lookup(f"peer.{peer}")).heartbeat(self.epoch)
                except:
                    pass
            time.sleep(0.1)

    def get_is_tracker(self):
        return self.is_tracker
    
    def get_index(self, peer_name):
        if not self.is_tracker:
            raise RuntimeError("not a tracker")
        return self.index.get(peer_name, [])
    
    def set_not_tracker(self):
        self.is_tracker = False
        self.index = {}

def start(name, host, port, peer_names, ns_host="localhost", ns_port=9090):
    daemon = Daemon(host=host, port=port)
    peer = Peer(name, peer_names, ns_host, ns_port)
    peer._daemon = daemon
    uri = daemon.register(peer)
    locate_ns(ns_host, ns_port).register(f"peer.{name}", uri)
    try:
        peer._get_tracker_proxy().update_files(name, peer.files)
    except:
        # logging.debug("no tracker → election")
        # threading.Thread(target=peer.start_election, daemon=True).start()
        pass
    return daemon, uri
