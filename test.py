import threading, time, os
import Pyro5.api
import ultimatePeer

def run_peer(name, port, out):
    daemon, uri = ultimatePeer.start(name, "localhost", port)
    out[name] = uri
    daemon.requestLoop()

if __name__ == "__main__":
    uris = {}

    t1 = threading.Thread(target=run_peer, args=("peer1", 50000, uris), daemon=True)
    t2 = threading.Thread(target=run_peer, args=("peer2", 50001, uris), daemon=True)
    t1.start(); t2.start()
    time.sleep(1)

    p1 = Pyro5.api.Proxy(uris["peer1"])
    p2 = Pyro5.api.Proxy(uris["peer2"])

    print(p1.ping("hello"))
    print(p2.ping("world"))

    file1 = p1.create_test_file("This is a test file for peer1.")
    file2 = p2.create_test_file("This is a test file for peer2.")

    print("Transferring file from peer1 to peer2...")
    file_data = p1.file_transfer(file1)
    with open("received_from_peer1.txt", "wb") as received_file:
        received_file.write(file_data)
    print("File received from peer1 and saved as 'received_from_peer1.txt'.")

    print("Transferring file from peer2 to peer1...")
    file_data = p2.file_transfer(file2)
    with open("received_from_peer2.txt", "wb") as received_file:
        received_file.write(file_data)
    print("File received from peer2 and saved as 'received_from_peer2.txt'.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
