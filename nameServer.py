from Pyro5.nameserver import start_ns

class NameServerThread:
    def _init_(self, host, port):
        super()._init_()
        self.host = host
        self.port = port

    def run_name_server(self):
        ns, daemon, bc_server = start_ns(host=self.host, port=self.port)

        daemon.requestLoop()