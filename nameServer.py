# nameServer.py
from Pyro5.nameserver import start_ns

class NameServerThread:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def run_name_server(self):
        ns, daemon, bc = start_ns(host=self.host, port=self.port)
        print(f"Name server running on {self.host}:{self.port}")
        daemon.requestLoop()

if __name__ == "__main__":
    NameServerThread("localhost", 9090).run_name_server()
