import Pyro5.api

@Pyro5.api.expose
class Peer:
    def __init__(self, name):
        self.name = name

    def ping(self, msg):
        return f"{self.name} got: {msg}"
    
    def file_transfer(self, file_name):
        with open(file_name, 'rb') as file:
            file_data = file.read()
        return file_data

    def create_test_file(self, content):
        """Creates a test file specific to this peer."""
        file_name = f"{self.name}_test.txt"
        with open(file_name, "w") as file:
            file.write(content)
        print(f"{self.name} created file: {file_name}")
        return file_name
    

def start(name, host, port):
    daemon = Pyro5.api.Daemon(host=host, port=port)
    uri = daemon.register(Peer(name))
    print(f"{name} running at {uri}")
    return daemon, uri